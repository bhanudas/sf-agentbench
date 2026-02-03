"""Multi-judge consensus scoring.

Aggregates scores from multiple judges for reliable evaluation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from rich.console import Console

from sf_agentbench.judges.base import Judge, JudgeResult, JudgeCriterion, Rubric

console = Console()


class ConsensusMethod(str, Enum):
    """Methods for combining scores from multiple judges."""
    
    WEIGHTED_AVERAGE = "weighted_average"
    MAJORITY_VOTE = "majority_vote"
    MIN_SCORE = "min_score"
    MAX_SCORE = "max_score"
    MEDIAN = "median"


@dataclass
class JudgeConfig:
    """Configuration for a judge in the consensus panel."""
    
    judge: Judge
    weight: float = 1.0
    name: str = ""
    
    def __post_init__(self):
        if not self.name:
            self.name = self.judge.model


@dataclass
class ConsensusResult:
    """Result from consensus judging."""
    
    overall_score: float = 0.0
    individual_results: list[JudgeResult] = field(default_factory=list)
    method: ConsensusMethod = ConsensusMethod.WEIGHTED_AVERAGE
    
    # Aggregated criteria
    criteria: list[JudgeCriterion] = field(default_factory=list)
    
    # Agreement metrics
    score_variance: float = 0.0
    max_disagreement: float = 0.0
    
    # Combined feedback
    feedback: str = ""
    strengths: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    
    # Totals
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "overall_score": self.overall_score,
            "method": self.method.value,
            "individual_results": [r.to_dict() for r in self.individual_results],
            "criteria": [
                {
                    "name": c.name,
                    "score": c.score,
                    "weight": c.weight,
                    "reasoning": c.reasoning,
                }
                for c in self.criteria
            ],
            "score_variance": self.score_variance,
            "max_disagreement": self.max_disagreement,
            "feedback": self.feedback,
            "total_cost_usd": self.total_cost_usd,
        }


class ConsensusJudge:
    """Combines multiple judges for consensus scoring.
    
    Runs the same evaluation through multiple judges and aggregates
    their scores using the configured method.
    """
    
    def __init__(
        self,
        judges: list[JudgeConfig],
        method: ConsensusMethod = ConsensusMethod.WEIGHTED_AVERAGE,
        verbose: bool = False,
    ):
        """Initialize the consensus judge.
        
        Args:
            judges: List of judge configurations
            method: Method for combining scores
            verbose: Enable verbose output
        """
        self.judges = judges
        self.method = method
        self.verbose = verbose
        
        # Normalize weights
        total_weight = sum(j.weight for j in judges)
        for judge in judges:
            judge.weight = judge.weight / total_weight
    
    def evaluate(
        self,
        code: str,
        requirements: str,
        rubric: Rubric,
        agent_id: str = "unknown",
    ) -> ConsensusResult:
        """Evaluate code using all judges and combine results.
        
        Args:
            code: The code to evaluate
            requirements: Task requirements
            rubric: Evaluation rubric
            agent_id: ID of the agent that produced the code
        
        Returns:
            ConsensusResult with combined scores
        """
        results: list[JudgeResult] = []
        
        if self.verbose:
            console.print(f"[dim]Running {len(self.judges)} judges...[/dim]")
        
        # Run each judge
        for judge_config in self.judges:
            if self.verbose:
                console.print(f"[dim]  {judge_config.name}...[/dim]")
            
            try:
                result = judge_config.judge.evaluate(
                    code=code,
                    requirements=requirements,
                    rubric=rubric,
                    agent_id=agent_id,
                )
                results.append(result)
            except Exception as e:
                console.print(f"[yellow]Judge {judge_config.name} failed: {e}[/yellow]")
        
        if not results:
            return ConsensusResult(method=self.method)
        
        # Combine results
        consensus = self._combine_results(results)
        
        if self.verbose:
            console.print(f"[dim]Consensus score: {consensus.overall_score:.2f}[/dim]")
            console.print(f"[dim]Variance: {consensus.score_variance:.4f}[/dim]")
        
        return consensus
    
    def _combine_results(self, results: list[JudgeResult]) -> ConsensusResult:
        """Combine individual judge results.
        
        Args:
            results: List of individual judge results
        
        Returns:
            Combined consensus result
        """
        consensus = ConsensusResult(
            individual_results=results,
            method=self.method,
        )
        
        # Calculate totals
        consensus.total_input_tokens = sum(r.input_tokens for r in results)
        consensus.total_output_tokens = sum(r.output_tokens for r in results)
        consensus.total_cost_usd = sum(r.estimated_cost_usd for r in results)
        consensus.total_duration_ms = sum(r.duration_ms for r in results)
        
        # Get all scores
        scores = [r.overall_score for r in results if r.parsed_successfully]
        
        if not scores:
            return consensus
        
        # Calculate overall score based on method
        if self.method == ConsensusMethod.WEIGHTED_AVERAGE:
            weighted_scores = []
            for result, judge_config in zip(results, self.judges):
                if result.parsed_successfully:
                    weighted_scores.append(result.overall_score * judge_config.weight)
            consensus.overall_score = sum(weighted_scores) / sum(
                j.weight for j, r in zip(self.judges, results) if r.parsed_successfully
            )
        
        elif self.method == ConsensusMethod.MAJORITY_VOTE:
            # Round to nearest 0.1 and take most common
            rounded = [round(s, 1) for s in scores]
            from collections import Counter
            consensus.overall_score = Counter(rounded).most_common(1)[0][0]
        
        elif self.method == ConsensusMethod.MIN_SCORE:
            consensus.overall_score = min(scores)
        
        elif self.method == ConsensusMethod.MAX_SCORE:
            consensus.overall_score = max(scores)
        
        elif self.method == ConsensusMethod.MEDIAN:
            sorted_scores = sorted(scores)
            mid = len(sorted_scores) // 2
            if len(sorted_scores) % 2 == 0:
                consensus.overall_score = (sorted_scores[mid - 1] + sorted_scores[mid]) / 2
            else:
                consensus.overall_score = sorted_scores[mid]
        
        # Calculate agreement metrics
        if len(scores) > 1:
            mean = sum(scores) / len(scores)
            consensus.score_variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            consensus.max_disagreement = max(scores) - min(scores)
        
        # Aggregate criteria
        consensus.criteria = self._aggregate_criteria(results)
        
        # Combine feedback
        all_strengths = set()
        all_improvements = set()
        feedback_parts = []
        
        for result in results:
            if result.parsed_successfully:
                all_strengths.update(result.strengths)
                all_improvements.update(result.improvements)
                if result.feedback:
                    feedback_parts.append(f"[{result.judge_model}] {result.feedback}")
        
        consensus.strengths = list(all_strengths)[:5]  # Top 5
        consensus.improvements = list(all_improvements)[:5]  # Top 5
        consensus.feedback = "\n\n".join(feedback_parts)
        
        return consensus
    
    def _aggregate_criteria(self, results: list[JudgeResult]) -> list[JudgeCriterion]:
        """Aggregate criteria scores across judges.
        
        Args:
            results: List of individual judge results
        
        Returns:
            Aggregated criteria with average scores
        """
        # Collect all criteria by name
        criteria_by_name: dict[str, list[JudgeCriterion]] = {}
        
        for result in results:
            if not result.parsed_successfully:
                continue
            for criterion in result.criteria:
                if criterion.name not in criteria_by_name:
                    criteria_by_name[criterion.name] = []
                criteria_by_name[criterion.name].append(criterion)
        
        # Average scores for each criterion
        aggregated = []
        for name, criteria in criteria_by_name.items():
            avg_score = sum(c.score for c in criteria) / len(criteria)
            weight = criteria[0].weight  # Use weight from first criterion
            
            # Combine reasoning
            reasonings = [c.reasoning for c in criteria if c.reasoning]
            combined_reasoning = "; ".join(reasonings[:2]) if reasonings else ""
            
            aggregated.append(JudgeCriterion(
                name=name,
                score=avg_score,
                weight=weight,
                reasoning=combined_reasoning,
            ))
        
        return aggregated
