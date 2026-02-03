"""Pydantic schemas for the web API.

These schemas define the request/response models for the REST API endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class RunStatus(str, Enum):
    """Status of a benchmark run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EventType(str, Enum):
    """Types of real-time events."""

    LOG = "log"
    STATUS = "status"
    PROGRESS = "progress"
    METRICS = "metrics"
    RESULT = "result"
    ERROR = "error"


# =============================================================================
# Run Schemas
# =============================================================================


class RunBase(BaseModel):
    """Base schema for run data."""

    task_id: str
    task_name: str
    agent_id: str


class RunCreate(BaseModel):
    """Schema for creating a new benchmark run."""

    task_id: str = Field(..., description="Task to run")
    agent_id: str = Field(..., description="Agent to use")
    model: str | None = Field(default=None, description="Model override")
    timeout: int = Field(default=1800, description="Timeout in seconds")
    iterations: int = Field(default=1, description="Number of iterations")


class RunScores(BaseModel):
    """Score breakdown for a run."""

    deployment: float = Field(default=0.0, ge=0.0, le=1.0)
    tests: float = Field(default=0.0, ge=0.0, le=1.0)
    static_analysis: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: float = Field(default=0.0, ge=0.0, le=1.0)
    rubric: float = Field(default=0.0, ge=0.0, le=1.0)
    final: float = Field(default=0.0, ge=0.0, le=1.0)


class RunResponse(RunBase):
    """Schema for run response data."""

    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    scores: RunScores
    status: RunStatus
    error: str | None = None
    scratch_org_username: str | None = None


class RunDetailResponse(RunResponse):
    """Schema for detailed run response including evaluation data."""

    agent_output: str = ""
    evaluation: dict[str, Any] | None = None


class RunListResponse(BaseModel):
    """Schema for paginated run list response."""

    runs: list[RunResponse]
    total: int
    limit: int
    offset: int


# =============================================================================
# Run Summary / Statistics
# =============================================================================


class RunSummaryResponse(BaseModel):
    """Summary statistics for all runs."""

    total_runs: int
    completed_runs: int
    failed_runs: int
    best_score: float
    worst_score: float
    average_score: float
    runs_by_agent: dict[str, int]
    avg_score_by_agent: dict[str, float]
    runs_by_task: dict[str, int]
    avg_score_by_task: dict[str, float]
    first_run: datetime | None = None
    last_run: datetime | None = None


class AgentComparisonResponse(BaseModel):
    """Comparison of agent performance."""

    agent_id: str
    total_runs: int
    completed_runs: int
    average_score: float
    best_score: float
    avg_deployment: float
    avg_tests: float
    avg_static_analysis: float
    avg_metadata: float
    avg_rubric: float
    tasks_completed: list[str]


# =============================================================================
# Q&A Schemas
# =============================================================================


class QARunCreate(BaseModel):
    """Schema for creating a new Q&A benchmark run."""

    test_bank_id: str = Field(..., description="Test bank to use")
    model: str = Field(..., description="Model to use")
    sample_size: int | None = Field(default=None, description="Sample N questions")
    domain: str | None = Field(default=None, description="Filter by domain")
    workers: int = Field(default=4, description="Number of parallel workers")


class QAQuestionResponse(BaseModel):
    """Schema for a Q&A question record."""

    question_id: str
    domain: str
    difficulty: str
    question_text: str
    correct_answer: str
    model_response: str
    extracted_answer: str
    is_correct: bool
    response_time: float
    timestamp: str


class QARunResponse(BaseModel):
    """Schema for Q&A run response data."""

    run_id: str
    model_id: str
    cli_id: str
    test_bank_id: str
    test_bank_name: str | None = None
    started_at: str
    completed_at: str | None = None
    total_questions: int
    correct_answers: int
    accuracy: float
    duration_seconds: float
    status: str


class QARunDetailResponse(QARunResponse):
    """Schema for detailed Q&A run including questions."""

    questions: list[QAQuestionResponse] = []


class QARunListResponse(BaseModel):
    """Schema for Q&A run list response."""

    runs: list[QARunResponse]
    total: int


class QAModelComparisonResponse(BaseModel):
    """Comparison of model performance on Q&A tests."""

    model_id: str
    run_count: int
    avg_accuracy: float
    best_accuracy: float
    avg_duration: float
    total_questions: int
    total_correct: int


