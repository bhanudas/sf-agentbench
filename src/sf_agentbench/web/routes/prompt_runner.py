"""API routes for the Prompt Runner feature.

This module provides endpoints to submit custom Salesforce development prompts,
run them through Claude Code with configurable iterations, and stream results.

All interactions are logged for auditability and runs are persisted to SQLite
for resume capability after page refresh or server restart.
"""

import asyncio
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from sf_agentbench.web.schemas import (
    PromptRunCreate,
    PromptRunResponse,
    PromptRunDetailResponse,
    PromptRunListResponse,
    PromptRunStatus,
    PromptLogEvent,
)

router = APIRouter(prefix="/prompt-runs", tags=["prompt-runner"])
logger = logging.getLogger(__name__)

# Configure logging for prompt runs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# =============================================================================
# Persistent SQLite Store for Prompt Runs
# =============================================================================


PROMPT_RUN_SCHEMA = """
CREATE TABLE IF NOT EXISTS prompt_runs (
    run_id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    iterations INTEGER NOT NULL,
    current_iteration INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_seconds REAL DEFAULT 0.0,
    error TEXT,
    iteration_results TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS prompt_run_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    iteration INTEGER,
    details TEXT DEFAULT '{}',
    FOREIGN KEY (run_id) REFERENCES prompt_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_prompt_run_logs_run_id ON prompt_run_logs(run_id);
CREATE INDEX IF NOT EXISTS idx_prompt_runs_started_at ON prompt_runs(started_at);
"""


