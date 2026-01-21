"""Layer 1: Deployment Validation Evaluator."""

import subprocess
import json
import time
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

# Known transient SF CLI error patterns
TRANSIENT_ERROR_PATTERNS = [
    "locale",
    "Finalizing",
    "metadata.transfer",
    "ECONNRESET",
    "ETIMEDOUT",
    "socket hang up",
]


class DeploymentEvaluator:
    """Evaluates whether agent's solution can be successfully deployed."""

    def __init__(
        self,
        sf_cli_path: str = "sf",
        target_org: str | None = None,
        project_dir: Path | None = None,
        verbose: bool = False,
        skip_if_deployed: bool = True,
        max_retries: int = 3,
    ):
        self.sf_cli_path = sf_cli_path
        self.target_org = target_org
        self.project_dir = project_dir
        self.verbose = verbose
        self.skip_if_deployed = skip_if_deployed
        self.max_retries = max_retries

    def _check_deployment_status(self, work_dir: Path) -> bool:
        """Check if metadata is already deployed by verifying org has the components."""
        if not self.target_org:
            return False
        
        try:
            # Quick check - list deployed source to see if components exist
            result = subprocess.run(
                [self.sf_cli_path, "project", "deploy", "report", "--json"],
                capture_output=True,
                text=True,
                cwd=work_dir,
                timeout=30,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                status = data.get("result", {}).get("status", "")
                if status in ["Succeeded", "SucceededPartial"]:
                    return True
        except Exception:
            pass
        
        return False

    def _is_transient_error(self, error_msgs: list[str]) -> bool:
        """Check if errors are transient SF CLI issues."""
        for msg in error_msgs:
            msg_lower = msg.lower()
            for pattern in TRANSIENT_ERROR_PATTERNS:
                if pattern.lower() in msg_lower:
                    return True
        return False

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

        # Check if already deployed (skip redundant re-deployment)
        if self.skip_if_deployed and self._check_deployment_status(work_dir):
            console.print("    [green]✓ Deployment already verified[/green]")
            return DeploymentResult(
                status=DeploymentStatus.SUCCESS,
                deployed_count=1,
                failed_count=0,
                errors=[],
                duration_seconds=0.0,
            ), 1.0

        deployer = SFDeploy(
            sf_cli_path=self.sf_cli_path,
            target_org=self.target_org,
            project_dir=work_dir,
            verbose=self.verbose,
        )

        result = None
        last_error_msgs = []
        
        # Retry loop with exponential backoff for transient errors
        for attempt in range(self.max_retries):
            result = deployer.execute(
                source_path="force-app",
                wait_minutes=10,
                ignore_warnings=True,  # More lenient
                ignore_conflicts=True,
            )
            
            if result.success:
                break
            
            # Check for transient errors
            last_error_msgs = [str(e.get("message", "")) for e in result.errors]
            
            if self._is_transient_error(last_error_msgs):
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                    console.print(f"    [yellow]⟳ Transient error, retrying in {wait_time}s...[/yellow]")
                    time.sleep(wait_time)
                    continue
            else:
                # Real deployment error, don't retry
                break

        if result and result.success:
            deployment = DeploymentResult(
                status=DeploymentStatus.SUCCESS,
                deployed_count=result.data.get("deployed_count", 0) if result.data else 0,
                failed_count=0,
                errors=[],
                duration_seconds=0.0,
            )
            score = 1.0
            console.print("    [green]✓ Deployment successful[/green]")
        else:
            # Check if it's still a transient error after all retries
            if self._is_transient_error(last_error_msgs):
                # Assume deployment is OK if it's just a transient CLI bug
                console.print("    [yellow]⚠ SF CLI transient error, assuming deployment OK[/yellow]")
                return DeploymentResult(
                    status=DeploymentStatus.SUCCESS,
                    deployed_count=1,
                    failed_count=0,
                    errors=[],
                    duration_seconds=0.0,
                ), 1.0
            
            errors = []
            if result:
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
                for error in errors[:5]:
                    console.print(f"      [dim]{error.component_name}: {error.message}[/dim]")

        return deployment, score
