"""Model comparison utilities.

Provides tools for comparing model performance across benchmarks.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from sf_agentbench.domain.models import WorkUnit, TestType

console = Console()


@dataclass
class ModelStats:
    """Statistics for a single model."""
    
    model_id: str
    
    # Q&A
    qa_correct: int = 0
    qa_total: int = 0
    qa_accuracy: float = 0.0
    
    # Coding
    coding_count: int = 0
    coding_avg_score: float = 0.0
    deployment_avg: float = 0.0
    test_avg: float = 0.0
    rubric_avg: float = 0.0
    
    # Cost
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    
    # Performance
    avg_duration_seconds: float = 0.0
    total_duration_seconds: float = 0.0


class ModelComparison:
    """Compares model performance across work units."""
    
    def __init__(self, work_units: list[WorkUnit]):
        """Initialize with work units.
        
        Args:
            work_units: List of completed work units
        """
        self.work_units = work_units
        self._stats: dict[str, ModelStats] = {}
        self._compute_stats()
    
    def _compute_stats(self) -> None:
        """Compute statistics for each model."""
        model_data: dict[str, list[WorkUnit]] = {}
        
        for wu in self.work_units:
            model_id = wu.agent.id
            if model_id not in model_data:
                model_data[model_id] = []
            model_data[model_id].append(wu)
        
        for model_id, units in model_data.items():
            stats = ModelStats(model_id=model_id)
            
            qa_scores = []
            coding_scores = []
            deployment_scores = []
            test_scores = []
            rubric_scores = []
            durations = []
            
            for wu in units:
                if wu.result:
                    if wu.test.type == TestType.QA:
                        if wu.result.total_questions > 0:
                            stats.qa_total += wu.result.total_questions
                            stats.qa_correct += wu.result.correct_answers
                            qa_scores.append(wu.result.score)
                    
                    elif wu.test.type == TestType.CODING:
                        coding_scores.append(wu.result.score)
                        if wu.result.deployment_score:
                            deployment_scores.append(wu.result.deployment_score)
                        if wu.result.test_score:
                            test_scores.append(wu.result.test_score)
                        if wu.result.rubric_score:
                            rubric_scores.append(wu.result.rubric_score)
                    
                    stats.total_tokens += wu.result.cost.total_tokens
                    stats.total_cost_usd += wu.result.cost.estimated_usd
                    durations.append(wu.result.duration_seconds)
            
            # Calculate averages
            if stats.qa_total > 0:
                stats.qa_accuracy = stats.qa_correct / stats.qa_total
            
            if coding_scores:
                stats.coding_count = len(coding_scores)
                stats.coding_avg_score = sum(coding_scores) / len(coding_scores)
            
            if deployment_scores:
                stats.deployment_avg = sum(deployment_scores) / len(deployment_scores)
            
            if test_scores:
                stats.test_avg = sum(test_scores) / len(test_scores)
            
            if rubric_scores:
                stats.rubric_avg = sum(rubric_scores) / len(rubric_scores)
            
            if durations:
                stats.total_duration_seconds = sum(durations)
                stats.avg_duration_seconds = sum(durations) / len(durations)
            
            self._stats[model_id] = stats
    
    def get_stats(self, model_id: str) -> ModelStats | None:
        """Get statistics for a model."""
        return self._stats.get(model_id)
    
    def get_all_stats(self) -> dict[str, ModelStats]:
        """Get all model statistics."""
        return self._stats
    
    def rank_by(self, metric: str = "qa_accuracy") -> list[tuple[str, float]]:
        """Rank models by a metric.
        
        Args:
            metric: Metric to rank by (qa_accuracy, coding_avg_score, rubric_avg, total_cost_usd)
        
        Returns:
            List of (model_id, value) tuples sorted descending
        """
        rankings = []
        
        for model_id, stats in self._stats.items():
            value = getattr(stats, metric, 0)
            if value is not None:
                rankings.append((model_id, value))
        
        # Sort descending (except for cost which we want ascending)
        reverse = metric != "total_cost_usd"
        return sorted(rankings, key=lambda x: x[1] or 0, reverse=reverse)
    
    def render_console(self) -> None:
        """Render comparison to console."""
        console.print(Panel("Model Comparison", border_style="magenta"))
        
        # Q&A Performance
        if any(s.qa_total > 0 for s in self._stats.values()):
            qa_table = Table(title="Q&A Performance")
            qa_table.add_column("Model", style="magenta")
            qa_table.add_column("Correct", justify="right")
            qa_table.add_column("Total", justify="right")
            qa_table.add_column("Accuracy", justify="right")
            
            for model_id, stats in sorted(
                self._stats.items(),
                key=lambda x: x[1].qa_accuracy,
                reverse=True,
            ):
                if stats.qa_total > 0:
                    accuracy = f"{stats.qa_accuracy * 100:.1f}%"
                    qa_table.add_row(
                        model_id,
                        str(stats.qa_correct),
                        str(stats.qa_total),
                        accuracy,
                    )
            
            console.print(qa_table)
            console.print()
        
        # Coding Performance
        if any(s.coding_count > 0 for s in self._stats.values()):
            coding_table = Table(title="Coding Performance")
            coding_table.add_column("Model", style="magenta")
            coding_table.add_column("Tasks", justify="right")
            coding_table.add_column("Deploy", justify="right")
            coding_table.add_column("Tests", justify="right")
            coding_table.add_column("Rubric", justify="right")
            coding_table.add_column("Overall", justify="right")
            
            for model_id, stats in sorted(
                self._stats.items(),
                key=lambda x: x[1].coding_avg_score,
                reverse=True,
            ):
                if stats.coding_count > 0:
                    coding_table.add_row(
                        model_id,
                        str(stats.coding_count),
                        f"{stats.deployment_avg * 100:.0f}%",
                        f"{stats.test_avg * 100:.0f}%",
                        f"{stats.rubric_avg * 100:.0f}%",
                        f"{stats.coding_avg_score * 100:.0f}%",
                    )
            
            console.print(coding_table)
            console.print()
        
        # Cost Comparison
        cost_table = Table(title="Cost & Performance")
        cost_table.add_column("Model", style="magenta")
        cost_table.add_column("Tokens", justify="right")
        cost_table.add_column("Cost", justify="right", style="yellow")
        cost_table.add_column("Avg Duration", justify="right")
        cost_table.add_column("Total Time", justify="right")
        
        for model_id, stats in sorted(
            self._stats.items(),
            key=lambda x: x[1].total_cost_usd,
        ):
            cost_table.add_row(
                model_id,
                f"{stats.total_tokens:,}",
                f"${stats.total_cost_usd:.4f}",
                f"{stats.avg_duration_seconds:.1f}s",
                f"{stats.total_duration_seconds:.1f}s",
            )
        
        console.print(cost_table)
    
    def to_dict(self) -> dict[str, dict]:
        """Convert to dictionary."""
        return {
            model_id: {
                "qa_correct": stats.qa_correct,
                "qa_total": stats.qa_total,
                "qa_accuracy": stats.qa_accuracy,
                "coding_count": stats.coding_count,
                "coding_avg_score": stats.coding_avg_score,
                "deployment_avg": stats.deployment_avg,
                "test_avg": stats.test_avg,
                "rubric_avg": stats.rubric_avg,
                "total_tokens": stats.total_tokens,
                "total_cost_usd": stats.total_cost_usd,
                "avg_duration_seconds": stats.avg_duration_seconds,
            }
            for model_id, stats in self._stats.items()
        }
    
    def get_winner(self, metric: str = "qa_accuracy") -> str | None:
        """Get the winning model for a metric."""
        rankings = self.rank_by(metric)
        if rankings:
            return rankings[0][0]
        return None
    
    def summary(self) -> str:
        """Generate a text summary of the comparison."""
        lines = ["Model Comparison Summary", "=" * 40]
        
        # Q&A winner
        qa_winner = self.get_winner("qa_accuracy")
        if qa_winner:
            stats = self._stats[qa_winner]
            lines.append(f"Best Q&A: {qa_winner} ({stats.qa_accuracy * 100:.1f}%)")
        
        # Coding winner
        coding_winner = self.get_winner("coding_avg_score")
        if coding_winner:
            stats = self._stats[coding_winner]
            lines.append(f"Best Coding: {coding_winner} ({stats.coding_avg_score * 100:.1f}%)")
        
        # Rubric winner
        rubric_winner = self.get_winner("rubric_avg")
        if rubric_winner:
            stats = self._stats[rubric_winner]
            lines.append(f"Best Rubric: {rubric_winner} ({stats.rubric_avg * 100:.1f}%)")
        
        # Most cost-effective
        cost_winner = self.get_winner("total_cost_usd")
        if cost_winner:
            stats = self._stats[cost_winner]
            lines.append(f"Most Efficient: {cost_winner} (${stats.total_cost_usd:.4f})")
        
        return "\n".join(lines)
