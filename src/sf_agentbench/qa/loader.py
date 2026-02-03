"""Test Bank Loader for Q&A Testing.

Loads and validates test bank JSON files according to the schema.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Question:
    """A single question from a test bank."""
    
    id: int | str
    type: str  # multiple_choice, true_false, short_answer, code, scenario
    question: str
    correct_answer: str | list[str]
    domain: str = ""
    difficulty: str = "medium"
    context: str = ""
    choices: dict[str, str] = field(default_factory=dict)
    explanation: str = ""
    tags: list[str] = field(default_factory=list)
    points: float = 1.0
    
    def format_for_prompt(self, include_choices: bool = True) -> str:
        """Format question for LLM prompt."""
        parts = []
        
        if self.context:
            parts.append(f"Context: {self.context}\n")
        
        parts.append(f"Question: {self.question}")
        
        if include_choices and self.choices:
            parts.append("\nChoices:")
            for letter, text in sorted(self.choices.items()):
                parts.append(f"  {letter}) {text}")
        
        return "\n".join(parts)
    
    def check_answer(self, response: str) -> tuple[bool, str]:
        """
        Check if a response contains the correct answer.
        
        Returns:
            (is_correct, extracted_answer)
        """
        response_upper = response.upper().strip()
        
        # For multiple choice, look for the letter
        if self.choices:
            correct = self.correct_answer.upper() if isinstance(self.correct_answer, str) else self.correct_answer
            
            import re
            
            # Pattern 0: Just a single letter (most common for well-prompted LLMs)
            if re.match(r'^[A-D]$', response_upper):
                extracted = response_upper
                return extracted == correct, extracted
            
            # Pattern 1: Letter at the very start (possibly with punctuation)
            match = re.match(r'^([A-D])[\.\)\:\s]', response_upper)
            if match:
                extracted = match.group(1)
                return extracted == correct, extracted
            
            # Pattern 2: Explicit "answer is X" or "correct answer is X"
            match = re.search(r'(?:answer|correct)\s*(?:is|:)\s*([A-D])', response_upper)
            if match:
                extracted = match.group(1)
                return extracted == correct, extracted
            
            # Pattern 3: "X)" or "(X)" format
            match = re.search(r'\(?([A-D])\)', response_upper)
            if match:
                extracted = match.group(1)
                return extracted == correct, extracted
            
            # Pattern 4: Look for any standalone letter
            for letter in ['A', 'B', 'C', 'D']:
                # Check if letter appears as a standalone word or with common delimiters
                if re.search(rf'\b{letter}\b', response_upper):
                    return letter == correct, letter
            
            # Fallback: check if correct answer text appears
            if isinstance(correct, str) and correct in self.choices:
                correct_text = self.choices[correct].upper()
                if correct_text in response_upper:
                    return True, correct
            
            return False, "UNKNOWN"
        
        # For non-multiple choice, do text comparison
        if isinstance(self.correct_answer, list):
            for ans in self.correct_answer:
                if ans.upper() in response_upper:
                    return True, ans
            return False, response[:50]
        else:
            return self.correct_answer.upper() in response_upper, response[:50]


@dataclass
class TestBank:
    """A collection of questions for testing."""
    
    id: str
    name: str
    description: str
    version: str
    questions: list[Question]
    domains: list[str] = field(default_factory=list)
    difficulty: str = "mixed"
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def filter_by_domain(self, domain: str) -> list[Question]:
        """Get questions for a specific domain."""
        return [q for q in self.questions if q.domain.lower() == domain.lower()]
    
    def filter_by_difficulty(self, difficulty: str) -> list[Question]:
        """Get questions of a specific difficulty."""
        return [q for q in self.questions if q.difficulty.lower() == difficulty.lower()]
    
    def sample(self, n: int, domain: str | None = None) -> list[Question]:
        """Get a random sample of n questions."""
        import random
        
        pool = self.filter_by_domain(domain) if domain else self.questions
        return random.sample(pool, min(n, len(pool)))


class TestBankLoader:
    """Loads test banks from JSON files."""
    
    def __init__(self, data_dir: Path | str | None = None):
        """
        Initialize the loader.
        
        Args:
            data_dir: Directory containing test bank files.
                     Defaults to docs/data in the project.
        """
        if data_dir is None:
            # Find project root
            current = Path(__file__).parent
            while current.parent != current:
                if (current / "pyproject.toml").exists():
                    data_dir = current / "docs" / "data"
                    break
                current = current.parent
            else:
                data_dir = Path("docs/data")
        
        self.data_dir = Path(data_dir)
    
    def load(self, filename: str) -> TestBank:
        """Load a test bank from a JSON file."""
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"Test bank not found: {filepath}")
        
        with open(filepath) as f:
            data = json.load(f)
        
        return self._parse_test_bank(data, filename)
    
    def _parse_test_bank(self, data: dict, source: str) -> TestBank:
        """Parse JSON data into a TestBank object."""
        metadata = data.get("metadata", {})
        
        questions = []
        for q_data in data.get("questions", []):
            question = Question(
                id=q_data.get("id", len(questions) + 1),
                type=q_data.get("type", "multiple_choice"),
                question=q_data.get("question", ""),
                correct_answer=q_data.get("correct_answer", ""),
                domain=q_data.get("domain", ""),
                difficulty=q_data.get("difficulty", "medium"),
                context=q_data.get("context", ""),
                choices=q_data.get("choices", {}),
                explanation=q_data.get("explanation", ""),
                tags=q_data.get("tags", []),
                points=q_data.get("points", 1.0),
            )
            questions.append(question)
        
        return TestBank(
            id=metadata.get("id", source.replace(".json", "")),
            name=metadata.get("name", source),
            description=metadata.get("description", ""),
            version=metadata.get("version", "1.0"),
            questions=questions,
            domains=metadata.get("domains", []),
            difficulty=metadata.get("difficulty", "mixed"),
            metadata=metadata,
        )
    
    def list_available(self) -> list[str]:
        """List available test bank files."""
        if not self.data_dir.exists():
            return []
        
        return [
            f.name for f in self.data_dir.glob("*.json")
            if f.name != "test_bank_schema.json"
        ]
