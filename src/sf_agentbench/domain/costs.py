"""Cost estimation and tracking for LLM usage.

Provides unified cost tracking across all models and test types.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sf_agentbench.domain.models import Cost, CostProfile


# Cost per 1M tokens (input/output) - pricing as of Jan 2026
MODEL_COSTS: dict[str, CostProfile] = {
    # Gemini models
    "gemini-2.0-flash": CostProfile(input_cost_per_million=0.075, output_cost_per_million=0.30),
    "gemini-2.5-pro": CostProfile(input_cost_per_million=1.25, output_cost_per_million=5.00),
    "gemini-1.5-pro": CostProfile(input_cost_per_million=1.25, output_cost_per_million=5.00),
    "gemini-1.5-flash": CostProfile(input_cost_per_million=0.075, output_cost_per_million=0.30),
    
    # Claude models
    "sonnet": CostProfile(input_cost_per_million=3.00, output_cost_per_million=15.00),
    "claude-sonnet-4": CostProfile(input_cost_per_million=3.00, output_cost_per_million=15.00),
    "claude-sonnet-4-20250514": CostProfile(input_cost_per_million=3.00, output_cost_per_million=15.00),
    "opus": CostProfile(input_cost_per_million=15.00, output_cost_per_million=75.00),
    "claude-opus-4": CostProfile(input_cost_per_million=15.00, output_cost_per_million=75.00),
    "claude-opus-4-20250514": CostProfile(input_cost_per_million=15.00, output_cost_per_million=75.00),
    "haiku": CostProfile(input_cost_per_million=0.25, output_cost_per_million=1.25),
    
    # OpenAI models
    "gpt-4o": CostProfile(input_cost_per_million=2.50, output_cost_per_million=10.00),
    "gpt-4o-mini": CostProfile(input_cost_per_million=0.15, output_cost_per_million=0.60),
    "gpt-4-turbo": CostProfile(input_cost_per_million=10.00, output_cost_per_million=30.00),
}

# Default cost profile for unknown models
DEFAULT_COST_PROFILE = CostProfile(
    input_cost_per_million=1.00,
    output_cost_per_million=3.00,
)


def get_cost_profile(model: str) -> CostProfile:
    """Get cost profile for a model, with fallback to default."""
    return MODEL_COSTS.get(model, DEFAULT_COST_PROFILE)


def estimate_tokens(text: str) -> int:
    """Estimate token count from text (rough: 4 chars per token)."""
    return len(text) // 4


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a given model and token count."""
    profile = get_cost_profile(model)
    return profile.estimate(input_tokens, output_tokens)


@dataclass
class CostTracker:
    """Tracks costs across multiple operations."""
    
    model: str
    costs: list[Cost] = field(default_factory=list)
    _profile: CostProfile | None = None
    
    def __post_init__(self):
        self._profile = get_cost_profile(self.model)
    
    def add(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        input_text: str | None = None,
        output_text: str | None = None,
    ) -> Cost:
        """Add a cost entry from tokens or text."""
        if input_text:
            input_tokens = estimate_tokens(input_text)
        if output_text:
            output_tokens = estimate_tokens(output_text)
        
        estimated_usd = self._profile.estimate(input_tokens, output_tokens)
        
        cost = Cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_usd=estimated_usd,
        )
        self.costs.append(cost)
        return cost
    
    @property
    def total(self) -> Cost:
        """Get total cost across all entries."""
        total = Cost()
        for cost in self.costs:
            total = total.add(cost)
        return total
    
    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.costs)
    
    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.costs)
    
    @property
    def total_usd(self) -> float:
        return sum(c.estimated_usd for c in self.costs)
    
    @property
    def entry_count(self) -> int:
        return len(self.costs)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "model": self.model,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_usd": self.total_usd,
            "entry_count": self.entry_count,
        }


@dataclass
class CostSummary:
    """Summary of costs across multiple models."""
    
    by_model: dict[str, Cost] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)
    
    def add(self, model: str, cost: Cost) -> None:
        """Add a cost entry for a model."""
        if model not in self.by_model:
            self.by_model[model] = Cost()
        self.by_model[model] = self.by_model[model].add(cost)
    
    @property
    def total(self) -> Cost:
        """Get total cost across all models."""
        total = Cost()
        for cost in self.by_model.values():
            total = total.add(cost)
        return total
    
    @property
    def total_usd(self) -> float:
        return self.total.estimated_usd
    
    def format_breakdown(self) -> str:
        """Format a breakdown of costs by model."""
        lines = ["Cost Breakdown:"]
        for model, cost in sorted(self.by_model.items(), key=lambda x: -x[1].estimated_usd):
            lines.append(
                f"  {model}: ${cost.estimated_usd:.4f} "
                f"({cost.input_tokens:,} in / {cost.output_tokens:,} out)"
            )
        lines.append(f"  Total: ${self.total_usd:.4f}")
        return "\n".join(lines)
