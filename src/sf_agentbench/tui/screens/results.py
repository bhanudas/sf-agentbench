"""Results viewer screen for SF-AgentBench TUI."""

import json
from pathlib import Path

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
    Sparkline,
)

from sf_agentbench.config import load_config
from sf_agentbench.storage import ResultsStore, RunRecord


class ResultsScreen(Screen):
    """Results viewer screen."""

    BINDINGS = [
        ("escape", "app.switch_screen('dashboard')", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.store = ResultsStore(self.config.results_dir)
        self.runs: list[RunRecord] = []

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main-content"):
            yield Static("📊 Benchmark Results", classes="title")
            yield Static(
                "View and analyze benchmark run results",
                classes="subtitle",
            )

            yield Rule()

            # Summary stats
            with Horizontal(id="results-stats"):
                with Container(classes="stat-box"):
                    yield Static("0", id="stat-total-runs", classes="stat-value")
                    yield Static("Total Runs", classes="stat-label")

                with Container(classes="stat-box"):
                    yield Static("-", id="stat-best-score", classes="stat-value score-excellent")
                    yield Static("Best Score", classes="stat-label")

                with Container(classes="stat-box"):
                    yield Static("-", id="stat-avg-score", classes="stat-value score-good")
                    yield Static("Avg Score", classes="stat-label")

                with Container(classes="stat-box"):
                    yield Static("-", id="stat-last-run", classes="stat-value")
                    yield Static("Last Run", classes="stat-label")

            yield Rule()

            # Results table
            yield Static("📋 Run History", classes="title")
            yield DataTable(id="results-table")

            yield Rule()

            # Score breakdown
            with Horizontal():
                with Vertical(classes="panel"):
                    yield Static("📈 Score Breakdown", classes="title")
                    yield Static(id="score-breakdown")

                with Vertical(classes="panel"):
                    yield Static("🎯 Layer Analysis", classes="title")
                    yield Static(id="layer-analysis")

            yield Rule()

            with Horizontal():
                yield Button("🔄 Refresh", id="btn-refresh", variant="primary")
                yield Button("📤 Export CSV", id="btn-export", variant="default")
                yield Button("◀ Back", id="btn-back", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Load and display results."""
        self._load_results()
        self._populate_table()
        self._update_stats()

    def _load_results(self) -> None:
        """Load results from database."""
        try:
            self.runs = self.store.list_runs(limit=100)
        except Exception:
            self.runs = []

    def _populate_table(self) -> None:
        """Populate the results table."""
        table = self.query_one("#results-table", DataTable)
        table.cursor_type = "row"
        table.clear()

        table.add_columns(
            "Run ID",
            "Task",
            "Agent",
            "Date",
            "Deploy",
            "Tests",
            "PMD",
            "Meta",
            "Rubric",
            "Final",
            "Status",
        )

        for run in self.runs:
            date_str = run.started_at.strftime("%Y-%m-%d") if run.started_at else "-"
            status_icon = {
                "completed": "✅",
                "failed": "❌",
                "running": "🔄",
                "pending": "⏳",
            }.get(run.status, "❓")

            table.add_row(
                run.run_id[:8],
                run.task_id[:15],
                run.agent_id[:10],
                date_str,
                self._format_score(run.deployment_score),
                self._format_score(run.test_score),
                self._format_score(run.static_analysis_score),
                self._format_score(run.metadata_score),
                self._format_score(run.rubric_score),
                self._format_score(run.final_score),
                status_icon,
            )

    def _format_score(self, score: float) -> str:
        """Format a score with color indicator."""
        if score >= 0.8:
            return f"🟢 {score:.2f}"
        elif score >= 0.6:
            return f"🟡 {score:.2f}"
        elif score > 0:
            return f"🔴 {score:.2f}"
        else:
            return "⚫ -"

    def _update_stats(self) -> None:
        """Update summary statistics from database."""
        try:
            summary = self.store.get_summary()
        except Exception:
            return

        self.query_one("#stat-total-runs", Static).update(str(summary.total_runs))
        
        if summary.total_runs > 0:
            self.query_one("#stat-best-score", Static).update(f"{summary.best_score:.2f}")
            self.query_one("#stat-avg-score", Static).update(f"{summary.average_score:.2f}")
            
            if summary.last_run:
                self.query_one("#stat-last-run", Static).update(
                    summary.last_run.strftime("%Y-%m-%d")
                )
        
    def _update_breakdown(self, summary) -> None:
        """Update the score breakdown visualization."""
        if not self.runs:
            return

        # Get agent comparison for layer breakdown
        try:
            comparisons = self.store.get_agent_comparison()
        except Exception:
            comparisons = []

        # Build breakdown text from runs
        layers = {
            "Deployment": [r.deployment_score for r in self.runs if r.deployment_score > 0],
            "Tests": [r.test_score for r in self.runs if r.test_score > 0],
            "Static Analysis": [r.static_analysis_score for r in self.runs if r.static_analysis_score > 0],
            "Metadata": [r.metadata_score for r in self.runs if r.metadata_score > 0],
            "Rubric": [r.rubric_score for r in self.runs if r.rubric_score > 0],
        }

        breakdown_text = ""
        for layer, scores in layers.items():
            if scores:
                avg = sum(scores) / len(scores)
                bar = "█" * int(avg * 20) + "░" * (20 - int(avg * 20))
                breakdown_text += f"{layer:15} [{bar}] {avg:.2f}\n"
            else:
                breakdown_text += f"{layer:15} [{'░' * 20}] -\n"

        self.query_one("#score-breakdown", Static).update(breakdown_text)

        # Layer analysis - show agent comparison
        if comparisons:
            analysis = "**Agent Comparison:**\n"
            for comp in comparisons[:5]:
                analysis += f"- {comp.agent_id}: {comp.average_score:.2f} avg ({comp.completed_runs} runs)\n"
        else:
            analysis = """
**Strengths:**
- Deployment success rate is high
- Test coverage meets requirements

**Areas for Improvement:**
- Consider async patterns for better scores
- Ensure CRUD/FLS checks are present
"""
        self.query_one("#layer-analysis", Static).update(analysis)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-back":
            self.app.switch_screen("dashboard")
        elif event.button.id == "btn-refresh":
            self._load_results()
            self._populate_table()
            self._update_stats()
            self.notify("Results refreshed")
        elif event.button.id == "btn-export":
            self._export_csv()

    def _export_csv(self) -> None:
        """Export results to CSV."""
        if not self.runs:
            self.notify("No results to export", severity="warning")
            return

        csv_path = self.config.results_dir / "benchmark_results.csv"
        try:
            self.store.export_to_csv(csv_path)
            self.notify(f"Exported {len(self.runs)} runs to {csv_path}")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")
