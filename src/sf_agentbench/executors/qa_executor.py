"""Q&A test executor.

Executes Q&A knowledge tests against LLM agents.
"""

import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from sf_agentbench.domain.models import (
    WorkUnit,
    QATest,
    Result,
    Cost,
    TestType,
)
from sf_agentbench.domain.costs import get_cost_profile, estimate_tokens
from sf_agentbench.events import EventBus, get_event_bus
from sf_agentbench.executors.base import Executor, ExecutorResult
from sf_agentbench.workers.base import WorkerContext

console = Console()


@dataclass
class QAQuestion:
    """A single Q&A question."""
    
    id: str
    question: str
    options: dict[str, str]
    correct_answer: str
    domain: str = ""
    difficulty: str = ""


@dataclass
class QAExecutorConfig:
    """Configuration for the Q&A executor."""
    
    timeout_per_question: int = 120  # seconds
    cli_id: str = "gemini-cli"
    model: str | None = None
    prompt_template: str = """You are a Salesforce certification exam expert.

Answer the following question by selecting the BEST answer from the options provided.

Question: {question}

Options:
{options}

Important: Your response must START with ONLY the letter of the correct answer (A, B, C, D, or E) followed by your explanation.

Example format:
B

The answer is B because...
"""


class QAExecutor(Executor):
    """Executor for Q&A knowledge tests.
    
    Runs Q&A questions against CLI-based LLM agents and evaluates responses.
    """
    
    def __init__(
        self,
        config: QAExecutorConfig | None = None,
        event_bus: EventBus | None = None,
        verbose: bool = False,
    ):
        """Initialize the Q&A executor.
        
        Args:
            config: Executor configuration
            event_bus: Event bus for communication
            verbose: Enable verbose output
        """
        super().__init__(event_bus, verbose)
        self.config = config or QAExecutorConfig()
    
    def execute(self, context: WorkerContext) -> ExecutorResult:
        """Execute Q&A test work unit.
        
        Args:
            context: Worker context with the work unit
        
        Returns:
            ExecutorResult with Q&A test results
        """
        work_unit = context.work_unit
        
        # Validate test type
        if work_unit.test.type != TestType.QA:
            return ExecutorResult(
                success=False,
                error=f"Expected QA test, got {work_unit.test.type}",
            )
        
        qa_test = work_unit.test
        if not isinstance(qa_test, QATest):
            return ExecutorResult(
                success=False,
                error="Invalid test type",
            )
        
        # Extract questions from test
        questions = self._extract_questions(qa_test)
        if not questions:
            return ExecutorResult(
                success=False,
                error="No questions in test",
            )
        
        self.log_info(context, f"Running {len(questions)} Q&A questions")
        
        # Run each question
        correct = 0
        total = len(questions)
        total_cost = Cost()
        total_duration = 0.0
        results_by_domain: dict[str, dict[str, int]] = {}
        
        for i, question in enumerate(questions):
            # Check for cancellation
            if self.check_cancel(context):
                return ExecutorResult(
                    success=False,
                    score=correct / total if total > 0 else 0.0,
                    error="Cancelled",
                    details={
                        "correct": correct,
                        "total": i,
                        "cancelled_at": i,
                    },
                )
            
            # Check for pause
            self.check_pause(context)
            
            # Update progress
            context.update_status("running", progress=i / total)
            
            # Run the question
            result = self._run_question(question, work_unit.agent, context)
            
            # Track results
            if result["is_correct"]:
                correct += 1
            
            total_cost = total_cost.add(result["cost"])
            total_duration += result["duration"]
            
            # Track by domain
            domain = question.domain or "General"
            if domain not in results_by_domain:
                results_by_domain[domain] = {"correct": 0, "total": 0}
            results_by_domain[domain]["total"] += 1
            if result["is_correct"]:
                results_by_domain[domain]["correct"] += 1
            
            # Log result
            status = "✓" if result["is_correct"] else "✗"
            self.log_info(
                context,
                f"Q{i+1}: {status} {domain} (expected={question.correct_answer}, got={result['answer']})",
            )
        
        # Calculate final score
        score = correct / total if total > 0 else 0.0
        
        return ExecutorResult(
            success=True,
            score=score,
            cost=total_cost,
            duration_seconds=total_duration,
            details={
                "correct": correct,
                "total": total,
                "by_domain": results_by_domain,
            },
        )
    
    def _extract_questions(self, qa_test: QATest) -> list[QAQuestion]:
        """Extract questions from a QA test."""
        questions = []
        
        for q in qa_test.questions:
            questions.append(QAQuestion(
                id=str(q.get("id", len(questions) + 1)),
                question=q.get("question", ""),
                options=q.get("options", {}),
                correct_answer=q.get("correct_answer", ""),
                domain=q.get("domain", ""),
                difficulty=q.get("difficulty", ""),
            ))
        
        return questions
    
    def _run_question(
        self,
        question: QAQuestion,
        agent: Any,
        context: WorkerContext,
    ) -> dict[str, Any]:
        """Run a single question against the agent.
        
        Args:
            question: The question to ask
            agent: The agent configuration
            context: Worker context
        
        Returns:
            Dictionary with result details
        """
        start_time = time.time()
        
        # Build prompt
        options_text = "\n".join(
            f"{k}. {v}" for k, v in sorted(question.options.items())
        )
        prompt = self.config.prompt_template.format(
            question=question.question,
            options=options_text,
        )
        
        # Call CLI agent
        try:
            response = self._call_cli_agent(prompt, agent)
        except Exception as e:
            return {
                "is_correct": False,
                "answer": "ERROR",
                "response": str(e),
                "cost": Cost(),
                "duration": time.time() - start_time,
            }
        
        # Extract answer
        extracted = self._extract_answer(response)
        is_correct = extracted == question.correct_answer
        
        # Estimate cost
        model = self.config.model or agent.model
        cost_profile = get_cost_profile(model)
        input_tokens = estimate_tokens(prompt)
        output_tokens = estimate_tokens(response)
        estimated_usd = cost_profile.estimate(input_tokens, output_tokens)
        
        cost = Cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_usd=estimated_usd,
        )
        
        return {
            "is_correct": is_correct,
            "answer": extracted,
            "expected": question.correct_answer,
            "response": response,
            "cost": cost,
            "duration": time.time() - start_time,
        }
    
    def _call_cli_agent(self, prompt: str, agent: Any) -> str:
        """Call the CLI agent with a prompt.
        
        Args:
            prompt: The prompt to send
            agent: Agent configuration
        
        Returns:
            The agent's response
        """
        from sf_agentbench.agents.cli_runner import CLI_AGENTS
        
        cli_config = CLI_AGENTS.get(self.config.cli_id)
        if not cli_config:
            # Fallback to direct Gemini CLI
            cli_config = CLI_AGENTS.get("gemini-cli")
        
        if not cli_config:
            raise ValueError(f"CLI agent '{self.config.cli_id}' not found")
        
        # Build command
        cmd = list(cli_config.command)
        model = self.config.model or agent.model
        
        if cli_config.model_flag and model:
            cmd.extend([cli_config.model_flag, model])
        
        if cli_config.prompt_flag:
            cmd.extend([cli_config.prompt_flag, prompt])
        
        # Create temp directory for execution
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create minimal sfdx-project.json if needed
            (temp_path / "sfdx-project.json").write_text(
                '{"packageDirectories": [{"path": "force-app", "default": true}], "sourceApiVersion": "59.0"}'
            )
            
            # Run command
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=temp_path,
                timeout=self.config.timeout_per_question,
                env=os.environ.copy(),
            )
            
            return process.stdout.strip()
    
    def _extract_answer(self, response: str) -> str:
        """Extract the answer letter from a response.
        
        Args:
            response: The full response text
        
        Returns:
            Single letter answer (A-E) or 'UNKNOWN'
        """
        if not response:
            return "UNKNOWN"
        
        # Clean response
        response = response.strip()
        
        # Check for single letter at start
        if response and response[0].upper() in "ABCDE":
            return response[0].upper()
        
        # Look for common patterns
        import re
        
        patterns = [
            r"^([A-E])\.",  # A.
            r"^([A-E])\)",  # A)
            r"^([A-E]):",  # A:
            r"^([A-E])\s",  # A followed by space
            r"answer is ([A-E])",  # answer is A
            r"correct answer: ([A-E])",  # correct answer: A
            r"^([A-E])$",  # Just the letter
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).upper()
        
        return "UNKNOWN"
