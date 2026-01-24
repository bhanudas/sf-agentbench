"""Layer 5: LLM-as-a-Judge Rubric Evaluator."""

import json
import os
import re
from pathlib import Path
from typing import Any

from rich.console import Console

from sf_agentbench.config import RubricConfig, BUILTIN_MODELS, ModelProvider
from sf_agentbench.models import RubricResult, RubricCriterion, Task

console = Console()


def _get_api_key(provider: str) -> str | None:
    """Get API key for the given provider."""
    env_vars = {
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "openai": "OPENAI_API_KEY",
    }

    env_var = env_vars.get(provider.lower())
    if env_var:
        key = os.environ.get(env_var)
        if key:
            return key

    # Try to get from auth module
    try:
        if provider.lower() == "anthropic":
            from sf_agentbench.agents.auth import get_anthropic_credentials
            creds = get_anthropic_credentials()
            if creds:
                return creds.get("api_key") if isinstance(creds, dict) else creds
        elif provider.lower() == "google":
            from sf_agentbench.agents.auth import get_google_credentials
            creds = get_google_credentials()
            if creds:
                return creds.get("api_key") if isinstance(creds, dict) else creds
    except (ImportError, Exception):
        pass

    return None


def _detect_provider(model: str) -> str:
    """Auto-detect provider from model name."""
    model_info = BUILTIN_MODELS.get(model)
    if model_info:
        return model_info["provider"].value

    # Fallback to name-based detection
    model_lower = model.lower()
    if "claude" in model_lower:
        return "anthropic"
    elif "gemini" in model_lower:
        return "google"
    elif "gpt" in model_lower or "o1" in model_lower or "o3" in model_lower:
        return "openai"

    return "anthropic"  # Default


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
                    try:
                        content = f.read_text()
                        code_parts.append(f"// File: {f.name}\n{content}")
                    except Exception:
                        pass

        # Collect Flows
        for f in force_app.glob("**/flows/*.flow-meta.xml"):
            try:
                content = f.read_text()
                code_parts.append(f"<!-- File: {f.name} -->\n{content}")
            except Exception:
                pass

        # Collect Validation Rules
        for f in force_app.glob("**/validationRules/*.validationRule-meta.xml"):
            try:
                content = f.read_text()
                code_parts.append(f"<!-- File: {f.name} -->\n{content}")
            except Exception:
                pass

        # Collect LWC JavaScript
        for f in force_app.glob("**/*.js"):
            try:
                content = f.read_text()
                code_parts.append(f"// File: {f.name}\n{content}")
            except Exception:
                pass

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

        Supports multiple providers and has robust fallback behavior.
        """
        # Build the prompt
        prompt = self._build_evaluation_prompt(code, requirements, rubric)

        # Try to call LLM
        try:
            response = self._call_llm(prompt)
            result = self._parse_llm_response(response, rubric)
            result.feedback = f"Evaluated by LLM ({self.config.model}). {result.feedback}"
            console.print(f"    [green]LLM evaluation successful[/green]")
            return result
        except ValueError as e:
            # API key not configured
            console.print(f"    [yellow]LLM not configured: {e}[/yellow]")
            if getattr(self.config, "fallback_to_heuristic", True):
                console.print(f"    [dim]Falling back to heuristic evaluation[/dim]")
                return self._heuristic_evaluation(code, rubric)
            raise
        except Exception as e:
            # API call failed
            console.print(f"    [yellow]LLM API call failed: {e}[/yellow]")
            if getattr(self.config, "fallback_to_heuristic", True):
                console.print(f"    [dim]Falling back to heuristic evaluation[/dim]")
                return self._heuristic_evaluation(code, rubric)
            raise

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
        Call LLM API with support for multiple providers.

        Supports:
        - Anthropic Claude
        - Google Gemini
        - OpenAI GPT
        """
        import httpx

        # Determine provider
        provider = self.config.provider
        if provider == "auto":
            provider = _detect_provider(self.config.model)

        # Get API key
        api_key = _get_api_key(provider)
        if not api_key:
            raise ValueError(f"No API key found for provider: {provider}")

        timeout = getattr(self.config, "timeout_seconds", 120)

        if provider == "anthropic":
            return self._call_anthropic(prompt, api_key, timeout)
        elif provider == "google":
            return self._call_google(prompt, api_key, timeout)
        elif provider == "openai":
            return self._call_openai(prompt, api_key, timeout)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def _call_anthropic(self, prompt: str, api_key: str, timeout: int) -> str:
        """Call Anthropic Claude API."""
        import httpx

        console.print(f"    [dim]Calling Anthropic API ({self.config.model})...[/dim]")

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
            timeout=float(timeout),
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]

    def _call_google(self, prompt: str, api_key: str, timeout: int) -> str:
        """Call Google Gemini API."""
        import httpx

        console.print(f"    [dim]Calling Google Gemini API ({self.config.model})...[/dim]")

        # Map model name if needed
        model = self.config.model
        if not model.startswith("models/"):
            model = f"models/{model}"

        url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent"

        response = httpx.post(
            url,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": self.config.temperature,
                    "maxOutputTokens": self.config.max_tokens,
                },
            },
            timeout=float(timeout),
        )
        response.raise_for_status()
        data = response.json()

        # Extract text from response
        candidates = data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts:
                return parts[0].get("text", "")

        raise ValueError("No content in Gemini response")

    def _call_openai(self, prompt: str, api_key: str, timeout: int) -> str:
        """Call OpenAI API."""
        import httpx

        console.print(f"    [dim]Calling OpenAI API ({self.config.model})...[/dim]")

        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=float(timeout),
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

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

        Enhanced rule-based evaluation with support for:
        - Apex code patterns
        - Flow metadata patterns
        - Validation rule patterns
        """
        criteria = []
        code_lower = code.lower()

        # Detect what type of code we're evaluating
        has_apex = ".cls" in code or "public class" in code_lower or "@istest" in code_lower
        has_flow = "<flow " in code_lower or "<recordupdates>" in code_lower or "flow-meta.xml" in code_lower
        has_validation = "<validationrule" in code_lower or "errorformula" in code_lower

        # Check for bulkification issues (Apex-specific)
        bulkification_score = 0.8  # Start with good score
        if has_apex:
            soql_in_loop = (
                "for(" in code_lower or "for (" in code_lower
            ) and "[select" in code_lower
            dml_in_loop = any(
                op in code_lower
                for op in ["insert ", "update ", "delete ", "upsert "]
            ) and ("for(" in code_lower or "for (" in code_lower)

            if soql_in_loop:
                bulkification_score -= 0.4
            if dml_in_loop:
                bulkification_score -= 0.4
            # Bonus for using collections
            if "list<" in code_lower or "map<" in code_lower or "set<" in code_lower:
                bulkification_score = min(1.0, bulkification_score + 0.2)

        criteria.append(
            RubricCriterion(
                name="Bulkification",
                weight=0.25,
                score=max(0, bulkification_score),
                reasoning="Heuristic check for SOQL/DML patterns and collections",
            )
        )

        # Check for async patterns (Apex-specific) or Flow patterns
        async_score = 0.7  # Default neutral score
        if has_apex:
            has_async = any(
                pattern in code_lower
                for pattern in ["queueable", "batchable", "schedulable", "@future"]
            )
            async_score = 0.9 if has_async else 0.6
        elif has_flow:
            # Flows handle async through their execution mode
            is_after_save = "aftersave" in code_lower or "triggertype>update" in code_lower
            async_score = 0.85 if is_after_save else 0.7

        criteria.append(
            RubricCriterion(
                name="Correct Use of Async Apex",
                weight=0.20,
                score=async_score,
                reasoning="Checked for async patterns or Flow execution mode",
            )
        )

        # Check for test quality
        test_score = 0.5  # Default
        if has_apex:
            has_asserts = "system.assert" in code_lower
            has_test_annotation = "@istest" in code_lower
            has_testmethod = "testmethod" in code_lower
            has_bulk_test = "200" in code or "list<" in code_lower and "for" in code_lower

            test_score = 0.3
            if has_test_annotation or has_testmethod:
                test_score += 0.25
            if has_asserts:
                test_score += 0.25
            if has_bulk_test:
                test_score += 0.2  # Bonus for bulk testing

        criteria.append(
            RubricCriterion(
                name="Test Quality",
                weight=0.20,
                score=min(1.0, test_score),
                reasoning="Checked for test annotations, assertions, and bulk patterns",
            )
        )

        # Check for security
        security_score = 0.7  # Default neutral
        if has_apex:
            has_crud_check = any(
                pattern in code_lower
                for pattern in ["isdeletable", "iscreateable", "isupdateable", "isaccessible", "stripfinal"]
            )
            # Check for hardcoded IDs (common Salesforce ID prefixes)
            has_hardcoded_id = any(
                prefix in code for prefix in ["001", "003", "005", "006", "00D", "00Q"]
            )
            has_with_security = "with security_enforced" in code_lower or "with user_mode" in code_lower

            security_score = 0.6
            if has_crud_check or has_with_security:
                security_score += 0.3
            if has_hardcoded_id:
                security_score -= 0.2
        elif has_validation:
            # Validation rules inherently respect security model
            security_score = 0.85
        elif has_flow:
            # Flows run in system context by default, check for user mode
            security_score = 0.75

        criteria.append(
            RubricCriterion(
                name="Security Best Practices",
                weight=0.20,
                score=max(0, min(1, security_score)),
                reasoning="Checked for security patterns and hardcoded values",
            )
        )

        # Code readability
        readability_score = 0.6  # Default
        if has_apex:
            has_comments = "//" in code or "/*" in code
            lines = code.split("\n")
            avg_line_length = sum(len(line) for line in lines) / max(1, len(lines))
            has_descriptive_names = any(
                len(name) > 10 for name in re.findall(r'\b[a-z][a-zA-Z]+\b', code)
            )

            readability_score = 0.5
            if has_comments:
                readability_score += 0.15
            if avg_line_length < 100:
                readability_score += 0.15
            if has_descriptive_names:
                readability_score += 0.2
        elif has_flow:
            # Check Flow has descriptive labels
            has_labels = "<label>" in code_lower
            has_descriptions = "<description>" in code_lower
            readability_score = 0.6
            if has_labels:
                readability_score += 0.2
            if has_descriptions:
                readability_score += 0.2

        criteria.append(
            RubricCriterion(
                name="Code Readability",
                weight=0.15,
                score=min(1, readability_score),
                reasoning="Checked for comments, naming, and structure",
            )
        )

        # Calculate overall weighted score
        total_weight = sum(c.weight for c in criteria)
        overall = sum(c.score * c.weight for c in criteria) / total_weight if total_weight > 0 else 0.5

        # Determine code type for feedback
        code_types = []
        if has_apex:
            code_types.append("Apex")
        if has_flow:
            code_types.append("Flow")
        if has_validation:
            code_types.append("Validation Rule")
        code_type_str = ", ".join(code_types) if code_types else "Code"

        return RubricResult(
            overall_score=overall,
            criteria=criteria,
            feedback=f"Evaluated {code_type_str} using enhanced heuristic rules (LLM not available). "
                     f"For more accurate evaluation, configure an LLM API key.",
        )
