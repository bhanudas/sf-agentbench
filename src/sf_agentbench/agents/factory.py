"""Factory for creating AI agents based on configuration."""

from sf_agentbench.agents.base import BaseAgent
from sf_agentbench.agents.claude import ClaudeAgent
from sf_agentbench.agents.openai import OpenAIAgent
from sf_agentbench.agents.gemini import GeminiAgent
from sf_agentbench.agents.kimi import KimiAgent
from sf_agentbench.config import AgentConfig, MODEL_REGISTRY, ModelProvider


def create_agent(config: AgentConfig, verbose: bool = False) -> BaseAgent:
    """
    Create an agent based on configuration.
    
    Args:
        config: Agent configuration
        verbose: Enable verbose output
        
    Returns:
        Configured agent instance
    """
    model_meta = MODEL_REGISTRY.get_model(config.model)
    
    # Determine provider from model metadata or config type
    if model_meta:
        provider = model_meta["provider"]
    else:
        # Fallback to config.type
        provider_map = {
            "claude": ModelProvider.ANTHROPIC,
            "anthropic": ModelProvider.ANTHROPIC,
            "openai": ModelProvider.OPENAI,
            "gpt": ModelProvider.OPENAI,
            "gemini": ModelProvider.GOOGLE,
            "google": ModelProvider.GOOGLE,
            "kimi": ModelProvider.KIMI,
            "moonshot": ModelProvider.KIMI,
        }
        provider = provider_map.get(config.type.lower(), ModelProvider.CUSTOM)
    
    # Get API key env
    api_key_env = config.api_key_env
    if not api_key_env and model_meta:
        api_key_env = model_meta.get("api_key_env")
    
    # Create appropriate agent
    if provider == ModelProvider.ANTHROPIC:
        return ClaudeAgent(
            model=config.model,
            api_key_env=api_key_env or "ANTHROPIC_API_KEY",
            max_iterations=config.max_iterations,
            timeout_seconds=config.timeout_seconds,
            verbose=verbose,
        )
    elif provider == ModelProvider.OPENAI:
        return OpenAIAgent(
            model=config.model,
            api_key_env=api_key_env or "OPENAI_API_KEY",
            max_iterations=config.max_iterations,
            timeout_seconds=config.timeout_seconds,
            verbose=verbose,
        )
    elif provider == ModelProvider.GOOGLE:
        return GeminiAgent(
            model=config.model,
            api_key_env=api_key_env or "GOOGLE_API_KEY",
            max_iterations=config.max_iterations,
            timeout_seconds=config.timeout_seconds,
            verbose=verbose,
        )
    elif provider == ModelProvider.KIMI:
        return KimiAgent(
            model=config.model,
            api_key_env=api_key_env or "KIMI_API_KEY",
            max_iterations=config.max_iterations,
            timeout_seconds=config.timeout_seconds,
            verbose=verbose,
        )
    else:
        # Default to Claude for custom/unknown
        return ClaudeAgent(
            model=config.model,
            api_key_env=api_key_env or "ANTHROPIC_API_KEY",
            max_iterations=config.max_iterations,
            timeout_seconds=config.timeout_seconds,
            verbose=verbose,
        )
