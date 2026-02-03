"""Configuration management for SF-AgentBench."""

from pathlib import Path
from typing import Any
from enum import Enum

from pydantic import BaseModel, Field, model_validator
import yaml


# ============================================================================
# SUPPORTED MODELS REGISTRY
# ============================================================================

class ModelProvider(str, Enum):
    """Supported model providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    KIMI = "kimi"
    CUSTOM = "custom"


# Built-in supported models with their metadata
BUILTIN_MODELS: dict[str, dict[str, Any]] = {
    # Anthropic Claude models
    "claude-opus-4-20250514": {
        "provider": ModelProvider.ANTHROPIC,
        "name": "Claude Opus 4",
        "api_key_env": "ANTHROPIC_API_KEY",
        "context_window": 200000,
    },
    "claude-sonnet-4-20250514": {
        "provider": ModelProvider.ANTHROPIC,
        "name": "Claude Sonnet 4",
        "api_key_env": "ANTHROPIC_API_KEY",
        "context_window": 200000,
    },
    # Note: Claude 3.x models (claude-3-5-sonnet, claude-3-opus) have been
    # deprecated by Anthropic. Use Claude 4 models (claude-sonnet-4, claude-opus-4) instead.
    # OpenAI models
    "gpt-4o": {
        "provider": ModelProvider.OPENAI,
        "name": "GPT-4o",
        "api_key_env": "OPENAI_API_KEY",
        "context_window": 128000,
    },
    "gpt-4o-mini": {
        "provider": ModelProvider.OPENAI,
        "name": "GPT-4o Mini",
        "api_key_env": "OPENAI_API_KEY",
        "context_window": 128000,
    },
    "gpt-4-turbo": {
        "provider": ModelProvider.OPENAI,
        "name": "GPT-4 Turbo",
        "api_key_env": "OPENAI_API_KEY",
        "context_window": 128000,
    },
    "o1": {
        "provider": ModelProvider.OPENAI,
        "name": "OpenAI o1",
        "api_key_env": "OPENAI_API_KEY",
        "context_window": 200000,
    },
    "o1-mini": {
        "provider": ModelProvider.OPENAI,
        "name": "OpenAI o1-mini",
        "api_key_env": "OPENAI_API_KEY",
        "context_window": 128000,
    },
    "o3-mini": {
        "provider": ModelProvider.OPENAI,
        "name": "OpenAI o3-mini",
        "api_key_env": "OPENAI_API_KEY",
        "context_window": 200000,
    },
    # GPT-5 series
    "gpt-5.2-very-high": {
        "provider": ModelProvider.OPENAI,
        "name": "GPT-5.2 Very High",
        "api_key_env": "OPENAI_API_KEY",
        "context_window": 256000,
    },
    "gpt-5.2": {
        "provider": ModelProvider.OPENAI,
        "name": "GPT-5.2",
        "api_key_env": "OPENAI_API_KEY",
        "context_window": 256000,
    },
    "gpt-5": {
        "provider": ModelProvider.OPENAI,
        "name": "GPT-5",
        "api_key_env": "OPENAI_API_KEY",
        "context_window": 256000,
    },
    # Google Gemini models
    "gemini-2.0-flash": {
        "provider": ModelProvider.GOOGLE,
        "name": "Gemini 2.0 Flash",
        "api_key_env": "GOOGLE_API_KEY",
        "context_window": 1000000,
    },
    "gemini-2.0-flash-thinking": {
        "provider": ModelProvider.GOOGLE,
        "name": "Gemini 2.0 Flash Thinking",
        "api_key_env": "GOOGLE_API_KEY",
        "context_window": 1000000,
    },
    "gemini-1.5-pro": {
        "provider": ModelProvider.GOOGLE,
        "name": "Gemini 1.5 Pro",
        "api_key_env": "GOOGLE_API_KEY",
        "context_window": 2000000,
    },
    "gemini-1.5-flash": {
        "provider": ModelProvider.GOOGLE,
        "name": "Gemini 1.5 Flash",
        "api_key_env": "GOOGLE_API_KEY",
        "context_window": 1000000,
    },
    # Gemini 2.5 models
    "gemini-2.5-pro": {
        "provider": ModelProvider.GOOGLE,
        "name": "Gemini 2.5 Pro",
        "api_key_env": "GOOGLE_API_KEY",
        "context_window": 1000000,
    },
    "gemini-2.5-flash": {
        "provider": ModelProvider.GOOGLE,
        "name": "Gemini 2.5 Flash",
        "api_key_env": "GOOGLE_API_KEY",
        "context_window": 1000000,
    },
    # Gemini 3.0 models
    "gemini-3.0-thinking": {
        "provider": ModelProvider.GOOGLE,
        "name": "Gemini 3.0 Thinking",
        "api_key_env": "GOOGLE_API_KEY",
        "context_window": 2000000,
    },
    "gemini-3.0-pro": {
        "provider": ModelProvider.GOOGLE,
        "name": "Gemini 3.0 Pro",
        "api_key_env": "GOOGLE_API_KEY",
        "context_window": 2000000,
    },
    "gemini-3-flash-preview": {
        "provider": ModelProvider.GOOGLE,
        "name": "Gemini 3 Flash Preview",
        "api_key_env": "GOOGLE_API_KEY",
        "context_window": 1000000,
    },
    # Kimi (Moonshot AI) models
    "kimi-k2": {
        "provider": ModelProvider.KIMI,
        "name": "Kimi K2",
        "api_key_env": "KIMI_API_KEY",
        "context_window": 128000,
    },
    "kimi-k2-0905": {
        "provider": ModelProvider.KIMI,
        "name": "Kimi K2 (0905)",
        "api_key_env": "KIMI_API_KEY",
        "context_window": 128000,
    },
    "kimi-k2-thinking": {
        "provider": ModelProvider.KIMI,
        "name": "Kimi K2 Thinking",
        "api_key_env": "KIMI_API_KEY",
        "context_window": 128000,
    },
}


class ModelRegistry:
    """Registry for managing supported models."""
    
    def __init__(self):
        self._models = dict(BUILTIN_MODELS)
        self._custom_models: dict[str, dict[str, Any]] = {}
    
    @property
    def all_models(self) -> dict[str, dict[str, Any]]:
        """Get all registered models (builtin + custom)."""
        return {**self._models, **self._custom_models}
    
    @property
    def model_ids(self) -> list[str]:
        """Get list of all model IDs."""
        return list(self.all_models.keys())
    
    def add_custom_model(
        self,
        model_id: str,
        name: str,
        provider: ModelProvider = ModelProvider.CUSTOM,
        api_key_env: str | None = None,
        context_window: int = 128000,
    ) -> None:
        """Add a custom model to the registry."""
        self._custom_models[model_id] = {
            "provider": provider,
            "name": name,
            "api_key_env": api_key_env,
            "context_window": context_window,
        }
    
    def get_model(self, model_id: str) -> dict[str, Any] | None:
        """Get model metadata by ID."""
        return self.all_models.get(model_id)
    
    def is_valid(self, model_id: str) -> bool:
        """Check if a model ID is valid."""
        return model_id in self.all_models
    
    def list_by_provider(self, provider: ModelProvider) -> list[str]:
        """List all models for a given provider."""
        return [
            mid for mid, meta in self.all_models.items()
            if meta["provider"] == provider
        ]


# Global model registry instance
MODEL_REGISTRY = ModelRegistry()


def get_supported_models() -> list[str]:
    """Get list of all supported model IDs."""
    return MODEL_REGISTRY.model_ids


def add_custom_model(
    model_id: str,
    name: str,
    provider: str = "custom",
    api_key_env: str | None = None,
) -> None:
    """Add a custom model to the registry."""
    MODEL_REGISTRY.add_custom_model(
        model_id=model_id,
        name=name,
        provider=ModelProvider(provider) if provider in [p.value for p in ModelProvider] else ModelProvider.CUSTOM,
        api_key_env=api_key_env,
    )


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
    model: str = Field(default="claude-sonnet-4-20250514")
    temperature: float = Field(default=0.0)
    max_tokens: int = Field(default=4096)
    num_evaluations: int = Field(default=1, description="Number of evaluations to average")
    timeout_seconds: int = Field(default=120, description="API call timeout")
    fallback_to_heuristic: bool = Field(default=True, description="Use heuristic if LLM fails")
    provider: str = Field(default="auto", description="LLM provider: auto, anthropic, google, openai")


class CustomModelConfig(BaseModel):
    """Configuration for a custom model."""
    
    id: str = Field(description="Unique model identifier")
    name: str = Field(description="Human-readable model name")
    provider: str = Field(default="custom", description="Provider: anthropic, openai, google, custom")
    api_key_env: str | None = Field(default=None, description="Environment variable for API key")
    context_window: int = Field(default=128000, description="Context window size")


class AgentConfig(BaseModel):
    """Configuration for the AI agent being benchmarked."""

    id: str = Field(default="claude-code", description="Agent identifier for results tracking")
    type: str = Field(
        default="claude",
        description="Agent type: claude, openai, gemini, custom",
    )
    model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model to use for the agent",
    )
    api_key_env: str | None = Field(
        default=None,
        description="Environment variable containing the API key (auto-detected from model if not set)",
    )
    max_iterations: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum agent iterations per task",
    )
    timeout_seconds: int = Field(
        default=1800,
        ge=60,
        description="Timeout per task in seconds",
    )

    # Optional agent-specific settings
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=8192, ge=256)
    system_prompt: str | None = Field(
        default=None,
        description="Custom system prompt for the agent",
    )
    
    @model_validator(mode="after")
    def resolve_api_key_env(self) -> "AgentConfig":
        """Auto-detect API key env from model if not explicitly set."""
        if self.api_key_env is None:
            model_meta = MODEL_REGISTRY.get_model(self.model)
            if model_meta:
                self.api_key_env = model_meta.get("api_key_env")
        return self
    
    def get_model_info(self) -> dict[str, Any] | None:
        """Get metadata for the configured model."""
        return MODEL_REGISTRY.get_model(self.model)
    
    def is_model_supported(self) -> bool:
        """Check if the configured model is in the registry."""
        return MODEL_REGISTRY.is_valid(self.model)


class BenchmarkConfig(BaseModel):
    """Main configuration for SF-AgentBench."""

    # Paths
    tasks_dir: Path = Field(default=Path("tasks"))
    results_dir: Path = Field(default=Path("results"))
    logs_dir: Path = Field(default=Path("logs"))

    # Agent configuration
    agent: AgentConfig = Field(default_factory=AgentConfig)
    
    # Custom models (added to the registry on load)
    custom_models: list[CustomModelConfig] = Field(
        default_factory=list,
        description="Custom models to add to the registry",
    )

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
    
    @model_validator(mode="after")
    def register_custom_models(self) -> "BenchmarkConfig":
        """Register any custom models defined in the config."""
        for cm in self.custom_models:
            MODEL_REGISTRY.add_custom_model(
                model_id=cm.id,
                name=cm.name,
                provider=ModelProvider(cm.provider) if cm.provider in [p.value for p in ModelProvider] else ModelProvider.CUSTOM,
                api_key_env=cm.api_key_env,
                context_window=cm.context_window,
            )
        return self

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
