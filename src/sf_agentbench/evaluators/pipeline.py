"""Main evaluation pipeline orchestrating all evaluation layers."""

from pathlib import Path

from rich.console import Console

from sf_agentbench.config import BenchmarkConfig
from sf_agentbench.evaluators.deployment import DeploymentEvaluator
from sf_agentbench.evaluators.functional import FunctionalTestEvaluator
from sf_agentbench.evaluators.static_analysis import StaticAnalysisEvaluator
from sf_agentbench.evaluators.metadata_diff import MetadataDiffEvaluator
from sf_agentbench.evaluators.rubric import RubricEvaluator
from sf_agentbench.models import EvaluationResult, Task

console = Console()


class EvaluationPipeline:
    """
    Orchestrates the 5-layer evaluation pipeline.

    Layers:
    1. Deployment Validation - Can the solution deploy?
    2. Functional Testing - Do Apex tests pass?
    3. Static Analysis - Code quality via PMD
    4. Metadata Diffing - Configuration accuracy
    5. Rubric Evaluation - LLM-as-a-Judge
    """

    def __init__(
        self,
        config: BenchmarkConfig,
        target_org: str | None = None,
        project_dir: Path | None = None,
    ):
        self.config = config

        # Initialize evaluators
        self.deployment = DeploymentEvaluator(
            sf_cli_path=config.sf_cli_path,
            target_org=target_org,
            project_dir=project_dir,
            verbose=config.verbose,
        )

        self.functional = FunctionalTestEvaluator(
            sf_cli_path=config.sf_cli_path,
            target_org=target_org,
            project_dir=project_dir,
            verbose=config.verbose,
        )

        self.static_analysis = StaticAnalysisEvaluator(
            sf_cli_path=config.sf_cli_path,
            target_org=target_org,
            project_dir=project_dir,
            pmd_config=config.pmd,
            verbose=config.verbose,
        )

        self.metadata_diff = MetadataDiffEvaluator(
            sf_cli_path=config.sf_cli_path,
            target_org=target_org,
            project_dir=project_dir,
            verbose=config.verbose,
        )

        self.rubric = RubricEvaluator(
            rubric_config=config.rubric,
            verbose=config.verbose,
        )

    def evaluate(self, task: Task, work_dir: Path) -> EvaluationResult:
        """
        Run the complete evaluation pipeline.

        Args:
            task: The benchmark task being evaluated
            work_dir: Working directory containing agent's solution

        Returns:
            Complete EvaluationResult with all layer scores
        """
        result = EvaluationResult()

        # Layer 1: Deployment Validation
        deployment_result, deployment_score = self.deployment.evaluate(task, work_dir)
        result.deployment = deployment_result
        result.deployment_score = deployment_score

        # Only continue if deployment succeeded
        if deployment_score < 1.0:
            console.print("  [yellow]Deployment failed, skipping remaining layers[/yellow]")
            return result

        # Layer 2: Functional Testing
        test_result, test_score = self.functional.evaluate(task, work_dir)
        result.apex_tests = test_result
        result.test_score = test_score

        # Layer 3: Static Analysis
        static_result, static_score = self.static_analysis.evaluate(task, work_dir)
        result.static_analysis = static_result
        result.static_analysis_score = static_score

        # Layer 4: Metadata Diffing
        diff_result, diff_score = self.metadata_diff.evaluate(task, work_dir)
        result.metadata_diff = diff_result
        result.metadata_score = diff_score

        # Layer 5: Rubric Evaluation
        rubric_result, rubric_score = self.rubric.evaluate(task, work_dir)
        result.rubric = rubric_result
        result.rubric_score = rubric_score

        return result
