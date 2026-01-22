"""Unified storage schema for SF-AgentBench.

Provides a single storage layer for all test types and results.
"""

import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
import uuid

from sf_agentbench.domain.models import (
    Benchmark,
    Test,
    QATest,
    CodingTest,
    TestType,
    Agent,
    WorkUnit,
    WorkUnitStatus,
    Result,
    Cost,
)
from sf_agentbench.domain.metrics import PerformanceMetrics


UNIFIED_SCHEMA = """
-- Benchmarks
CREATE TABLE IF NOT EXISTS benchmarks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL
);

-- Tests
CREATE TABLE IF NOT EXISTS tests (
    id TEXT PRIMARY KEY,
    benchmark_id TEXT,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    config TEXT,
    timeout_seconds INTEGER DEFAULT 300,
    FOREIGN KEY (benchmark_id) REFERENCES benchmarks(id)
);

-- Agents
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    cli_id TEXT NOT NULL,
    model TEXT NOT NULL,
    display_name TEXT,
    cost_profile TEXT
);

-- Work Units
CREATE TABLE IF NOT EXISTS work_units (
    id TEXT PRIMARY KEY,
    test_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    scratch_org TEXT,
    work_dir TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (test_id) REFERENCES tests(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Results
CREATE TABLE IF NOT EXISTS results (
    id TEXT PRIMARY KEY,
    work_unit_id TEXT NOT NULL UNIQUE,
    score REAL NOT NULL,
    duration_seconds REAL,
    error TEXT,
    
    -- Token/Cost tracking
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    estimated_cost_usd REAL DEFAULT 0.0,
    
    -- Q&A specific
    correct_answers INTEGER,
    total_questions INTEGER,
    
    -- Coding specific
    deployment_score REAL,
    test_score REAL,
    static_analysis_score REAL,
    rubric_score REAL,
    
    -- Details
    details TEXT,
    
    FOREIGN KEY (work_unit_id) REFERENCES work_units(id)
);

-- Runs (grouping of work units)
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    benchmark_id TEXT,
    name TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    config TEXT,
    
    -- Summary
    total_work_units INTEGER DEFAULT 0,
    completed_work_units INTEGER DEFAULT 0,
    failed_work_units INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    
    FOREIGN KEY (benchmark_id) REFERENCES benchmarks(id)
);

-- Run <-> Work Unit mapping
CREATE TABLE IF NOT EXISTS run_work_units (
    run_id TEXT NOT NULL,
    work_unit_id TEXT NOT NULL,
    PRIMARY KEY (run_id, work_unit_id),
    FOREIGN KEY (run_id) REFERENCES runs(id),
    FOREIGN KEY (work_unit_id) REFERENCES work_units(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_work_units_test ON work_units(test_id);
CREATE INDEX IF NOT EXISTS idx_work_units_agent ON work_units(agent_id);
CREATE INDEX IF NOT EXISTS idx_work_units_status ON work_units(status);
CREATE INDEX IF NOT EXISTS idx_results_work_unit ON results(work_unit_id);
CREATE INDEX IF NOT EXISTS idx_results_score ON results(score);
CREATE INDEX IF NOT EXISTS idx_runs_benchmark ON runs(benchmark_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
"""


