"""Layer 3: Static Code Analysis Evaluator."""

from pathlib import Path

from rich.console import Console

from sf_agentbench.aci import SFScanCode
from sf_agentbench.config import PMDConfig
from sf_agentbench.models import (
    StaticAnalysisResult,
    PMDViolation,
    Task,
)

console = Console()


class StaticAnalysisEvaluator:
    """Evaluates code quality using PMD/Salesforce Code Analyzer."""

    def __init__(
        self,
        sf_cli_path: str = "sf",
        target_org: str | None = None,
        project_dir: Path | None = None,
        pmd_config: PMDConfig | None = None,
        verbose: bool = False,
    ):
        self.sf_cli_path = sf_cli_path
        self.target_org = target_org
        self.project_dir = project_dir
        self.pmd_config = pmd_config or PMDConfig()
        self.verbose = verbose

    def evaluate(self, task: Task, work_dir: Path) -> tuple[StaticAnalysisResult, float]:
        """
        Run static code analysis.

        Args:
            task: The benchmark task
            work_dir: Working directory with agent's solution

        Returns:
            Tuple of (StaticAnalysisResult, score)
        """
        console.print("  [dim]Layer 3: Static Code Analysis[/dim]")

        if not self.pmd_config.enabled:
            console.print("    [dim]Skipped (disabled)[/dim]")
            return StaticAnalysisResult(), 1.0

        scanner = SFScanCode(
            sf_cli_path=self.sf_cli_path,
            target_org=self.target_org,
            project_dir=work_dir,
            verbose=self.verbose,
        )

        result = scanner.execute(
            target="force-app",
            severity_threshold=1,
        )

        if result.data:
            data = result.data
            violations = [
                PMDViolation(
                    rule=v.get("rule", "Unknown"),
                    severity=v.get("severity", "medium"),
                    file=v.get("file", "Unknown"),
                    line=v.get("line", 0),
                    column=v.get("column"),
                    message=v.get("message", ""),
                )
                for v in data.get("violations", [])
            ]

            analysis_result = StaticAnalysisResult(
                total_violations=data.get("total_violations", 0),
                critical_count=data.get("critical_count", 0),
                high_count=data.get("high_count", 0),
                medium_count=data.get("medium_count", 0),
                low_count=data.get("low_count", 0),
                violations=violations,
                penalty_score=data.get("penalty_score", 0.0),
            )

            # Calculate score (1.0 - penalty, capped)
            penalty = min(analysis_result.penalty_score, self.pmd_config.max_penalty)
            score = 1.0 - penalty

            if analysis_result.total_violations == 0:
                console.print("    [green]✓ No violations found[/green]")
            else:
                console.print(
                    f"    [yellow]Found {analysis_result.total_violations} violations "
                    f"(penalty: {penalty*100:.1f}%)[/yellow]"
                )

                if self.verbose:
                    # Show critical/high violations
                    for v in violations:
                        if v.severity in ("critical", "high"):
                            console.print(
                                f"      [dim]{v.severity}: {v.rule} at {v.file}:{v.line}[/dim]"
                            )

        else:
            # Scanner not available or error
            analysis_result = StaticAnalysisResult()
            score = 1.0
            console.print("    [dim]Scanner not available, skipping[/dim]")

        return analysis_result, score