class QADomainAnalysisResponse(BaseModel):
    """Performance analysis by domain."""

    domain: str
    model_id: str
    total_questions: int
    correct_answers: int
    accuracy: float
    avg_response_time: float


# =============================================================================
# Task Schemas
# =============================================================================


class TaskResponse(BaseModel):
    """Schema for task data."""

    id: str
    name: str
    description: str
    tier: str
    categories: list[str]
    time_limit_minutes: int


class TaskDetailResponse(TaskResponse):
    """Schema for detailed task data including README."""

    readme: str = ""
    evaluation_tests: list[str] = []
    requires_data: bool = False


class TaskListResponse(BaseModel):
    """Schema for task list response."""

    tasks: list[TaskResponse]
    total: int


# =============================================================================
# Test Bank Schemas
# =============================================================================


class TestBankResponse(BaseModel):
    """Schema for test bank data."""

    id: str
    name: str
    description: str = ""
    question_count: int
    domains: list[str]


class TestBankListResponse(BaseModel):
    """Schema for test bank list response."""

    banks: list[TestBankResponse]
    total: int


# =============================================================================
# Model Schemas
# =============================================================================


class ModelResponse(BaseModel):
    """Schema for AI model data."""

    id: str
    name: str
    provider: str
    api_key_env: str | None = None
    context_window: int = 0
    is_available: bool = False


class ModelListResponse(BaseModel):
    """Schema for model list response."""

    models: list[ModelResponse]
    total: int


# =============================================================================
# Configuration Schemas
# =============================================================================


class ConfigResponse(BaseModel):
    """Schema for current configuration."""

    devhub_username: str | None = None
    tasks_dir: str
    results_dir: str
    evaluation_weights: dict[str, float]
    default_model: str | None = None


# =============================================================================
# Event Schemas (for WebSocket)
# =============================================================================


class EventData(BaseModel):
    """Schema for event data sent over WebSocket."""

    type: EventType
    timestamp: datetime
    data: dict[str, Any]


class LogEventData(BaseModel):
    """Schema for log event data."""

    level: str
    source: str
    message: str
    work_unit_id: str | None = None
    details: dict[str, Any] = {}


class StatusEventData(BaseModel):
    """Schema for status event data."""

    work_unit_id: str
    status: str
    progress: float | None = None
    metrics: dict[str, Any] = {}


class ProgressEventData(BaseModel):
    """Schema for progress event data."""

    work_unit_id: str
    current: int
    total: int
    message: str = ""


class MetricsEventData(BaseModel):
    """Schema for metrics event data."""

    total_work_units: int
    completed_work_units: int
    failed_work_units: int
    running_work_units: int
    pending_work_units: int
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    workers_active: int = 0
    workers_total: int = 0


# =============================================================================
# Prompt Runner Schemas
# =============================================================================


class PromptRunCreate(BaseModel):
    """Schema for creating a new prompt run."""

    prompt: str = Field(..., min_length=10, description="Salesforce development prompt/challenge")
    iterations: int = Field(..., description="Number of iterations (1, 5, 10, or 25)")

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Create an Apex trigger that prevents duplicate Contacts by email",
                "iterations": 5,
            }
        }


class PromptRunStatus(str, Enum):
    """Status of a prompt run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PromptRunResponse(BaseModel):
    """Schema for prompt run response data."""

    run_id: str
    prompt: str
    iterations: int
    current_iteration: int = 0
    status: PromptRunStatus
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    error: str | None = None


class PromptRunDetailResponse(PromptRunResponse):
    """Schema for detailed prompt run response including logs."""

    logs: list[str] = []
    iteration_results: list[dict[str, Any]] = []


class PromptRunListResponse(BaseModel):
    """Schema for paginated prompt run list response."""

    runs: list[PromptRunResponse]
    total: int
    limit: int
    offset: int


class PromptLogEvent(BaseModel):
    """Schema for a log event from a prompt run."""

    timestamp: datetime
    level: str
    message: str
    iteration: int | None = None
    details: dict[str, Any] = {}


# =============================================================================
# Health Check
# =============================================================================


class HealthResponse(BaseModel):
    """Schema for health check response."""

    status: str = "healthy"
    version: str
    timestamp: datetime
