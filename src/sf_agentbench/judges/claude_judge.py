"""Claude Opus 4.5 judge implementation.

Uses the Anthropic API to evaluate code quality.
"""

import os
import time
from datetime import datetime
from typing import Any

from rich.console import Console

from sf_agentbench.judges.base import Judge, JudgeResult, Rubric
from sf_agentbench.domain.costs import get_cost_profile, estimate_tokens

console = Console()


class ClaudeJudge(Judge):
    """Judge using Claude Opus 4.5 via Anthropic API.
    
    This is the primary judge for high-quality, consistent evaluations.
    """
    
    def __init__(
        self,
        model: str = "claude-opus-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        api_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the Claude judge.
        
        Args:
            model: Claude model to use
            temperature: Sampling temperature (0 = deterministic)
            max_tokens: Maximum tokens in response
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            verbose: Enable verbose output
        """
        super().__init__(model, temperature, max_tokens, verbose)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY or pass api_key."
            )
    
    def evaluate(
        self,
        code: str,
        requirements: str,
        rubric: Rubric,
        agent_id: str = "unknown",
    ) -> JudgeResult:
        """Evaluate code using Claude.
        
        Args:
            code: The code to evaluate
            requirements: Task requirements
            rubric: Evaluation rubric
            agent_id: ID of the agent that produced the code
        
        Returns:
            JudgeResult with scores and feedback
        """
        started_at = datetime.utcnow()
        
        # Build prompt
        prompt = self.build_prompt(code, requirements, rubric, agent_id)
        
        if self.verbose:
            console.print(f"[dim]Calling Claude judge ({self.model})...[/dim]")
        
        try:
            # Call Anthropic API
            response_text, input_tokens, output_tokens = self._call_api(prompt)
            
            # Parse response
            result = self.parse_response(response_text, rubric)
            
            # Add metadata
            result.started_at = started_at
            result.completed_at = datetime.utcnow()
            result.duration_ms = int((result.completed_at - started_at).total_seconds() * 1000)
            result.input_tokens = input_tokens
            result.output_tokens = output_tokens
            result.prompt_template = prompt
            result.code_submitted = code
            result.requirements = requirements
            
            # Calculate cost
            cost_profile = get_cost_profile(self.model)
            result.estimated_cost_usd = cost_profile.estimate(input_tokens, output_tokens)
            
            if self.verbose:
                console.print(f"[dim]  Score: {result.overall_score:.2f}[/dim]")
                console.print(f"[dim]  Tokens: {input_tokens} in / {output_tokens} out[/dim]")
                console.print(f"[dim]  Cost: ${result.estimated_cost_usd:.4f}[/dim]")
            
            return result
            
        except Exception as e:
            console.print(f"[red]Claude judge error: {e}[/red]")
            
            result = JudgeResult(
                judge_model=self.model,
                rubric_name=rubric.name,
                rubric_version=rubric.version,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                parsed_successfully=False,
                parse_error=str(e),
                prompt_template=prompt,
                code_submitted=code,
                requirements=requirements,
            )
            result.duration_ms = int((result.completed_at - started_at).total_seconds() * 1000)
            return result
    
    def _call_api(self, prompt: str) -> tuple[str, int, int]:
        """Call the Anthropic API.
        
        Args:
            prompt: The prompt to send
        
        Returns:
            Tuple of (response_text, input_tokens, output_tokens)
        """
        import httpx
        
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        
        # Extract response text
        content = data.get("content", [])
        text = ""
        for block in content:
            if block.get("type") == "text":
                text += block.get("text", "")
        
        # Extract token counts
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", estimate_tokens(prompt))
        output_tokens = usage.get("output_tokens", estimate_tokens(text))
        
        return text, input_tokens, output_tokens


class ClaudeSonnetJudge(ClaudeJudge):
    """Judge using Claude Sonnet 4 for faster, cheaper evaluations."""
    
    def __init__(
        self,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        api_key: str | None = None,
        verbose: bool = False,
    ):
        super().__init__(
            model="claude-sonnet-4-20250514",
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            verbose=verbose,
        )
