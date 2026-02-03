"""Verbose judge logging for analysis and debugging.

Stores complete LLM judge interactions in the database.
"""

import sqlite3
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sf_agentbench.judges.base import JudgeResult


@dataclass
class JudgeLogConfig:
    """Configuration for judge logging."""
    
    enabled: bool = True
    store_prompts: bool = True
    store_responses: bool = True
    store_reasoning: bool = True
    retention_days: int = 90  # 0 = forever


@dataclass
class JudgeLogEntry:
    """A single judge log entry."""
    
    id: str
    work_unit_id: str
    judge_model: str
    rubric_name: str
    rubric_version: str
    
    # Timing
    started_at: str
    completed_at: str | None
    duration_ms: int
    
    # Input (when store_prompts = true)
    prompt_template: str | None
    code_submitted: str | None
    requirements: str | None
    
    # Output (when store_responses = true)
    raw_response: str | None
    parsed_successfully: bool
    parse_error: str | None
    
    # Tokens & Cost
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    
    # Result
    overall_score: float
    criteria_json: str | None  # Full criteria with reasoning


class JudgeLogStore:
    """SQLite storage for judge logs."""
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS judge_logs (
        id TEXT PRIMARY KEY,
        work_unit_id TEXT NOT NULL,
        judge_model TEXT NOT NULL,
        rubric_name TEXT NOT NULL,
        rubric_version TEXT,
        
        -- Timing
        started_at TEXT NOT NULL,
        completed_at TEXT,
        duration_ms INTEGER,
        
        -- Input (when store_prompts = true)
        prompt_template TEXT,
        code_submitted TEXT,
        requirements TEXT,
        
        -- Output (when store_responses = true)
        raw_response TEXT,
        parsed_successfully BOOLEAN,
        parse_error TEXT,
        
        -- Tokens & Cost
        input_tokens INTEGER,
        output_tokens INTEGER,
        estimated_cost_usd REAL,
        
        -- Result
        overall_score REAL,
        criteria_json TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_judge_logs_work_unit ON judge_logs(work_unit_id);
    CREATE INDEX IF NOT EXISTS idx_judge_logs_model ON judge_logs(judge_model);
    CREATE INDEX IF NOT EXISTS idx_judge_logs_score ON judge_logs(overall_score);
    CREATE INDEX IF NOT EXISTS idx_judge_logs_started ON judge_logs(started_at);
    """
    
    def __init__(self, db_path: Path, config: JudgeLogConfig | None = None):
        """Initialize the judge log store.
        
        Args:
            db_path: Path to SQLite database
            config: Logging configuration
        """
        self.db_path = db_path
        self.config = config or JudgeLogConfig()
        
        # Ensure parent directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(self.SCHEMA)
    
    def log(self, work_unit_id: str, result: JudgeResult) -> str:
        """Log a judge result.
        
        Args:
            work_unit_id: ID of the work unit being evaluated
            result: The judge result to log
        
        Returns:
            ID of the log entry
        """
        if not self.config.enabled:
            return ""
        
        import uuid
        log_id = str(uuid.uuid4())[:12]
        
        # Build entry
        entry = JudgeLogEntry(
            id=log_id,
            work_unit_id=work_unit_id,
            judge_model=result.judge_model,
            rubric_name=result.rubric_name,
            rubric_version=result.rubric_version,
            started_at=result.started_at.isoformat() if result.started_at else datetime.utcnow().isoformat(),
            completed_at=result.completed_at.isoformat() if result.completed_at else None,
            duration_ms=result.duration_ms,
            prompt_template=result.prompt_template if self.config.store_prompts else None,
            code_submitted=result.code_submitted if self.config.store_prompts else None,
            requirements=result.requirements if self.config.store_prompts else None,
            raw_response=result.raw_response if self.config.store_responses else None,
            parsed_successfully=result.parsed_successfully,
            parse_error=result.parse_error if result.parse_error else None,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            overall_score=result.overall_score,
            criteria_json=json.dumps([
                {
                    "name": c.name,
                    "score": c.score,
                    "weight": c.weight,
                    "reasoning": c.reasoning if self.config.store_reasoning else "",
                    "line_refs": c.line_refs,
                }
                for c in result.criteria
            ]) if result.criteria else None,
        )
        
        # Insert into database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO judge_logs (
                    id, work_unit_id, judge_model, rubric_name, rubric_version,
                    started_at, completed_at, duration_ms,
                    prompt_template, code_submitted, requirements,
                    raw_response, parsed_successfully, parse_error,
                    input_tokens, output_tokens, estimated_cost_usd,
                    overall_score, criteria_json
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?
                )
                """,
                (
                    entry.id, entry.work_unit_id, entry.judge_model,
                    entry.rubric_name, entry.rubric_version,
                    entry.started_at, entry.completed_at, entry.duration_ms,
                    entry.prompt_template, entry.code_submitted, entry.requirements,
                    entry.raw_response, entry.parsed_successfully, entry.parse_error,
                    entry.input_tokens, entry.output_tokens, entry.estimated_cost_usd,
                    entry.overall_score, entry.criteria_json,
                ),
            )
        
        return log_id
    
    def get(self, log_id: str) -> JudgeLogEntry | None:
        """Get a log entry by ID.
        
        Args:
            log_id: ID of the log entry
        
        Returns:
            The log entry, or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM judge_logs WHERE id = ?",
                (log_id,),
            ).fetchone()
            
            if not row:
                return None
            
            return self._row_to_entry(row)
    
    def get_by_work_unit(self, work_unit_id: str) -> list[JudgeLogEntry]:
        """Get all log entries for a work unit.
        
        Args:
            work_unit_id: ID of the work unit
        
        Returns:
            List of log entries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM judge_logs WHERE work_unit_id = ? ORDER BY started_at DESC",
                (work_unit_id,),
            ).fetchall()
            
            return [self._row_to_entry(row) for row in rows]
    
    def query(
        self,
        model: str | None = None,
        rubric: str | None = None,
        min_score: float | None = None,
        max_score: float | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[JudgeLogEntry]:
        """Query log entries with filters.
        
        Args:
            model: Filter by judge model
            rubric: Filter by rubric name
            min_score: Minimum overall score
            max_score: Maximum overall score
            since: Only entries after this time
            limit: Maximum entries to return
        
        Returns:
            List of matching log entries
        """
        conditions = []
        params = []
        
        if model:
            conditions.append("judge_model LIKE ?")
            params.append(f"%{model}%")
        
        if rubric:
            conditions.append("rubric_name LIKE ?")
            params.append(f"%{rubric}%")
        
        if min_score is not None:
            conditions.append("overall_score >= ?")
            params.append(min_score)
        
        if max_score is not None:
            conditions.append("overall_score <= ?")
            params.append(max_score)
        
        if since:
            conditions.append("started_at >= ?")
            params.append(since.isoformat())
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT * FROM judge_logs
                WHERE {where_clause}
                ORDER BY started_at DESC
                LIMIT ?
                """,
                params + [limit],
            ).fetchall()
            
            return [self._row_to_entry(row) for row in rows]
    
    def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics.
        
        Returns:
            Dictionary with statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            # Total counts
            total = conn.execute("SELECT COUNT(*) FROM judge_logs").fetchone()[0]
            
            # By model
            by_model = conn.execute(
                """
                SELECT judge_model, COUNT(*) as count, 
                       AVG(overall_score) as avg_score,
                       SUM(estimated_cost_usd) as total_cost
                FROM judge_logs
                GROUP BY judge_model
                """
            ).fetchall()
            
            # By rubric
            by_rubric = conn.execute(
                """
                SELECT rubric_name, COUNT(*) as count,
                       AVG(overall_score) as avg_score
                FROM judge_logs
                GROUP BY rubric_name
                """
            ).fetchall()
            
            return {
                "total_entries": total,
                "by_model": [
                    {"model": r[0], "count": r[1], "avg_score": r[2], "total_cost": r[3]}
                    for r in by_model
                ],
                "by_rubric": [
                    {"rubric": r[0], "count": r[1], "avg_score": r[2]}
                    for r in by_rubric
                ],
            }
    
    def cleanup(self, before: datetime | None = None) -> int:
        """Clean up old log entries.
        
        Args:
            before: Delete entries before this time (default: use retention_days)
        
        Returns:
            Number of entries deleted
        """
        if before is None:
            if self.config.retention_days == 0:
                return 0  # Keep forever
            before = datetime.utcnow() - timedelta(days=self.config.retention_days)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM judge_logs WHERE started_at < ?",
                (before.isoformat(),),
            )
            return cursor.rowcount
    
    def export_csv(self, output_path: Path) -> int:
        """Export logs to CSV.
        
        Args:
            output_path: Path for the CSV file
        
        Returns:
            Number of entries exported
        """
        import csv
        
        entries = self.query(limit=10000)
        
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "work_unit_id", "judge_model", "rubric_name",
                "started_at", "duration_ms", "overall_score",
                "input_tokens", "output_tokens", "estimated_cost_usd",
                "parsed_successfully",
            ])
            
            for entry in entries:
                writer.writerow([
                    entry.id, entry.work_unit_id, entry.judge_model, entry.rubric_name,
                    entry.started_at, entry.duration_ms, entry.overall_score,
                    entry.input_tokens, entry.output_tokens, entry.estimated_cost_usd,
                    entry.parsed_successfully,
                ])
        
        return len(entries)
    
    def _row_to_entry(self, row: sqlite3.Row) -> JudgeLogEntry:
        """Convert a database row to a log entry."""
        return JudgeLogEntry(
            id=row["id"],
            work_unit_id=row["work_unit_id"],
            judge_model=row["judge_model"],
            rubric_name=row["rubric_name"],
            rubric_version=row["rubric_version"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            duration_ms=row["duration_ms"] or 0,
            prompt_template=row["prompt_template"],
            code_submitted=row["code_submitted"],
            requirements=row["requirements"],
            raw_response=row["raw_response"],
            parsed_successfully=bool(row["parsed_successfully"]),
            parse_error=row["parse_error"],
            input_tokens=row["input_tokens"] or 0,
            output_tokens=row["output_tokens"] or 0,
            estimated_cost_usd=row["estimated_cost_usd"] or 0.0,
            overall_score=row["overall_score"] or 0.0,
            criteria_json=row["criteria_json"],
        )


# Analysis queries as functions

def find_inconsistent_judgments(store: JudgeLogStore) -> list[dict]:
    """Find cases where the same code got different scores.
    
    Args:
        store: The judge log store
    
    Returns:
        List of inconsistent judgment cases
    """
    with sqlite3.connect(store.db_path) as conn:
        # Group by code hash and find high variance
        rows = conn.execute(
            """
            SELECT 
                substr(code_submitted, 1, 100) as code_preview,
                judge_model,
                COUNT(*) as evaluations,
                AVG(overall_score) as avg_score,
                MAX(overall_score) - MIN(overall_score) as score_range
            FROM judge_logs
            WHERE code_submitted IS NOT NULL
            GROUP BY code_submitted, judge_model
            HAVING score_range > 0.1
            ORDER BY score_range DESC
            LIMIT 20
            """
        ).fetchall()
        
        return [
            {
                "code_preview": r[0],
                "model": r[1],
                "evaluations": r[2],
                "avg_score": r[3],
                "score_range": r[4],
            }
            for r in rows
        ]


def get_cost_breakdown(store: JudgeLogStore) -> list[dict]:
    """Get cost breakdown by rubric and model.
    
    Args:
        store: The judge log store
    
    Returns:
        List of cost breakdown entries
    """
    with sqlite3.connect(store.db_path) as conn:
        rows = conn.execute(
            """
            SELECT 
                rubric_name,
                judge_model,
                COUNT(*) as evaluations,
                SUM(estimated_cost_usd) as total_cost,
                AVG(duration_ms) as avg_latency_ms
            FROM judge_logs
            GROUP BY rubric_name, judge_model
            ORDER BY total_cost DESC
            """
        ).fetchall()
        
        return [
            {
                "rubric": r[0],
                "model": r[1],
                "evaluations": r[2],
                "total_cost": r[3],
                "avg_latency_ms": r[4],
            }
            for r in rows
        ]


def find_low_confidence_judgments(store: JudgeLogStore) -> list[JudgeLogEntry]:
    """Find judgments with mid-range scores (potentially uncertain).
    
    Args:
        store: The judge log store
    
    Returns:
        List of low-confidence log entries
    """
    return store.query(min_score=0.4, max_score=0.6, limit=50)
