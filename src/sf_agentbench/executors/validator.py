"""Unified validator for test results.

Validates and scores results from all test types.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from sf_agentbench.domain.models import WorkUnit, Result, TestType
from sf_agentbench.judges.base import Rubric, JudgeResult
from sf_agentbench.judges.claude_judge import ClaudeJudge
from sf_agentbench.judges.logging import JudgeLogStore, JudgeLogConfig

console = Console()


@dataclass
class ValidationResult:
    """Result of validating a work unit."""
    
    work_unit_id: str
    test_type: TestType
    
    # Scores
    automated_score: float = 0.0  # From tests/deployment
    rubric_score: float = 0.0  # From LLM judge
    final_score: float = 0.0  # Combined
    
    # Components
    deployment_score: float = 0.0
    test_score: float = 0.0
    static_analysis_score: float = 0.0
    
    # Judge result
    judge_result: JudgeResult | None = None
    
    # Details
    details: dict[str, Any] = field(default_factory=dict)
    
    def calculate_final_score(
        self,
        automated_weight: float = 0.7,
        rubric_weight: float = 0.3,
    ) -> float:
        """Calculate the final combined score.
        
        Args:
            automated_weight: Weight for automated scores
            rubric_weight: Weight for rubric score
        
        Returns:
            Final score between 0 and 1
        """
        self.final_score = (
            self.automated_score * automated_weight +
            self.rubric_score * rubric_weight
        )
        return self.final_score


class Validator:
    """Unified validator for all test types.
    
    Combines automated testing with LLM judge evaluation.
    """
    
    def __init__(
        self,
        rubrics_dir: Path | None = None,
        judge_log_store: JudgeLogStore | None = None,
        use_judge: bool = True,
        judge_model: str = "claude-opus-4-20250514",
        verbose: bool = False,
    ):
        """Initialize the validator.
        
        Args:
            rubrics_dir: Directory containing rubric YAML files
            judge_log_store: Store for judge logs
            use_judge: Whether to use LLM judge
            judge_model: Model to use for judging
            verbose: Enable verbose output
        """
        self.rubrics_dir = rubrics_dir or Path("rubrics")
        self.judge_log_store = judge_log_store
        self.use_judge = use_judge
        self.judge_model = judge_model
        self.verbose = verbose
        
        # Load rubrics
        self._rubrics: dict[str, Rubric] = {}
        self._load_rubrics()
    
    def _load_rubrics(self) -> None:
        """Load rubrics from the rubrics directory."""
        if not self.rubrics_dir.exists():
            return
        
        for yaml_path in self.rubrics_dir.glob("*.yaml"):
            try:
                rubric = Rubric.from_yaml(yaml_path)
                self._rubrics[rubric.name] = rubric
                if self.verbose:
                    console.print(f"[dim]Loaded rubric: {rubric.name}[/dim]")
            except Exception as e:
                console.print(f"[yellow]Failed to load rubric {yaml_path}: {e}[/yellow]")
    
    def get_rubric(self, name: str) -> Rubric | None:
        """Get a rubric by name."""
        return self._rubrics.get(name)
    
    def list_rubrics(self) -> list[str]:
        """List available rubric names."""
        return list(self._rubrics.keys())
    
    def validate(
        self,
        work_unit: WorkUnit,
        code: str | None = None,
        work_dir: Path | None = None,
        rubric_name: str = "Salesforce Best Practices",
    ) -> ValidationResult:
        """Validate a completed work unit.
        
        Args:
            work_unit: The work unit to validate
            code: Code to evaluate (for rubric scoring)
            work_dir: Working directory with the solution
            rubric_name: Name of the rubric to use
        
        Returns:
            ValidationResult with scores
        """
        result = ValidationResult(
            work_unit_id=work_unit.id,
            test_type=work_unit.test.type,
        )
        
        if work_unit.test.type == TestType.QA:
            # Q&A validation is just the accuracy from execution
            if work_unit.result:
                result.automated_score = work_unit.result.score
                result.test_score = work_unit.result.score
            result.final_score = result.automated_score
            
        elif work_unit.test.type == TestType.CODING:
            # Coding validation combines automated + rubric
            if work_unit.result:
                result.deployment_score = work_unit.result.deployment_score
                result.test_score = work_unit.result.test_score
                result.static_analysis_score = work_unit.result.static_analysis_score
                
                # Calculate automated score
                result.automated_score = (
                    result.deployment_score * 0.4 +
                    result.test_score * 0.4 +
                    result.static_analysis_score * 0.2
                )
            
            # Run LLM judge if enabled
            if self.use_judge and code:
                result.rubric_score, result.judge_result = self._run_judge(
                    work_unit,
                    code,
                    rubric_name,
                )
            
            result.calculate_final_score()
        
        return result
    
    def _run_judge(
        self,
        work_unit: WorkUnit,
        code: str,
        rubric_name: str,
    ) -> tuple[float, JudgeResult | None]:
        """Run the LLM judge on the code.
        
        Args:
            work_unit: The work unit being validated
            code: The code to evaluate
            rubric_name: Name of the rubric to use
        
        Returns:
            Tuple of (score, JudgeResult)
        """
        rubric = self._rubrics.get(rubric_name)
        if not rubric:
            if self.verbose:
                console.print(f"[yellow]Rubric not found: {rubric_name}[/yellow]")
            return 0.0, None
        
        # Get requirements from the test
        requirements = ""
        if hasattr(work_unit.test, 'config'):
            requirements = work_unit.test.config.get("requirements", "")
        
        try:
            judge = ClaudeJudge(
                model=self.judge_model,
                verbose=self.verbose,
            )
            
            result = judge.evaluate(
                code=code,
                requirements=requirements,
                rubric=rubric,
                agent_id=work_unit.agent.id,
            )
            
            # Log the result
            if self.judge_log_store:
                self.judge_log_store.log(work_unit.id, result)
            
            return result.overall_score, result
            
        except Exception as e:
            console.print(f"[red]Judge error: {e}[/red]")
            return 0.0, None
    
    def validate_batch(
        self,
        work_units: list[WorkUnit],
        rubric_name: str = "Salesforce Best Practices",
    ) -> list[ValidationResult]:
        """Validate multiple work units.
        
        Args:
            work_units: List of work units to validate
            rubric_name: Rubric to use for coding tests
        
        Returns:
            List of validation results
        """
        results = []
        
        for work_unit in work_units:
            # Get code from work directory if available
            code = None
            if work_unit.work_dir:
                code = self._collect_code(work_unit.work_dir)
            
            result = self.validate(
                work_unit=work_unit,
                code=code,
                work_dir=work_unit.work_dir,
                rubric_name=rubric_name,
            )
            results.append(result)
        
        return results
    
    def _collect_code(self, work_dir: Path) -> str:
        """Collect all relevant code from a working directory.
        
        Args:
            work_dir: The working directory
        
        Returns:
            Combined code as a string
        """
        code_parts = []
        
        # Collect Apex classes
        for cls_file in work_dir.rglob("*.cls"):
            try:
                content = cls_file.read_text()
                code_parts.append(f"// {cls_file.name}\n{content}")
            except Exception:
                pass
        
        # Collect Flow metadata
        for flow_file in work_dir.rglob("*.flow-meta.xml"):
            try:
                content = flow_file.read_text()
                code_parts.append(f"<!-- {flow_file.name} -->\n{content}")
            except Exception:
                pass
        
        # Collect LWC
        for js_file in work_dir.rglob("*.js"):
            if "node_modules" not in str(js_file):
                try:
                    content = js_file.read_text()
                    code_parts.append(f"// {js_file.name}\n{content}")
                except Exception:
                    pass
        
        return "\n\n".join(code_parts)
