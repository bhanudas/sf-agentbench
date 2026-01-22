"""Q&A Runner for testing LLMs with question banks.

Runs questions against LLM CLIs and evaluates responses.
Supports multi-threaded execution for faster benchmarking.
"""

import subprocess
import json
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.logging import RichHandler

from .loader import Question, TestBank
from .storage import QAResultsStore

console = Console()

# Thread-safe lock for console output
_console_lock = threading.Lock()

# Setup logging
def setup_qa_logging(log_dir: Path, run_id: str) -> logging.Logger:
    """Setup logging for a Q&A run."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"qa_run_{run_id}.log"
    
    logger = logging.getLogger(f"qa.{run_id}")
    logger.setLevel(logging.DEBUG)
    
    # File handler - detailed
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(fh)
    
    return logger


# Base prompt template for Q&A
QA_PROMPT_TEMPLATE = """You are taking a Salesforce certification exam. Answer the following question.

{question}

Instructions:
- For multiple choice questions, respond with ONLY the letter of your answer (A, B, C, or D)
- Be concise and direct
- Do not explain your reasoning unless asked

Your answer:"""


@dataclass
class QAResult:
    """Result from a single Q&A test."""
    
    question_id: int | str
    question_text: str
    expected_answer: str
    model_response: str
    extracted_answer: str
    is_correct: bool
    response_time_seconds: float
    domain: str = ""
    explanation: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class QARunSummary:
    """Summary of a Q&A test run."""
    
    model_id: str
    test_bank_id: str
    started_at: datetime
    completed_at: datetime
    total_questions: int
    correct_answers: int
    results: list[QAResult] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    
    @property
    def accuracy(self) -> float:
        """Calculate accuracy percentage."""
        if self.total_questions == 0:
            return 0.0
        return (self.correct_answers / self.total_questions) * 100
    
    @property
    def duration_seconds(self) -> float:
        """Total run duration."""
        return (self.completed_at - self.started_at).total_seconds()
    
    @property
    def cost_per_question(self) -> float:
        """Cost per question in USD."""
        if self.total_questions == 0:
            return 0.0
        return self.estimated_cost_usd / self.total_questions
    
    @property
    def avg_response_time(self) -> float:
        """Average response time per question in seconds."""
        if not self.results:
            return 0.0
        return sum(r.response_time_seconds for r in self.results) / len(self.results)
    
    def by_domain(self) -> dict[str, dict]:
        """Get results grouped by domain."""
        domains: dict[str, dict] = {}
        
        for result in self.results:
            domain = result.domain or "Unknown"
            if domain not in domains:
                domains[domain] = {"total": 0, "correct": 0}
            domains[domain]["total"] += 1
            if result.is_correct:
                domains[domain]["correct"] += 1
        
        return domains
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "model_id": self.model_id,
            "test_bank_id": self.test_bank_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "total_questions": self.total_questions,
            "correct_answers": self.correct_answers,
            "accuracy": self.accuracy,
            "duration_seconds": self.duration_seconds,
            "results": [
                {
                    "question_id": r.question_id,
                    "expected": r.expected_answer,
                    "extracted": r.extracted_answer,
                    "correct": r.is_correct,
                    "response_time": r.response_time_seconds,
                    "domain": r.domain,
                }
                for r in self.results
            ],
            "by_domain": self.by_domain(),
        }


# CLI configurations for Q&A (simpler than coding tasks)
QA_CLI_CONFIGS = {
    "gemini-cli": {
        "command": ["gemini"],
        "model_flag": "-m",
        "prompt_flag": "-p",
        "default_model": "gemini-2.0-flash",
    },
    "claude-code": {
        "command": ["claude"],
        "model_flag": "--model",
        "prompt_flag": "-p",
        "default_model": "sonnet",
    },
}

# API configurations for direct API access (more reliable than CLI)
QA_API_CONFIGS = {
    "gemini": {
        "provider": "google",
        "models": ["gemini-2.0-flash", "gemini-2.5-pro", "gemini-3.0-thinking"],
        "default_model": "gemini-2.0-flash",
    },
    "claude": {
        "provider": "anthropic",
        "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514"],
        "default_model": "claude-sonnet-4-20250514",
    },
}

# Cost per 1M tokens (input/output) - approximate pricing as of Jan 2026
# Source: https://openai.com/pricing, https://www.anthropic.com/pricing, https://ai.google.dev/pricing
MODEL_COSTS = {
    # Gemini models
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    # Claude models
    "sonnet": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "opus": {"input": 15.00, "output": 75.00},
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    "haiku": {"input": 0.25, "output": 1.25},
    # OpenAI models (for future)
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a given model and token count."""
    costs = MODEL_COSTS.get(model, MODEL_COSTS.get("gemini-2.0-flash"))  # Default fallback
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    return input_cost + output_cost

