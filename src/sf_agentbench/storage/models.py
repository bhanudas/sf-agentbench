"""Storage models for results persistence."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RunRecord(BaseModel):
    """A single benchmark run record."""

    run_id: str = Field(..., description="Unique run identifier")
    task_id: str = Field(..., description="Task that was run")
    task_name: str = Field(..., description="Human-readable task name")
    agent_id: str = Field(..., description="Agent that performed the run")
    
    # Timestamps
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)
    duration_seconds: float = Field(default=0.0)
    
    # Scores (0.0 to 1.0)
    deployment_score: float = Field(default=0.0)
    test_score: float = Field(default=0.0)
    static_analysis_score: float = Field(default=0.0)
    metadata_score: float = Field(default=0.0)
    rubric_score: float = Field(default=0.0)
    final_score: float = Field(default=0.0)
    
    # Status
    status: str = Field(default="pending")  # pending, running, completed, failed
    error: str | None = Field(default=None)
    
    # Scratch org info
    scratch_org_username: str | None = Field(default=None)
    
    # Path to detailed results JSON
    results_path: str | None = Field(default=None)


class RunSummary(BaseModel):
    """Summary statistics for runs."""

    total_runs: int = Field(default=0)
    completed_runs: int = Field(default=0)
    failed_runs: int = Field(default=0)
    
    # Score statistics
    best_score: float = Field(default=0.0)
    worst_score: float = Field(default=0.0)
    average_score: float = Field(default=0.0)
    
    # By agent
    runs_by_agent: dict[str, int] = Field(default_factory=dict)
    avg_score_by_agent: dict[str, float] = Field(default_factory=dict)
    
    # By task
    runs_by_task: dict[str, int] = Field(default_factory=dict)
    avg_score_by_task: dict[str, float] = Field(default_factory=dict)
    
    # By tier
    runs_by_tier: dict[str, int] = Field(default_factory=dict)
    avg_score_by_tier: dict[str, float] = Field(default_factory=dict)
    
    # Time range
    first_run: datetime | None = Field(default=None)
    last_run: datetime | None = Field(default=None)


class AgentComparison(BaseModel):
    """Comparison of agents across tasks."""

    agent_id: str
    total_runs: int = Field(default=0)
    completed_runs: int = Field(default=0)
    average_score: float = Field(default=0.0)
    best_score: float = Field(default=0.0)
    
    # Layer averages
    avg_deployment: float = Field(default=0.0)
    avg_tests: float = Field(default=0.0)
    avg_static_analysis: float = Field(default=0.0)
    avg_metadata: float = Field(default=0.0)
    avg_rubric: float = Field(default=0.0)
    
    # Tasks completed
    tasks_completed: list[str] = Field(default_factory=list)
