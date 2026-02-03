"""Main TUI Application for SF-AgentBench."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer

from sf_agentbench.config import load_config, BenchmarkConfig
from sf_agentbench.tui.screens.dashboard import DashboardScreen
from sf_agentbench.tui.screens.tasks import TasksScreen
from sf_agentbench.tui.screens.run import RunScreen
from sf_agentbench.tui.screens.results import ResultsScreen
from sf_agentbench.tui.screens.config import ConfigScreen


class SFAgentBenchApp(App):
    """SF-AgentBench Terminal User Interface."""

    TITLE = "SF-AgentBench"
    SUB_TITLE = "AI Agent Benchmark for Salesforce Development"

    CSS = """
    Screen {
        background: $surface;
    }

    Header {
        background: #1a5f7a;
        color: #ffffff;
    }

    Footer {
        background: #1a5f7a;
    }

    .title {
        text-style: bold;
        color: #57c5b6;
    }

    .subtitle {
        color: #a0a0a0;
    }

    .success {
        color: #57c5b6;
    }

    .warning {
        color: #ffc107;
    }

    .error {
        color: #dc3545;
    }

    .muted {
        color: #6c757d;
    }

    .score-excellent {
        color: #28a745;
        text-style: bold;
    }

    .score-good {
        color: #57c5b6;
    }

    .score-fair {
        color: #ffc107;
    }

    .score-poor {
        color: #dc3545;
    }

    DataTable {
        height: auto;
        max-height: 100%;
    }

    DataTable > .datatable--header {
        background: #1a5f7a;
        color: #ffffff;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: #159895;
        color: #ffffff;
    }

    .panel {
        border: solid #1a5f7a;
        padding: 1;
        margin: 1;
    }

    .stat-box {
        border: round #57c5b6;
        padding: 1 2;
        margin: 0 1;
        min-width: 20;
        height: 5;
    }

    .stat-value {
        text-style: bold;
        text-align: center;
    }

    .stat-label {
        color: #a0a0a0;
        text-align: center;
    }

    ProgressBar {
        padding: 1;
    }

    ProgressBar > .bar--bar {
        color: #57c5b6;
    }

    ProgressBar > .bar--complete {
        color: #28a745;
    }

    Button {
        margin: 1;
    }

    Button.primary {
        background: #1a5f7a;
    }

    Button.primary:hover {
        background: #159895;
    }

    Button.success {
        background: #28a745;
    }

    Button.danger {
        background: #dc3545;
    }

    Input {
        margin: 1;
    }

    Input:focus {
        border: tall #57c5b6;
    }

    #sidebar {
        width: 30;
        background: $surface-darken-1;
        border-right: solid #1a5f7a;
        padding: 1;
    }

    #main-content {
        padding: 1;
    }

    .nav-item {
        padding: 1 2;
        margin: 0;
    }

    .nav-item:hover {
        background: #1a5f7a 30%;
    }

    .nav-item.-active {
        background: #1a5f7a;
        color: #ffffff;
    }

    RichLog {
        background: $surface-darken-2;
        border: solid #1a5f7a;
        padding: 1;
        height: 100%;
    }

    .markdown-viewer {
        padding: 1 2;
        background: $surface-darken-1;
        border: solid #1a5f7a;
    }
    """

    BINDINGS = [
        Binding("d", "switch_screen('dashboard')", "Dashboard", show=True),
        Binding("t", "switch_screen('tasks')", "Tasks", show=True),
        Binding("r", "switch_screen('run')", "Run", show=True),
        Binding("s", "switch_screen('results')", "Results", show=True),
        Binding("c", "switch_screen('config')", "Config", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("?", "help", "Help", show=True),
    ]

    SCREENS = {
        "dashboard": DashboardScreen,
        "tasks": TasksScreen,
        "run": RunScreen,
        "results": ResultsScreen,
        "config": ConfigScreen,
    }

    def __init__(self) -> None:
        super().__init__()
        self.config: BenchmarkConfig = load_config()

    def on_mount(self) -> None:
        """Mount the application."""
        self.push_screen("dashboard")

    def action_switch_screen(self, screen: str) -> None:
        """Switch to a different screen."""
        self.switch_screen(screen)

    def action_help(self) -> None:
        """Show help."""
        self.notify(
            "Use D/T/R/S/C to navigate, Q to quit",
            title="Keyboard Shortcuts",
        )
