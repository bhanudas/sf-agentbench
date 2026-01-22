"""Main REPL console with Rich Live display.

Provides a Claude Code-style interface where logs scroll above while
the user can always type commands below.

Now integrates with the shared event store to monitor activity from
other processes (like CLI commands).
"""

import sys
import threading
import queue
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Any

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from sf_agentbench.events import (
    EventBus,
    LogEvent,
    StatusEvent,
    MetricsEvent,
    CommandEvent,
    LogLevel,
    get_event_bus,
    get_shared_store,
    SharedEventStore,
)
from sf_agentbench.repl.commands import CommandParser, CommandHandler, CommandContext, ParsedCommand
from sf_agentbench.repl.renderer import LogRenderer, StatusBar


class REPLConsole:
    """Interactive REPL console for monitoring and controlling benchmarks.
    
    Features:
    - Real-time log streaming (from local and remote processes)
    - Status bar with progress
    - Command input always available
    - Log filtering
    - Pause/resume/cancel support
    - Cross-process monitoring via shared event store
    """
    
    def __init__(
        self,
        event_bus: EventBus | None = None,
        console: Console | None = None,
        pool: Any = None,
        scheduler: Any = None,
        storage: Any = None,
        poll_shared_events: bool = True,
    ):
        """Initialize the REPL console.
        
        Args:
            event_bus: Event bus for communication
            console: Rich console instance
            pool: Worker pool instance
            scheduler: Scheduler instance
            storage: Storage instance
            poll_shared_events: Whether to poll the shared event store
        """
        self.event_bus = event_bus or get_event_bus()
        self.console = console or Console()
        self.pool = pool
        self.scheduler = scheduler
        self.storage = storage
        self.poll_shared_events = poll_shared_events
        
        # Components
        self.log_renderer = LogRenderer()
        self.status_bar = StatusBar()
        self.command_parser = CommandParser()
        
        # Shared event store for cross-process monitoring
        self._shared_store: SharedEventStore | None = None
        self._last_event_id = 0
        self._poll_thread: threading.Thread | None = None
        
        # State
        self._running = False
        self._should_quit = threading.Event()
        self._command_queue: queue.Queue[str] = queue.Queue()
        self._input_thread: threading.Thread | None = None
        
        # Active work units being tracked
        self._active_work_units: dict[str, dict] = {}
        
        # Setup command handler
        self.command_context = CommandContext(
            console=self.console,
            event_bus=self.event_bus,
            pool=pool,
            scheduler=scheduler,
            storage=storage,
            on_quit=self._handle_quit,
            on_clear=self._handle_clear,
            on_filter_logs=self._handle_filter_logs,
        )
        self.command_handler = CommandHandler(self.command_context)
        
        # Subscribe to events
        self.event_bus.subscribe(LogEvent, self._on_log_event)
        self.event_bus.subscribe(StatusEvent, self._on_status_event)
        self.event_bus.subscribe(MetricsEvent, self._on_metrics_event)
    
    def start(self) -> None:
        """Start the REPL console."""
        if self._running:
            return
        
        self._running = True
        self._should_quit.clear()
        self.status_bar.started_at = datetime.utcnow()
        
        # Start event bus async processing
        self.event_bus.start_async()
        
        # Start polling shared event store (for cross-process monitoring)
        if self.poll_shared_events:
            self._start_shared_poll()
        
        # Print welcome message
        self._print_welcome()
        
        # Run the main loop
        self._run_loop()
    
    def stop(self) -> None:
        """Stop the REPL console."""
        self._running = False
        self._should_quit.set()
        
        # Stop polling thread
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=2.0)
        
        self.event_bus.stop_async()
    
    def _start_shared_poll(self) -> None:
        """Start polling the shared event store for cross-process events."""
        try:
            self._shared_store = get_shared_store()
            # Start from the latest event to avoid seeing old events
            self._last_event_id = self._shared_store.get_latest_id()
            
            self._poll_thread = threading.Thread(
                target=self._poll_shared_events,
                daemon=True,
                name="shared-event-poller",
            )
            self._poll_thread.start()
            
            # Log that we're monitoring
            self.event_bus.log_info(
                "repl",
                "Cross-process monitoring enabled - will show activity from CLI commands"
            )
        except Exception as e:
            self.event_bus.log_warn("repl", f"Could not enable cross-process monitoring: {e}")
    
    def _poll_shared_events(self) -> None:
        """Background thread that polls shared event store."""
        poll_interval = 0.5  # Check every 500ms
        
        while self._running and not self._should_quit.is_set():
            try:
                if self._shared_store:
                    events = self._shared_store.get_events_since(
                        since_id=self._last_event_id,
                        limit=50,
                    )
                    
                    for event_id, event in events:
                        self._last_event_id = event_id
                        # Forward to local event bus
                        self.event_bus.publish(event)
                        
                        # Track active work units
                        if isinstance(event, StatusEvent):
                            self._update_work_unit_tracking(event)
            except Exception as e:
                # Silently ignore poll errors to avoid spamming logs
                pass
            
            time.sleep(poll_interval)
    
    def _update_work_unit_tracking(self, event: StatusEvent) -> None:
        """Update tracking of active work units from status events."""
        work_unit_id = event.work_unit_id
        if not work_unit_id:
            return
        
        if event.status in ("completed", "failed", "cancelled"):
            # Remove from active tracking
            self._active_work_units.pop(work_unit_id, None)
            
            # Update status bar
            self.status_bar.completed_work_units += 1
            if event.status == "failed":
                self.status_bar.failed_work_units += 1
            
            if event.metrics:
                cost = event.metrics.get("cost_usd", 0)
                if cost:
                    self.status_bar.total_cost_usd += cost
        else:
            # Add/update active work unit
            if work_unit_id not in self._active_work_units:
                self.status_bar.total_work_units += 1
            
            self._active_work_units[work_unit_id] = {
                "status": event.status,
                "progress": event.progress,
                "metrics": event.metrics or {},
            }
        
        # Update status bar with active count
        self.status_bar.workers_active = len(self._active_work_units)
        self.status_bar.running_work_units = len(self._active_work_units)
    
    def _run_loop(self) -> None:
        """Main REPL loop."""
        try:
            while self._running and not self._should_quit.is_set():
                # Render current state
                self._render()
                
                # Get command input
                try:
                    command = Prompt.ask(
                        "[bold cyan]>[/bold cyan]",
                        console=self.console,
                    )
                    
                    if command:
                        parsed = self.command_parser.parse(command)
                        self.command_handler.handle(parsed)
                    
                except KeyboardInterrupt:
                    self.console.print("\n[yellow]Use 'quit' to exit[/yellow]")
                except EOFError:
                    break
                    
        except Exception as e:
            self.console.print(f"[red]REPL error: {e}[/red]")
        finally:
            self.stop()
    
    def _render(self) -> None:
        """Render the current state to console."""
        # Clear screen for fresh render
        # self.console.clear()
        
        # Render header
        header = self.status_bar.render_header()
        self.console.print(Panel(header, border_style="magenta"))
        
        # Render logs
        logs = self.log_renderer.render()
        log_panel = Panel(
            logs,
            title="Logs",
            border_style="dim",
            height=min(20, self.log_renderer.max_lines + 2),
        )
        self.console.print(log_panel)
        
        # Render progress
        progress = self.status_bar.render()
        self.console.print(progress)
    
    def _print_welcome(self) -> None:
        """Print welcome message."""
        self.console.print()
        self.console.print("[bold magenta]SF-AgentBench Interactive Console[/bold magenta]")
        self.console.print("[dim]Type 'help' for available commands, 'quit' to exit[/dim]")
        self.console.print()
    
    def _on_log_event(self, event: LogEvent) -> None:
        """Handle log events."""
        self.log_renderer.add(event)
    
    def _on_status_event(self, event: StatusEvent) -> None:
        """Handle status events."""
        # Update relevant status bar fields
        pass
    
    def _on_metrics_event(self, event: MetricsEvent) -> None:
        """Handle metrics events."""
        self.status_bar.update(event)
    
    def _handle_quit(self) -> None:
        """Handle quit command."""
        self.console.print("\n[yellow]Shutting down...[/yellow]")
        
        # Cancel pending work
        if self.pool:
            cancelled = self.pool.cancel_all()
            if cancelled > 0:
                self.console.print(f"[dim]Cancelled {cancelled} pending work units[/dim]")
        
        self._should_quit.set()
    
    def _handle_clear(self) -> None:
        """Handle clear command."""
        self.log_renderer.clear()
    
    def _handle_filter_logs(self, source: str | None, level: LogLevel | None) -> None:
        """Handle log filter change."""
        self.log_renderer.set_filter(source=source, level=level)


class SimplifiedREPL:
    """A simpler REPL for non-interactive mode.
    
    Just processes commands without the fancy live display.
    """
    
    def __init__(
        self,
        event_bus: EventBus | None = None,
        console: Console | None = None,
    ):
        self.event_bus = event_bus or get_event_bus()
        self.console = console or Console()
        
        self.command_parser = CommandParser()
        self.command_context = CommandContext(
            console=self.console,
            event_bus=self.event_bus,
        )
        self.command_handler = CommandHandler(self.command_context)
        
        self._running = False
    
    def run_command(self, command: str) -> None:
        """Run a single command."""
        parsed = self.command_parser.parse(command)
        self.command_handler.handle(parsed)
    
    def start(self) -> None:
        """Start simple command loop."""
        self._running = True
        
        self.console.print("[bold]SF-AgentBench[/bold]")
        self.console.print("[dim]Type 'help' for commands, 'quit' to exit[/dim]")
        
        while self._running:
            try:
                command = input("> ").strip()
                if command:
                    if command.lower() in ("quit", "exit", "q"):
                        break
                    self.run_command(command)
            except KeyboardInterrupt:
                print("\nUse 'quit' to exit")
            except EOFError:
                break
        
        self._running = False
