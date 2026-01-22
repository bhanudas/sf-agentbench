"""Log and status rendering for the REPL.

Provides formatted output for logs, status bars, and progress indicators.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn, TimeRemainingColumn
from rich.table import Table
from rich.text import Text
from rich.live import Live

from sf_agentbench.events import LogEvent, LogLevel, StatusEvent, MetricsEvent


# Color scheme for different log levels
LOG_COLORS = {
    LogLevel.DEBUG: "dim",
    LogLevel.INFO: "white",
    LogLevel.WARN: "yellow",
    LogLevel.ERROR: "red bold",
}

# Status colors
STATUS_COLORS = {
    "pending": "dim",
    "running": "cyan",
    "paused": "yellow",
    "completed": "green",
    "failed": "red",
    "cancelled": "dim red",
    "timeout": "yellow",
}


@dataclass
class LogRenderer:
    """Renders log events with filtering and formatting."""
    
    max_lines: int = 50
    show_timestamp: bool = True
    show_source: bool = True
    min_level: LogLevel = LogLevel.INFO
    source_filter: str | None = None
    
    _lines: list[Text] = field(default_factory=list)
    
    def add(self, event: LogEvent) -> None:
        """Add a log event to the buffer."""
        # Apply filters
        if event.level.value < self.min_level.value:
            return
        
        if self.source_filter and self.source_filter.lower() not in event.source.lower():
            return
        
        # Format the line
        line = self._format_event(event)
        self._lines.append(line)
        
        # Trim to max lines
        if len(self._lines) > self.max_lines:
            self._lines = self._lines[-self.max_lines:]
    
    def _format_event(self, event: LogEvent) -> Text:
        """Format a log event as Rich Text."""
        text = Text()
        
        # Timestamp
        if self.show_timestamp:
            timestamp = event.timestamp.strftime("%H:%M:%S")
            text.append(f"[{timestamp}] ", style="dim")
        
        # Source
        if self.show_source and event.source:
            text.append(f"[{event.source}] ", style="cyan")
        
        # Level indicator for warnings and errors
        if event.level == LogLevel.WARN:
            text.append("⚠ ", style="yellow")
        elif event.level == LogLevel.ERROR:
            text.append("✗ ", style="red bold")
        elif event.level == LogLevel.INFO:
            # Check for success/failure indicators in message
            if "✓" in event.message or "complete" in event.message.lower():
                pass  # Keep as-is
        
        # Message
        style = LOG_COLORS.get(event.level, "white")
        text.append(event.message, style=style)
        
        return text
    
    def render(self) -> Group:
        """Render all log lines as a Rich Group."""
        if not self._lines:
            return Group(Text("  No logs yet...", style="dim"))
        
        return Group(*self._lines)
    
    def clear(self) -> None:
        """Clear all log lines."""
        self._lines.clear()
    
    def set_filter(
        self,
        source: str | None = None,
        level: LogLevel | None = None,
    ) -> None:
        """Update filters."""
        self.source_filter = source
        if level:
            self.min_level = level


@dataclass
class StatusBar:
    """Renders the status bar with progress and metrics."""
    
    total_work_units: int = 0
    completed_work_units: int = 0
    failed_work_units: int = 0
    running_work_units: int = 0
    
    workers_active: int = 0
    workers_total: int = 0
    
    total_cost_usd: float = 0.0
    
    started_at: datetime | None = None
    
    def update(self, event: MetricsEvent) -> None:
        """Update status from a metrics event."""
        self.total_work_units = event.total_work_units
        self.completed_work_units = event.completed_work_units
        self.failed_work_units = event.failed_work_units
        self.running_work_units = event.running_work_units
        self.workers_active = event.workers_active
        self.workers_total = event.workers_total
        self.total_cost_usd = event.total_cost_usd
    
    @property
    def progress(self) -> float:
        """Calculate progress as percentage."""
        if self.total_work_units == 0:
            return 0.0
        return self.completed_work_units / self.total_work_units
    
    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time."""
        if self.started_at is None:
            return 0.0
        return (datetime.utcnow() - self.started_at).total_seconds()
    
    @property
    def eta_seconds(self) -> float | None:
        """Estimate time remaining."""
        if self.completed_work_units == 0:
            return None
        if self.total_work_units == self.completed_work_units:
            return 0.0
        
        rate = self.completed_work_units / self.elapsed_seconds
        remaining = self.total_work_units - self.completed_work_units
        return remaining / rate if rate > 0 else None
    
    def render(self) -> Panel:
        """Render the status bar as a Rich Panel."""
        # Progress bar
        progress = int(self.progress * 20)
        bar = "█" * progress + "░" * (20 - progress)
        
        # ETA
        eta_str = ""
        if self.eta_seconds:
            minutes = int(self.eta_seconds // 60)
            seconds = int(self.eta_seconds % 60)
            eta_str = f"  ETA: {minutes}m {seconds}s"
        
        # Build status line
        text = Text()
        text.append("Progress: ")
        text.append(bar, style="cyan")
        text.append(f" {self.completed_work_units}/{self.total_work_units}")
        text.append(f" ({self.progress * 100:.0f}%)", style="dim")
        text.append(eta_str, style="dim")
        
        return Panel(text, border_style="dim")
    
    def render_header(self) -> Text:
        """Render the header bar."""
        text = Text()
        text.append("SF-AgentBench", style="bold magenta")
        text.append(" v0.2.0", style="dim")
        
        # Workers
        text.append("                    ")
        text.append("Workers: ", style="dim")
        text.append(f"{self.workers_active}/{self.workers_total}", style="cyan")
        
        # Cost
        text.append("  Cost: ", style="dim")
        text.append(f"${self.total_cost_usd:.4f}", style="yellow")
        
        return text


def render_work_unit_table(work_units: list[dict]) -> Table:
    """Render a table of work units."""
    table = Table(show_header=True, header_style="bold")
    
    table.add_column("ID", style="dim", width=12)
    table.add_column("Test", style="cyan")
    table.add_column("Agent", style="magenta")
    table.add_column("Status", width=10)
    table.add_column("Score", justify="right", width=8)
    table.add_column("Duration", justify="right", width=10)
    
    for wu in work_units:
        status = wu.get("status", "pending")
        status_style = STATUS_COLORS.get(status, "white")
        
        score = wu.get("score")
        score_str = f"{score:.2f}" if score is not None else "-"
        
        duration = wu.get("duration_seconds", 0)
        duration_str = f"{duration:.1f}s" if duration > 0 else "-"
        
        table.add_row(
            wu.get("id", "")[:12],
            wu.get("test_name", wu.get("test_id", ""))[:30],
            wu.get("agent_id", "")[:20],
            Text(status, style=status_style),
            score_str,
            duration_str,
        )
    
    return table


def render_cost_breakdown(by_model: dict[str, dict]) -> Table:
    """Render a cost breakdown table."""
    table = Table(show_header=True, header_style="bold")
    
    table.add_column("Model", style="magenta")
    table.add_column("Input Tokens", justify="right")
    table.add_column("Output Tokens", justify="right")
    table.add_column("Cost", justify="right", style="yellow")
    
    total_cost = 0.0
    
    for model, data in sorted(by_model.items(), key=lambda x: -x[1].get("estimated_usd", 0)):
        cost = data.get("estimated_usd", 0)
        total_cost += cost
        
        table.add_row(
            model,
            f"{data.get('input_tokens', 0):,}",
            f"{data.get('output_tokens', 0):,}",
            f"${cost:.4f}",
        )
    
    table.add_row(
        Text("Total", style="bold"),
        "",
        "",
        Text(f"${total_cost:.4f}", style="bold yellow"),
    )
    
    return table
