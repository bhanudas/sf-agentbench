"""API routes for Q&A benchmark runs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks

from sf_agentbench.web.schemas import (
    QARunCreate,
    QARunResponse,
    QARunDetailResponse,
    QARunListResponse,
    QAQuestionResponse,
    QAModelComparisonResponse,
    QADomainAnalysisResponse,
    TestBankResponse,
    TestBankListResponse,
)

router = APIRouter(prefix="/qa", tags=["qa"])


# =============================================================================
# Dependencies
# =============================================================================


def get_qa_store():
    """Get the Q&A results store instance."""
    from sf_agentbench.qa import QAResultsStore
    from sf_agentbench.config import load_config

    config = load_config()
    return QAResultsStore(config.results_dir)


def get_test_bank_loader():
    """Get the test bank loader instance."""
    from sf_agentbench.qa import TestBankLoader

    return TestBankLoader()


# =============================================================================
# Helper Functions
# =============================================================================


def dict_to_qa_run_response(record: dict) -> QARunResponse:
    """Convert a Q&A run dict to a QARunResponse."""
    return QARunResponse(
        run_id=record["run_id"],
        model_id=record["model_id"],
        cli_id=record["cli_id"],
        test_bank_id=record["test_bank_id"],
        test_bank_name=record.get("test_bank_name"),
        started_at=record["started_at"],
        completed_at=record.get("completed_at"),
        total_questions=record.get("total_questions", 0),
        correct_answers=record.get("correct_answers", 0),
        accuracy=record.get("accuracy", 0.0),
        duration_seconds=record.get("duration_seconds", 0.0),
        status=record.get("status", "unknown"),
    )


# =============================================================================
# Test Bank Routes
# =============================================================================


@router.get("/banks", response_model=TestBankListResponse)
async def list_test_banks(loader=Depends(get_test_bank_loader)):
    """List available Q&A test banks."""
    bank_files = loader.list_available()

    banks = []
    for bank_file in bank_files:
        try:
            bank = loader.load(bank_file)
            banks.append(
                TestBankResponse(
                    id=bank.id,
                    name=bank.name,
                    description=bank.description,
                    question_count=len(bank.questions),
                    domains=bank.domains,
                )
            )
        except Exception:
            # Skip banks that fail to load
            pass

    return TestBankListResponse(banks=banks, total=len(banks))


@router.get("/banks/{bank_id}", response_model=TestBankResponse)
async def get_test_bank(bank_id: str, loader=Depends(get_test_bank_loader)):
    """Get details of a specific test bank."""
    bank_files = loader.list_available()

    for bank_file in bank_files:
        try:
            bank = loader.load(bank_file)
            if bank.id == bank_id or bank_file == bank_id:
                return TestBankResponse(
                    id=bank.id,
                    name=bank.name,
                    description=bank.description,
                    question_count=len(bank.questions),
                    domains=bank.domains,
                )
        except Exception:
            continue

    raise HTTPException(status_code=404, detail=f"Test bank not found: {bank_id}")


# =============================================================================
# Q&A Run Routes
# =============================================================================


@router.get("/runs", response_model=QARunListResponse)
async def list_qa_runs(
    model_id: Annotated[str | None, Query(description="Filter by model ID")] = None,
    test_bank_id: Annotated[
        str | None, Query(description="Filter by test bank ID")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    store=Depends(get_qa_store),
):
    """List all Q&A benchmark runs with optional filters."""
    runs = store.list_runs(
        model_id=model_id,
        test_bank_id=test_bank_id,
        limit=limit,
    )

    return QARunListResponse(
        runs=[dict_to_qa_run_response(r) for r in runs],
        total=len(runs),
    )


@router.get("/runs/{run_id}", response_model=QARunDetailResponse)
async def get_qa_run(run_id: str, store=Depends(get_qa_store)):
    """Get detailed information about a specific Q&A run."""
    record = store.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Q&A run not found: {run_id}")

    # Get questions for this run
    questions_data = store.get_run_questions(run_id)

    questions = [
        QAQuestionResponse(
            question_id=str(q["question_id"]),
            domain=q.get("domain", ""),
            difficulty=q.get("difficulty", ""),
            question_text=q.get("question_text", ""),
            correct_answer=q.get("correct_answer", ""),
            model_response=q.get("model_response", ""),
            extracted_answer=q.get("extracted_answer", ""),
            is_correct=bool(q.get("is_correct", False)),
            response_time=q.get("response_time", 0.0),
            timestamp=q.get("timestamp", ""),
        )
        for q in questions_data
    ]

    return QARunDetailResponse(
        run_id=record["run_id"],
        model_id=record["model_id"],
        cli_id=record["cli_id"],
        test_bank_id=record["test_bank_id"],
        test_bank_name=record.get("test_bank_name"),
        started_at=record["started_at"],
        completed_at=record.get("completed_at"),
        total_questions=record.get("total_questions", 0),
        correct_answers=record.get("correct_answers", 0),
        accuracy=record.get("accuracy", 0.0),
        duration_seconds=record.get("duration_seconds", 0.0),
        status=record.get("status", "unknown"),
        questions=questions,
    )


@router.post("/runs", response_model=QARunResponse)
async def create_qa_run(
    run_create: QARunCreate,
    background_tasks: BackgroundTasks,
    store=Depends(get_qa_store),
    loader=Depends(get_test_bank_loader),
):
    """Start a new Q&A benchmark run.

    This creates a new Q&A run and starts it in the background.
    """
    # Validate test bank exists
    bank_files = loader.list_available()
    test_bank = None
    for bank_file in bank_files:
        try:
            bank = loader.load(bank_file)
            if bank.id == run_create.test_bank_id or bank_file == run_create.test_bank_id:
                test_bank = bank
                break
        except Exception:
            continue

    if not test_bank:
        raise HTTPException(
            status_code=404, detail=f"Test bank not found: {run_create.test_bank_id}"
        )

    # Start the run
    run_id = store.start_run(
        model_id=run_create.model,
        cli_id="api",
        test_bank_id=test_bank.id,
        test_bank_name=test_bank.name,
    )

    # In a full implementation, we would start the Q&A runner in the background
    # background_tasks.add_task(run_qa_benchmark, run_id, run_create, test_bank)

    return QARunResponse(
        run_id=run_id,
        model_id=run_create.model,
        cli_id="api",
        test_bank_id=test_bank.id,
        test_bank_name=test_bank.name,
        started_at="",
        completed_at=None,
        total_questions=0,
        correct_answers=0,
        accuracy=0.0,
        duration_seconds=0.0,
        status="running",
    )


# =============================================================================
# Analysis Routes
# =============================================================================


@router.get("/comparison", response_model=list[QAModelComparisonResponse])
async def get_model_comparison(
    test_bank_id: Annotated[
        str | None, Query(description="Filter by test bank ID")
    ] = None,
    store=Depends(get_qa_store),
):
    """Compare model performance on Q&A tests."""
    comparison = store.get_model_comparison(test_bank_id=test_bank_id)

    return [
        QAModelComparisonResponse(
            model_id=m["model_id"],
            run_count=m.get("run_count", 0),
            avg_accuracy=m.get("avg_accuracy", 0.0),
            best_accuracy=m.get("best_accuracy", 0.0),
            avg_duration=m.get("avg_duration", 0.0),
            total_questions=m.get("total_questions", 0),
            total_correct=m.get("total_correct", 0),
        )
        for m in comparison
    ]


@router.get("/domains", response_model=list[QADomainAnalysisResponse])
async def get_domain_analysis(
    model_id: Annotated[str | None, Query(description="Filter by model ID")] = None,
    test_bank_id: Annotated[
        str | None, Query(description="Filter by test bank ID")
    ] = None,
    store=Depends(get_qa_store),
):
    """Analyze Q&A performance by domain."""
    analysis = store.get_domain_analysis(model_id=model_id, test_bank_id=test_bank_id)

    return [
        QADomainAnalysisResponse(
            domain=d["domain"],
            model_id=d["model_id"],
            total_questions=d.get("total_questions", 0),
            correct_answers=d.get("correct_answers", 0),
            accuracy=d.get("accuracy", 0.0),
            avg_response_time=d.get("avg_response_time", 0.0),
        )
        for d in analysis
    ]


@router.get("/hardest", response_model=list[dict])
async def get_hardest_questions(
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    store=Depends(get_qa_store),
):
    """Get the hardest questions (lowest accuracy)."""
    return store.get_hardest_questions(limit=limit)
