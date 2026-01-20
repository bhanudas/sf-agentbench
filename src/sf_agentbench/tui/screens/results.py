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


class ResultsScreen(Screen):
    """Results viewer screen."""

    BINDINGS = [
        ("escape", "app.switch_screen('dashboard')", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.results = []

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
        """Load results from file."""
        results_file = self.config.results_dir / "benchmark_results.json"
        if results_file.exists():
            try:
                with open(results_file) as f:
                    self.results = json.load(f)
            except Exception:
                self.results = []
        else:
            self.results = []

    def _populate_table(self) -> None:
        """Populate the results table."""
        table = self.query_one("#results-table", DataTable)
        table.cursor_type = "row"
        table.clear()

        table.add_columns(
            "Task",
            "Agent",
            "Date",
            "Deploy",
            "Tests",
            "PMD",
            "Metadata",
            "Rubric",
            "Final",
        )

        for result in self.results:
            eval_data = result.get("evaluation", {})

            final_score = eval_data.get("final_score", 0)
            score_display = self._format_score(final_score)

            table.add_row(
                result.get("task_id", "-"),
                result.get("agent_id", "-"),
                result.get("started_at", "-")[:10] if result.get("started_at") else "-",
                self._format_score(eval_data.get("deployment_score", 0)),
                self._format_score(eval_data.get("test_score", 0)),
                self._format_score(eval_data.get("static_analysis_score", 0)),
                self._format_score(eval_data.get("metadata_score", 0)),
                self._format_score(eval_data.get("rubric_score", 0)),
                score_display,
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
        """Update summary statistics."""
        if not self.results:
            return

        total_runs = len(self.results)
        self.query_one("#stat-total-runs", Static).update(str(total_runs))

        scores = [
            r.get("evaluation", {}).get("final_score", 0)
            for r in self.results
            if r.get("evaluation", {}).get("final_score", 0) > 0
        ]

        if scores:
            best = max(scores)
            avg = sum(scores) / len(scores)
            self.query_one("#stat-best-score", Static).update(f"{best:.2f}")
            self.query_one("#stat-avg-score", Static).update(f"{avg:.2f}")

        if self.results:
            last_run = self.results[-1].get("started_at", "-")
            if last_run and len(last_run) > 10:
                last_run = last_run[:10]
            self.query_one("#stat-last-run", Static).update(last_run)

        # Update score breakdown
        self._update_breakdown()

    def _update_breakdown(self) -> None:
        """Update the score breakdown visualization."""
        if not self.results:
            return

        # Calculate averages per layer
        layers = {
            "Deployment": [],
            "Tests": [],
            "Static Analysis": [],
            "Metadata": [],
            "Rubric": [],
        }

        for result in self.results:
            eval_data = result.get("evaluation", {})
            if eval_data.get("deployment_score"):
                layers["Deployment"].append(eval_data["deployment_score"])
            if eval_data.get("test_score"):
                layers["Tests"].append(eval_data["test_score"])
            if eval_data.get("static_analysis_score"):
                layers["Static Analysis"].append(eval_data["static_analysis_score"])
            if eval_data.get("metadata_score"):
                layers["Metadata"].append(eval_data["metadata_score"])
            if eval_data.get("rubric_score"):
                layers["Rubric"].append(eval_data["rubric_score"])

        breakdown_text = ""
        for layer, scores in layers.items():
            if scores:
                avg = sum(scores) / len(scores)
                bar = "█" * int(avg * 20) + "░" * (20 - int(avg * 20))
                breakdown_text += f"{layer:15} [{bar}] {avg:.2f}\n"
            else:
                breakdown_text += f"{layer:15} [{'░' * 20}] -\n"

        self.query_one("#score-breakdown", Static).update(breakdown_text)

        # Layer analysis
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
        if not self.results:
            self.notify("No results to export", severity="warning")
            return

        csv_path = self.config.results_dir / "benchmark_results.csv"
        try:
            with open(csv_path, "w") as f:
                f.write("task_id,agent_id,date,deploy,tests,pmd,metadata,rubric,final\n")
                for result in self.results:
                    eval_data = result.get("evaluation", {})
                    f.write(
                        f"{result.get('task_id', '')},"
                        f"{result.get('agent_id', '')},"
                        f"{result.get('started_at', '')[:10] if result.get('started_at') else ''},"
                        f"{eval_data.get('deployment_score', 0):.2f},"
                        f"{eval_data.get('test_score', 0):.2f},"
                        f"{eval_data.get('static_analysis_score', 0):.2f},"
                        f"{eval_data.get('metadata_score', 0):.2f},"
                        f"{eval_data.get('rubric_score', 0):.2f},"
                        f"{eval_data.get('final_score', 0):.2f}\n"
                    )
            self.notify(f"Exported to {csv_path}")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")
