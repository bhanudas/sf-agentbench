"""SF-AgentBench: A benchmarking framework for AI agents on Salesforce development."""

__version__ = "0.1.0"

from sf_agentbench.config import BenchmarkConfig
from sf_agentbench.harness import BenchmarkHarness
from sf_agentbench.models import Task, TaskResult, EvaluationResult

__all__ = [
    "__version__",
    "BenchmarkConfig",
    "BenchmarkHarness",
    "Task",
    "TaskResult",
    "EvaluationResult",
]