class PromptRunStore:
    """Persistent SQLite store for prompt runs with event streaming."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            # Default to results directory
            from sf_agentbench.config import load_config
            try:
                config = load_config()
                db_path = Path(config.results_dir) / "prompt_runs.db"
            except Exception:
                db_path = Path.home() / ".sf-agentbench" / "prompt_runs.db"

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.subscribers: dict[str, list[asyncio.Queue]] = {}

        # Initialize database
        self._init_db()
        logger.info(f"PromptRunStore initialized with database: {db_path}")

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(PROMPT_RUN_SCHEMA)
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_run(self, run_id: str, prompt: str, iterations: int) -> dict:
        """Create a new prompt run record."""
        started_at = datetime.now(timezone.utc)

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO prompt_runs (run_id, prompt, iterations, status, started_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, prompt, iterations, PromptRunStatus.PENDING.value, started_at.isoformat()),
            )
            conn.commit()

        # Initialize subscribers list for this run
        self.subscribers[run_id] = []

        logger.info(f"Created prompt run {run_id}: prompt_length={len(prompt)}, iterations={iterations}")

        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict | None:
        """Get a prompt run by ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM prompt_runs WHERE run_id = ?", (run_id,)
            ).fetchone()

            if not row:
                return None

            return self._row_to_run(row)

    def _row_to_run(self, row: sqlite3.Row) -> dict:
        """Convert a database row to a run dictionary."""
        return {
            "run_id": row["run_id"],
            "prompt": row["prompt"],
            "iterations": row["iterations"],
            "current_iteration": row["current_iteration"],
            "status": PromptRunStatus(row["status"]),
            "started_at": datetime.fromisoformat(row["started_at"]),
            "completed_at": datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            "duration_seconds": row["duration_seconds"],
            "error": row["error"],
            "iteration_results": json.loads(row["iteration_results"]),
        }

    def update_run(self, run_id: str, **updates) -> dict | None:
        """Update a prompt run."""
        if not self.get_run(run_id):
            return None

        # Build update query dynamically
        set_clauses = []
        values = []

        for key, value in updates.items():
            if key == "status" and hasattr(value, "value"):
                value = value.value
            elif key == "completed_at" and isinstance(value, datetime):
                value = value.isoformat()
            elif key == "iteration_results" and isinstance(value, list):
                value = json.dumps(value)

            set_clauses.append(f"{key} = ?")
            values.append(value)

        if not set_clauses:
            return self.get_run(run_id)

        values.append(run_id)

        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE prompt_runs SET {', '.join(set_clauses)} WHERE run_id = ?",
                values,
            )
            conn.commit()

        logger.debug(f"Updated prompt run {run_id}: {updates}")
        return self.get_run(run_id)

    def add_log(self, run_id: str, level: str, message: str, iteration: int | None = None, details: dict = None):
        """Add a log entry and notify subscribers."""
        timestamp = datetime.now(timezone.utc)

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO prompt_run_logs (run_id, timestamp, level, message, iteration, details)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, timestamp.isoformat(), level, message, iteration, json.dumps(details or {})),
            )
            conn.commit()

        # Log to Python logger as well
        log_level = getattr(logging, level.upper(), logging.INFO)
        logger.log(log_level, f"[{run_id}] {message}")

        # Notify WebSocket subscribers
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "iteration": iteration,
            "details": details or {},
        }
        asyncio.create_task(self._notify_subscribers(run_id, log_entry))

    async def _notify_subscribers(self, run_id: str, log_entry: dict):
        """Notify all WebSocket subscribers of a new log entry."""
        if run_id not in self.subscribers:
            return

        message = {
            "type": "log",
            "data": {
                "timestamp": log_entry["timestamp"].isoformat(),
                "level": log_entry["level"],
                "message": log_entry["message"],
                "iteration": log_entry["iteration"],
                "details": log_entry["details"],
            },
        }

        for queue in self.subscribers[run_id]:
            try:
                await queue.put(message)
            except Exception:
                pass

    def subscribe(self, run_id: str) -> asyncio.Queue:
        """Subscribe to log events for a run."""
        if run_id not in self.subscribers:
            self.subscribers[run_id] = []
        queue = asyncio.Queue()
        self.subscribers[run_id].append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue):
        """Unsubscribe from log events."""
        if run_id in self.subscribers and queue in self.subscribers[run_id]:
            self.subscribers[run_id].remove(queue)

    def list_runs(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """List all runs with pagination."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM prompt_runs
                ORDER BY started_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

            return [self._row_to_run(row) for row in rows]

    def count_runs(self) -> int:
        """Get total number of runs."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM prompt_runs").fetchone()
            return row[0] if row else 0

    def get_logs(self, run_id: str) -> list[dict]:
        """Get all logs for a run."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM prompt_run_logs
                WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()

            return [
                {
                    "timestamp": datetime.fromisoformat(row["timestamp"]),
                    "level": row["level"],
                    "message": row["message"],
                    "iteration": row["iteration"],
                    "details": json.loads(row["details"]),
                }
                for row in rows
            ]


# Global store instance
_store: PromptRunStore | None = None


def get_store() -> PromptRunStore:
    """Get the global prompt run store."""
    global _store
    if _store is None:
        _store = PromptRunStore()
    return _store


# =============================================================================
# Background Task: Execute Prompt Run
# =============================================================================


async def execute_prompt_run(run_id: str, prompt: str, iterations: int):
    """Execute a prompt run using Claude Code agent.

    This runs in the background and streams logs to subscribers.
    """
    store = get_store()

    try:
        # Update status to running
        store.update_run(run_id, status=PromptRunStatus.RUNNING)
        store.add_log(run_id, "INFO", f"Starting prompt run with {iterations} iteration(s)")

        # Import CLI runner and agent config
        from sf_agentbench.agents.cli_runner import CLIAgentRunner, CLI_AGENTS

        # Get Claude Code agent config
        agent_config = CLI_AGENTS.get("claude-code")
        if not agent_config:
            raise ValueError("Claude Code agent not found in configuration")

        store.add_log(run_id, "INFO", f"Using agent: {agent_config.name}")

        iteration_results = []

        for i in range(1, iterations + 1):
            store.update_run(run_id, current_iteration=i)
            store.add_log(run_id, "INFO", f"=== Iteration {i}/{iterations} ===", iteration=i)

            try:
                # Create a runner for this iteration
                runner = CLIAgentRunner()

                # Build the prompt with iteration context
                iteration_prompt = f"""## Salesforce Development Challenge

{prompt}

