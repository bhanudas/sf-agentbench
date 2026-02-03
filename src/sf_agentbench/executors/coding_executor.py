"""Coding test executor.

Executes Salesforce coding tasks against CLI-based AI agents.
"""

import os
import shutil
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
    CodingTest,
    Result,
    Cost,
    TestType,
)
from sf_agentbench.domain.costs import get_cost_profile, estimate_tokens
from sf_agentbench.events import EventBus, get_event_bus
from sf_agentbench.executors.base import Executor, ExecutorResult
from sf_agentbench.workers.base import WorkerContext
from sf_agentbench.workers.scheduler import ScratchOrgPool, ScratchOrg

console = Console()


@dataclass
class CodingExecutorConfig:
    """Configuration for the coding executor."""
    
    # Timeouts
    timeout_per_phase: int = 600  # seconds (10 min per phase)
    total_timeout: int = 1800  # seconds (30 min total)
    
    # CLI configuration
    cli_id: str = "claude-code"
    model: str | None = None
    
    # Phases
    multi_phase: bool = True
    phases: list[str] = field(default_factory=lambda: ["BUILD", "DEPLOY", "TEST"])
    
    # DevHub
    devhub_username: str = ""


class CodingExecutor(Executor):
    """Executor for Salesforce coding tasks.
    
    Runs coding tasks through a multi-phase process with scratch org integration.
    """
    
    def __init__(
        self,
        config: CodingExecutorConfig | None = None,
        scratch_org_pool: ScratchOrgPool | None = None,
        event_bus: EventBus | None = None,
        verbose: bool = False,
    ):
        """Initialize the coding executor.
        
        Args:
            config: Executor configuration
            scratch_org_pool: Pool of scratch orgs to use
            event_bus: Event bus for communication
            verbose: Enable verbose output
        """
        super().__init__(event_bus, verbose)
        self.config = config or CodingExecutorConfig()
        self.scratch_org_pool = scratch_org_pool
    
    def execute(self, context: WorkerContext) -> ExecutorResult:
        """Execute coding test work unit.
        
        Args:
            context: Worker context with the work unit
        
        Returns:
            ExecutorResult with coding test results
        """
        work_unit = context.work_unit
        
        # Validate test type
        if work_unit.test.type != TestType.CODING:
            return ExecutorResult(
                success=False,
                error=f"Expected CODING test, got {work_unit.test.type}",
            )
        
        coding_test = work_unit.test
        if not isinstance(coding_test, CodingTest):
            return ExecutorResult(
                success=False,
                error="Invalid test type",
            )
        
        # Get task path
        if not coding_test.task_path:
            return ExecutorResult(
                success=False,
                error="No task path specified",
            )
        
        task_path = Path(coding_test.task_path)
        if not task_path.exists():
            return ExecutorResult(
                success=False,
                error=f"Task path not found: {task_path}",
            )
        
        self.log_info(context, f"Starting coding task: {coding_test.name}")
        
        # Acquire scratch org
        scratch_org: ScratchOrg | None = None
        if self.scratch_org_pool:
            self.log_info(context, "Acquiring scratch org...")
            scratch_org = self.scratch_org_pool.acquire(work_unit.id)
            if not scratch_org:
                return ExecutorResult(
                    success=False,
                    error="Failed to acquire scratch org",
                )
            context.scratch_org = scratch_org.username
            self.log_info(context, f"Using scratch org: {scratch_org.username}")
        
        try:
            # Setup working directory
            with tempfile.TemporaryDirectory() as temp_dir:
                work_dir = Path(temp_dir) / "work"
                shutil.copytree(task_path, work_dir)
                
                # Read task requirements
                requirements = self._read_requirements(work_dir)
                
                # Run phases
                if self.config.multi_phase:
                    result = self._run_multi_phase(
                        context,
                        work_dir,
                        requirements,
                        work_unit.agent,
                        scratch_org,
                    )
                else:
                    result = self._run_single_phase(
                        context,
                        work_dir,
                        requirements,
                        work_unit.agent,
                        scratch_org,
                    )
                
                return result
                
        finally:
            # Release scratch org
            if scratch_org and self.scratch_org_pool:
                self.scratch_org_pool.release(scratch_org)
    
    def _read_requirements(self, work_dir: Path) -> str:
        """Read task requirements from README or task.yaml."""
        # Try README.md
        readme_path = work_dir / "README.md"
        if readme_path.exists():
            return readme_path.read_text()
        
        # Try task.yaml
        task_yaml = work_dir / "task.yaml"
        if task_yaml.exists():
            import yaml
            with open(task_yaml) as f:
                data = yaml.safe_load(f)
            return data.get("description", "") + "\n\n" + data.get("requirements", "")
        
        return "Complete the Salesforce development task in this directory."
    
    def _run_multi_phase(
        self,
        context: WorkerContext,
        work_dir: Path,
        requirements: str,
        agent: Any,
        scratch_org: ScratchOrg | None,
    ) -> ExecutorResult:
        """Run the task through multiple phases.
        
        Args:
            context: Worker context
            work_dir: Working directory
            requirements: Task requirements
            agent: Agent configuration
            scratch_org: Scratch org to use
        
        Returns:
            ExecutorResult with combined results
        """
        total_cost = Cost()
        total_duration = 0.0
        phase_results = {}
        
        phases = self.config.phases
        
        for i, phase in enumerate(phases):
            # Check for cancellation
            if self.check_cancel(context):
                return ExecutorResult(
                    success=False,
                    error="Cancelled",
                    details={"phase_results": phase_results, "cancelled_at": phase},
                )
            
            # Check for pause
            self.check_pause(context)
            
            # Update progress
            context.update_status("running", progress=(i / len(phases)))
            
            self.log_info(context, f"Starting {phase} phase")
            
            # Build phase prompt
            prompt = self._build_phase_prompt(phase, requirements, scratch_org)
            
            # Run the phase
            phase_result = self._run_cli_agent(
                context,
                work_dir,
                prompt,
                agent,
            )
            
            phase_results[phase] = phase_result
            total_cost = total_cost.add(phase_result.get("cost", Cost()))
            total_duration += phase_result.get("duration", 0.0)
            
            if not phase_result.get("success", False):
                self.log_info(context, f"{phase} phase encountered issues")
        
        # Evaluate final results
        evaluation = self._evaluate_solution(work_dir, scratch_org)
        
        return ExecutorResult(
            success=True,
            score=evaluation.get("score", 0.0),
            cost=total_cost,
            duration_seconds=total_duration,
            details={
                "phase_results": phase_results,
                "evaluation": evaluation,
            },
        )
    
    def _run_single_phase(
        self,
        context: WorkerContext,
        work_dir: Path,
        requirements: str,
        agent: Any,
        scratch_org: ScratchOrg | None,
    ) -> ExecutorResult:
        """Run the task in a single phase.
        
        Args:
            context: Worker context
            work_dir: Working directory
            requirements: Task requirements
            agent: Agent configuration
            scratch_org: Scratch org to use
        
        Returns:
            ExecutorResult
        """
        # Build prompt
        prompt = self._build_full_prompt(requirements, scratch_org)
        
        # Run agent
        result = self._run_cli_agent(context, work_dir, prompt, agent)
        
        # Evaluate
        evaluation = self._evaluate_solution(work_dir, scratch_org)
        
        return ExecutorResult(
            success=True,
            score=evaluation.get("score", 0.0),
            cost=result.get("cost", Cost()),
            duration_seconds=result.get("duration", 0.0),
            details={
                "agent_result": result,
                "evaluation": evaluation,
            },
        )
    
    def _build_phase_prompt(
        self,
        phase: str,
        requirements: str,
        scratch_org: ScratchOrg | None,
    ) -> str:
        """Build a prompt for a specific phase."""
        org_info = ""
        if scratch_org:
            org_info = f"\nTarget Scratch Org: {scratch_org.username}\n"
        
        if phase == "BUILD":
            return f"""You are a Salesforce developer. Complete the following task:

{requirements}
{org_info}
Phase: BUILD
- Read the requirements carefully
- Create or modify the necessary Salesforce metadata
- Follow Salesforce best practices
- Do NOT deploy yet - just build the solution

When complete, output: PHASE COMPLETE
"""
        elif phase == "DEPLOY":
            return f"""You are a Salesforce developer continuing your work.

{requirements}
{org_info}
Phase: DEPLOY
- Review your changes
- Deploy to the scratch org using: sf project deploy start --target-org {scratch_org.username if scratch_org else 'default'}
- Fix any deployment errors
- Ensure successful deployment

When deployment succeeds, output: PHASE COMPLETE
"""
        elif phase == "TEST":
            return f"""You are a Salesforce developer validating your work.

{requirements}
{org_info}
Phase: TEST
- Run Apex tests: sf apex run test --target-org {scratch_org.username if scratch_org else 'default'} --code-coverage
- Verify all tests pass
- Check for any runtime errors
- Ensure the solution meets requirements

When tests pass, output: PHASE COMPLETE
"""
        else:
            return requirements
    
    def _build_full_prompt(
        self,
        requirements: str,
        scratch_org: ScratchOrg | None,
    ) -> str:
        """Build a full task prompt."""
        org_info = ""
        if scratch_org:
            org_info = f"\nTarget Scratch Org: {scratch_org.username}\n"
        
        return f"""You are a Salesforce developer. Complete the following task:

{requirements}
{org_info}
Steps:
1. Read and understand the requirements
2. Create/modify necessary Salesforce metadata (Apex, Flows, etc.)
3. Deploy to the scratch org
4. Run and pass all tests

Follow Salesforce best practices. When complete, output: TASK COMPLETE
"""
    
    def _run_cli_agent(
        self,
        context: WorkerContext,
        work_dir: Path,
        prompt: str,
        agent: Any,
    ) -> dict[str, Any]:
        """Run the CLI agent with a prompt.
        
        Args:
            context: Worker context
            work_dir: Working directory
            prompt: The prompt to send
            agent: Agent configuration
        
        Returns:
            Dictionary with result details
        """
        from sf_agentbench.agents.cli_runner import CLI_AGENTS
        
        start_time = time.time()
        
        cli_config = CLI_AGENTS.get(self.config.cli_id)
        if not cli_config:
            return {
                "success": False,
                "error": f"CLI agent '{self.config.cli_id}' not found",
                "duration": 0.0,
                "cost": Cost(),
            }
        
        # Build command
        cmd = list(cli_config.command)
        model = self.config.model or agent.model
        
        if cli_config.model_flag and model:
            cmd.extend([cli_config.model_flag, model])
        
        if cli_config.prompt_flag:
            cmd.extend([cli_config.prompt_flag, prompt])
        
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=work_dir,
                timeout=self.config.timeout_per_phase,
                env=os.environ.copy(),
            )
            
            output = process.stdout
            success = "PHASE COMPLETE" in output or "TASK COMPLETE" in output
            
            # Estimate cost
            cost_profile = get_cost_profile(model)
            input_tokens = estimate_tokens(prompt)
            output_tokens = estimate_tokens(output)
            estimated_usd = cost_profile.estimate(input_tokens, output_tokens)
            
            return {
                "success": success,
                "output": output,
                "stderr": process.stderr,
                "exit_code": process.returncode,
                "duration": time.time() - start_time,
                "cost": Cost(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_usd=estimated_usd,
                ),
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout",
                "duration": time.time() - start_time,
                "cost": Cost(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time,
                "cost": Cost(),
            }
    
    def _evaluate_solution(
        self,
        work_dir: Path,
        scratch_org: ScratchOrg | None,
    ) -> dict[str, Any]:
        """Evaluate the final solution.
        
        Args:
            work_dir: Working directory with the solution
            scratch_org: Scratch org used for deployment
        
        Returns:
            Dictionary with evaluation scores
        """
        scores = {
            "deployment": 0.0,
            "tests": 0.0,
            "static_analysis": 0.0,
        }
        
        # Check for deployment success
        if scratch_org:
            # This would normally run sf project deploy preview
            scores["deployment"] = 0.5  # Placeholder
        
        # Check for test files
        test_classes = list(work_dir.rglob("*Test.cls"))
        if test_classes:
            scores["tests"] = 0.5  # Placeholder
        
        # Calculate overall score
        weights = {
            "deployment": 0.4,
            "tests": 0.4,
            "static_analysis": 0.2,
        }
        
        overall = sum(
            scores[k] * weights[k]
            for k in scores
        )
        
        return {
            "score": overall,
            "components": scores,
        }
