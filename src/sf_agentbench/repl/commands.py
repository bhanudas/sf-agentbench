"""Command parsing and handling for the REPL.

Parses user commands and dispatches to appropriate handlers.
"""

import shlex
from dataclasses import dataclass, field
from typing import Callable, Any
from enum import Enum

from rich.console import Console
from rich.table import Table
from rich.text import Text

from sf_agentbench.events import EventBus, CommandEvent, CommandType, LogLevel


class CommandName(str, Enum):
    """Available REPL commands."""
    
    STATUS = "status"
    LOGS = "logs"
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"
    RETRY = "retry"
    INJECT = "inject"
    COSTS = "costs"
    ORGS = "orgs"
    WORKERS = "workers"
    EXPORT = "export"
    RUBRIC = "rubric"
    JUDGE = "judge"
    JUDGE_LOGS = "judge-logs"
    JUDGE_REPLAY = "judge-replay"
    HELP = "help"
    QUIT = "quit"
    CLEAR = "clear"


@dataclass
class ParsedCommand:
    """A parsed command with arguments."""
    
    name: str
    args: list[str] = field(default_factory=list)
    options: dict[str, str | bool] = field(default_factory=dict)
    raw: str = ""
    
    @property
    def is_valid(self) -> bool:
        return len(self.name) > 0


class CommandParser:
    """Parses command strings into structured commands."""
    
    def parse(self, input_str: str) -> ParsedCommand:
        """Parse a command string.
        
        Args:
            input_str: Raw command string
        
        Returns:
            ParsedCommand with name, args, and options
        """
        input_str = input_str.strip()
        if not input_str:
            return ParsedCommand(name="", raw=input_str)
        
        try:
            parts = shlex.split(input_str)
        except ValueError:
            # Invalid quoting, fall back to simple split
            parts = input_str.split()
        
        if not parts:
            return ParsedCommand(name="", raw=input_str)
        
        name = parts[0].lower()
        args = []
        options = {}
        
        i = 1
        while i < len(parts):
            part = parts[i]
            
            if part.startswith("--"):
                # Long option
                key = part[2:]
                if "=" in key:
                    key, value = key.split("=", 1)
                    options[key] = value
                elif i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                    options[key] = parts[i + 1]
                    i += 1
                else:
                    options[key] = True
            elif part.startswith("-") and len(part) == 2:
                # Short option
                key = part[1]
                if i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                    options[key] = parts[i + 1]
                    i += 1
                else:
                    options[key] = True
            else:
                args.append(part)
            
            i += 1
        
        return ParsedCommand(name=name, args=args, options=options, raw=input_str)


@dataclass
class CommandContext:
    """Context for command handlers."""
    
    console: Console
    event_bus: EventBus
    pool: Any = None  # WorkerPool
    scheduler: Any = None  # Scheduler
    storage: Any = None  # Storage
    rubric_manager: Any = None  # RubricManager
    
    # Callbacks
    on_quit: Callable[[], None] | None = None
    on_clear: Callable[[], None] | None = None
    on_filter_logs: Callable[[str | None, LogLevel | None], None] | None = None


