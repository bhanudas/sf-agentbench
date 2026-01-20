"""Layer 5: LLM-as-a-Judge Rubric Evaluator."""

import json
from pathlib import Path
from typing import Any

from rich.console import Console

from sf_agentbench.config import RubricConfig
from sf_agentbench.models import RubricResult, RubricCriterion, Task

console = Console()


# Default rubric for Salesforce development evaluation
DEFAULT_RUBRIC = [
    {
        "name": "Correct Use of Async Apex",
        "weight": 0.20,
        "description": (
            "Did the agent use Queueable, Batchable, or Future methods where appropriate? "
            "Are long-running operations handled asynchronously?"
        ),
    },
    {
        "name": "Bulkification",
        "weight": 0.25,
        "description": (
            "Are DML and SOQL operations performed on collections rather than single records? "
            "Are there any queries or DML inside loops?"
        ),
    },
    {
        "name": "Test Quality",
        "weight": 0.20,
        "description": (
            "Do the tests use System.assert effectively? "
            "Are edge cases and bulk scenarios covered? "
            "Is there positive and negative testing?"
        ),
    },
    {
        "name": "Code Readability",
        "weight": 0.15,
        "description": (
            "Are variables named clearly and descriptively? "
            "Is logic separated into helper methods? "
            "Are comments used appropriately?"
        ),
    },
    {
        "name": "Security Best Practices",
        "weight": 0.20,
        "description": (
            "Are CRUD/FLS checks present when needed? "
            "Are hardcoded IDs avoided? "
            "Is user input properly validated?"
        ),
    },
]


