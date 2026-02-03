"""Layer 2: Functional Testing Evaluator."""

from pathlib import Path

from rich.console import Console

from sf_agentbench.aci import SFRunApexTests
from sf_agentbench.models import (
    ApexTestResult,
    TestMethodResult,
    TestStatus,
    Task,
)

console = Console()


class FunctionalTestEvaluator:
    """Evaluates agent's solution using Apex tests."""

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

    def evaluate(self, task: Task, work_dir: Path) -> tuple[ApexTestResult, float]:
        """
        Run evaluation Apex tests.

        Args:
            task: The benchmark task
            work_dir: Working directory with agent's solution

        Returns:
            Tuple of (ApexTestResult, score)
        """
        console.print("  [dim]Layer 2: Functional Testing[/dim]")

        runner = SFRunApexTests(
            sf_cli_path=self.sf_cli_path,
            target_org=self.target_org,
            project_dir=work_dir,
            verbose=self.verbose,
        )

        # Run specified evaluation tests or all local tests
        if task.evaluation_tests:
            result = runner.execute(
                test_classes=task.evaluation_tests,
                code_coverage=True,
            )
        else:
            result = runner.execute(
                test_level="RunLocalTests",
                code_coverage=True,
            )

        if result.success and result.data:
            data = result.data
            test_results = [
                TestMethodResult(
                    class_name=t.get("class_name", "Unknown"),
                    method_name=t.get("method_name", "Unknown"),
                    status=TestStatus(t.get("status", "fail")),
                    message=t.get("message"),
                    stack_trace=t.get("stack_trace"),
                    duration_ms=t.get("duration_ms", 0),
                )
                for t in data.get("test_results", [])
            ]

            apex_result = ApexTestResult(
                total_tests=data.get("total_tests", 0),
                passed=data.get("passed", 0),
                failed=data.get("failed", 0),
                skipped=data.get("skipped", 0),
                pass_rate=data.get("pass_rate", 0.0),
                code_coverage=data.get("code_coverage_percent", 0.0),
                test_results=test_results,
            )

            score = apex_result.pass_rate
            console.print(
                f"    [{'green' if score >= 0.75 else 'yellow'}]"
                f"Tests: {apex_result.passed}/{apex_result.total_tests} passed "
                f"({score*100:.1f}%)[/]"
            )

            if apex_result.code_coverage > 0:
                console.print(f"    [dim]Code coverage: {apex_result.code_coverage:.1f}%[/dim]")

        else:
            # No tests ran or error
            apex_result = ApexTestResult(
                total_tests=0,
                passed=0,
                failed=0,
                skipped=0,
                pass_rate=0.0,
            )
            score = 0.0
            console.print("    [red]✗ Test execution failed[/red]")

            if self.verbose and result.errors:
                for error in result.errors[:3]:
                    console.print(f"      [dim]{error}[/dim]")

        return apex_result, score
