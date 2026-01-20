"""Data models for SF-AgentBench."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TaskTier(str, Enum):
    """Task difficulty tiers aligned with Salesforce certifications."""

    TIER_1 = "tier-1"  # Single-domain, declarative focus (Admin basics)
    TIER_2 = "tier-2"  # Multi-domain, declarative + simple code
    TIER_3 = "tier-3"  # Complex code, async processing, integrations (PD1)
    TIER_4 = "tier-4"  # Full-stack, LWC, external integrations (PD2)


class TaskCategory(str, Enum):
    """Categories of Salesforce development skills."""

    SCHEMA = "schema"
    VALIDATION = "validation"
    FLOW = "flow"
    APEX_TRIGGER = "apex-trigger"
    APEX_CLASS = "apex-class"
    APEX_TEST = "apex-test"
    APEX_ASYNC = "apex-async"
    APEX_REST = "apex-rest"
    LWC = "lwc"
    SECURITY = "security"
    INTEGRATION = "integration"


class DeploymentStatus(str, Enum):
    """Status of a metadata deployment."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


class TestStatus(str, Enum):
    """Status of an Apex test run."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


class Task(BaseModel):
    """A benchmark task definition."""

    id: str = Field(..., description="Unique task identifier")
    name: str = Field(..., description="Human-readable task name")
    description: str = Field(..., description="Task description/requirements")
    tier: TaskTier = Field(..., description="Difficulty tier")
    categories: list[TaskCategory] = Field(default_factory=list, description="Skill categories")
    path: Path = Field(..., description="Path to task directory")
    time_limit_minutes: int = Field(default=30, description="Time limit for task completion")
    
    # Scratch org configuration
    scratch_def_path: Path | None = Field(
        default=None, description="Path to project-scratch-def.json"
    )
    requires_data: bool = Field(default=False, description="Whether task requires data import")
    data_plan_path: Path | None = Field(default=None, description="Path to data import plan")
    
    # Evaluation configuration
    evaluation_tests: list[str] = Field(
        default_factory=list, description="Apex test classes for evaluation"
    )
    expected_metadata_path: Path | None = Field(
        default=None, description="Path to expected metadata for diffing"
    )

    class Config:
        use_enum_values = True


class DeploymentError(BaseModel):
    """A deployment error from Salesforce."""

    component_type: str = Field(..., description="Metadata component type")
    component_name: str = Field(..., description="Component name")
    line: int | None = Field(default=None, description="Line number of error")
    column: int | None = Field(default=None, description="Column number of error")
    message: str = Field(..., description="Error message")
    error_code: str | None = Field(default=None, description="Salesforce error code")


class DeploymentResult(BaseModel):
    """Result of a metadata deployment."""

    status: DeploymentStatus
    deployed_count: int = Field(default=0, description="Number of components deployed")
    failed_count: int = Field(default=0, description="Number of components failed")
    errors: list[DeploymentError] = Field(default_factory=list)
    duration_seconds: float = Field(default=0.0)


class TestMethodResult(BaseModel):
    """Result of a single test method."""

    class_name: str
    method_name: str
    status: TestStatus
    message: str | None = Field(default=None)
    stack_trace: str | None = Field(default=None)
    duration_ms: float = Field(default=0.0)


class ApexTestResult(BaseModel):
    """Result of running Apex tests."""

    total_tests: int = Field(default=0)
    passed: int = Field(default=0)
    failed: int = Field(default=0)
    skipped: int = Field(default=0)
    pass_rate: float = Field(default=0.0)
    code_coverage: float = Field(default=0.0, description="Overall code coverage percentage")
    test_results: list[TestMethodResult] = Field(default_factory=list)
    duration_seconds: float = Field(default=0.0)


class PMDViolation(BaseModel):
    """A PMD/Code Analyzer violation."""

    rule: str = Field(..., description="PMD rule name")
    severity: str = Field(..., description="Violation severity (critical/high/medium/low)")
    file: str = Field(..., description="File path")
    line: int = Field(..., description="Line number")
    column: int | None = Field(default=None)
    message: str = Field(..., description="Violation message")


class StaticAnalysisResult(BaseModel):
    """Result of static code analysis."""

    total_violations: int = Field(default=0)
    critical_count: int = Field(default=0)
    high_count: int = Field(default=0)
    medium_count: int = Field(default=0)
    low_count: int = Field(default=0)
    violations: list[PMDViolation] = Field(default_factory=list)
    penalty_score: float = Field(
        default=0.0, description="Calculated penalty based on violations"
    )


class MetadataDiffResult(BaseModel):
    """Result of metadata comparison."""

    is_match: bool = Field(default=False)
    accuracy_score: float = Field(default=0.0, description="0.0 to 1.0")
    missing_components: list[str] = Field(default_factory=list)
    extra_components: list[str] = Field(default_factory=list)
    differences: dict[str, Any] = Field(default_factory=dict)


class RubricCriterion(BaseModel):
    """A single rubric criterion evaluation."""

    name: str
    weight: float
    score: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(default="")


class RubricResult(BaseModel):
    """Result of LLM-as-a-Judge rubric evaluation."""

    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    criteria: list[RubricCriterion] = Field(default_factory=list)
    feedback: str = Field(default="")


class EvaluationResult(BaseModel):
    """Complete evaluation result for a task."""

    # Layer 1: Deployment
    deployment: DeploymentResult | None = Field(default=None)
    deployment_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Layer 2: Functional Testing
    apex_tests: ApexTestResult | None = Field(default=None)
    test_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Layer 3: Static Analysis
    static_analysis: StaticAnalysisResult | None = Field(default=None)
    static_analysis_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Layer 4: Metadata Diffing
    metadata_diff: MetadataDiffResult | None = Field(default=None)
    metadata_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Layer 5: Rubric
    rubric: RubricResult | None = Field(default=None)
    rubric_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Composite
    final_score: float = Field(default=0.0, ge=0.0, le=1.0)

    def calculate_final_score(
        self,
        deployment_weight: float = 0.20,
        test_weight: float = 0.40,
        static_weight: float = 0.10,
        metadata_weight: float = 0.15,
        rubric_weight: float = 0.15,
    ) -> float:
        """Calculate the weighted final score."""
        self.final_score = (
            deployment_weight * self.deployment_score
            + test_weight * self.test_score
            + static_weight * self.static_analysis_score
            + metadata_weight * self.metadata_score
            + rubric_weight * self.rubric_score
        )
        return self.final_score


class ScratchOrgInfo(BaseModel):
    """Information about a Scratch Org."""

    org_id: str = Field(..., description="Salesforce Org ID")
    username: str = Field(..., description="Scratch org username")
    instance_url: str = Field(..., description="Org instance URL")
    login_url: str | None = Field(default=None, description="Login URL for browser access")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = Field(default=None)
    status: str = Field(default="active")


class TaskResult(BaseModel):
    """Complete result of running a task."""

    task_id: str
    task_name: str
    agent_id: str = Field(..., description="Identifier of the agent that ran the task")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)
    duration_seconds: float = Field(default=0.0)
    scratch_org: ScratchOrgInfo | None = Field(default=None)
    evaluation: EvaluationResult = Field(default_factory=EvaluationResult)
    agent_output: str = Field(default="", description="Raw agent output/logs")
    error: str | None = Field(default=None, description="Error if task failed to complete")

    @property
    def is_complete(self) -> bool:
        """Check if the task completed successfully."""
        return self.completed_at is not None and self.error is None