def estimate_tokens(text: str) -> int:
    """Rough estimate of tokens (4 chars per token on average)."""
    return len(text) // 4


class QARunner:
    """Runs Q&A tests against LLM CLIs with optional multi-threading."""
    
    def __init__(
        self,
        cli_id: str = "gemini-cli",
        model: str | None = None,
        timeout_seconds: int = 60,
        verbose: bool = False,
        workers: int = 1,
        results_dir: Path | str | None = None,
        logs_dir: Path | str | None = None,
    ):
        """
        Initialize the Q&A runner.
        
        Args:
            cli_id: Which CLI to use (gemini-cli, claude-code)
            model: Model to use (overrides CLI default)
            timeout_seconds: Timeout per question
            verbose: Show detailed output
            workers: Number of parallel worker threads (1 = sequential)
            results_dir: Directory for storing results (default: results/)
            logs_dir: Directory for log files (default: logs/)
        """
        if cli_id not in QA_CLI_CONFIGS:
            raise ValueError(f"Unknown CLI: {cli_id}. Available: {list(QA_CLI_CONFIGS.keys())}")
        
        self.cli_id = cli_id
        self.cli_config = QA_CLI_CONFIGS[cli_id]
        self.model = model or self.cli_config["default_model"]
        self.timeout = timeout_seconds
        self.verbose = verbose
        self.workers = max(1, workers)  # At least 1 worker
        
        # Setup storage
        self.results_dir = Path(results_dir or "results")
        self.logs_dir = Path(logs_dir or "logs")
        self.store = QAResultsStore(self.results_dir)
        
        # Logging will be setup per-run
        self.logger: logging.Logger | None = None
        self.run_id: str | None = None
        
        # Thread-safe storage lock
        self._store_lock = threading.Lock()
    
    def _build_command(self, prompt: str) -> list[str]:
        """Build the CLI command."""
        cmd = list(self.cli_config["command"])
        
        # Add model flag
        if self.cli_config.get("model_flag") and self.model:
            cmd.extend([self.cli_config["model_flag"], self.model])
        
        # Add prompt flag
        if self.cli_config.get("prompt_flag"):
            cmd.extend([self.cli_config["prompt_flag"], prompt])
        
        return cmd
    
    def ask_question(self, question: Question) -> QAResult:
        """
        Ask a single question to the LLM.
        
        Args:
            question: The question to ask
            
        Returns:
            QAResult with the response and evaluation
        """
        # Format the prompt
        formatted_q = question.format_for_prompt()
        prompt = QA_PROMPT_TEMPLATE.format(question=formatted_q)
        
        # Build command
        cmd = self._build_command(prompt)
        
        if self.verbose:
            console.print(f"[dim]Running: {' '.join(cmd[:4])}...[/dim]")
        
        # Log the prompt
        if self.logger:
            self.logger.debug(f"Question {question.id}: {question.question[:100]}...")
            self.logger.debug(f"Prompt sent: {prompt[:200]}...")
        
        # Execute
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=Path.home(),  # Run from home to avoid any project context
            )
            response = result.stdout.strip()
            
            if result.returncode != 0 and not response:
                response = f"ERROR: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            response = "TIMEOUT"
            if self.logger:
                self.logger.warning(f"Question {question.id} timed out after {self.timeout}s")
        except Exception as e:
            response = f"ERROR: {str(e)}"
            if self.logger:
                self.logger.error(f"Question {question.id} error: {e}")
        
        elapsed = time.time() - start_time
        
        # Evaluate the response
        is_correct, extracted = question.check_answer(response)
        
        # Log the result
        if self.logger:
            status = "CORRECT" if is_correct else "INCORRECT"
            self.logger.info(
                f"Q{question.id} [{question.domain}]: {status} "
                f"(expected={question.correct_answer}, got={extracted}, time={elapsed:.1f}s)"
            )
            self.logger.debug(f"Full response: {response}")
        
        # Store in database for playback (thread-safe)
        if self.run_id:
            with self._store_lock:
                self.store.log_question(
                    run_id=self.run_id,
                    question_id=question.id,
                    domain=question.domain,
                    difficulty=question.difficulty,
                    question_text=question.question,
                    correct_answer=str(question.correct_answer),
                    prompt_sent=prompt,
                    model_response=response,
                    extracted_answer=extracted,
                    is_correct=is_correct,
                    response_time=elapsed,
                )
        
        # Estimate tokens for cost tracking
        input_tokens = estimate_tokens(prompt)
        output_tokens = estimate_tokens(response)
        
        return QAResult(
            question_id=question.id,
            question_text=question.question,
            expected_answer=str(question.correct_answer),
            model_response=response,
            extracted_answer=extracted,
            is_correct=is_correct,
            response_time_seconds=elapsed,
            domain=question.domain,
            explanation=question.explanation,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    
    def run_test_bank(
        self,
        test_bank: TestBank,
        questions: list[Question] | None = None,
        on_result: Callable[[QAResult], None] | None = None,
    ) -> QARunSummary:
        """
        Run a full test bank or subset of questions.
        
        Args:
            test_bank: The test bank to run
            questions: Optional subset of questions (defaults to all)
            on_result: Callback for each result
            
        Returns:
            QARunSummary with all results
        """
        questions_to_run = questions or test_bank.questions
        started_at = datetime.now()
        results: list[QAResult] = []
        correct_count = 0
        error_message = None
        
        # Start run in storage
        self.run_id = self.store.start_run(
            model_id=self.model,
            cli_id=self.cli_id,
            test_bank_id=test_bank.id,
            test_bank_name=test_bank.name,
        )
        
        # Setup logging for this run
        self.logger = setup_qa_logging(self.logs_dir, self.run_id)
        self.logger.info(f"Starting Q&A run: {self.run_id}")
        self.logger.info(f"Model: {self.model} via {self.cli_id}")
        self.logger.info(f"Test bank: {test_bank.name} ({len(questions_to_run)} questions)")
        
        console.print(f"\n[bold cyan]Running Q&A Test: {test_bank.name}[/bold cyan]")
        console.print(f"  Run ID: [dim]{self.run_id}[/dim]")
        console.print(f"  Model: [magenta]{self.model}[/magenta] via {self.cli_id}")
        console.print(f"  Questions: {len(questions_to_run)}")
        console.print(f"  Workers: [yellow]{self.workers}[/yellow] {'(parallel)' if self.workers > 1 else '(sequential)'}")
        console.print()
        
        try:
            if self.workers > 1:
                # Multi-threaded execution
                results, correct_count = self._run_parallel(
                    questions_to_run, on_result
                )
            else:
                # Sequential execution (original behavior)
                results, correct_count = self._run_sequential(
                    questions_to_run, on_result
                )
        
        except Exception as e:
            error_message = str(e)
            self.logger.error(f"Run failed: {e}")
            console.print(f"[red]Error: {e}[/red]")
        
        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()
        
        # Complete run in storage
        self.store.complete_run(
            run_id=self.run_id,
            total_questions=len(questions_to_run),
            correct_answers=correct_count,
            duration_seconds=duration,
            error=error_message,
        )
        
        # Calculate tokens and cost
        total_input_tokens = sum(r.input_tokens for r in results)
        total_output_tokens = sum(r.output_tokens for r in results)
        estimated_cost = estimate_cost(self.model, total_input_tokens, total_output_tokens)
        
        # Log summary
        accuracy = (correct_count / len(questions_to_run) * 100) if questions_to_run else 0
        self.logger.info(f"Run completed: {correct_count}/{len(questions_to_run)} ({accuracy:.1f}%)")
        self.logger.info(f"Duration: {duration:.1f}s")
        self.logger.info(f"Tokens: {total_input_tokens:,} in / {total_output_tokens:,} out")
        self.logger.info(f"Estimated cost: ${estimated_cost:.4f}")
        
        return QARunSummary(
            model_id=self.model,
            test_bank_id=test_bank.id,
            started_at=started_at,
            completed_at=completed_at,
            total_questions=len(questions_to_run),
            correct_answers=correct_count,
            results=results,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            estimated_cost_usd=estimated_cost,
        )
    
    def _run_sequential(
        self,
        questions: list[Question],
        on_result: Callable[[QAResult], None] | None = None,
    ) -> tuple[list[QAResult], int]:
        """Run questions sequentially (single-threaded)."""
        results: list[QAResult] = []
        correct_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running questions...", total=len(questions))
            
            for question in questions:
                progress.update(task, description=f"Q{question.id} ({question.domain})")
                
                result = self.ask_question(question)
                results.append(result)
                
                if result.is_correct:
                    correct_count += 1
                    status = "[green]✓[/green]"
                else:
                    status = "[red]✗[/red]"
                
                if self.verbose or not result.is_correct:
                    console.print(
                        f"  {status} Q{question.id}: "
                        f"Expected {result.expected_answer}, "
                        f"Got {result.extracted_answer} "
                        f"[dim]({result.response_time_seconds:.1f}s)[/dim]"
                    )
                
                if on_result:
                    on_result(result)
                
                progress.advance(task)
        
        return results, correct_count
    
    def _run_parallel(
        self,
        questions: list[Question],
        on_result: Callable[[QAResult], None] | None = None,
    ) -> tuple[list[QAResult], int]:
        """Run questions in parallel using ThreadPoolExecutor."""
        results: list[QAResult] = []
        correct_count = 0
        completed = 0
        
        with Progress(
            SpinnerColumn(),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Running {len(questions)} questions with {self.workers} workers...",
                total=len(questions)
            )
            
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                # Submit all questions
                future_to_question = {
                    executor.submit(self.ask_question, q): q
                    for q in questions
                }
                
                # Process as they complete
                for future in as_completed(future_to_question):
                    question = future_to_question[future]
                    
                    try:
                        result = future.result()
                        results.append(result)
                        
                        if result.is_correct:
                            correct_count += 1
                            status = "[green]✓[/green]"
                        else:
                            status = "[red]✗[/red]"
                        
                        # Thread-safe console output
                        with _console_lock:
                            if self.verbose or not result.is_correct:
                                console.print(
                                    f"  {status} Q{question.id}: "
                                    f"Expected {result.expected_answer}, "
                                    f"Got {result.extracted_answer} "
                                    f"[dim]({result.response_time_seconds:.1f}s)[/dim]"
                                )
                        
                        if on_result:
                            on_result(result)
                            
                    except Exception as e:
                        with _console_lock:
                            console.print(f"  [red]✗[/red] Q{question.id}: Error - {e}")
                        if self.logger:
                            self.logger.error(f"Q{question.id} failed: {e}")
                    
                    completed += 1
                    progress.update(task, completed=completed)
        
        # Sort results by question ID to maintain order
        results.sort(key=lambda r: r.question_id)
        
        return results, correct_count
    
    def print_summary(self, summary: QARunSummary) -> None:
        """Print a formatted summary of results."""
        console.print("\n" + "=" * 60)
        console.print("[bold]Q&A TEST RESULTS[/bold]")
        console.print("=" * 60)
        
        # Overall stats
        accuracy_color = "green" if summary.accuracy >= 80 else "yellow" if summary.accuracy >= 60 else "red"
        console.print(f"  Model:     [magenta]{summary.model_id}[/magenta]")
        console.print(f"  Test Bank: {summary.test_bank_id}")
        console.print(f"  Duration:  {summary.duration_seconds:.1f}s")
        console.print(f"  Score:     [{accuracy_color}]{summary.correct_answers}/{summary.total_questions} ({summary.accuracy:.1f}%)[/{accuracy_color}]")
        
        # Cost information
        if summary.estimated_cost_usd > 0:
            console.print(f"  Tokens:    {summary.total_input_tokens:,} in / {summary.total_output_tokens:,} out")
            console.print(f"  Est. Cost: [yellow]${summary.estimated_cost_usd:.4f}[/yellow] (${summary.cost_per_question:.5f}/question)")
        
        # By domain breakdown
        by_domain = summary.by_domain()
        if len(by_domain) > 1:
            console.print("\n[bold]By Domain:[/bold]")
            
            table = Table(show_header=True)
            table.add_column("Domain", style="cyan")
            table.add_column("Correct", justify="right")
            table.add_column("Total", justify="right")
            table.add_column("Accuracy", justify="right")
            
            for domain, stats in sorted(by_domain.items()):
                acc = (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                acc_color = "green" if acc >= 80 else "yellow" if acc >= 60 else "red"
                table.add_row(
                    domain,
                    str(stats["correct"]),
                    str(stats["total"]),
                    f"[{acc_color}]{acc:.0f}%[/{acc_color}]",
                )
            
            console.print(table)
        
        # Incorrect answers
        incorrect = [r for r in summary.results if not r.is_correct]
        if incorrect:
            console.print(f"\n[bold red]Incorrect Answers ({len(incorrect)}):[/bold red]")
            for r in incorrect[:5]:  # Show first 5
                console.print(f"  Q{r.question_id}: Expected {r.expected_answer}, Got {r.extracted_answer}")
                console.print(f"    [dim]{r.question_text[:80]}...[/dim]")
            if len(incorrect) > 5:
                console.print(f"  [dim]... and {len(incorrect) - 5} more[/dim]")
        
        console.print("=" * 60)


class QAAPIRunner:
    """Runs Q&A tests using direct API calls (more reliable than CLI)."""
    
    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        timeout_seconds: int = 30,
        verbose: bool = False,
        workers: int = 4,
        results_dir: Path | str | None = None,
        logs_dir: Path | str | None = None,
    ):
        """
        Initialize the API-based Q&A runner.
        
        Args:
            model: Model to use (e.g., gemini-2.0-flash, claude-sonnet-4-20250514)
            timeout_seconds: Timeout per question
            verbose: Show detailed output
            workers: Number of parallel worker threads
            results_dir: Directory for storing results
            logs_dir: Directory for log files
        """
        self.model = model
        self.timeout = timeout_seconds
        self.verbose = verbose
        self.workers = max(1, workers)
        
        # Determine provider from model name
        if "gemini" in model.lower():
            self.provider = "google"
        elif "claude" in model.lower() or "sonnet" in model.lower() or "opus" in model.lower():
            self.provider = "anthropic"
        else:
            self.provider = "unknown"
        
        # Setup storage
        self.results_dir = Path(results_dir or "results")
        self.logs_dir = Path(logs_dir or "logs")
        self.store = QAResultsStore(self.results_dir)
        
        # API clients (lazy loaded)
        self._gemini_client = None
        self._anthropic_client = None
        
        # Logging
        self.logger: logging.Logger | None = None
        self.run_id: str | None = None
        self._store_lock = threading.Lock()
    
    def _get_gemini_client(self):
        """Get or create Gemini client."""
        if self._gemini_client is None:
            try:
                from google import genai
                from sf_agentbench.agents.auth import get_google_credentials
                
                creds = get_google_credentials()
                if creds and creds.get("api_key"):
                    self._gemini_client = genai.Client(api_key=creds["api_key"])
                else:
                    import os
                    api_key = os.environ.get("GOOGLE_API_KEY")
                    if api_key:
                        self._gemini_client = genai.Client(api_key=api_key)
                    else:
                        raise ValueError("No Google API key found")
            except ImportError:
                raise ImportError("Please install google-genai: pip install google-genai")
        return self._gemini_client
    
    def _get_anthropic_client(self):
        """Get or create Anthropic client."""
        if self._anthropic_client is None:
            try:
                import anthropic
                from sf_agentbench.agents.auth import get_anthropic_credentials
                
                # get_anthropic_credentials returns the API key directly as a string
                api_key = get_anthropic_credentials()
                if api_key:
                    self._anthropic_client = anthropic.Anthropic(api_key=api_key)
                else:
                    import os
                    api_key = os.environ.get("ANTHROPIC_API_KEY")
                    if api_key:
                        self._anthropic_client = anthropic.Anthropic(api_key=api_key)
                    else:
                        raise ValueError("No Anthropic API key found")
            except ImportError:
                raise ImportError("Please install anthropic: pip install anthropic")
        return self._anthropic_client
    
    def _call_gemini(self, prompt: str) -> tuple[str, int, int]:
        """Call Gemini API and return (response, input_tokens, output_tokens)."""
        from google.genai import types
        
        client = self._get_gemini_client()
        response = client.models.generate_content(
            model=self.model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=100),
        )
        
        text = ""
        # Handle potential None values in response
        if response.candidates:
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            text += part.text
        
        # If no text extracted, try to get text from response directly
        if not text and hasattr(response, 'text'):
            text = response.text or ""
        
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
            output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
        
        return text.strip(), input_tokens, output_tokens
    
    def _call_anthropic(self, prompt: str) -> tuple[str, int, int]:
        """Call Anthropic API and return (response, input_tokens, output_tokens)."""
        client = self._get_anthropic_client()
        
        response = client.messages.create(
            model=self.model,
            max_tokens=100,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        
        text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                text += block.text
        
        input_tokens = response.usage.input_tokens if response.usage else 0
        output_tokens = response.usage.output_tokens if response.usage else 0
        
        return text.strip(), input_tokens, output_tokens
    
    def ask_question(self, question: Question) -> QAResult:
        """Ask a single question using API."""
        formatted_q = question.format_for_prompt()
        prompt = QA_PROMPT_TEMPLATE.format(question=formatted_q)
        
        if self.logger:
            self.logger.debug(f"Question {question.id}: {question.question[:100]}...")
        
        start_time = time.time()
        input_tokens = 0
        output_tokens = 0
        
        try:
            if self.provider == "google":
                response, input_tokens, output_tokens = self._call_gemini(prompt)
            elif self.provider == "anthropic":
                response, input_tokens, output_tokens = self._call_anthropic(prompt)
            else:
                response = "ERROR: Unknown provider"
        except Exception as e:
            response = f"ERROR: {str(e)}"
            if self.logger:
                self.logger.error(f"Question {question.id} error: {e}")
        
        elapsed = time.time() - start_time
        
        # Evaluate
        is_correct, extracted = question.check_answer(response)
        
        if self.logger:
            status = "CORRECT" if is_correct else "INCORRECT"
            self.logger.info(
                f"Q{question.id} [{question.domain}]: {status} "
                f"(expected={question.correct_answer}, got={extracted}, time={elapsed:.1f}s)"
            )
        
        # Store for playback
        if self.run_id:
            with self._store_lock:
                self.store.log_question(
                    run_id=self.run_id,
                    question_id=question.id,
                    domain=question.domain,
                    difficulty=question.difficulty,
                    question_text=question.question,
                    correct_answer=str(question.correct_answer),
                    prompt_sent=prompt,
                    model_response=response,
                    extracted_answer=extracted,
                    is_correct=is_correct,
                    response_time=elapsed,
                )
        
        return QAResult(
            question_id=question.id,
            question_text=question.question,
            expected_answer=str(question.correct_answer),
            model_response=response,
            extracted_answer=extracted,
            is_correct=is_correct,
            response_time_seconds=elapsed,
            domain=question.domain,
            explanation=question.explanation,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    
    def run(
        self,
        test_bank: TestBank,
        max_questions: int | None = None,
        progress_callback: Callable[[QAResult], None] | None = None,
    ) -> QARunSummary:
        """Run Q&A tests using API."""
        questions = test_bank.questions
        if max_questions:
            questions = questions[:max_questions]
        
        # Start run in storage
        self.run_id = self.store.start_run(
            model_id=self.model,
            cli_id="api",  # Indicate this is API-based
            test_bank_id=test_bank.id,
            test_bank_name=test_bank.name,
        )
        
        self.logger = setup_qa_logging(self.logs_dir, self.run_id)
        
        console.print(f"\n[bold cyan]Running Q&A Test via API: {test_bank.name}[/bold cyan]")
        console.print(f"  Run ID: [dim]{self.run_id}[/dim]")
        console.print(f"  Model: [magenta]{self.model}[/magenta] via API")
        console.print(f"  Questions: {len(questions)}")
        console.print(f"  Workers: [yellow]{self.workers}[/yellow] (parallel)")
        console.print()
        
        self.logger.info(f"Starting Q&A run {self.run_id}")
        self.logger.info(f"Model: {self.model}, Questions: {len(questions)}, Workers: {self.workers}")
        
        started_at = datetime.now()
        results: list[QAResult] = []
        correct_count = 0
        
        # Run with thread pool
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(self.ask_question, q): q for q in questions}
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result.is_correct:
                        correct_count += 1
                        with _console_lock:
                            console.print(f"  [green]✓[/green] Q{result.question_id}: Correct ({result.response_time_seconds:.1f}s)")
                    else:
                        with _console_lock:
                            console.print(f"  [red]✗[/red] Q{result.question_id}: Expected {result.expected_answer}, Got {result.extracted_answer} ({result.response_time_seconds:.1f}s)")
                    
                    if progress_callback:
                        progress_callback(result)
                        
                except Exception as e:
                    self.logger.error(f"Error processing question: {e}")
        
        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()
        
        # Calculate totals
        total_input = sum(r.input_tokens for r in results)
        total_output = sum(r.output_tokens for r in results)
        total_cost = estimate_cost(self.model, total_input, total_output)
        
        # Complete run in storage
        self.store.complete_run(
            run_id=self.run_id,
            total_questions=len(questions),
            correct_answers=correct_count,
            duration_seconds=duration,
        )
        
        summary = QARunSummary(
            model_id=self.model,
            test_bank_id=test_bank.name,
            started_at=started_at,
            completed_at=completed_at,
            total_questions=len(results),
            correct_answers=correct_count,
            results=results,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            estimated_cost_usd=total_cost,
        )
        
        self.logger.info(f"Run complete: {correct_count}/{len(results)} correct ({summary.accuracy:.1f}%)")
        
        return summary
    
    def print_summary(self, summary: QARunSummary) -> None:
        """Print a formatted summary (reuse from QARunner)."""
        # Same implementation as QARunner.print_summary
        console.print("\n" + "=" * 60)
        console.print(f"[bold]Q&A Benchmark Results: {summary.model_id}[/bold]")
        console.print("=" * 60)
        
        acc_color = "green" if summary.accuracy >= 80 else "yellow" if summary.accuracy >= 60 else "red"
        console.print(f"  Questions: {summary.total_questions}")
        console.print(f"  Correct:   {summary.correct_answers}")
        console.print(f"  Accuracy:  [{acc_color}]{summary.accuracy:.1f}%[/{acc_color}]")
        
        duration = (summary.completed_at - summary.started_at).total_seconds()
        console.print(f"  Duration:  {duration:.1f}s ({summary.avg_response_time:.2f}s/question)")
        
        if summary.estimated_cost_usd > 0:
            console.print(f"  Tokens:    {summary.total_input_tokens:,} in / {summary.total_output_tokens:,} out")
            console.print(f"  Est. Cost: [yellow]${summary.estimated_cost_usd:.4f}[/yellow]")
        
        by_domain = summary.by_domain()
        if len(by_domain) > 1:
            console.print("\n[bold]By Domain:[/bold]")
            table = Table(show_header=True)
            table.add_column("Domain", style="cyan")
            table.add_column("Correct", justify="right")
            table.add_column("Total", justify="right")
            table.add_column("Accuracy", justify="right")
            
            for domain, stats in sorted(by_domain.items()):
                acc = (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                acc_color = "green" if acc >= 80 else "yellow" if acc >= 60 else "red"
                table.add_row(domain, str(stats["correct"]), str(stats["total"]), f"[{acc_color}]{acc:.0f}%[/{acc_color}]")
            
            console.print(table)
        
        console.print("=" * 60)
