"""SQLite-based results store for SF-AgentBench."""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sf_agentbench.storage.models import RunRecord, RunSummary, AgentComparison
from sf_agentbench.models import TaskResult, EvaluationResult


class ResultsStore:
    """Persistent storage for benchmark results using SQLite."""

    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = results_dir / "benchmark_results.db"
        self.runs_dir = results_dir / "runs"
        self.runs_dir.mkdir(exist_ok=True)
        
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    duration_seconds REAL DEFAULT 0,
                    deployment_score REAL DEFAULT 0,
                    test_score REAL DEFAULT 0,
                    static_analysis_score REAL DEFAULT 0,
                    metadata_score REAL DEFAULT 0,
                    rubric_score REAL DEFAULT 0,
                    final_score REAL DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    error TEXT,
                    scratch_org_username TEXT,
                    results_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Index for common queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_agent ON runs(agent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at)")
            
            conn.commit()

    def save_run(self, result: TaskResult) -> str:
        """
        Save a task result to the database and filesystem.
        
        Returns the run_id.
        """
        run_id = str(uuid.uuid4())[:12]
        
        # Save detailed JSON to filesystem
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        results_file = run_dir / "result.json"
        with open(results_file, "w") as f:
            json.dump(result.model_dump(mode="json"), f, indent=2, default=str)
        
        # Save agent output if present
        if result.agent_output:
            (run_dir / "agent_output.txt").write_text(result.agent_output)
        
        # Extract scores
        eval_result = result.evaluation
        
        # Insert into database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO runs (
                    run_id, task_id, task_name, agent_id,
                    started_at, completed_at, duration_seconds,
                    deployment_score, test_score, static_analysis_score,
                    metadata_score, rubric_score, final_score,
                    status, error, scratch_org_username, results_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                result.task_id,
                result.task_name,
                result.agent_id,
                result.started_at.isoformat() if result.started_at else None,
                result.completed_at.isoformat() if result.completed_at else None,
                result.duration_seconds,
                eval_result.deployment_score,
                eval_result.test_score,
                eval_result.static_analysis_score,
                eval_result.metadata_score,
                eval_result.rubric_score,
                eval_result.final_score,
                "completed" if result.is_complete else ("failed" if result.error else "pending"),
                result.error,
                result.scratch_org.username if result.scratch_org else None,
                str(results_file),
            ))
            conn.commit()
        
        return run_id

    def get_run(self, run_id: str) -> RunRecord | None:
        """Get a single run by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?",
                (run_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return self._row_to_record(row)
        return None

    def get_run_details(self, run_id: str) -> TaskResult | None:
        """Get full run details from JSON file."""
        record = self.get_run(run_id)
        if record and record.results_path:
            results_path = Path(record.results_path)
            if results_path.exists():
                with open(results_path) as f:
                    data = json.load(f)
                return TaskResult(**data)
        return None

    def list_runs(
        self,
        task_id: str | None = None,
        agent_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RunRecord]:
        """List runs with optional filters."""
        query = "SELECT * FROM runs WHERE 1=1"
        params: list[Any] = []
        
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def get_summary(self) -> RunSummary:
        """Get summary statistics for all runs."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Basic counts
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    MAX(final_score) as best,
                    MIN(CASE WHEN final_score > 0 THEN final_score END) as worst,
                    AVG(CASE WHEN status = 'completed' THEN final_score END) as avg,
                    MIN(started_at) as first_run,
                    MAX(started_at) as last_run
                FROM runs
            """)
            row = cursor.fetchone()
            
            summary = RunSummary(
                total_runs=row["total"] or 0,
                completed_runs=row["completed"] or 0,
                failed_runs=row["failed"] or 0,
                best_score=row["best"] or 0.0,
                worst_score=row["worst"] or 0.0,
                average_score=row["avg"] or 0.0,
                first_run=datetime.fromisoformat(row["first_run"]) if row["first_run"] else None,
                last_run=datetime.fromisoformat(row["last_run"]) if row["last_run"] else None,
            )
            
            # By agent
            cursor = conn.execute("""
                SELECT agent_id, COUNT(*) as count, AVG(final_score) as avg
                FROM runs WHERE status = 'completed'
                GROUP BY agent_id
            """)
            for row in cursor.fetchall():
                summary.runs_by_agent[row["agent_id"]] = row["count"]
                summary.avg_score_by_agent[row["agent_id"]] = row["avg"] or 0.0
            
            # By task
            cursor = conn.execute("""
                SELECT task_id, COUNT(*) as count, AVG(final_score) as avg
                FROM runs WHERE status = 'completed'
                GROUP BY task_id
            """)
            for row in cursor.fetchall():
                summary.runs_by_task[row["task_id"]] = row["count"]
                summary.avg_score_by_task[row["task_id"]] = row["avg"] or 0.0
            
            return summary

    def get_agent_comparison(self) -> list[AgentComparison]:
        """Get comparison of all agents."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            cursor = conn.execute("""
                SELECT 
                    agent_id,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    AVG(CASE WHEN status = 'completed' THEN final_score END) as avg_score,
                    MAX(final_score) as best_score,
                    AVG(CASE WHEN status = 'completed' THEN deployment_score END) as avg_deploy,
                    AVG(CASE WHEN status = 'completed' THEN test_score END) as avg_tests,
                    AVG(CASE WHEN status = 'completed' THEN static_analysis_score END) as avg_static,
                    AVG(CASE WHEN status = 'completed' THEN metadata_score END) as avg_meta,
                    AVG(CASE WHEN status = 'completed' THEN rubric_score END) as avg_rubric
                FROM runs
                GROUP BY agent_id
                ORDER BY avg_score DESC
            """)
            
            comparisons = []
            for row in cursor.fetchall():
                # Get tasks completed by this agent
                tasks_cursor = conn.execute("""
                    SELECT DISTINCT task_id FROM runs 
                    WHERE agent_id = ? AND status = 'completed'
                """, (row["agent_id"],))
                tasks = [t["task_id"] for t in tasks_cursor.fetchall()]
                
                comparisons.append(AgentComparison(
                    agent_id=row["agent_id"],
                    total_runs=row["total"] or 0,
                    completed_runs=row["completed"] or 0,
                    average_score=row["avg_score"] or 0.0,
                    best_score=row["best_score"] or 0.0,
                    avg_deployment=row["avg_deploy"] or 0.0,
                    avg_tests=row["avg_tests"] or 0.0,
                    avg_static_analysis=row["avg_static"] or 0.0,
                    avg_metadata=row["avg_meta"] or 0.0,
                    avg_rubric=row["avg_rubric"] or 0.0,
                    tasks_completed=tasks,
                ))
            
            return comparisons

    def get_task_history(self, task_id: str, limit: int = 20) -> list[RunRecord]:
        """Get run history for a specific task."""
        return self.list_runs(task_id=task_id, limit=limit)

    def get_agent_history(self, agent_id: str, limit: int = 20) -> list[RunRecord]:
        """Get run history for a specific agent."""
        return self.list_runs(agent_id=agent_id, limit=limit)

    def delete_run(self, run_id: str) -> bool:
        """Delete a run and its associated files."""
        import shutil
        
        run_dir = self.runs_dir / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
            conn.commit()
            return cursor.rowcount > 0

    def export_to_json(self, output_path: Path) -> None:
        """Export all runs to a JSON file."""
        runs = self.list_runs(limit=10000)
        data = [r.model_dump(mode="json") for r in runs]
        
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def export_to_csv(self, output_path: Path) -> None:
        """Export all runs to a CSV file."""
        runs = self.list_runs(limit=10000)
        
        with open(output_path, "w") as f:
            # Header
            f.write("run_id,task_id,task_name,agent_id,started_at,duration_seconds,")
            f.write("deployment_score,test_score,static_analysis_score,")
            f.write("metadata_score,rubric_score,final_score,status,error\n")
            
            # Data
            for run in runs:
                f.write(f"{run.run_id},{run.task_id},{run.task_name},{run.agent_id},")
                f.write(f"{run.started_at},{run.duration_seconds:.2f},")
                f.write(f"{run.deployment_score:.2f},{run.test_score:.2f},")
                f.write(f"{run.static_analysis_score:.2f},{run.metadata_score:.2f},")
                f.write(f"{run.rubric_score:.2f},{run.final_score:.2f},")
                f.write(f"{run.status},{run.error or ''}\n")

    def _row_to_record(self, row: sqlite3.Row) -> RunRecord:
        """Convert a database row to a RunRecord."""
        return RunRecord(
            run_id=row["run_id"],
            task_id=row["task_id"],
            task_name=row["task_name"],
            agent_id=row["agent_id"],
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else datetime.utcnow(),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            duration_seconds=row["duration_seconds"] or 0.0,
            deployment_score=row["deployment_score"] or 0.0,
            test_score=row["test_score"] or 0.0,
            static_analysis_score=row["static_analysis_score"] or 0.0,
            metadata_score=row["metadata_score"] or 0.0,
            rubric_score=row["rubric_score"] or 0.0,
            final_score=row["final_score"] or 0.0,
            status=row["status"] or "pending",
            error=row["error"],
            scratch_org_username=row["scratch_org_username"],
            results_path=row["results_path"],
        )
