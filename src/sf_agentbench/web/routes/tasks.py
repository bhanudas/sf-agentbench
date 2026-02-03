"""API routes for tasks and models."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from sf_agentbench.web.schemas import (
    TaskResponse,
    TaskDetailResponse,
    TaskListResponse,
    ModelResponse,
    ModelListResponse,
    ConfigResponse,
)

router = APIRouter(tags=["tasks"])


# =============================================================================
# Dependencies
# =============================================================================


def get_config():
    """Get the benchmark configuration."""
    from sf_agentbench.config import load_config

    return load_config()


def get_task_loader():
    """Get the task loader instance."""
    from sf_agentbench.harness import TaskLoader
    from sf_agentbench.config import load_config

    config = load_config()
    return TaskLoader(config.tasks_dir)


# =============================================================================
# Task Routes
# =============================================================================


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    tier: Annotated[str | None, Query(description="Filter by tier")] = None,
    category: Annotated[str | None, Query(description="Filter by category")] = None,
    loader=Depends(get_task_loader),
):
    """List all available benchmark tasks."""
    from sf_agentbench.models import TaskTier, TaskCategory

    tasks = loader.discover_tasks()

    # Apply filters
    if tier:
        try:
            tier_enum = TaskTier(tier)
            tasks = [t for t in tasks if t.tier == tier_enum]
        except ValueError:
            pass  # Invalid tier, return all

    if category:
        try:
            cat_enum = TaskCategory(category)
            tasks = [t for t in tasks if cat_enum in t.categories]
        except ValueError:
            pass  # Invalid category, return all

    return TaskListResponse(
        tasks=[
            TaskResponse(
                id=t.id,
                name=t.name,
                description=t.description,
                tier=t.tier.value if hasattr(t.tier, "value") else str(t.tier),
                categories=[
                    c.value if hasattr(c, "value") else str(c) for c in t.categories
                ],
                time_limit_minutes=t.time_limit_minutes,
            )
            for t in tasks
        ],
        total=len(tasks),
    )


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str, loader=Depends(get_task_loader)):
    """Get detailed information about a specific task."""
    task = loader.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    readme = loader.get_task_readme(task)

    return TaskDetailResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        tier=task.tier.value if hasattr(task.tier, "value") else str(task.tier),
        categories=[
            c.value if hasattr(c, "value") else str(c) for c in task.categories
        ],
        time_limit_minutes=task.time_limit_minutes,
        readme=readme,
        evaluation_tests=task.evaluation_tests,
        requires_data=task.requires_data,
    )


# =============================================================================
# Model Routes
# =============================================================================


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    provider: Annotated[str | None, Query(description="Filter by provider")] = None,
):
    """List all supported AI models."""
    import os
    from sf_agentbench.config import MODEL_REGISTRY, ModelProvider

    models = []
    all_models = MODEL_REGISTRY.all_models

    for model_id, meta in all_models.items():
        # Filter by provider if specified
        if provider and meta["provider"].value != provider:
            continue

        # Check if API key is available
        api_key_env = meta.get("api_key_env", "")
        is_available = bool(os.getenv(api_key_env)) if api_key_env else False

        models.append(
            ModelResponse(
                id=model_id,
                name=meta.get("name", model_id),
                provider=meta["provider"].value,
                api_key_env=api_key_env,
                context_window=meta.get("context_window", 0),
                is_available=is_available,
            )
        )

    return ModelListResponse(models=models, total=len(models))


@router.get("/models/{model_id}", response_model=ModelResponse)
async def get_model(model_id: str):
    """Get details of a specific AI model."""
    import os
    from sf_agentbench.config import MODEL_REGISTRY

    all_models = MODEL_REGISTRY.all_models
    if model_id not in all_models:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")

    meta = all_models[model_id]
    api_key_env = meta.get("api_key_env", "")
    is_available = bool(os.getenv(api_key_env)) if api_key_env else False

    return ModelResponse(
        id=model_id,
        name=meta.get("name", model_id),
        provider=meta["provider"].value,
        api_key_env=api_key_env,
        context_window=meta.get("context_window", 0),
        is_available=is_available,
    )


# =============================================================================
# CLI Agents Routes
# =============================================================================


@router.get("/agents")
async def list_cli_agents():
    """List available CLI-based AI agents."""
    from sf_agentbench.agents.cli_runner import CLI_AGENTS, get_available_cli_agents

    available = get_available_cli_agents()

    agents = []
    for agent_id, config in CLI_AGENTS.items():
        agents.append(
            {
                "id": agent_id,
                "name": config.name,
                "default_model": config.default_model or "default",
                "is_installed": agent_id in available,
                "command": config.command[0] if config.command else "",
            }
        )

    return {"agents": agents, "total": len(agents)}


# =============================================================================
# Configuration Routes
# =============================================================================


@router.get("/config", response_model=ConfigResponse)
async def get_config_info(config=Depends(get_config)):
    """Get current configuration settings."""
    return ConfigResponse(
        devhub_username=config.devhub_username,
        tasks_dir=str(config.tasks_dir),
        results_dir=str(config.results_dir),
        evaluation_weights={
            "deployment": config.evaluation_weights.deployment,
            "functional_tests": config.evaluation_weights.functional_tests,
            "static_analysis": config.evaluation_weights.static_analysis,
            "metadata_diff": config.evaluation_weights.metadata_diff,
            "rubric": config.evaluation_weights.rubric,
        },
        default_model=config.agent.model if config.agent else None,
    )
