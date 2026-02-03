"""Tests for SF-AgentBench models."""

import pytest
from datetime import datetime

from sf_agentbench.models import (
    Task,
    TaskTier,
    TaskCategory,
    TaskResult,
    EvaluationResult,
    DeploymentResult,
    DeploymentStatus,
    ApexTestResult,
    StaticAnalysisResult,
    RubricResult,
    ScratchOrgInfo,
)


class TestTask:
    """Tests for Task model."""

    def test_task_creation(self, tmp_path):
        """Test creating a Task."""
        task = Task(
            id="test-task",
            name="Test Task",
            description="A test task",
            tier=TaskTier.TIER_1,
            categories=[TaskCategory.APEX_CLASS, TaskCategory.APEX_TEST],
            path=tmp_path,
        )

        assert task.id == "test-task"
        assert task.tier == TaskTier.TIER_1
        assert len(task.categories) == 2
        assert task.time_limit_minutes == 30  # default

    def test_task_with_custom_time_limit(self, tmp_path):
        """Test Task with custom time limit."""
        task = Task(
            id="quick-task",
            name="Quick Task",
            description="A quick task",
            tier=TaskTier.TIER_2,
            path=tmp_path,
            time_limit_minutes=15,
        )

        assert task.time_limit_minutes == 15


class TestEvaluationResult:
    """Tests for EvaluationResult model."""

    def test_default_scores(self):
        """Test default evaluation scores are zero."""
        result = EvaluationResult()

        assert result.deployment_score == 0.0
        assert result.test_score == 0.0
        assert result.static_analysis_score == 0.0
        assert result.metadata_score == 0.0
        assert result.rubric_score == 0.0
        assert result.final_score == 0.0

    def test_calculate_final_score(self):
        """Test final score calculation with weights."""
        result = EvaluationResult(
            deployment_score=1.0,
            test_score=0.8,
            static_analysis_score=0.9,
            metadata_score=1.0,
            rubric_score=0.7,
        )

        score = result.calculate_final_score()

        # 0.20*1.0 + 0.40*0.8 + 0.10*0.9 + 0.15*1.0 + 0.15*0.7
        expected = 0.20 + 0.32 + 0.09 + 0.15 + 0.105
        assert abs(score - expected) < 0.001

    def test_calculate_final_score_custom_weights(self):
        """Test final score with custom weights."""
        result = EvaluationResult(
            deployment_score=1.0,
            test_score=1.0,
            static_analysis_score=1.0,
            metadata_score=1.0,
            rubric_score=1.0,
        )

        score = result.calculate_final_score(
            deployment_weight=0.5,
            test_weight=0.5,
            static_weight=0.0,
            metadata_weight=0.0,
            rubric_weight=0.0,
        )

        assert score == 1.0


class TestTaskResult:
    """Tests for TaskResult model."""

    def test_task_result_creation(self):
        """Test creating a TaskResult."""
        result = TaskResult(
            task_id="test-task",
            task_name="Test Task",
            agent_id="claude-code",
        )

        assert result.task_id == "test-task"
        assert result.agent_id == "claude-code"
        assert result.started_at is not None
        assert result.completed_at is None
        assert not result.is_complete

    def test_task_result_completion(self):
        """Test TaskResult completion status."""
        result = TaskResult(
            task_id="test-task",
            task_name="Test Task",
            agent_id="test-agent",
            completed_at=datetime.utcnow(),
        )

        assert result.is_complete

    def test_task_result_with_error(self):
        """Test TaskResult with error is not complete."""
        result = TaskResult(
            task_id="test-task",
            task_name="Test Task",
            agent_id="test-agent",
            completed_at=datetime.utcnow(),
            error="Deployment failed",
        )

        assert not result.is_complete


class TestDeploymentResult:
    """Tests for DeploymentResult model."""

    def test_successful_deployment(self):
        """Test successful deployment result."""
        result = DeploymentResult(
            status=DeploymentStatus.SUCCESS,
            deployed_count=15,
            failed_count=0,
        )

        assert result.status == DeploymentStatus.SUCCESS
        assert result.deployed_count == 15

    def test_failed_deployment(self):
        """Test failed deployment result."""
        result = DeploymentResult(
            status=DeploymentStatus.FAILURE,
            deployed_count=0,
            failed_count=3,
        )

        assert result.status == DeploymentStatus.FAILURE
        assert result.failed_count == 3


class TestApexTestResult:
    """Tests for ApexTestResult model."""

    def test_apex_test_result(self):
        """Test Apex test result."""
        result = ApexTestResult(
            total_tests=10,
            passed=8,
            failed=2,
            pass_rate=0.8,
            code_coverage=85.5,
        )

        assert result.total_tests == 10
        assert result.pass_rate == 0.8
        assert result.code_coverage == 85.5


class TestStaticAnalysisResult:
    """Tests for StaticAnalysisResult model."""

    def test_static_analysis_result(self):
        """Test static analysis result."""
        result = StaticAnalysisResult(
            total_violations=5,
            critical_count=0,
            high_count=1,
            medium_count=3,
            low_count=1,
            penalty_score=0.05,
        )

        assert result.total_violations == 5
        assert result.penalty_score == 0.05


class TestScratchOrgInfo:
    """Tests for ScratchOrgInfo model."""

    def test_scratch_org_info(self):
        """Test ScratchOrgInfo model."""
        org = ScratchOrgInfo(
            org_id="00D123456789012",
            username="test@scratch.org",
            instance_url="https://test.salesforce.com",
        )

        assert org.org_id == "00D123456789012"
        assert org.status == "active"
