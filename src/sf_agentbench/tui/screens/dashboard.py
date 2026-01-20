"""Dashboard screen for SF-AgentBench TUI."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.screen import Screen
from textual.widgets import (
    Header,
    Footer,
    Static,
    Button,
    Label,
    Rule,
    Markdown,
)

from sf_agentbench.config import load_config
from sf_agentbench.harness import TaskLoader


class StatBox(Static):
    """A box displaying a statistic."""

    def __init__(self, label: str, value: str, style_class: str = "") -> None:
        super().__init__()
        self.label = label
        self.value = value
        self.style_class = style_class

    def compose(self) -> ComposeResult:
        yield Static(self.value, classes=f"stat-value {self.style_class}")
        yield Static(self.label, classes="stat-label")


class DashboardScreen(Screen):
    """Main dashboard screen."""

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main-content"):
            yield Static(
                "🚀 SF-AgentBench Dashboard",
                classes="title",
            )
            yield Static(
                "Benchmark AI Agents on Salesforce Development",
                classes="subtitle",
            )

            yield Rule()

            # Stats row
            with Horizontal(id="stats-row"):
                config = load_config()
                loader = TaskLoader(config.tasks_dir)
                tasks = loader.discover_tasks()

                tier_counts = {}
                for task in tasks:
                    tier = task.tier.value
                    tier_counts[tier] = tier_counts.get(tier, 0) + 1

                with Container(classes="stat-box"):
                    yield StatBox("Total Tasks", str(len(tasks)), "score-excellent")

                with Container(classes="stat-box"):
                    yield StatBox("Tier 1", str(tier_counts.get("tier-1", 0)), "score-good")

                with Container(classes="stat-box"):
                    yield StatBox("Tier 2", str(tier_counts.get("tier-2", 0)), "score-good")

                with Container(classes="stat-box"):
                    yield StatBox("Tier 3", str(tier_counts.get("tier-3", 0)), "score-fair")

                with Container(classes="stat-box"):
                    yield StatBox("Tier 4", str(tier_counts.get("tier-4", 0)), "score-poor")

            yield Rule()

            # Quick actions
            yield Static("⚡ Quick Actions", classes="title")

            with Horizontal():
                yield Button("Browse Tasks", id="btn-tasks", variant="primary")
                yield Button("Run Benchmark", id="btn-run", variant="success")
                yield Button("View Results", id="btn-results", variant="default")
                yield Button("Configuration", id="btn-config", variant="default")

            yield Rule()

            # Info panel
            with Container(classes="panel"):
                yield Markdown("""
## Getting Started

1. **Browse Tasks** - View available benchmark tasks by tier
2. **Run Benchmark** - Execute tasks with your configured AI agent
3. **View Results** - Analyze scores and performance metrics
4. **Configuration** - Adjust agent, evaluation weights, and settings

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `D` | Dashboard |
| `T` | Tasks |
| `R` | Run |
| `S` | Results |
| `C` | Config |
| `Q` | Quit |
| `?` | Help |

### Evaluation Layers

The benchmark evaluates solutions across 5 layers:

1. **Deployment** (20%) - Can the code deploy?
2. **Functional Tests** (40%) - Do Apex tests pass?
3. **Static Analysis** (10%) - Code quality via PMD
4. **Metadata Diff** (15%) - Configuration accuracy
5. **Rubric** (15%) - LLM-as-a-Judge evaluation
""")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "btn-tasks":
            self.app.switch_screen("tasks")
        elif button_id == "btn-run":
            self.app.switch_screen("run")
        elif button_id == "btn-results":
            self.app.switch_screen("results")
        elif button_id == "btn-config":
            self.app.switch_screen("config")