class RubricEvaluator:
    """Evaluates solution quality using LLM-as-a-Judge approach."""

    def __init__(
        self,
        rubric_config: RubricConfig | None = None,
        rubric: list[dict[str, Any]] | None = None,
        verbose: bool = False,
    ):
        self.config = rubric_config or RubricConfig()
        self.rubric = rubric or DEFAULT_RUBRIC
        self.verbose = verbose

    def evaluate(self, task: Task, work_dir: Path) -> tuple[RubricResult, float]:
        """
        Evaluate solution using LLM-as-a-Judge.

        Args:
            task: The benchmark task
            work_dir: Working directory with agent's solution

        Returns:
            Tuple of (RubricResult, score)
        """
        console.print("  [dim]Layer 5: Rubric Evaluation (LLM-as-a-Judge)[/dim]")

        if not self.config.enabled:
            console.print("    [dim]Skipped (disabled)[/dim]")
            return RubricResult(overall_score=1.0), 1.0

        # Collect code for evaluation
        code_content = self._collect_code(work_dir)

        if not code_content:
            console.print("    [dim]No code found to evaluate[/dim]")
            return RubricResult(overall_score=0.5), 0.5

        # Get task requirements
        requirements = self._get_requirements(task, work_dir)

        try:
            # Call LLM for evaluation
            result = self._evaluate_with_llm(
                code=code_content,
                requirements=requirements,
                rubric=self.rubric,
            )

            console.print(f"    Rubric score: {result.overall_score*100:.1f}%")

            if self.verbose:
                for criterion in result.criteria:
                    console.print(
                        f"      - {criterion.name}: {criterion.score*100:.0f}%"
                    )

            return result, result.overall_score

        except Exception as e:
            console.print(f"    [yellow]LLM evaluation failed: {e}[/yellow]")
            # Return neutral score on failure
            return RubricResult(overall_score=0.5), 0.5

    def _collect_code(self, work_dir: Path) -> str:
        """Collect all relevant code from work directory."""
        code_parts = []
        force_app = work_dir / "force-app"

        if not force_app.exists():
            return ""

        # Collect Apex classes and triggers
        for pattern in ["**/*.cls", "**/*.trigger"]:
            for f in force_app.glob(pattern):
                if "-meta.xml" not in f.name:
                    content = f.read_text()
                    code_parts.append(f"// File: {f.name}\n{content}")

        # Collect LWC JavaScript
        for f in force_app.glob("**/*.js"):
            content = f.read_text()
            code_parts.append(f"// File: {f.name}\n{content}")

        return "\n\n".join(code_parts)

    def _get_requirements(self, task: Task, work_dir: Path) -> str:
        """Get task requirements for context."""
        readme_path = work_dir / "README.md"
        if readme_path.exists():
            return readme_path.read_text()
        return task.description

    def _evaluate_with_llm(
        self,
        code: str,
        requirements: str,
        rubric: list[dict[str, Any]],
    ) -> RubricResult:
        """
        Call LLM to evaluate code against rubric.

        This is a placeholder that can be implemented with various LLM providers.
        For now, it returns a simulated evaluation.
        """
        # Build the prompt
        prompt = self._build_evaluation_prompt(code, requirements, rubric)

        # Try to call LLM (placeholder - implement with actual provider)
        try:
            response = self._call_llm(prompt)
            return self._parse_llm_response(response, rubric)
        except Exception:
            # Fall back to heuristic evaluation
            return self._heuristic_evaluation(code, rubric)

    def _build_evaluation_prompt(
        self,
        code: str,
        requirements: str,
        rubric: list[dict[str, Any]],
    ) -> str:
        """Build the evaluation prompt for the LLM."""
        rubric_text = "\n".join(
            f"{i+1}. {r['name']} (weight: {r['weight']}): {r['description']}"
            for i, r in enumerate(rubric)
        )

        return f"""You are an expert Salesforce developer evaluating code quality.

## Task Requirements:
{requirements}

## Code to Evaluate:
```
{code[:10000]}  # Truncate if too long
```

## Evaluation Rubric:
{rubric_text}

## Instructions:
Evaluate the code against each criterion in the rubric. For each criterion:
1. Assign a score from 0.0 to 1.0
2. Provide brief reasoning

Return your evaluation as JSON in this format:
{{
    "criteria": [
        {{
            "name": "Criterion Name",
            "score": 0.85,
            "reasoning": "Brief explanation"
        }}
    ],
    "overall_feedback": "Summary of evaluation"
}}
"""

    def _call_llm(self, prompt: str) -> str:
        """
        Call LLM API.

        This is a placeholder - implement with your preferred LLM provider:
        - Anthropic Claude
        - OpenAI GPT-4
        - Google Gemini
        - etc.
        """
        # Placeholder: Try to use httpx if API key is available
        import os

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            import httpx

            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.config.model,
                    "max_tokens": self.config.max_tokens,
                    "temperature": self.config.temperature,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

        raise NotImplementedError("LLM API not configured")

    def _parse_llm_response(
        self, response: str, rubric: list[dict[str, Any]]
    ) -> RubricResult:
        """Parse LLM response into RubricResult."""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")

            criteria = []
            for item in data.get("criteria", []):
                criteria.append(
                    RubricCriterion(
                        name=item.get("name", "Unknown"),
                        weight=self._get_weight(item.get("name", ""), rubric),
                        score=float(item.get("score", 0.5)),
                        reasoning=item.get("reasoning", ""),
                    )
                )

            # Calculate weighted overall score
            if criteria:
                total_weight = sum(c.weight for c in criteria)
                overall = sum(c.score * c.weight for c in criteria) / total_weight
            else:
                overall = 0.5

            return RubricResult(
                overall_score=overall,
                criteria=criteria,
                feedback=data.get("overall_feedback", ""),
            )

        except Exception as e:
            console.print(f"    [dim]Failed to parse LLM response: {e}[/dim]")
            return RubricResult(overall_score=0.5)

    def _get_weight(self, name: str, rubric: list[dict[str, Any]]) -> float:
        """Get weight for a criterion by name."""
        for r in rubric:
            if r["name"].lower() == name.lower():
                return r["weight"]
        return 0.2  # Default weight

    def _heuristic_evaluation(
        self, code: str, rubric: list[dict[str, Any]]
    ) -> RubricResult:
        """
        Perform heuristic code evaluation when LLM is unavailable.

        This is a simple rule-based evaluation as fallback.
        """
        criteria = []
        code_lower = code.lower()

        # Check for bulkification issues
        soql_in_loop = (
            "for(" in code_lower or "for (" in code_lower
        ) and "[select" in code_lower
        dml_in_loop = any(
            op in code_lower
            for op in ["insert ", "update ", "delete ", "upsert "]
        ) and ("for(" in code_lower or "for (" in code_lower)

        bulkification_score = 1.0
        if soql_in_loop:
            bulkification_score -= 0.4
        if dml_in_loop:
            bulkification_score -= 0.4

        criteria.append(
            RubricCriterion(
                name="Bulkification",
                weight=0.25,
                score=max(0, bulkification_score),
                reasoning="Heuristic check for SOQL/DML in loops",
            )
        )

        # Check for async patterns
        has_async = any(
            pattern in code_lower
            for pattern in ["queueable", "batchable", "schedulable", "@future"]
        )
        criteria.append(
            RubricCriterion(
                name="Correct Use of Async Apex",
                weight=0.20,
                score=0.8 if has_async else 0.5,
                reasoning="Checked for async patterns",
            )
        )

        # Check for test quality
        has_asserts = "system.assert" in code_lower
        has_test_annotation = "@istest" in code_lower
        test_score = 0.3
        if has_test_annotation:
            test_score += 0.3
        if has_asserts:
            test_score += 0.4

        criteria.append(
            RubricCriterion(
                name="Test Quality",
                weight=0.20,
                score=test_score,
                reasoning="Checked for test annotations and assertions",
            )
        )

        # Check for security
        has_crud_check = any(
            pattern in code_lower
            for pattern in ["isdeletable", "iscreateable", "isupdateable", "isaccessible"]
        )
        has_hardcoded_id = "001" in code or "003" in code  # Common ID prefixes

        security_score = 0.6
        if has_crud_check:
            security_score += 0.3
        if has_hardcoded_id:
            security_score -= 0.3

        criteria.append(
            RubricCriterion(
                name="Security Best Practices",
                weight=0.20,
                score=max(0, min(1, security_score)),
                reasoning="Checked for CRUD/FLS and hardcoded IDs",
            )
        )

        # Code readability (basic check)
        has_comments = "//" in code or "/*" in code
        avg_line_length = sum(len(line) for line in code.split("\n")) / max(
            1, len(code.split("\n"))
        )
        readability_score = 0.5
        if has_comments:
            readability_score += 0.2
        if avg_line_length < 100:
            readability_score += 0.2

        criteria.append(
            RubricCriterion(
                name="Code Readability",
                weight=0.15,
                score=min(1, readability_score),
                reasoning="Checked for comments and line length",
            )
        )

        # Calculate overall
        overall = sum(c.score * c.weight for c in criteria) / sum(c.weight for c in criteria)

        return RubricResult(
            overall_score=overall,
            criteria=criteria,
            feedback="Evaluated using heuristic rules (LLM not available)",
        )
