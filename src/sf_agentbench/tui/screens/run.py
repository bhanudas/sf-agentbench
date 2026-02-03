"""Run benchmark screen for SF-AgentBench TUI."""

import asyncio
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Header,
    Footer,
    Static,
    Button,
    Input,
    Label,
    ProgressBar,
    RichLog,
    Rule,
    Select,
)

from sf_agentbench.config import load_config
from sf_agentbench.harness import TaskLoader
from sf_agentbench.models import Task


class RunScreen(Screen):
    """Run benchmark screen with real-time progress."""

    BINDINGS = [
        ("escape", "app.switch_screen('dashboard')", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.loader = TaskLoader(self.config.tasks_dir)
        self.tasks = self.loader.discover_tasks()
        self.is_running = False
        self.current_task: Task | None = None

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main-content"):
            yield Static("🏃 Run Benchmark", classes="title")
            yield Static(
                "Execute benchmark tasks with your configured AI agent",
                classes="subtitle",
            )

            yield Rule()

            # Configuration section
            with Container(classes="panel"):
                yield Static("⚙️ Run Configuration", classes="title")

                with Horizontal():
                    with Vertical():
                        yield Label("Select Task:")
                        task_options = [(t.name, t.id) for t in self.tasks]
                        task_options.insert(0, ("All Tasks", "all"))
                        yield Select(task_options, id="task-select", value="all")

                    with Vertical():
                        yield Label("Agent ID:")
                        yield Input(
                            placeholder="e.g., claude-code",
                            id="agent-id",
                            value=self.config.agent.id,
                        )

                    with Vertical():
                        yield Label("DevHub Username:")
                        yield Input(
                            placeholder="admin@devhub.org",
                            id="devhub",
                            value=self.config.devhub_username or "",
                        )

                with Horizontal():
                    yield Button("▶ Start Benchmark", id="btn-start", variant="success")
                    yield Button("⏹ Stop", id="btn-stop", variant="danger")
                    yield Button("◀ Back", id="btn-back", variant="default")

            yield Rule()

            # Progress section
            with Container(classes="panel"):
                yield Static("📊 Progress", classes="title")

                with Horizontal(id="progress-stats"):
                    with Container(classes="stat-box"):
                        yield Static("0", id="stat-completed", classes="stat-value")
                        yield Static("Completed", classes="stat-label")

                    with Container(classes="stat-box"):
                        yield Static("0", id="stat-failed", classes="stat-value")
                        yield Static("Failed", classes="stat-label")

                    with Container(classes="stat-box"):
                        yield Static("-", id="stat-current", classes="stat-value")
                        yield Static("Current", classes="stat-label")

                    with Container(classes="stat-box"):
                        yield Static("-", id="stat-score", classes="stat-value score-good")
                        yield Static("Avg Score", classes="stat-label")

                yield ProgressBar(id="run-progress", total=100, show_eta=True)
                yield Static("Ready to start", id="status-text", classes="muted")

            yield Rule()

            # Log output
            yield Static("📝 Execution Log", classes="title")
            yield RichLog(id="run-log", highlight=True, markup=True)

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-back":
            self.app.switch_screen("dashboard")
        elif event.button.id == "btn-start":
            self._start_benchmark()
        elif event.button.id == "btn-stop":
            self._stop_benchmark()

    def _start_benchmark(self) -> None:
        """Start the benchmark run."""
        if self.is_running:
            self.notify("Benchmark already running", severity="warning")
            return

        self.is_running = True

        # Get configuration from inputs
        task_select = self.query_one("#task-select", Select)
        agent_input = self.query_one("#agent-id", Input)
        devhub_input = self.query_one("#devhub", Input)

        selected_task_id = task_select.value
        agent_id = agent_input.value or "unknown"
        devhub = devhub_input.value or None

        log = self.query_one("#run-log", RichLog)
        log.clear()
        log.write("[bold blue]═══ SF-AgentBench Run Started ═══[/]")
        log.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log.write(f"Agent: {agent_id}")
        log.write(f"DevHub: {devhub or 'default'}")
        log.write("")

        # Determine tasks to run
        if selected_task_id == "all":
            tasks_to_run = self.tasks
            log.write(f"[cyan]Running all {len(tasks_to_run)} tasks[/]")
        else:
            task = next((t for t in self.tasks if t.id == selected_task_id), None)
            if task:
                tasks_to_run = [task]
                log.write(f"[cyan]Running task: {task.name}[/]")
            else:
                log.write("[red]Task not found![/]")
                self.is_running = False
                return

        # Update progress
        progress = self.query_one("#run-progress", ProgressBar)
        progress.update(total=len(tasks_to_run))

        status = self.query_one("#status-text", Static)
        status.update("Initializing...")

        # Start async run
        self.run_worker(self._run_benchmark_async(tasks_to_run, agent_id, devhub))

    async def _run_benchmark_async(
        self,
        tasks: list[Task],
        agent_id: str,
        devhub: str | None,
    ) -> None:
        """Run benchmark asynchronously."""
        log = self.query_one("#run-log", RichLog)
        progress = self.query_one("#run-progress", ProgressBar)
        status = self.query_one("#status-text", Static)

        completed = 0
        failed = 0
        total_score = 0.0

        for i, task in enumerate(tasks):
            if not self.is_running:
                log.write("[yellow]Benchmark stopped by user[/]")
                break

            log.write("")
            log.write(f"[bold cyan]━━━ Task {i+1}/{len(tasks)}: {task.name} ━━━[/]")

            # Update current task stat
            current_stat = self.query_one("#stat-current", Static)
            current_stat.update(task.id[:12])

            status.update(f"Running: {task.name}")

            try:
                # Simulate task phases (in real impl, this calls the harness)
                phases = [
                    ("Creating Scratch Org", 2),
                    ("Deploying metadata", 1),
                    ("Running agent", 3),
                    ("Evaluating results", 2),
                    ("Cleanup", 1),
                ]

                for phase_name, duration in phases:
                    if not self.is_running:
                        break
                    log.write(f"  [dim]→ {phase_name}...[/]")
                    await asyncio.sleep(duration * 0.1)  # Simulated delay

                # Simulate a score (in real impl, comes from evaluation)
                import random
                score = random.uniform(0.6, 1.0)
                total_score += score
                completed += 1

                score_class = (
                    "green" if score >= 0.8 else
                    "yellow" if score >= 0.6 else
                    "red"
                )
                log.write(f"  [bold {score_class}]✓ Score: {score:.2f}[/]")

            except Exception as e:
                failed += 1
                log.write(f"  [bold red]✗ Error: {e}[/]")

            # Update progress
            progress.advance(1)

            # Update stats
            self.query_one("#stat-completed", Static).update(str(completed))
            self.query_one("#stat-failed", Static).update(str(failed))

            if completed > 0:
                avg_score = total_score / completed
                score_stat = self.query_one("#stat-score", Static)
                score_stat.update(f"{avg_score:.2f}")

        # Benchmark complete
        self.is_running = False
        log.write("")
        log.write("[bold blue]═══ Benchmark Complete ═══[/]")
        log.write(f"Completed: {completed}, Failed: {failed}")
        if completed > 0:
            log.write(f"Average Score: {total_score / completed:.2f}")

        status.update("Complete!")
        self.notify(f"Benchmark complete! {completed} tasks, avg score: {total_score/max(completed,1):.2f}")

    def _stop_benchmark(self) -> None:
        """Stop the running benchmark."""
        if self.is_running:
            self.is_running = False
            log = self.query_one("#run-log", RichLog)
            log.write("[yellow]Stopping benchmark...[/]")
            self.query_one("#status-text", Static).update("Stopping...")
