"""Event types for the event bus system.

Defines all event types used for communication between workers and REPL.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class LogLevel(str, Enum):
    """Log severity levels."""
    
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class CommandType(str, Enum):
    """Types of commands that can be sent to workers."""
    
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"
    RETRY = "retry"
    INJECT_PROMPT = "inject_prompt"
    STATUS = "status"
    SHUTDOWN = "shutdown"


@dataclass
class Event:
    """Base class for all events."""
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = ""
    
    def __post_init__(self):
        if not self.event_id:
            import uuid
            self.event_id = str(uuid.uuid4())[:8]


@dataclass
class LogEvent(Event):
    """A log message from a worker or agent."""
    
    level: LogLevel = LogLevel.INFO
    source: str = ""  # agent id or worker id
    message: str = ""
    work_unit_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    
    def format(self, show_timestamp: bool = True) -> str:
        """Format the log event for display."""
        parts = []
        if show_timestamp:
            parts.append(f"[{self.timestamp.strftime('%H:%M:%S')}]")
        if self.source:
            parts.append(f"[{self.source}]")
        parts.append(self.message)
        return " ".join(parts)
    
    @classmethod
    def debug(cls, source: str, message: str, **kwargs) -> "LogEvent":
        return cls(level=LogLevel.DEBUG, source=source, message=message, **kwargs)
    
    @classmethod
    def info(cls, source: str, message: str, **kwargs) -> "LogEvent":
        return cls(level=LogLevel.INFO, source=source, message=message, **kwargs)
    
    @classmethod
    def warn(cls, source: str, message: str, **kwargs) -> "LogEvent":
        return cls(level=LogLevel.WARN, source=source, message=message, **kwargs)
    
    @classmethod
    def error(cls, source: str, message: str, **kwargs) -> "LogEvent":
        return cls(level=LogLevel.ERROR, source=source, message=message, **kwargs)


@dataclass
class StatusEvent(Event):
    """Status update for a work unit."""
    
    work_unit_id: str = ""
    status: str = ""  # WorkUnitStatus value
    progress: float | None = None  # 0.0 to 1.0
    metrics: dict[str, Any] = field(default_factory=dict)
    agent_id: str | None = None
    test_id: str | None = None
    
    @property
    def progress_percent(self) -> float:
        if self.progress is None:
            return 0.0
        return self.progress * 100


@dataclass
class CommandEvent(Event):
    """A command sent from REPL to workers."""
    
    command: CommandType = CommandType.STATUS
    args: list[str] = field(default_factory=list)
    work_unit_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def pause(cls, work_unit_id: str | None = None) -> "CommandEvent":
        return cls(command=CommandType.PAUSE, work_unit_id=work_unit_id)
    
    @classmethod
    def resume(cls, work_unit_id: str | None = None) -> "CommandEvent":
        return cls(command=CommandType.RESUME, work_unit_id=work_unit_id)
    
    @classmethod
    def cancel(cls, work_unit_id: str) -> "CommandEvent":
        return cls(command=CommandType.CANCEL, work_unit_id=work_unit_id)
    
    @classmethod
    def retry(cls, work_unit_id: str) -> "CommandEvent":
        return cls(command=CommandType.RETRY, work_unit_id=work_unit_id)
    
    @classmethod
    def inject_prompt(cls, work_unit_id: str, prompt: str) -> "CommandEvent":
        return cls(
            command=CommandType.INJECT_PROMPT,
            work_unit_id=work_unit_id,
            payload={"prompt": prompt},
        )
    
    @classmethod
    def shutdown(cls) -> "CommandEvent":
        return cls(command=CommandType.SHUTDOWN)


@dataclass
class MetricsEvent(Event):
    """Metrics update event."""
    
    total_work_units: int = 0
    completed_work_units: int = 0
    failed_work_units: int = 0
    running_work_units: int = 0
    pending_work_units: int = 0
    
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    
    workers_active: int = 0
    workers_total: int = 0
    
    scratch_orgs_available: int = 0
    scratch_orgs_in_use: int = 0
    
    @property
    def progress(self) -> float:
        if self.total_work_units == 0:
            return 0.0
        return self.completed_work_units / self.total_work_units


@dataclass
class ProgressEvent(Event):
    """Progress update for a specific operation."""
    
    operation: str = ""  # e.g., "qa_test", "coding_deploy"
    work_unit_id: str | None = None
    current: int = 0
    total: int = 0
    message: str = ""
    
    @property
    def progress(self) -> float:
        if self.total == 0:
            return 0.0
        return self.current / self.total
    
    @property
    def progress_percent(self) -> float:
        return self.progress * 100
