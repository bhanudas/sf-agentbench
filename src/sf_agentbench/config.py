"""Configuration management for SF-AgentBench."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
import yaml


class ScratchOrgConfig(BaseModel):
    """Configuration for Scratch Org management."""

    default_duration_days: int = Field(default=1, ge=1, le=30)
    edition: str = Field(default="Developer")
    wait_minutes: int = Field(default=10, description="Minutes to wait for org creation")
    use_snapshots: bool = Field(default=False)
    snapshot_name: str | None = Field(default=None)


class EvaluationWeights(BaseModel):
    """Weights for evaluation scoring."""

    deployment: float = Field(default=0.20, ge=0.0, le=1.0)
    functional_tests: float = Field(default=0.40, ge=0.0, le=1.0)
    static_analysis: float = Field(default=0.10, ge=0.0, le=1.0)
    metadata_diff: float = Field(default=0.15, ge=0.0, le=1.0)
    rubric: float = Field(default=0.15, ge=0.0, le=1.0)

    def validate_sum(self) -> bool:
        """Validate that weights sum to 1.0."""
        total = (
            self.deployment
            + self.functional_tests
            + self.static_analysis
            + self.metadata_diff
            + self.rubric
        )
        return abs(total - 1.0) < 0.001


class PMDConfig(BaseModel):
    """Configuration for PMD/Code Analyzer."""

    enabled: bool = Field(default=True)
    ruleset: str = Field(default="default")
    critical_weight: float = Field(default=3.0)
    high_weight: float = Field(default=2.0)
    medium_weight: float = Field(default=1.0)
    low_weight: float = Field(default=0.5)
    max_penalty: float = Field(default=0.10, description="Maximum penalty from PMD violations")


class RubricConfig(BaseModel):
    """Configuration for LLM-as-a-Judge rubric evaluation."""

    enabled: bool = Field(default=True)
    model: str = Field(default="claude-3-5-sonnet-20241022")
    temperature: float = Field(default=0.0)
    max_tokens: int = Field(default=2048)
    num_evaluations: int = Field(default=1, description="Number of evaluations to average")


class BenchmarkConfig(BaseModel):
    """Main configuration for SF-AgentBench."""

    # Paths
    tasks_dir: Path = Field(default=Path("tasks"))
    results_dir: Path = Field(default=Path("results"))
    logs_dir: Path = Field(default=Path("logs"))

    # Salesforce CLI
    sf_cli_path: str = Field(default="sf")
    devhub_username: str | None = Field(default=None)

    # Scratch Org settings
    scratch_org: ScratchOrgConfig = Field(default_factory=ScratchOrgConfig)

    # Evaluation settings
    evaluation_weights: EvaluationWeights = Field(default_factory=EvaluationWeights)
    pmd: PMDConfig = Field(default_factory=PMDConfig)
    rubric: RubricConfig = Field(default_factory=RubricConfig)

    # Execution settings
    parallel_runs: int = Field(default=1, ge=1, le=10)
    timeout_minutes: int = Field(default=60)
    cleanup_orgs: bool = Field(default=True, description="Delete scratch orgs after run")

    # Logging
    verbose: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    @classmethod
    def from_yaml(cls, path: Path) -> "BenchmarkConfig":
        """Load configuration from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, path: Path) -> None:
        """Save configuration to a YAML file."""
        with open(path, "w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)

    @classmethod
    def default(cls) -> "BenchmarkConfig":
        """Create a default configuration."""
        return cls()


def load_config(config_path: Path | None = None) -> BenchmarkConfig:
    """Load configuration from file or use defaults."""
    if config_path and config_path.exists():
        return BenchmarkConfig.from_yaml(config_path)

    # Check for default config locations
    default_paths = [
        Path("sf-agentbench.yaml"),
        Path("sf-agentbench.yml"),
        Path(".sf-agentbench.yaml"),
        Path(".sf-agentbench.yml"),
    ]

    for path in default_paths:
        if path.exists():
            return BenchmarkConfig.from_yaml(path)

    return BenchmarkConfig.default()
