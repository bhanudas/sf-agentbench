"""Layer 1: Deployment Validation Evaluator."""

from pathlib import Path
from typing import Any

from rich.console import Console

from sf_agentbench.aci import SFDeploy
from sf_agentbench.models import (
    DeploymentResult,
    DeploymentStatus,
    DeploymentError,
    Task,
)

console = Console()


class DeploymentEvaluator:
    """Evaluates whether agent's solution can be successfully deployed."""

    def __init__(
        self,
        sf_cli_path: str = "sf",
        target_org: str | None = None,
        project_dir: Path | None = None,
        verbose: bool = False,
    ):
        self.sf_cli_path = sf_cli_path
        self.target_org = target_org
        self.project_dir = project_dir
        self.verbose = verbose

    def evaluate(self, task: Task, work_dir: Path) -> tuple[DeploymentResult, float]:
        """
        Evaluate deployment of agent's solution.

        Args:
            task: The benchmark task
            work_dir: Working directory with agent's solution

        Returns:
            Tuple of (DeploymentResult, score)
        """
        console.print("  [dim]Layer 1: Deployment Validation[/dim]")

        deployer = SFDeploy(
            sf_cli_path=self.sf_cli_path,
            target_org=self.target_org,
            project_dir=work_dir,
            verbose=self.verbose,
        )

        # Try deployment with retry for transient SF CLI errors
        result = deployer.execute(
            source_path="force-app",
            wait_minutes=10,
            ignore_warnings=False,
            ignore_conflicts=True,
        )

        # Handle known SF CLI bugs (version 2.5.8 locale error)
        if not result.success:
            error_msgs = [str(e.get("message", "")) for e in result.errors]
            is_cli_bug = any("locale" in msg or "Finalizing" in msg for msg in error_msgs)
            
            if is_cli_bug:
                # Retry once for transient SF CLI issues
                import time
                time.sleep(2)
                result = deployer.execute(
                    source_path="force-app",
                    wait_minutes=10,
                    ignore_warnings=False,
                    ignore_conflicts=True,
                )

        if result.success:
            deployment = DeploymentResult(
                status=DeploymentStatus.SUCCESS,
                deployed_count=result.data.get("deployed_count", 0),
                failed_count=0,
                errors=[],
                duration_seconds=0.0,  # Could parse from result
            )
            score = 1.0
            console.print("    [green]✓ Deployment successful[/green]")
        else:
            errors = [
                DeploymentError(
                    component_type=e.get("component_type", "Unknown"),
                    component_name=e.get("component_name", "Unknown"),
                    line=e.get("line"),
                    column=e.get("column"),
                    message=e.get("message", "Unknown error"),
                    error_code=e.get("error_code"),
                )
                for e in result.errors
            ]

            deployment = DeploymentResult(
                status=DeploymentStatus.FAILURE,
                deployed_count=0,
                failed_count=len(errors),
                errors=errors,
            )
            score = 0.0
            console.print(f"    [red]✗ Deployment failed ({len(errors)} errors)[/red]")

            if self.verbose:
                for error in errors[:5]:  # Show first 5 errors
                    console.print(f"      [dim]{error.component_name}: {error.message}[/dim]")

        return deployment, score
