"""Report generation with rubric drill-down.

Generates comprehensive reports with rubric scoring breakdown.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from sf_agentbench.domain.models import WorkUnit, TestType, Result
from sf_agentbench.judges.base import JudgeResult, JudgeCriterion
from sf_agentbench.storage.unified import UnifiedStore

console = Console()


class ReportFormat(str, Enum):
    """Report output formats."""
    
    CONSOLE = "console"
    JSON = "json"
    HTML = "html"
    MARKDOWN = "markdown"


@dataclass
class RubricBreakdown:
    """Breakdown of rubric scores for a work unit."""
    
    work_unit_id: str
    agent_id: str
    judge_model: str
    rubric_name: str
    overall_score: float
    criteria: list[dict] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    """A complete benchmark report."""
    
    title: str
    generated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Summary
    total_work_units: int = 0
    completed_work_units: int = 0
    failed_work_units: int = 0
    total_cost_usd: float = 0.0
    total_duration_seconds: float = 0.0
    
    # Scores by model
    model_scores: dict[str, dict] = field(default_factory=dict)
    
    # Rubric breakdowns
    rubric_breakdowns: list[RubricBreakdown] = field(default_factory=list)
    
    # By test type
    qa_summary: dict[str, Any] = field(default_factory=dict)
    coding_summary: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "generated_at": self.generated_at.isoformat(),
            "summary": {
                "total_work_units": self.total_work_units,
                "completed_work_units": self.completed_work_units,
                "failed_work_units": self.failed_work_units,
                "total_cost_usd": self.total_cost_usd,
                "total_duration_seconds": self.total_duration_seconds,
            },
            "model_scores": self.model_scores,
            "rubric_breakdowns": [
                {
                    "work_unit_id": rb.work_unit_id,
                    "agent_id": rb.agent_id,
                    "judge_model": rb.judge_model,
                    "rubric_name": rb.rubric_name,
                    "overall_score": rb.overall_score,
                    "criteria": rb.criteria,
                }
                for rb in self.rubric_breakdowns
            ],
            "qa_summary": self.qa_summary,
            "coding_summary": self.coding_summary,
        }


class ReportGenerator:
    """Generates benchmark reports with rubric drill-down."""
    
    def __init__(
        self,
        store: UnifiedStore | None = None,
        verbose: bool = False,
    ):
        """Initialize the report generator.
        
        Args:
            store: Unified storage instance
            verbose: Enable verbose output
        """
        self.store = store
        self.verbose = verbose
    
    def generate(
        self,
        work_units: list[WorkUnit],
        title: str = "Benchmark Report",
        include_rubrics: bool = True,
    ) -> BenchmarkReport:
        """Generate a report from work units.
        
        Args:
            work_units: List of completed work units
            title: Report title
            include_rubrics: Include rubric breakdowns
        
        Returns:
            BenchmarkReport with all data
        """
        report = BenchmarkReport(title=title)
        report.total_work_units = len(work_units)
        
        # Aggregate by model
        model_data: dict[str, list[WorkUnit]] = {}
        
        for wu in work_units:
            agent_id = wu.agent.id
            if agent_id not in model_data:
                model_data[agent_id] = []
            model_data[agent_id].append(wu)
            
            # Count status
            if wu.status.value == "completed":
                report.completed_work_units += 1
            elif wu.status.value == "failed":
                report.failed_work_units += 1
            
            # Sum costs and duration
            if wu.result:
                report.total_cost_usd += wu.result.cost.estimated_usd
                report.total_duration_seconds += wu.result.duration_seconds
        
        # Calculate per-model scores
        for agent_id, agent_work_units in model_data.items():
            qa_scores = []
            coding_scores = []
            rubric_scores = []
            total_cost = 0.0
            
            for wu in agent_work_units:
                if wu.result:
                    total_cost += wu.result.cost.estimated_usd
                    
                    if wu.test.type == TestType.QA:
                        qa_scores.append(wu.result.score)
                    elif wu.test.type == TestType.CODING:
                        coding_scores.append(wu.result.score)
                        if wu.result.rubric_score:
                            rubric_scores.append(wu.result.rubric_score)
            
            report.model_scores[agent_id] = {
                "qa_accuracy": sum(qa_scores) / len(qa_scores) if qa_scores else None,
                "coding_score": sum(coding_scores) / len(coding_scores) if coding_scores else None,
                "rubric_score": sum(rubric_scores) / len(rubric_scores) if rubric_scores else None,
                "total_cost_usd": total_cost,
                "work_units": len(agent_work_units),
            }
        
        # Add rubric breakdowns if requested
        if include_rubrics:
            report.rubric_breakdowns = self._extract_rubric_breakdowns(work_units)
        
        return report
    
    def _extract_rubric_breakdowns(self, work_units: list[WorkUnit]) -> list[RubricBreakdown]:
        """Extract rubric breakdowns from work units."""
        breakdowns = []
        
        for wu in work_units:
            if wu.result and wu.result.rubric_score:
                # Try to get detailed rubric data from details
                details = wu.result.details or {}
                rubric_data = details.get("rubric_result", {})
                
                if rubric_data:
                    breakdown = RubricBreakdown(
                        work_unit_id=wu.id,
                        agent_id=wu.agent.id,
                        judge_model=rubric_data.get("judge_model", "unknown"),
                        rubric_name=rubric_data.get("rubric_name", "unknown"),
                        overall_score=wu.result.rubric_score,
                        criteria=rubric_data.get("criteria", []),
                    )
                    breakdowns.append(breakdown)
        
        return breakdowns
    
    def render(
        self,
        report: BenchmarkReport,
        format: ReportFormat = ReportFormat.CONSOLE,
        output_path: Path | None = None,
    ) -> str:
        """Render a report to the specified format.
        
        Args:
            report: The report to render
            format: Output format
            output_path: Path to save the output
        
        Returns:
            Rendered report string
        """
        if format == ReportFormat.CONSOLE:
            return self._render_console(report)
        elif format == ReportFormat.JSON:
            output = json.dumps(report.to_dict(), indent=2)
        elif format == ReportFormat.MARKDOWN:
            output = self._render_markdown(report)
        elif format == ReportFormat.HTML:
            output = self._render_html(report)
        else:
            output = str(report.to_dict())
        
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output)
        
        return output
    
    def _render_console(self, report: BenchmarkReport) -> str:
        """Render report to console."""
        # Title
        console.print(Panel(
            Text(report.title, style="bold magenta"),
            border_style="magenta",
        ))
        
        # Summary
        summary_table = Table(title="Summary", show_header=False)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value")
        
        summary_table.add_row("Total Work Units", str(report.total_work_units))
        summary_table.add_row("Completed", str(report.completed_work_units))
        summary_table.add_row("Failed", str(report.failed_work_units))
        summary_table.add_row("Total Cost", f"${report.total_cost_usd:.4f}")
        summary_table.add_row("Duration", f"{report.total_duration_seconds:.1f}s")
        
        console.print(summary_table)
        console.print()
        
        # Model Scores
        if report.model_scores:
            model_table = Table(title="Model Comparison")
            model_table.add_column("Model", style="magenta")
            model_table.add_column("Q&A", justify="right")
            model_table.add_column("Coding", justify="right")
            model_table.add_column("Rubric", justify="right")
            model_table.add_column("Cost", justify="right", style="yellow")
            
            for model, scores in report.model_scores.items():
                qa = f"{scores['qa_accuracy']*100:.1f}%" if scores.get('qa_accuracy') else "-"
                coding = f"{scores['coding_score']*100:.1f}%" if scores.get('coding_score') else "-"
                rubric = f"{scores['rubric_score']*100:.1f}%" if scores.get('rubric_score') else "-"
                cost = f"${scores['total_cost_usd']:.4f}"
                
                model_table.add_row(model, qa, coding, rubric, cost)
            
            console.print(model_table)
            console.print()
        
        # Rubric Breakdowns
        if report.rubric_breakdowns:
            console.print(Panel("Rubric Breakdowns", border_style="cyan"))
            
            for breakdown in report.rubric_breakdowns[:5]:  # Top 5
                rubric_table = Table(
                    title=f"{breakdown.agent_id} - {breakdown.rubric_name}",
                    show_header=True,
                )
                rubric_table.add_column("Criterion")
                rubric_table.add_column("Score", justify="right")
                rubric_table.add_column("Progress", width=20)
                
                for criterion in breakdown.criteria:
                    name = criterion.get("name", "Unknown")
                    score = criterion.get("score", 0)
                    
                    # Create progress bar
                    filled = int(score * 20)
                    bar = "█" * filled + "░" * (20 - filled)
                    
                    rubric_table.add_row(
                        name,
                        f"{score:.2f}",
                        bar,
                    )
                
                console.print(rubric_table)
                console.print()
        
        return ""  # Console output is direct
    
    def _render_markdown(self, report: BenchmarkReport) -> str:
        """Render report as Markdown."""
        lines = [
            f"# {report.title}",
            "",
            f"*Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "## Summary",
            "",
            f"- **Total Work Units:** {report.total_work_units}",
            f"- **Completed:** {report.completed_work_units}",
            f"- **Failed:** {report.failed_work_units}",
            f"- **Total Cost:** ${report.total_cost_usd:.4f}",
            f"- **Duration:** {report.total_duration_seconds:.1f}s",
            "",
        ]
        
        if report.model_scores:
            lines.extend([
                "## Model Comparison",
                "",
                "| Model | Q&A | Coding | Rubric | Cost |",
                "|-------|-----|--------|--------|------|",
            ])
            
            for model, scores in report.model_scores.items():
                qa = f"{scores['qa_accuracy']*100:.1f}%" if scores.get('qa_accuracy') else "-"
                coding = f"{scores['coding_score']*100:.1f}%" if scores.get('coding_score') else "-"
                rubric = f"{scores['rubric_score']*100:.1f}%" if scores.get('rubric_score') else "-"
                cost = f"${scores['total_cost_usd']:.4f}"
                
                lines.append(f"| {model} | {qa} | {coding} | {rubric} | {cost} |")
            
            lines.append("")
        
        if report.rubric_breakdowns:
            lines.extend([
                "## Rubric Breakdowns",
                "",
            ])
            
            for breakdown in report.rubric_breakdowns:
                lines.extend([
                    f"### {breakdown.agent_id}",
                    f"*Rubric: {breakdown.rubric_name}, Judge: {breakdown.judge_model}*",
                    "",
                    f"**Overall Score:** {breakdown.overall_score:.2f}",
                    "",
                    "| Criterion | Score |",
                    "|-----------|-------|",
                ])
                
                for criterion in breakdown.criteria:
                    name = criterion.get("name", "Unknown")
                    score = criterion.get("score", 0)
                    lines.append(f"| {name} | {score:.2f} |")
                
                lines.append("")
        
        return "\n".join(lines)
    
    def _render_html(self, report: BenchmarkReport) -> str:
        """Render report as HTML."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{report.title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }}
        h1 {{ color: #9b59b6; }}
        h2 {{ color: #3498db; border-bottom: 2px solid #3498db; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #f4f4f4; }}
        .score {{ text-align: right; }}
        .cost {{ color: #f39c12; }}
        .progress {{ background: linear-gradient(to right, #3498db 0%, #3498db var(--progress), #eee var(--progress), #eee 100%); height: 20px; border-radius: 4px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px; margin: 20px 0; }}
        .summary-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
        .summary-card h3 {{ margin: 0; font-size: 24px; color: #2c3e50; }}
        .summary-card p {{ margin: 5px 0 0; color: #7f8c8d; }}
    </style>
</head>
<body>
    <h1>{report.title}</h1>
    <p><em>Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}</em></p>
    
    <div class="summary">
        <div class="summary-card">
            <h3>{report.total_work_units}</h3>
            <p>Total Work Units</p>
        </div>
        <div class="summary-card">
            <h3>{report.completed_work_units}</h3>
            <p>Completed</p>
        </div>
        <div class="summary-card">
            <h3>{report.failed_work_units}</h3>
            <p>Failed</p>
        </div>
        <div class="summary-card">
            <h3>${report.total_cost_usd:.4f}</h3>
            <p>Total Cost</p>
        </div>
    </div>
"""
        
        if report.model_scores:
            html += """
    <h2>Model Comparison</h2>
    <table>
        <tr><th>Model</th><th class="score">Q&A</th><th class="score">Coding</th><th class="score">Rubric</th><th class="score cost">Cost</th></tr>
"""
            for model, scores in report.model_scores.items():
                qa = f"{scores['qa_accuracy']*100:.1f}%" if scores.get('qa_accuracy') else "-"
                coding = f"{scores['coding_score']*100:.1f}%" if scores.get('coding_score') else "-"
                rubric = f"{scores['rubric_score']*100:.1f}%" if scores.get('rubric_score') else "-"
                cost = f"${scores['total_cost_usd']:.4f}"
                html += f"        <tr><td>{model}</td><td class='score'>{qa}</td><td class='score'>{coding}</td><td class='score'>{rubric}</td><td class='score cost'>{cost}</td></tr>\n"
            
            html += "    </table>\n"
        
        if report.rubric_breakdowns:
            html += "    <h2>Rubric Breakdowns</h2>\n"
            
            for breakdown in report.rubric_breakdowns[:5]:
                html += f"""
    <h3>{breakdown.agent_id}</h3>
    <p><em>Rubric: {breakdown.rubric_name}, Judge: {breakdown.judge_model}</em></p>
    <p><strong>Overall Score:</strong> {breakdown.overall_score:.2f}</p>
    <table>
        <tr><th>Criterion</th><th class="score">Score</th><th>Progress</th></tr>
"""
                for criterion in breakdown.criteria:
                    name = criterion.get("name", "Unknown")
                    score = criterion.get("score", 0)
                    progress = int(score * 100)
                    html += f"        <tr><td>{name}</td><td class='score'>{score:.2f}</td><td><div class='progress' style='--progress: {progress}%'></div></td></tr>\n"
                
                html += "    </table>\n"
        
        html += """
</body>
</html>"""
        
        return html
