"""Base classes for LLM judges.

Defines the Judge protocol and result structures.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
import json
import re


@dataclass
class JudgeCriterion:
    """A single criterion evaluation from a judge."""
    
    name: str
    score: float  # 0.0 to 1.0
    weight: float = 1.0
    reasoning: str = ""
    line_refs: list[int] = field(default_factory=list)
    
    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


@dataclass
class JudgeResult:
    """Complete result from an LLM judge evaluation."""
    
    overall_score: float = 0.0  # 0.0 to 1.0
    criteria: list[JudgeCriterion] = field(default_factory=list)
    feedback: str = ""
    strengths: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    
    # Metadata
    judge_model: str = ""
    rubric_name: str = ""
    rubric_version: str = ""
    
    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int = 0
    
    # Token tracking
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    
    # Raw data for logging
    prompt_template: str = ""
    code_submitted: str = ""
    requirements: str = ""
    raw_response: str = ""
    parsed_successfully: bool = True
    parse_error: str = ""
    
    def calculate_overall_score(self) -> float:
        """Calculate weighted overall score from criteria."""
        if not self.criteria:
            return 0.0
        
        total_weight = sum(c.weight for c in self.criteria)
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(c.score * c.weight for c in self.criteria)
        self.overall_score = weighted_sum / total_weight
        return self.overall_score
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "overall_score": self.overall_score,
            "criteria": [
                {
                    "name": c.name,
                    "score": c.score,
                    "weight": c.weight,
                    "reasoning": c.reasoning,
                    "line_refs": c.line_refs,
                }
                for c in self.criteria
            ],
            "feedback": self.feedback,
            "strengths": self.strengths,
            "improvements": self.improvements,
            "judge_model": self.judge_model,
            "rubric_name": self.rubric_name,
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
        }


@dataclass
class Rubric:
    """A rubric for evaluating code."""
    
    name: str
    version: str = "1.0"
    description: str = ""
    judge_model: str = "claude-opus-4-20250514"
    criteria: list[dict[str, Any]] = field(default_factory=list)
    
    @classmethod
    def from_yaml(cls, path: Path) -> "Rubric":
        """Load a rubric from a YAML file."""
        import yaml
        
        with open(path) as f:
            data = yaml.safe_load(f)
        
        return cls(
            name=data.get("name", path.stem),
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            judge_model=data.get("judge_model", "claude-opus-4-20250514"),
            criteria=data.get("criteria", []),
        )
    
    def format_for_prompt(self) -> str:
        """Format the rubric for inclusion in a prompt."""
        lines = [f"# {self.name} (v{self.version})", ""]
        
        for i, criterion in enumerate(self.criteria, 1):
            name = criterion.get("name", f"Criterion {i}")
            weight = criterion.get("weight", 1.0)
            description = criterion.get("description", "")
            scoring_guide = criterion.get("scoring_guide", {})
            
            lines.append(f"## {i}. {name} (weight: {weight})")
            lines.append(description.strip())
            
            if scoring_guide:
                lines.append("\nScoring Guide:")
                for score, desc in sorted(scoring_guide.items(), reverse=True):
                    lines.append(f"  {score}: {desc}")
            
            lines.append("")
        
        return "\n".join(lines)


class Judge(ABC):
    """Abstract base class for LLM judges."""
    
    def __init__(
        self,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        verbose: bool = False,
    ):
        """Initialize the judge.
        
        Args:
            model: Model identifier
            temperature: Sampling temperature (0 = deterministic)
            max_tokens: Maximum tokens in response
            verbose: Enable verbose output
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.verbose = verbose
    
    @abstractmethod
    def evaluate(
        self,
        code: str,
        requirements: str,
        rubric: Rubric,
    ) -> JudgeResult:
        """Evaluate code against a rubric.
        
        Args:
            code: The code to evaluate
            requirements: Task requirements
            rubric: Evaluation rubric
        
        Returns:
            JudgeResult with scores and feedback
        """
        pass
    
    def build_prompt(
        self,
        code: str,
        requirements: str,
        rubric: Rubric,
        agent_id: str = "unknown",
    ) -> str:
        """Build the evaluation prompt.
        
        Args:
            code: The code to evaluate
            requirements: Task requirements
            rubric: Evaluation rubric
            agent_id: ID of the agent that produced the code
        
        Returns:
            Formatted prompt string
        """
        rubric_text = rubric.format_for_prompt()
        
        # Detect language
        language = "apex"
        if ".js" in code or "import" in code and "from" in code:
            language = "javascript"
        elif ".py" in code or "def " in code:
            language = "python"
        
        return f"""You are an expert Salesforce code reviewer acting as an impartial judge.

## Task Requirements
{requirements}

## Code Submitted by: {agent_id}
```{language}
{code[:15000]}
```

## Evaluation Rubric
{rubric_text}

## Instructions
1. Evaluate ONLY what is present in the code
2. Score each criterion from 0.0 to 1.0
3. Provide specific line references for issues
4. Be consistent - the same code should get the same score
5. Do not penalize for things not relevant to the task

Return your evaluation as JSON in this exact format:
{{
    "criteria": [
        {{
            "name": "Criterion Name",
            "score": 0.85,
            "reasoning": "Brief explanation with specifics",
            "line_refs": [12, 45]
        }}
    ],
    "overall_feedback": "Summary of evaluation",
    "strengths": ["Strength 1", "Strength 2"],
    "improvements": ["Improvement 1", "Improvement 2"]
}}

Return ONLY the JSON, no other text."""
    
    def parse_response(self, response: str, rubric: Rubric) -> JudgeResult:
        """Parse the LLM response into a JudgeResult.
        
        Args:
            response: Raw LLM response
            rubric: The rubric used for evaluation
        
        Returns:
            Parsed JudgeResult
        """
        result = JudgeResult(
            judge_model=self.model,
            rubric_name=rubric.name,
            rubric_version=rubric.version,
            raw_response=response,
        )
        
        try:
            # Extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", response)
            if not json_match:
                result.parsed_successfully = False
                result.parse_error = "No JSON found in response"
                return result
            
            data = json.loads(json_match.group())
            
            # Parse criteria
            for item in data.get("criteria", []):
                # Find matching rubric criterion for weight
                weight = 1.0
                for rc in rubric.criteria:
                    if rc.get("name", "").lower() == item.get("name", "").lower():
                        weight = rc.get("weight", 1.0)
                        break
                
                criterion = JudgeCriterion(
                    name=item.get("name", "Unknown"),
                    score=float(item.get("score", 0.5)),
                    weight=weight,
                    reasoning=item.get("reasoning", ""),
                    line_refs=item.get("line_refs", []),
                )
                result.criteria.append(criterion)
            
            result.feedback = data.get("overall_feedback", "")
            result.strengths = data.get("strengths", [])
            result.improvements = data.get("improvements", [])
            result.parsed_successfully = True
            
            # Calculate overall score
            result.calculate_overall_score()
            
        except json.JSONDecodeError as e:
            result.parsed_successfully = False
            result.parse_error = f"JSON parse error: {e}"
        except Exception as e:
            result.parsed_successfully = False
            result.parse_error = f"Parse error: {e}"
        
        return result
