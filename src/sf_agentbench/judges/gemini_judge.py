"""Gemini judge implementation.

Uses the Google Gemini API for cross-validation of evaluations.
"""

import os
import time
from datetime import datetime
from typing import Any

from rich.console import Console

from sf_agentbench.judges.base import Judge, JudgeResult, Rubric
from sf_agentbench.domain.costs import get_cost_profile, estimate_tokens

console = Console()


class GeminiJudge(Judge):
    """Judge using Gemini 2.5 Pro via Google AI API.
    
    Used as a secondary judge for cross-validation.
    """
    
    def __init__(
        self,
        model: str = "gemini-2.5-pro",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        api_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the Gemini judge.
        
        Args:
            model: Gemini model to use
            temperature: Sampling temperature (0 = deterministic)
            max_tokens: Maximum tokens in response
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
            verbose: Enable verbose output
        """
        super().__init__(model, temperature, max_tokens, verbose)
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "Google API key required. Set GOOGLE_API_KEY or pass api_key."
            )
    
    def evaluate(
        self,
        code: str,
        requirements: str,
        rubric: Rubric,
        agent_id: str = "unknown",
    ) -> JudgeResult:
        """Evaluate code using Gemini.
        
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
            console.print(f"[dim]Calling Gemini judge ({self.model})...[/dim]")
        
        try:
            # Call Google AI API
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
            console.print(f"[red]Gemini judge error: {e}[/red]")
            
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
        """Call the Google AI API.
        
        Args:
            prompt: The prompt to send
        
        Returns:
            Tuple of (response_text, input_tokens, output_tokens)
        """
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=self.api_key)
            
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                ),
            )
            
            text = response.text or ""
            
            # Get token counts from usage metadata if available
            input_tokens = estimate_tokens(prompt)
            output_tokens = estimate_tokens(text)
            
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                if hasattr(usage, 'prompt_token_count'):
                    input_tokens = usage.prompt_token_count
                if hasattr(usage, 'candidates_token_count'):
                    output_tokens = usage.candidates_token_count
            
            return text, input_tokens, output_tokens
            
        except ImportError:
            # Fallback to REST API
            return self._call_rest_api(prompt)
    
    def _call_rest_api(self, prompt: str) -> tuple[str, int, int]:
        """Call the Google AI REST API directly.
        
        Args:
            prompt: The prompt to send
        
        Returns:
            Tuple of (response_text, input_tokens, output_tokens)
        """
        import httpx
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        
        response = httpx.post(
            url,
            params={"key": self.api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": self.temperature,
                    "maxOutputTokens": self.max_tokens,
                },
            },
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        
        # Extract response text
        text = ""
        candidates = data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            for part in parts:
                text += part.get("text", "")
        
        # Estimate tokens
        input_tokens = estimate_tokens(prompt)
        output_tokens = estimate_tokens(text)
        
        # Use actual counts if available
        usage = data.get("usageMetadata", {})
        if "promptTokenCount" in usage:
            input_tokens = usage["promptTokenCount"]
        if "candidatesTokenCount" in usage:
            output_tokens = usage["candidatesTokenCount"]
        
        return text, input_tokens, output_tokens
