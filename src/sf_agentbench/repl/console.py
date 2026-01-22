"""Main REPL console with Rich Live display.

Provides a Claude Code-style interface where logs scroll above while
the user can always type commands below.
"""

import sys
import threading
import queue
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
)
from sf_agentbench.repl.commands import CommandParser, CommandHandler, CommandContext, ParsedCommand
from sf_agentbench.repl.renderer import LogRenderer, StatusBar


class REPLConsole:
    """Interactive REPL console for monitoring and controlling benchmarks.
    
    Features:
    - Real-time log streaming
    - Status bar with progress
    - Command input always available
    - Log filtering
    - Pause/resume/cancel support
    """
    
    def __init__(
        self,
        event_bus: EventBus | None = None,
        console: Console | None = None,
        pool: Any = None,
        scheduler: Any = None,
        storage: Any = None,
    ):
        """Initialize the REPL console.
        
        Args:
            event_bus: Event bus for communication
            console: Rich console instance
            pool: Worker pool instance
            scheduler: Scheduler instance
            storage: Storage instance
        """
        self.event_bus = event_bus or get_event_bus()
        self.console = console or Console()
        self.pool = pool
        self.scheduler = scheduler
        self.storage = storage
        
        # Components
        self.log_renderer = LogRenderer()
        self.status_bar = StatusBar()
        self.command_parser = CommandParser()
        
        # State
        self._running = False
        self._should_quit = threading.Event()
        self._command_queue: queue.Queue[str] = queue.Queue()
        self._input_thread: threading.Thread | None = None
        
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
        
        # Print welcome message
        self._print_welcome()
        
        # Run the main loop
        self._run_loop()
    
    def stop(self) -> None:
        """Stop the REPL console."""
        self._running = False
        self._should_quit.set()
        self.event_bus.stop_async()
    
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
