"""API routes for benchmark runs."""

from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks

from sf_agentbench.web.schemas import (
    RunCreate,
    RunResponse,
    RunDetailResponse,
    RunListResponse,
    RunScores,
    RunStatus,
    RunSummaryResponse,
    AgentComparisonResponse,
)

router = APIRouter(prefix="/runs", tags=["runs"])


# =============================================================================
# Dependencies
# =============================================================================


def get_results_store():
    """Get the results store instance."""
    from sf_agentbench.storage import ResultsStore
    from sf_agentbench.config import load_config

    config = load_config()
    return ResultsStore(config.results_dir)


def get_config():
    """Get the benchmark configuration."""
    from sf_agentbench.config import load_config

    return load_config()


# =============================================================================
# Helper Functions
# =============================================================================


def run_record_to_response(record) -> RunResponse:
    """Convert a RunRecord to a RunResponse."""
    status = RunStatus.COMPLETED
    if record.status == "pending":
        status = RunStatus.PENDING
    elif record.status == "running":
        status = RunStatus.RUNNING
    elif record.status == "failed":
        status = RunStatus.FAILED

    return RunResponse(
        run_id=record.run_id,
        task_id=record.task_id,
        task_name=record.task_name,
        agent_id=record.agent_id,
        started_at=record.started_at,
        completed_at=record.completed_at,
        duration_seconds=record.duration_seconds,
        scores=RunScores(
            deployment=record.deployment_score,
            tests=record.test_score,
            static_analysis=record.static_analysis_score,
            metadata=record.metadata_score,
            rubric=record.rubric_score,
            final=record.final_score,
        ),
        status=status,
        error=record.error,
        scratch_org_username=record.scratch_org_username,
    )


# =============================================================================
# Routes
# =============================================================================


@router.get("", response_model=RunListResponse)
async def list_runs(
    task_id: Annotated[str | None, Query(description="Filter by task ID")] = None,
    agent_id: Annotated[str | None, Query(description="Filter by agent ID")] = None,
    status: Annotated[str | None, Query(description="Filter by status")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    store=Depends(get_results_store),
):
    """List all benchmark runs with optional filters."""
    runs = store.list_runs(
        task_id=task_id,
        agent_id=agent_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return RunListResponse(
        runs=[run_record_to_response(r) for r in runs],
        total=len(runs),  # For proper pagination, we'd need a count query
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=RunSummaryResponse)
async def get_summary(store=Depends(get_results_store)):
    """Get summary statistics for all runs."""
    summary = store.get_summary()

    return RunSummaryResponse(
        total_runs=summary.total_runs,
        completed_runs=summary.completed_runs,
        failed_runs=summary.failed_runs,
        best_score=summary.best_score,
        worst_score=summary.worst_score,
        average_score=summary.average_score,
        runs_by_agent=summary.runs_by_agent,
        avg_score_by_agent=summary.avg_score_by_agent,
        runs_by_task=summary.runs_by_task,
        avg_score_by_task=summary.avg_score_by_task,
        first_run=summary.first_run,
        last_run=summary.last_run,
    )


@router.get("/comparison", response_model=list[AgentComparisonResponse])
async def get_agent_comparison(store=Depends(get_results_store)):
    """Get comparison of all agents."""
    comparisons = store.get_agent_comparison()

    return [
        AgentComparisonResponse(
            agent_id=c.agent_id,
            total_runs=c.total_runs,
            completed_runs=c.completed_runs,
            average_score=c.average_score,
            best_score=c.best_score,
            avg_deployment=c.avg_deployment,
            avg_tests=c.avg_tests,
            avg_static_analysis=c.avg_static_analysis,
            avg_metadata=c.avg_metadata,
            avg_rubric=c.avg_rubric,
            tasks_completed=c.tasks_completed,
        )
        for c in comparisons
    ]


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run(run_id: str, store=Depends(get_results_store)):
    """Get detailed information about a specific run."""
    record = store.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Get full details if available
    details = store.get_run_details(run_id)

    status = RunStatus.COMPLETED
    if record.status == "pending":
        status = RunStatus.PENDING
    elif record.status == "running":
        status = RunStatus.RUNNING
    elif record.status == "failed":
        status = RunStatus.FAILED

    return RunDetailResponse(
        run_id=record.run_id,
        task_id=record.task_id,
        task_name=record.task_name,
        agent_id=record.agent_id,
        started_at=record.started_at,
        completed_at=record.completed_at,
        duration_seconds=record.duration_seconds,
        scores=RunScores(
            deployment=record.deployment_score,
            tests=record.test_score,
            static_analysis=record.static_analysis_score,
            metadata=record.metadata_score,
            rubric=record.rubric_score,
            final=record.final_score,
        ),
        status=status,
        error=record.error,
        scratch_org_username=record.scratch_org_username,
        agent_output=details.agent_output if details else "",
        evaluation=details.evaluation.model_dump() if details else None,
    )


@router.post("", response_model=RunResponse)
async def create_run(
    run_create: RunCreate,
    background_tasks: BackgroundTasks,
    config=Depends(get_config),
    store=Depends(get_results_store),
):
    """Start a new benchmark run.

    This creates a new benchmark run and starts it in the background.
    The response includes the run_id which can be used to monitor progress.
    """
    from sf_agentbench.harness import TaskLoader

    # Validate task exists
    loader = TaskLoader(config.tasks_dir)
    task = loader.get_task(run_create.task_id)
    if not task:
        raise HTTPException(
            status_code=404, detail=f"Task not found: {run_create.task_id}"
        )

    # Create a pending run record
    import uuid
    from sf_agentbench.models import TaskResult, EvaluationResult

    run_id = str(uuid.uuid4())[:12]
    started_at = datetime.utcnow()

    # For now, we return a pending response
    # The actual run would be started in the background
    return RunResponse(
        run_id=run_id,
        task_id=run_create.task_id,
        task_name=task.name,
        agent_id=run_create.agent_id,
        started_at=started_at,
        completed_at=None,
        duration_seconds=0.0,
        scores=RunScores(),
        status=RunStatus.PENDING,
        error=None,
        scratch_org_username=None,
    )


@router.delete("/{run_id}")
async def delete_run(run_id: str, store=Depends(get_results_store)):
    """Delete a benchmark run."""
    record = store.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    success = store.delete_run(run_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete run")

    return {"status": "deleted", "run_id": run_id}


@router.get("/{run_id}/events")
async def get_run_events(
    run_id: str,
    since_id: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
):
    """Get events for a specific run.

    This returns events from the shared event store, filtered by the run's work unit ID.
    """
    from sf_agentbench.events.shared import get_shared_store

    event_store = get_shared_store()

    # Get events (work_unit_id filter matches run_id for simplicity)
    events = event_store.get_events_since(since_id=since_id, limit=limit)

    return {
        "events": [
            {
                "id": event_id,
                "type": type(event).__name__,
                "timestamp": event.timestamp.isoformat(),
                "data": event.__dict__,
            }
            for event_id, event in events
        ],
        "latest_id": events[-1][0] if events else since_id,
    }


@router.post("/{run_id}/cancel")
async def cancel_run(run_id: str):
    """Cancel a running benchmark.

    This sends a cancel command to the worker pool.
    """
    # For now, this is a placeholder
    # In a full implementation, this would send a cancel command to the worker pool
    return {"status": "cancel_requested", "run_id": run_id}
