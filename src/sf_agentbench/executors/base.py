"""Base executor protocol and interfaces.

Defines the common interface for all executors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from sf_agentbench.domain.models import WorkUnit, Result, Cost
from sf_agentbench.events import EventBus
from sf_agentbench.workers.base import WorkerContext


@dataclass
class ExecutorResult:
    """Result from executing a work unit."""
    
    success: bool = False
    score: float = 0.0
    cost: Cost = field(default_factory=Cost)
    duration_seconds: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    
    def to_result(self) -> Result:
        """Convert to a Result object."""
        return Result(
            score=self.score,
            cost=self.cost,
            duration_seconds=self.duration_seconds,
            details=self.details,
            error=self.error,
        )


class Executor(ABC):
    """Abstract base class for test executors.
    
    Executors handle the actual execution of tests against agents.
    They must handle pause/cancel signals from the worker context.
    """
    
    def __init__(
        self,
        event_bus: EventBus | None = None,
        verbose: bool = False,
    ):
        """Initialize the executor.
        
        Args:
            event_bus: Event bus for communication
            verbose: Enable verbose output
        """
        from sf_agentbench.events import get_event_bus
        self.event_bus = event_bus or get_event_bus()
        self.verbose = verbose
    
    @abstractmethod
    def execute(self, context: WorkerContext) -> ExecutorResult:
        """Execute a work unit.
        
        Args:
            context: The worker context with work unit and control signals
        
        Returns:
            ExecutorResult with execution outcome
        """
        pass
    
    def log_info(self, context: WorkerContext, message: str) -> None:
        """Log an info message."""
        context.log_info(message)
    
    def log_error(self, context: WorkerContext, message: str) -> None:
        """Log an error message."""
        context.log_error(message)
    
    def check_pause(self, context: WorkerContext) -> bool:
        """Check if execution should pause.
        
        Returns:
            True if paused (and now resumed), False otherwise
        """
        return context.check_pause()
    
    def check_cancel(self, context: WorkerContext) -> bool:
        """Check if execution should be cancelled.
        
        Returns:
            True if should cancel
        """
        return context.check_cancel()