class UnifiedStore:
    """Unified storage for all benchmark data.
    
    Provides CRUD operations for benchmarks, tests, agents, work units, and results.
    """
    
    def __init__(self, db_path: Path):
        """Initialize the unified store.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(UNIFIED_SCHEMA)
    
    # Benchmark operations
    
    def save_benchmark(self, benchmark: Benchmark) -> str:
        """Save a benchmark."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO benchmarks (id, name, version, description, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    benchmark.id,
                    benchmark.name,
                    benchmark.version,
                    benchmark.description,
                    benchmark.created_at.isoformat(),
                ),
            )
            
            # Save tests
            for test in benchmark.tests:
                self._save_test(conn, test, benchmark.id)
        
        return benchmark.id
    
    def get_benchmark(self, benchmark_id: str) -> Benchmark | None:
        """Get a benchmark by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM benchmarks WHERE id = ?",
                (benchmark_id,),
            ).fetchone()
            
            if not row:
                return None
            
            # Load tests
            tests = self._get_tests_for_benchmark(conn, benchmark_id)
            
            return Benchmark(
                id=row["id"],
                name=row["name"],
                version=row["version"],
                description=row["description"] or "",
                tests=tests,
                created_at=datetime.fromisoformat(row["created_at"]),
            )
    
    def list_benchmarks(self) -> list[Benchmark]:
        """List all benchmarks."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id FROM benchmarks ORDER BY created_at DESC"
            ).fetchall()
            
            return [
                self.get_benchmark(row["id"])
                for row in rows
                if self.get_benchmark(row["id"])
            ]
    
    def _save_test(self, conn: sqlite3.Connection, test: Test, benchmark_id: str | None) -> None:
        """Save a test."""
        config = {}
        
        if isinstance(test, QATest):
            config = {
                "questions": test.questions,
                "domain": test.domain,
                "test_bank_path": str(test.test_bank_path) if test.test_bank_path else None,
            }
        elif isinstance(test, CodingTest):
            config = {
                "task_path": str(test.task_path) if test.task_path else None,
                "tier": test.tier,
                "categories": test.categories,
                "requires_scratch_org": test.requires_scratch_org,
            }
        else:
            config = test.config
        
        conn.execute(
            """
            INSERT OR REPLACE INTO tests (id, benchmark_id, type, name, config, timeout_seconds)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                test.id,
                benchmark_id,
                test.type.value,
                test.name,
                json.dumps(config),
                test.timeout_seconds,
            ),
        )
    
    def _get_tests_for_benchmark(self, conn: sqlite3.Connection, benchmark_id: str) -> list[Test]:
        """Get all tests for a benchmark."""
        rows = conn.execute(
            "SELECT * FROM tests WHERE benchmark_id = ?",
            (benchmark_id,),
        ).fetchall()
        
        tests = []
        for row in rows:
            config = json.loads(row["config"]) if row["config"] else {}
            test_type = TestType(row["type"])
            
            if test_type == TestType.QA:
                test = QATest(
                    id=row["id"],
                    name=row["name"],
                    questions=config.get("questions", []),
                    domain=config.get("domain", ""),
                    test_bank_path=Path(config["test_bank_path"]) if config.get("test_bank_path") else None,
                    timeout_seconds=row["timeout_seconds"],
                )
            elif test_type == TestType.CODING:
                test = CodingTest(
                    id=row["id"],
                    name=row["name"],
                    task_path=Path(config["task_path"]) if config.get("task_path") else None,
                    tier=config.get("tier", "tier-1"),
                    categories=config.get("categories", []),
                    requires_scratch_org=config.get("requires_scratch_org", True),
                    timeout_seconds=row["timeout_seconds"],
                )
            else:
                test = Test(
                    id=row["id"],
                    type=test_type,
                    name=row["name"],
                    config=config,
                    timeout_seconds=row["timeout_seconds"],
                )
            
            tests.append(test)
        
        return tests
    
    # Agent operations
    
    def save_agent(self, agent: Agent) -> str:
        """Save an agent."""
        cost_profile = None
        if agent.cost_profile:
            cost_profile = json.dumps({
                "input_cost_per_million": agent.cost_profile.input_cost_per_million,
                "output_cost_per_million": agent.cost_profile.output_cost_per_million,
            })
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO agents (id, cli_id, model, display_name, cost_profile)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    agent.id,
                    agent.cli_id,
                    agent.model,
                    agent.display_name,
                    cost_profile,
                ),
            )
        
        return agent.id
    
    def get_agent(self, agent_id: str) -> Agent | None:
        """Get an agent by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM agents WHERE id = ?",
                (agent_id,),
            ).fetchone()
            
            if not row:
                return None
            
            from sf_agentbench.domain.models import CostProfile
            
            cost_profile = None
            if row["cost_profile"]:
                cp_data = json.loads(row["cost_profile"])
                cost_profile = CostProfile(
                    input_cost_per_million=cp_data["input_cost_per_million"],
                    output_cost_per_million=cp_data["output_cost_per_million"],
                )
            
            return Agent(
                id=row["id"],
                cli_id=row["cli_id"],
                model=row["model"],
                display_name=row["display_name"],
                cost_profile=cost_profile,
            )
    
    def list_agents(self) -> list[Agent]:
        """List all agents."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id FROM agents").fetchall()
            
            return [
                self.get_agent(row["id"])
                for row in rows
                if self.get_agent(row["id"])
            ]
    
    # Work Unit operations
    
    def save_work_unit(self, work_unit: WorkUnit) -> str:
        """Save a work unit."""
        # Ensure test and agent are saved
        with sqlite3.connect(self.db_path) as conn:
            self._save_test(conn, work_unit.test, None)
        self.save_agent(work_unit.agent)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO work_units (
                    id, test_id, agent_id, status, priority, retry_count, max_retries,
                    scratch_org, work_dir, created_at, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    work_unit.id,
                    work_unit.test.id,
                    work_unit.agent.id,
                    work_unit.status.value,
                    work_unit.priority,
                    work_unit.retry_count,
                    work_unit.max_retries,
                    work_unit.scratch_org,
                    str(work_unit.work_dir) if work_unit.work_dir else None,
                    work_unit.created_at.isoformat(),
                    work_unit.started_at.isoformat() if work_unit.started_at else None,
                    work_unit.completed_at.isoformat() if work_unit.completed_at else None,
                ),
            )
            
            # Save result if present
            if work_unit.result:
                self._save_result(conn, work_unit.id, work_unit.result)
        
        return work_unit.id
    
    def _save_result(self, conn: sqlite3.Connection, work_unit_id: str, result: Result) -> None:
        """Save a result."""
        result_id = str(uuid.uuid4())[:12]
        
        conn.execute(
            """
            INSERT OR REPLACE INTO results (
                id, work_unit_id, score, duration_seconds, error,
                input_tokens, output_tokens, estimated_cost_usd,
                correct_answers, total_questions,
                deployment_score, test_score, static_analysis_score, rubric_score,
                details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result_id,
                work_unit_id,
                result.score,
                result.duration_seconds,
                result.error,
                result.cost.input_tokens,
                result.cost.output_tokens,
                result.cost.estimated_usd,
                result.correct_answers,
                result.total_questions,
                result.deployment_score,
                result.test_score,
                result.static_analysis_score,
                result.rubric_score,
                json.dumps(result.details),
            ),
        )
    
    def get_work_unit(self, work_unit_id: str) -> WorkUnit | None:
        """Get a work unit by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM work_units WHERE id = ?",
                (work_unit_id,),
            ).fetchone()
            
            if not row:
                return None
            
            # Get test and agent
            test = self._get_test_by_id(conn, row["test_id"])
            agent = self.get_agent(row["agent_id"])
            
            if not test or not agent:
                return None
            
            # Get result
            result = self._get_result_for_work_unit(conn, work_unit_id)
            
            return WorkUnit(
                id=row["id"],
                test=test,
                agent=agent,
                status=WorkUnitStatus(row["status"]),
                result=result,
                created_at=datetime.fromisoformat(row["created_at"]),
                started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                scratch_org=row["scratch_org"],
                work_dir=Path(row["work_dir"]) if row["work_dir"] else None,
                priority=row["priority"],
                retry_count=row["retry_count"],
                max_retries=row["max_retries"],
            )
    
    def _get_test_by_id(self, conn: sqlite3.Connection, test_id: str) -> Test | None:
        """Get a test by ID."""
        row = conn.execute(
            "SELECT * FROM tests WHERE id = ?",
            (test_id,),
        ).fetchone()
        
        if not row:
            return None
        
        config = json.loads(row["config"]) if row["config"] else {}
        test_type = TestType(row["type"])
        
        if test_type == TestType.QA:
            return QATest(
                id=row["id"],
                name=row["name"],
                questions=config.get("questions", []),
                domain=config.get("domain", ""),
                timeout_seconds=row["timeout_seconds"],
            )
        elif test_type == TestType.CODING:
            return CodingTest(
                id=row["id"],
                name=row["name"],
                task_path=Path(config["task_path"]) if config.get("task_path") else None,
                tier=config.get("tier", "tier-1"),
                timeout_seconds=row["timeout_seconds"],
            )
        
        return Test(
            id=row["id"],
            type=test_type,
            name=row["name"],
            config=config,
            timeout_seconds=row["timeout_seconds"],
        )
    
    def _get_result_for_work_unit(self, conn: sqlite3.Connection, work_unit_id: str) -> Result | None:
        """Get result for a work unit."""
        row = conn.execute(
            "SELECT * FROM results WHERE work_unit_id = ?",
            (work_unit_id,),
        ).fetchone()
        
        if not row:
            return None
        
        return Result(
            score=row["score"],
            cost=Cost(
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
                estimated_usd=row["estimated_cost_usd"] or 0.0,
            ),
            duration_seconds=row["duration_seconds"] or 0.0,
            details=json.loads(row["details"]) if row["details"] else {},
            error=row["error"],
            correct_answers=row["correct_answers"] or 0,
            total_questions=row["total_questions"] or 0,
            deployment_score=row["deployment_score"] or 0.0,
            test_score=row["test_score"] or 0.0,
            static_analysis_score=row["static_analysis_score"] or 0.0,
            rubric_score=row["rubric_score"] or 0.0,
        )
    
    def query_work_units(
        self,
        status: WorkUnitStatus | None = None,
        agent_id: str | None = None,
        test_type: TestType | None = None,
        limit: int = 100,
    ) -> list[WorkUnit]:
        """Query work units with filters."""
        conditions = []
        params = []
        
        if status:
            conditions.append("status = ?")
            params.append(status.value)
        
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT id FROM work_units
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params + [limit],
            ).fetchall()
            
            return [
                self.get_work_unit(row["id"])
                for row in rows
                if self.get_work_unit(row["id"])
            ]
    
    # Statistics
    
    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        with sqlite3.connect(self.db_path) as conn:
            benchmarks = conn.execute("SELECT COUNT(*) FROM benchmarks").fetchone()[0]
            tests = conn.execute("SELECT COUNT(*) FROM tests").fetchone()[0]
            agents = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            work_units = conn.execute("SELECT COUNT(*) FROM work_units").fetchone()[0]
            results = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
            
            # Cost totals
            total_cost = conn.execute(
                "SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM results"
            ).fetchone()[0]
            
            # By status
            by_status = conn.execute(
                "SELECT status, COUNT(*) FROM work_units GROUP BY status"
            ).fetchall()
            
            return {
                "benchmarks": benchmarks,
                "tests": tests,
                "agents": agents,
                "work_units": work_units,
                "results": results,
                "total_cost_usd": total_cost,
                "by_status": {row[0]: row[1] for row in by_status},
            }