---
This is iteration {i} of {iterations}. Please provide a complete solution.
"""

                # Define output callback for streaming
                def on_output(line: str, iter_num=i):
                    store.add_log(run_id, "OUTPUT", line.rstrip(), iteration=iter_num)

                # Run the agent
                store.add_log(run_id, "INFO", "Invoking Claude Code agent...", iteration=i)

                result = runner.run_agent(
                    agent_config=agent_config,
                    prompt=iteration_prompt,
                    on_output=on_output,
                )

                # Record iteration result
                iter_result = {
                    "iteration": i,
                    "exit_code": result.exit_code,
                    "duration_seconds": result.duration_seconds,
                    "timed_out": result.timed_out,
                    "files_modified": result.files_modified,
                }
                iteration_results.append(iter_result)

                if result.timed_out:
                    store.add_log(run_id, "WARNING", f"Iteration {i} timed out", iteration=i)
                elif result.exit_code != 0:
                    store.add_log(run_id, "WARNING", f"Iteration {i} exited with code {result.exit_code}", iteration=i)
                else:
                    store.add_log(run_id, "INFO", f"Iteration {i} completed successfully", iteration=i)

            except Exception as e:
                store.add_log(run_id, "ERROR", f"Iteration {i} failed: {str(e)}", iteration=i)
                iteration_results.append({
                    "iteration": i,
                    "error": str(e),
                })

        # Complete the run
        completed_at = datetime.now(timezone.utc)
        run = store.get_run(run_id)
        duration = (completed_at - run["started_at"]).total_seconds()

        store.update_run(
            run_id,
            status=PromptRunStatus.COMPLETED,
            completed_at=completed_at,
            duration_seconds=duration,
            iteration_results=iteration_results,
        )
        store.add_log(run_id, "INFO", f"Prompt run completed in {duration:.1f}s")

        # Notify completion
        await _notify_completion(run_id, store)

    except Exception as e:
        logger.exception(f"Prompt run {run_id} failed")
        store.update_run(
            run_id,
            status=PromptRunStatus.FAILED,
            completed_at=datetime.now(timezone.utc),
            error=str(e),
        )
        store.add_log(run_id, "ERROR", f"Run failed: {str(e)}")
        await _notify_completion(run_id, store)


async def _notify_completion(run_id: str, store: PromptRunStore):
    """Notify subscribers that the run has completed."""
    if run_id not in store.subscribers:
        return

    run = store.get_run(run_id)
    message = {
        "type": "complete",
        "data": {
            "run_id": run_id,
            "status": run["status"].value if hasattr(run["status"], "value") else run["status"],
            "duration_seconds": run["duration_seconds"],
            "error": run["error"],
        },
    }

    for queue in store.subscribers[run_id]:
        try:
            await queue.put(message)
        except Exception:
            pass


# =============================================================================
# REST Endpoints
# =============================================================================


@router.post("", response_model=PromptRunResponse)
async def create_prompt_run(
    request: PromptRunCreate,
    background_tasks: BackgroundTasks,
    store: PromptRunStore = Depends(get_store),
):
    """Create and start a new prompt run.

    Submits a Salesforce development prompt to be solved by Claude Code
    with the specified number of iterations.
    """
    # Validate iterations
    valid_iterations = {1, 5, 10, 25}
    if request.iterations not in valid_iterations:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid iterations: {request.iterations}. Must be one of: {sorted(valid_iterations)}",
        )

    # Create run record
    run_id = str(uuid.uuid4())[:12]
    run = store.create_run(run_id, request.prompt, request.iterations)

    # Log the creation
    logger.info(f"Created prompt run {run_id}: iterations={request.iterations}, prompt_length={len(request.prompt)}")

    # Start background execution
    background_tasks.add_task(execute_prompt_run, run_id, request.prompt, request.iterations)

    return PromptRunResponse(
        run_id=run["run_id"],
        prompt=run["prompt"],
        iterations=run["iterations"],
        current_iteration=run["current_iteration"],
        status=run["status"],
        started_at=run["started_at"],
        completed_at=run["completed_at"],
        duration_seconds=run["duration_seconds"],
        error=run["error"],
    )


@router.get("", response_model=PromptRunListResponse)
async def list_prompt_runs(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    store: PromptRunStore = Depends(get_store),
):
    """List all prompt runs with pagination."""
    runs = store.list_runs(limit=limit, offset=offset)

    return PromptRunListResponse(
        runs=[
            PromptRunResponse(
                run_id=r["run_id"],
                prompt=r["prompt"],
                iterations=r["iterations"],
                current_iteration=r["current_iteration"],
                status=r["status"],
                started_at=r["started_at"],
                completed_at=r["completed_at"],
                duration_seconds=r["duration_seconds"],
                error=r["error"],
            )
            for r in runs
        ],
        total=store.count_runs(),
        limit=limit,
        offset=offset,
    )


@router.get("/{run_id}", response_model=PromptRunDetailResponse)
async def get_prompt_run(
    run_id: str,
    store: PromptRunStore = Depends(get_store),
):
    """Get detailed information about a prompt run including logs."""
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Prompt run not found: {run_id}")

    logs = store.get_logs(run_id)

    return PromptRunDetailResponse(
        run_id=run["run_id"],
        prompt=run["prompt"],
        iterations=run["iterations"],
        current_iteration=run["current_iteration"],
        status=run["status"],
        started_at=run["started_at"],
        completed_at=run["completed_at"],
        duration_seconds=run["duration_seconds"],
        error=run["error"],
        logs=[log["message"] for log in logs],
        iteration_results=run.get("iteration_results", []),
    )


@router.post("/{run_id}/cancel")
async def cancel_prompt_run(
    run_id: str,
    store: PromptRunStore = Depends(get_store),
):
    """Cancel a running prompt run."""
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Prompt run not found: {run_id}")

    if run["status"] not in (PromptRunStatus.PENDING, PromptRunStatus.RUNNING):
        raise HTTPException(status_code=400, detail=f"Cannot cancel run with status: {run['status']}")

    store.update_run(
        run_id,
        status=PromptRunStatus.CANCELLED,
        completed_at=datetime.now(timezone.utc),
    )
    store.add_log(run_id, "INFO", "Run cancelled by user")

    return {"status": "cancelled", "run_id": run_id}


# =============================================================================
# WebSocket Endpoint for Streaming Logs
# =============================================================================


@router.websocket("/ws/{run_id}")
async def websocket_prompt_run(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for streaming prompt run logs.

    Protocol:
    - Server -> Client:
      - {"type": "connected", "data": {...}}
      - {"type": "log", "data": {"timestamp": ..., "level": ..., "message": ..., "iteration": ...}}
      - {"type": "status", "data": {"status": ..., "current_iteration": ...}}
      - {"type": "complete", "data": {"status": ..., "duration_seconds": ..., "error": ...}}

    - Client -> Server:
      - {"command": "ping"} -> {"type": "pong"}
    """
    store = get_store()

    # Check run exists
    run = store.get_run(run_id)
    if not run:
        await websocket.close(code=4004, reason="Run not found")
        return

    await websocket.accept()

    # Subscribe to logs
    queue = store.subscribe(run_id)

    try:
        # Send connection acknowledgment
        await websocket.send_json({
            "type": "connected",
            "data": {
                "run_id": run_id,
                "status": run["status"].value if hasattr(run["status"], "value") else run["status"],
                "current_iteration": run["current_iteration"],
                "iterations": run["iterations"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        })

        # Send existing logs
        for log in store.get_logs(run_id):
            await websocket.send_json({
                "type": "log",
                "data": {
                    "timestamp": log["timestamp"].isoformat(),
                    "level": log["level"],
                    "message": log["message"],
                    "iteration": log["iteration"],
                },
            })

        # Stream new logs
        while True:
            try:
                # Wait for new messages with timeout
                message = await asyncio.wait_for(queue.get(), timeout=1.0)
                await websocket.send_json(message)

                # Check if run completed
                if message.get("type") == "complete":
                    break

            except asyncio.TimeoutError:
                # Check if run is still active
                run = store.get_run(run_id)
                if run and run["status"] in (PromptRunStatus.COMPLETED, PromptRunStatus.FAILED, PromptRunStatus.CANCELLED):
                    # Send final status if not already sent
                    await websocket.send_json({
                        "type": "complete",
                        "data": {
                            "run_id": run_id,
                            "status": run["status"].value if hasattr(run["status"], "value") else run["status"],
                            "duration_seconds": run["duration_seconds"],
                            "error": run["error"],
                        },
                    })
                    break

                # Send periodic status update
                await websocket.send_json({
                    "type": "status",
                    "data": {
                        "run_id": run_id,
                        "status": run["status"].value if hasattr(run["status"], "value") else run["status"],
                        "current_iteration": run["current_iteration"],
                    },
                })

            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    finally:
        store.unsubscribe(run_id, queue)
