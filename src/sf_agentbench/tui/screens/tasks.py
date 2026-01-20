"""Tasks browser screen for SF-AgentBench TUI."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Header,
    Footer,
    Static,
    Button,
    DataTable,
    Markdown,
    Rule,
    TabbedContent,
    TabPane,
)

from sf_agentbench.config import load_config
from sf_agentbench.harness import TaskLoader
from sf_agentbench.models import Task


class TasksScreen(Screen):
    """Tasks browser screen."""

    BINDINGS = [
        ("escape", "app.switch_screen('dashboard')", "Back"),
        ("enter", "select_task", "Select"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.loader = TaskLoader(self.config.tasks_dir)
        self.tasks = self.loader.discover_tasks()
        self.selected_task: Task | None = None

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main-content"):
            yield Static("📋 Benchmark Tasks", classes="title")
            yield Static(
                f"Found {len(self.tasks)} tasks across all tiers",
                classes="subtitle",
            )

            yield Rule()

            with Horizontal():
                # Tasks table
                with Vertical(id="tasks-list"):
                    yield DataTable(id="tasks-table")

                # Task details panel
                with Vertical(id="task-details", classes="panel"):
                    yield Static("Select a task to view details", id="task-info")

            yield Rule()

            with Horizontal():
                yield Button("◀ Back", id="btn-back", variant="default")
                yield Button("▶ Run Selected Task", id="btn-run-task", variant="success")

        yield Footer()

    def on_mount(self) -> None:
        """Populate the tasks table."""
        table = self.query_one("#tasks-table", DataTable)
        table.cursor_type = "row"

        table.add_columns(
            "ID",
            "Name",
            "Tier",
            "Categories",
            "Time",
        )

        for task in self.tasks:
            # Handle both enum and string categories
            cat_list = [c.value if hasattr(c, 'value') else str(c) for c in task.categories[:2]]
            categories = ", ".join(cat_list)
            if len(task.categories) > 2:
                categories += "..."

            tier_value = task.tier.value if hasattr(task.tier, 'value') else str(task.tier)
            tier_display = {
                "tier-1": "🟢 Tier 1",
                "tier-2": "🟡 Tier 2",
                "tier-3": "🟠 Tier 3",
                "tier-4": "🔴 Tier 4",
            }.get(tier_value, tier_value)

            table.add_row(
                task.id,
                task.name,
                tier_display,
                categories or "-",
                f"{task.time_limit_minutes}m",
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle task selection."""
        table = self.query_one("#tasks-table", DataTable)
        row_key = event.row_key

        if row_key is not None:
            row_index = table.get_row_index(row_key)
            if 0 <= row_index < len(self.tasks):
                self.selected_task = self.tasks[row_index]
                self._update_task_details()

    def _update_task_details(self) -> None:
        """Update the task details panel."""
        if not self.selected_task:
            return

        task = self.selected_task
        readme = self.loader.get_task_readme(task)

        cat_list = [c.value if hasattr(c, 'value') else str(c) for c in task.categories]
        categories = ", ".join(f"`{c}`" for c in cat_list)

        tier_value = task.tier.value if hasattr(task.tier, 'value') else str(task.tier)

        details = f"""## {task.name}

**ID:** `{task.id}`

**Tier:** {tier_value}

**Time Limit:** {task.time_limit_minutes} minutes

**Categories:** {categories or "None"}

---

{readme}
"""

        # Update the details container
        details_container = self.query_one("#task-details")
        details_container.remove_children()
        details_container.mount(Markdown(details, classes="markdown-viewer"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-back":
            self.app.switch_screen("dashboard")
        elif event.button.id == "btn-run-task":
            if self.selected_task:
                # Store selected task and switch to run screen
                self.app.selected_task = self.selected_task
                self.app.switch_screen("run")
            else:
                self.notify("Please select a task first", severity="warning")

    def action_select_task(self) -> None:
        """Select the current task."""
        if self.selected_task:
            self.app.selected_task = self.selected_task
            self.app.switch_screen("run")