class CommandHandler:
    """Handles REPL commands."""
    
    def __init__(self, context: CommandContext):
        """Initialize the command handler.
        
        Args:
            context: Command context with dependencies
        """
        self.context = context
        self.console = context.console
        self.event_bus = context.event_bus
        
        # Command registry
        self._handlers: dict[str, Callable[[ParsedCommand], None]] = {
            "status": self._handle_status,
            "logs": self._handle_logs,
            "pause": self._handle_pause,
            "resume": self._handle_resume,
            "cancel": self._handle_cancel,
            "retry": self._handle_retry,
            "inject": self._handle_inject,
            "costs": self._handle_costs,
            "orgs": self._handle_orgs,
            "workers": self._handle_workers,
            "export": self._handle_export,
            "rubric": self._handle_rubric,
            "judge": self._handle_judge,
            "judge-logs": self._handle_judge_logs,
            "judge-replay": self._handle_judge_replay,
            "help": self._handle_help,
            "quit": self._handle_quit,
            "q": self._handle_quit,
            "exit": self._handle_quit,
            "clear": self._handle_clear,
            "?": self._handle_help,
        }
    
    def handle(self, cmd: ParsedCommand) -> bool:
        """Handle a parsed command.
        
        Args:
            cmd: The parsed command
        
        Returns:
            True if command was handled, False otherwise
        """
        if not cmd.is_valid:
            return False
        
        handler = self._handlers.get(cmd.name)
        if handler:
            try:
                handler(cmd)
                return True
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
                return True
        else:
            self.console.print(f"[yellow]Unknown command: {cmd.name}[/yellow]")
            self.console.print("[dim]Type 'help' for available commands[/dim]")
            return True
    
    def _handle_status(self, cmd: ParsedCommand) -> None:
        """Show current status."""
        if self.context.pool:
            status = self.context.pool.get_status()
            
            table = Table(title="Pool Status", show_header=False)
            table.add_column("Metric", style="cyan")
            table.add_column("Value")
            
            table.add_row("Workers", f"{status['workers_active']}/{status['workers_total']}")
            table.add_row("Queue", str(status['queue_size']))
            table.add_row("Submitted", str(status['total_submitted']))
            table.add_row("Completed", str(status['total_completed']))
            table.add_row("Failed", str(status['total_failed']))
            
            self.console.print(table)
        else:
            self.console.print("[yellow]No pool available[/yellow]")
    
    def _handle_logs(self, cmd: ParsedCommand) -> None:
        """Filter logs."""
        source = cmd.args[0] if cmd.args else None
        level = None
        
        if "level" in cmd.options:
            level_str = cmd.options["level"]
            if isinstance(level_str, str):
                try:
                    level = LogLevel(level_str.upper())
                except ValueError:
                    self.console.print(f"[yellow]Invalid level: {level_str}[/yellow]")
                    return
        
        if self.context.on_filter_logs:
            self.context.on_filter_logs(source, level)
            
            if source:
                self.console.print(f"[dim]Filtering logs to: {source}[/dim]")
            elif level:
                self.console.print(f"[dim]Filtering logs to level: {level.value}[/dim]")
            else:
                self.console.print("[dim]Log filter cleared[/dim]")
    
    def _handle_pause(self, cmd: ParsedCommand) -> None:
        """Pause work unit(s)."""
        work_unit_id = cmd.args[0] if cmd.args else None
        
        if work_unit_id:
            self.event_bus.send_command(CommandType.PAUSE, work_unit_id=work_unit_id)
            self.console.print(f"[yellow]Pausing: {work_unit_id}[/yellow]")
        elif self.context.pool:
            self.context.pool.pause_all()
            self.console.print("[yellow]Pausing all work units[/yellow]")
    
    def _handle_resume(self, cmd: ParsedCommand) -> None:
        """Resume work unit(s)."""
        work_unit_id = cmd.args[0] if cmd.args else None
        
        if work_unit_id:
            self.event_bus.send_command(CommandType.RESUME, work_unit_id=work_unit_id)
            self.console.print(f"[green]Resuming: {work_unit_id}[/green]")
        elif self.context.pool:
            self.context.pool.resume_all()
            self.console.print("[green]Resuming all work units[/green]")
    
    def _handle_cancel(self, cmd: ParsedCommand) -> None:
        """Cancel a work unit."""
        if not cmd.args:
            self.console.print("[yellow]Usage: cancel <work_unit_id>[/yellow]")
            return
        
        work_unit_id = cmd.args[0]
        self.event_bus.send_command(CommandType.CANCEL, work_unit_id=work_unit_id)
        self.console.print(f"[red]Cancelling: {work_unit_id}[/red]")
    
    def _handle_retry(self, cmd: ParsedCommand) -> None:
        """Retry a failed work unit."""
        if not cmd.args:
            self.console.print("[yellow]Usage: retry <work_unit_id>[/yellow]")
            return
        
        work_unit_id = cmd.args[0]
        self.event_bus.send_command(CommandType.RETRY, work_unit_id=work_unit_id)
        self.console.print(f"[cyan]Retrying: {work_unit_id}[/cyan]")
    
    def _handle_inject(self, cmd: ParsedCommand) -> None:
        """Inject a prompt into a running agent."""
        if len(cmd.args) < 2:
            self.console.print("[yellow]Usage: inject <work_unit_id> <prompt>[/yellow]")
            return
        
        work_unit_id = cmd.args[0]
        prompt = " ".join(cmd.args[1:])
        
        self.event_bus.send_command(
            CommandType.INJECT_PROMPT,
            work_unit_id=work_unit_id,
            prompt=prompt,
        )
        self.console.print(f"[cyan]Injecting prompt to: {work_unit_id}[/cyan]")
    
    def _handle_costs(self, cmd: ParsedCommand) -> None:
        """Show cost breakdown."""
        # This would query the storage for cost data
        self.console.print("[dim]Cost breakdown not yet implemented[/dim]")
    
    def _handle_orgs(self, cmd: ParsedCommand) -> None:
        """Show scratch org pool status."""
        if self.context.scheduler and hasattr(self.context.scheduler, 'scratch_org_pool'):
            pool = self.context.scheduler.scratch_org_pool
            if pool:
                status = pool.get_status()
                
                table = Table(title="Scratch Org Pool", show_header=True)
                table.add_column("Username", style="cyan")
                table.add_column("In Use")
                table.add_column("Work Unit")
                
                for org in status.get("orgs", []):
                    in_use = "✓" if org["in_use"] else ""
                    table.add_row(
                        org["username"],
                        in_use,
                        org.get("work_unit_id", "") or "",
                    )
                
                self.console.print(table)
                self.console.print(f"[dim]Available: {status['available']}/{status['total']}[/dim]")
            else:
                self.console.print("[yellow]No scratch org pool configured[/yellow]")
        else:
            self.console.print("[yellow]Scheduler not available[/yellow]")
    
    def _handle_workers(self, cmd: ParsedCommand) -> None:
        """Show worker pool status."""
        if self.context.pool:
            status = self.context.pool.get_status()
            
            table = Table(title="Worker Pool", show_header=False)
            table.add_column("Metric", style="cyan")
            table.add_column("Value")
            
            table.add_row("Total Workers", str(status['workers_total']))
            table.add_row("Active", str(status['workers_active']))
            table.add_row("Idle", str(status['workers_idle']))
            table.add_row("Queue Depth", str(status['queue_size']))
            
            self.console.print(table)
        else:
            self.console.print("[yellow]No pool available[/yellow]")
    
    def _handle_export(self, cmd: ParsedCommand) -> None:
        """Export results."""
        output_path = cmd.args[0] if cmd.args else "results_export.json"
        self.console.print(f"[dim]Exporting to: {output_path}[/dim]")
        # Implementation would go here
    
    def _handle_rubric(self, cmd: ParsedCommand) -> None:
        """Rubric management commands."""
        if not cmd.args:
            self.console.print("[yellow]Usage: rubric <list|show|edit> [name][/yellow]")
            return
        
        subcommand = cmd.args[0]
        
        if subcommand == "list":
            self.console.print("[dim]Available rubrics:[/dim]")
            self.console.print("  • salesforce_best_practices")
            self.console.print("  • security_audit")
            self.console.print("  • qa_accuracy")
        elif subcommand == "show":
            if len(cmd.args) < 2:
                self.console.print("[yellow]Usage: rubric show <name>[/yellow]")
            else:
                self.console.print(f"[dim]Rubric: {cmd.args[1]}[/dim]")
        elif subcommand == "edit":
            if len(cmd.args) < 2:
                self.console.print("[yellow]Usage: rubric edit <name>[/yellow]")
            else:
                self.console.print(f"[dim]Opening editor for: {cmd.args[1]}[/dim]")
    
    def _handle_judge(self, cmd: ParsedCommand) -> None:
        """Run judge on a work unit."""
        if not cmd.args:
            self.console.print("[yellow]Usage: judge <work_unit_id> [--compare][/yellow]")
            return
        
        work_unit_id = cmd.args[0]
        self.console.print(f"[dim]Running judge on: {work_unit_id}[/dim]")
    
    def _handle_judge_logs(self, cmd: ParsedCommand) -> None:
        """View judge logs."""
        work_unit_id = cmd.args[0] if cmd.args else None
        
        if work_unit_id:
            self.console.print(f"[dim]Judge logs for: {work_unit_id}[/dim]")
        else:
            self.console.print("[dim]Recent judge logs:[/dim]")
    
    def _handle_judge_replay(self, cmd: ParsedCommand) -> None:
        """Replay a judge prompt."""
        if not cmd.args:
            self.console.print("[yellow]Usage: judge-replay <log_id>[/yellow]")
            return
        
        log_id = cmd.args[0]
        self.console.print(f"[dim]Replaying judge prompt: {log_id}[/dim]")
    
    def _handle_help(self, cmd: ParsedCommand) -> None:
        """Show help."""
        table = Table(title="Available Commands", show_header=True)
        table.add_column("Command", style="cyan")
        table.add_column("Description")
        
        commands = [
            ("status", "Show current work unit status and resource usage"),
            ("logs [agent]", "Filter logs to specific agent"),
            ("logs --level <level>", "Filter to specific log level"),
            ("pause [id]", "Pause a specific work unit or all"),
            ("resume [id]", "Resume paused work units"),
            ("cancel <id>", "Cancel a running or pending work unit"),
            ("retry <id>", "Retry a failed work unit"),
            ("inject <id> <prompt>", "Send a prompt to a running agent"),
            ("costs", "Show running cost breakdown by model"),
            ("orgs", "Show scratch org pool status"),
            ("workers", "Show worker pool status and queue depth"),
            ("export [path]", "Export current results to file"),
            ("rubric list", "Show available rubrics"),
            ("rubric show <name>", "Display rubric criteria"),
            ("judge <id>", "Re-run judge on completed solution"),
            ("judge-logs [id]", "View judge logs"),
            ("clear", "Clear log display"),
            ("help", "Show this help"),
            ("quit", "Graceful shutdown"),
        ]
        
        for cmd_name, desc in commands:
            table.add_row(cmd_name, desc)
        
        self.console.print(table)
    
    def _handle_quit(self, cmd: ParsedCommand) -> None:
        """Quit the REPL."""
        if self.context.on_quit:
            self.context.on_quit()
        else:
            self.console.print("[yellow]Quitting...[/yellow]")
    
    def _handle_clear(self, cmd: ParsedCommand) -> None:
        """Clear the display."""
        if self.context.on_clear:
            self.context.on_clear()
        self.console.clear()
