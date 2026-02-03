"""Core domain models for SF-AgentBench.

Defines the unified domain model for benchmarks, tests, agents, and results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
import uuid


class TestType(str, Enum):
    """Types of benchmark tests."""
    
    QA = "qa"  # Question/Answer knowledge tests
    CODING = "coding"  # Salesforce coding tasks
    LWC = "lwc"  # Lightning Web Component tasks (future)
    INTEGRATION = "integration"  # Integration tests (future)


class WorkUnitStatus(str, Enum):
    """Status of a work unit through its lifecycle."""
    
    PENDING = "pending"  # Queued, waiting to start
    RUNNING = "running"  # Currently executing
    PAUSED = "paused"  # Paused by user command
    COMPLETED = "completed"  # Finished successfully
    FAILED = "failed"  # Finished with error
    CANCELLED = "cancelled"  # Cancelled by user
    TIMEOUT = "timeout"  # Exceeded time limit


@dataclass
class CostProfile:
    """Cost profile for a model (per 1M tokens)."""
    
    input_cost_per_million: float  # USD per 1M input tokens
    output_cost_per_million: float  # USD per 1M output tokens
    
    def estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD."""
        input_cost = (input_tokens / 1_000_000) * self.input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * self.output_cost_per_million
        return input_cost + output_cost


@dataclass
class Cost:
    """Cost tracking for a single execution."""
    
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_usd: float = 0.0
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
    
    def add(self, other: "Cost") -> "Cost":
        """Add another cost to this one."""
        return Cost(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            estimated_usd=self.estimated_usd + other.estimated_usd,
        )


@dataclass
class Agent:
    """An AI agent configuration for benchmarking."""
    
    id: str  # Unique identifier (e.g., "claude-sonnet-gemini-cli")
    cli_id: str  # CLI tool ID (e.g., "gemini-cli", "claude-code")
    model: str  # Model name (e.g., "gemini-2.0-flash", "sonnet")
    cost_profile: CostProfile | None = None
    display_name: str | None = None
    
    def __post_init__(self):
        if not self.display_name:
            self.display_name = f"{self.cli_id}/{self.model}"
    
    @classmethod
    def from_cli(cls, cli_id: str, model: str) -> "Agent":
        """Create an agent from CLI and model."""
        return cls(
            id=f"{cli_id}-{model}",
            cli_id=cli_id,
            model=model,
        )


@dataclass
class Test:
    """Base class for all test types."""
    
    id: str
    type: TestType
    name: str
    config: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 300  # 5 minutes default
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:12]


@dataclass
class QATest(Test):
    """A Q&A knowledge test."""
    
    questions: list[dict] = field(default_factory=list)
    domain: str = ""
    test_bank_path: Path | None = None
    
    def __post_init__(self):
        self.type = TestType.QA
        super().__post_init__()
    
    @property
    def question_count(self) -> int:
        return len(self.questions)


@dataclass
class CodingTest(Test):
    """A Salesforce coding task test."""
    
    task_path: Path | None = None
    tier: str = "tier-1"  # tier-1, tier-2, tier-3, tier-4
    categories: list[str] = field(default_factory=list)
    requires_scratch_org: bool = True
    
    def __post_init__(self):
        self.type = TestType.CODING
        super().__post_init__()


@dataclass
class Benchmark:
    """A versioned collection of tests."""
    
    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    tests: list[Test] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:12]
    
    def add_test(self, test: Test) -> None:
        """Add a test to the benchmark."""
        self.tests.append(test)
    
    def get_tests_by_type(self, test_type: TestType) -> list[Test]:
        """Get all tests of a specific type."""
        return [t for t in self.tests if t.type == test_type]
    
    @property
    def qa_tests(self) -> list[QATest]:
        return [t for t in self.tests if isinstance(t, QATest)]
    
    @property
    def coding_tests(self) -> list[CodingTest]:
        return [t for t in self.tests if isinstance(t, CodingTest)]


@dataclass
class Result:
    """Result from executing a work unit."""
    
    score: float = 0.0  # 0.0 to 1.0
    cost: Cost = field(default_factory=Cost)
    duration_seconds: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    
    # For Q&A tests
    correct_answers: int = 0
    total_questions: int = 0
    
    # For coding tests
    deployment_score: float = 0.0
    test_score: float = 0.0
    static_analysis_score: float = 0.0
    rubric_score: float = 0.0
    
    @property
    def accuracy(self) -> float:
        """Calculate accuracy for Q&A tests."""
        if self.total_questions == 0:
            return 0.0
        return self.correct_answers / self.total_questions
    
    @property
    def is_success(self) -> bool:
        return self.error is None and self.score > 0


@dataclass
class WorkUnit:
    """A single unit of work: one test executed by one agent."""
    
    id: str
    test: Test
    agent: Agent
    status: WorkUnitStatus = WorkUnitStatus.PENDING
    result: Result | None = None
    
    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Execution context
    scratch_org: str | None = None
    work_dir: Path | None = None
    
    # Control
    priority: int = 0  # Higher = more urgent
    retry_count: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:12]
    
    def start(self) -> None:
        """Mark work unit as started."""
        self.status = WorkUnitStatus.RUNNING
        self.started_at = datetime.utcnow()
    
    def complete(self, result: Result) -> None:
        """Mark work unit as completed."""
        self.status = WorkUnitStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.result = result
    
    def fail(self, error: str) -> None:
        """Mark work unit as failed."""
        self.status = WorkUnitStatus.FAILED
        self.completed_at = datetime.utcnow()
        if self.result is None:
            self.result = Result()
        self.result.error = error
    
    def pause(self) -> None:
        """Pause the work unit."""
        if self.status == WorkUnitStatus.RUNNING:
            self.status = WorkUnitStatus.PAUSED
    
    def resume(self) -> None:
        """Resume a paused work unit."""
        if self.status == WorkUnitStatus.PAUSED:
            self.status = WorkUnitStatus.RUNNING
    
    def cancel(self) -> None:
        """Cancel the work unit."""
        if self.status in (WorkUnitStatus.PENDING, WorkUnitStatus.RUNNING, WorkUnitStatus.PAUSED):
            self.status = WorkUnitStatus.CANCELLED
            self.completed_at = datetime.utcnow()
    
    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        if self.started_at is None:
            return 0.0
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()
    
    @property
    def is_terminal(self) -> bool:
        """Check if work unit is in a terminal state."""
        return self.status in (
            WorkUnitStatus.COMPLETED,
            WorkUnitStatus.FAILED,
            WorkUnitStatus.CANCELLED,
            WorkUnitStatus.TIMEOUT,
        )
    
    def can_retry(self) -> bool:
        """Check if work unit can be retried."""
        return (
            self.status == WorkUnitStatus.FAILED
            and self.retry_count < self.max_retries
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "test_id": self.test.id,
            "test_type": self.test.type.value,
            "agent_id": self.agent.id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "score": self.result.score if self.result else None,
            "error": self.result.error if self.result else None,
            "scratch_org": self.scratch_org,
            "priority": self.priority,
            "retry_count": self.retry_count,
        }
