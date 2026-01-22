"""SF-AgentBench: A benchmarking framework for AI agents on Salesforce development."""

__version__ = "0.2.0"

from sf_agentbench.config import BenchmarkConfig
from sf_agentbench.harness import BenchmarkHarness
from sf_agentbench.models import Task, TaskResult, EvaluationResult

# New architecture components
from sf_agentbench.domain import (
    Benchmark,
    Test,
    TestType,
    Agent,
    WorkUnit,
    WorkUnitStatus,
    Result,
    Cost,
)
from sf_agentbench.events import EventBus, get_event_bus
from sf_agentbench.workers import WorkerPool, Scheduler

__all__ = [
    "__version__",
    # Legacy
    "BenchmarkConfig",
    "BenchmarkHarness",
    "Task",
    "TaskResult",
    "EvaluationResult",
    # New architecture
    "Benchmark",
    "Test",
    "TestType",
    "Agent",
    "WorkUnit",
    "WorkUnitStatus",
    "Result",
    "Cost",
    "EventBus",
    "get_event_bus",
    "WorkerPool",
    "Scheduler",
]
