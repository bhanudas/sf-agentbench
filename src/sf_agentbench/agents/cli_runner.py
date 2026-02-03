"""CLI-based agent runner for real AI coding assistants.

Runs actual CLI tools (Claude Code, Gemini CLI, Aider, etc.) in monitored
subprocess terminals with isolated scratch orgs.
"""

import os
import subprocess
import shutil
import json
import time
import signal
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from datetime import datetime

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

console = Console()


@dataclass
class CLIAgentConfig:
    """Configuration for a CLI-based agent."""

    id: str
    name: str
    command: list[str]  # e.g., ["claude", "--print"] or ["gemini"]
    prompt_flag: str | None = None  # e.g., "-p" for passing prompt
    working_dir_flag: str | None = None  # Flag for working directory
    model_flag: str | None = None  # e.g., "-m" for model selection
    default_model: str | None = None  # Default model if not specified
    env_vars: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 1800  # 30 minutes default
    setup_commands: list[list[str]] = field(default_factory=list)
    # Phase-specific timeouts (more granular control)
    phase_timeouts: dict[str, int] = field(default_factory=lambda: {
        "build": 600,   # 10 minutes for creating files
        "deploy": 300,  # 5 minutes for deployment
        "test": 300,    # 5 minutes for testing
    })
    # Max retries per phase
    max_phase_retries: int = 2
    # Custom prompt builder function name (if agent needs different prompts)
    prompt_style: str = "default"  # "default", "gemini", "aider"
    # Maximum feedback iterations (deployment/test error -> fix loop)
    max_feedback_iterations: int = 5
    # Whether the agent supports --continue for session continuity
    supports_continue: bool = False


# Pre-configured CLI agents
CLI_AGENTS = {
    "claude-code": CLIAgentConfig(
        id="claude-code",
        name="Claude Code",
        # --dangerously-skip-permissions is needed for -p mode to write files
        # This is safe because we run in isolated temp directories for benchmarking
        command=["claude", "--dangerously-skip-permissions"],
        prompt_flag="-p",
        model_flag="--model",
        default_model=None,  # Uses Claude's default
        timeout_seconds=1800,
        phase_timeouts={"build": 600, "deploy": 300, "test": 300},
        max_phase_retries=2,
        prompt_style="default",
        max_feedback_iterations=5,
        supports_continue=True,  # Claude Code supports --continue for session continuity
    ),
    "gemini-cli": CLIAgentConfig(
        id="gemini-cli",
        name="Gemini CLI",
        # -y for auto-accept, --sandbox=false to allow file writes
        command=["gemini", "-y", "--sandbox=false"],
        prompt_flag="-p",
        model_flag="-m",
        default_model="gemini-2.5-pro",
        timeout_seconds=2400,  # 40 minutes - Gemini often needs more time
        phase_timeouts={"build": 900, "deploy": 600, "test": 600},  # More time per phase
        max_phase_retries=3,  # More retries for Gemini
        prompt_style="gemini",  # Use Gemini-specific prompts
    ),
    "aider": CLIAgentConfig(
        id="aider",
        name="Aider",
        command=["aider", "--no-git", "--yes"],
        prompt_flag="--message",
        model_flag="--model",
        default_model=None,
        timeout_seconds=1800,
        phase_timeouts={"build": 600, "deploy": 300, "test": 300},
        max_phase_retries=2,
        prompt_style="aider",
    ),
    "codex": CLIAgentConfig(
        id="codex",
        name="OpenAI Codex CLI",
        command=["codex"],
        prompt_flag=None,
        model_flag=None,
        timeout_seconds=1800,
        prompt_style="default",
    ),
    "cline": CLIAgentConfig(
        id="cline",
        name="Cline",
        command=["cline"],
        prompt_flag=None,
        model_flag=None,
        timeout_seconds=1800,
        prompt_style="default",
    ),
    "kimi-code": CLIAgentConfig(
        id="kimi-code",
        name="Kimi Code",
        # -y (--yolo/--yes) for auto-approve, similar to Claude's --dangerously-skip-permissions
        command=["kimi", "-y"],
        prompt_flag="-p",
        model_flag="-m",
        default_model=None,  # Uses Kimi's default model
        timeout_seconds=1800,
        phase_timeouts={"build": 600, "deploy": 300, "test": 300},
        max_phase_retries=2,
        prompt_style="default",
        max_feedback_iterations=5,
        supports_continue=True,  # Kimi Code supports --continue for session continuity
    ),
}


@dataclass
class CLIRunResult:
    """Result from running a CLI agent."""
    
    agent_id: str
    scratch_org: str
    work_dir: Path
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    files_modified: list[str] = field(default_factory=list)


class CLIAgentRunner:
    """Runs CLI-based AI agents in isolated environments."""
    
    def __init__(
        self,
        task_path: Path,
        devhub_username: str,
        verbose: bool = False,
    ):
        self.task_path = task_path
        self.devhub_username = devhub_username
        self.verbose = verbose
        self.work_dir: Path | None = None
        self.scratch_org: str | None = None
        self._process: subprocess.Popen | None = None
    
    def setup_environment(self, agent_id: str) -> tuple[Path, str]:
        """
        Set up an isolated environment for the agent.
        
        Returns:
            Tuple of (work_dir, scratch_org_username)
        """
        # Create unique working directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        work_dir = Path(f"/tmp/sf-agentbench/{agent_id}_{timestamp}")
        work_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy task files to working directory
        console.print(f"  [dim]Copying task to {work_dir}[/dim]")
        shutil.copytree(self.task_path, work_dir, dirs_exist_ok=True)
        
        # Remove any existing solution files (agent should create these)
        self._clean_solution_files(work_dir)
        
        self.work_dir = work_dir
        
        # Create unique scratch org
        console.print(f"  [dim]Creating scratch org for {agent_id}...[/dim]")
        org_alias = f"sfb-{agent_id[:8]}-{timestamp[-6:]}"
        
        result = subprocess.run(
            [
                "sf", "org", "create", "scratch",
                "--definition-file", "config/project-scratch-def.json",
                "--target-dev-hub", self.devhub_username,
                "--duration-days", "1",
                "--wait", "10",
                "--alias", org_alias,
                "--set-default",
                "--json"
            ],
            capture_output=True,
            text=True,
            cwd=work_dir,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create scratch org: {result.stderr}")
        
        org_data = json.loads(result.stdout)
        self.scratch_org = org_data["result"]["username"]
        
        console.print(f"  [green]✓ Scratch org: {self.scratch_org}[/green]")
        
        # Deploy base metadata (custom fields, test classes)
        console.print(f"  [dim]Deploying base metadata...[/dim]")
        subprocess.run(
            [
                "sf", "project", "deploy", "start",
                "--target-org", self.scratch_org,
                "--source-dir", "force-app",
                "--ignore-conflicts",
                "--wait", "10"
            ],
            capture_output=True,
            cwd=work_dir,
        )
        console.print(f"  [green]✓ Base metadata deployed[/green]")
        
        return work_dir, self.scratch_org
    
    def _clean_solution_files(self, work_dir: Path):
        """Remove solution files so agent starts fresh."""
        # Remove validation rules (agent should create)
        validation_rules = work_dir.glob("**/validationRules/*.xml")
        for f in validation_rules:
            f.unlink()

        # Remove flows (agent should create)
        flows = work_dir.glob("**/flows/*.xml")
        for f in flows:
            # Keep test flows, remove solution flows
            if "Test" not in f.name:
                f.unlink()

        # Remove non-test Apex classes (agent should create)
        classes = work_dir.glob("**/classes/*.cls")
        for f in classes:
            if "Test" not in f.name:
                f.unlink()
                # Also remove meta file
                meta = f.with_suffix(".cls-meta.xml")
                if meta.exists():
                    meta.unlink()

    def _normalize_metadata_files(self, work_dir: Path) -> int:
        """
        Fix common Salesforce metadata file extension issues.

        CLI agents often create files with incorrect extensions. This method
        normalizes them to the correct Salesforce metadata format.

        Returns:
            Number of files fixed
        """
        fixes_count = 0

        # Fix flow files: .flow -> .flow-meta.xml
        for f in work_dir.glob("**/flows/*.flow"):
            if not f.name.endswith("-meta.xml"):
                new_name = f.with_name(f.name.replace(".flow", ".flow-meta.xml"))
                f.rename(new_name)
                console.print(f"  [yellow]⚠ Fixed flow extension: {f.name} → {new_name.name}[/yellow]")
                fixes_count += 1

        # Fix validation rules: .validationRule -> .validationRule-meta.xml
        for f in work_dir.glob("**/validationRules/*.validationRule"):
            if not f.name.endswith("-meta.xml"):
                new_name = f.with_name(f.name.replace(".validationRule", ".validationRule-meta.xml"))
                f.rename(new_name)
                console.print(f"  [yellow]⚠ Fixed validation rule extension: {f.name} → {new_name.name}[/yellow]")
                fixes_count += 1

        # Fix trigger files that are missing -meta.xml companion
        for f in work_dir.glob("**/triggers/*.trigger"):
            meta_file = f.with_suffix(".trigger-meta.xml")
            if not meta_file.exists():
                # Create a basic meta file
                meta_content = """<?xml version="1.0" encoding="UTF-8"?>
<ApexTrigger xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>58.0</apiVersion>
    <status>Active</status>
</ApexTrigger>
"""
                meta_file.write_text(meta_content)
                console.print(f"  [yellow]⚠ Created missing trigger meta: {meta_file.name}[/yellow]")
                fixes_count += 1

        # Fix class files that are missing -meta.xml companion
        for f in work_dir.glob("**/classes/*.cls"):
            meta_file = f.with_suffix(".cls-meta.xml")
            if not meta_file.exists():
                # Create a basic meta file
                meta_content = """<?xml version="1.0" encoding="UTF-8"?>
<ApexClass xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>58.0</apiVersion>
    <status>Active</status>
</ApexClass>
"""
                meta_file.write_text(meta_content)
                console.print(f"  [yellow]⚠ Created missing class meta: {meta_file.name}[/yellow]")
                fixes_count += 1

        return fixes_count

    def _run_deployment(self) -> tuple[bool, str, str]:
        """
        Run Salesforce deployment and return results.
        
        Returns:
            Tuple of (success, stdout, error_message)
        """
        if not self.work_dir or not self.scratch_org:
            return False, "", "Work directory or scratch org not set"
        
        console.print("  [dim]Running deployment...[/dim]")
        
        result = subprocess.run(
            [
                "sf", "project", "deploy", "start",
                "--source-dir", "force-app",
                "--target-org", self.scratch_org,
                "--wait", "10",
                "--json"
            ],
            capture_output=True,
            text=True,
            cwd=self.work_dir,
        )
        
        stdout = result.stdout
        stderr = result.stderr
        
        # Try to parse JSON response
        try:
            data = json.loads(stdout)
            if data.get("status") == 0:
                console.print("  [green]✓ Deployment successful[/green]")
                return True, stdout, ""
            else:
                # Extract error messages
                errors = []
                if "result" in data:
                    result_data = data["result"]
                    if "details" in result_data:
                        details = result_data["details"]
                        if "componentFailures" in details:
                            for failure in details["componentFailures"]:
                                problem = failure.get("problem", "Unknown error")
                                component = failure.get("fullName", "Unknown component")
                                errors.append(f"- {component}: {problem}")
                
                if not errors:
                    errors = [data.get("message", "Deployment failed")]
                
                error_msg = "\n".join(errors)
                console.print(f"  [red]✗ Deployment failed: {len(errors)} error(s)[/red]")
                return False, stdout, error_msg
        except json.JSONDecodeError:
            # Non-JSON output - check return code
            if result.returncode == 0:
                console.print("  [green]✓ Deployment successful[/green]")
                return True, stdout, ""
            else:
                error_msg = stderr or stdout or "Deployment failed with unknown error"
                console.print(f"  [red]✗ Deployment failed[/red]")
                return False, stdout, error_msg

    def _run_tests(self) -> tuple[bool, str, str]:
        """
        Run Apex tests and return results.
        
        Returns:
            Tuple of (success, stdout, failure_details)
        """
        if not self.work_dir or not self.scratch_org:
            return False, "", "Work directory or scratch org not set"
        
        console.print("  [dim]Running Apex tests...[/dim]")
        
        result = subprocess.run(
            [
                "sf", "apex", "run", "test",
                "--target-org", self.scratch_org,
                "--test-level", "RunLocalTests",
                "--result-format", "json",
                "--wait", "10"
            ],
            capture_output=True,
            text=True,
            cwd=self.work_dir,
        )
        
        stdout = result.stdout
        stderr = result.stderr
        
        # Try to parse JSON response
        try:
            data = json.loads(stdout)
            summary = data.get("result", {}).get("summary", {})
            outcome = summary.get("outcome", "").lower()
            
            if outcome == "passed":
                passing = summary.get("passing", 0)
                console.print(f"  [green]✓ All tests passed ({passing} tests)[/green]")
                return True, stdout, ""
            else:
                # Extract failure details
                failures = []
                tests = data.get("result", {}).get("tests", [])
                for test in tests:
                    if test.get("Outcome") == "Fail":
                        method = test.get("MethodName", "Unknown")
                        message = test.get("Message", "No message")
                        stack = test.get("StackTrace", "")
                        failures.append(f"- {method}: {message}")
                        if stack:
                            # Include first few lines of stack trace
                            stack_lines = stack.split("\n")[:3]
                            for line in stack_lines:
                                failures.append(f"    {line}")
                
                if not failures:
                    failures = [f"Tests failed: {summary.get('failing', 0)} failures"]
                
                failure_msg = "\n".join(failures)
                console.print(f"  [red]✗ Tests failed: {summary.get('failing', 0)} failure(s)[/red]")
                return False, stdout, failure_msg
        except json.JSONDecodeError:
            # Non-JSON output - check return code
            if result.returncode == 0:
                console.print("  [green]✓ Tests passed[/green]")
                return True, stdout, ""
            else:
                failure_msg = stderr or stdout or "Tests failed with unknown error"
                console.print(f"  [red]✗ Tests failed[/red]")
                return False, stdout, failure_msg

    def _build_fix_prompt(
        self,
        error_type: str,
        error_message: str,
        prompt_style: str = "default",
    ) -> str:
        """
        Build a prompt asking the agent to fix an error.
        
        Args:
            error_type: "deployment" or "test"
            error_message: The error details
            prompt_style: Prompt style - 'default', 'gemini', or 'aider'
        
        Returns:
            Fix prompt for the agent
        """
        if error_type == "deployment":
            if prompt_style == "gemini":
                return f"""# Deployment Failed - Please Fix

The deployment to Salesforce failed with the following error(s):

```
{error_message}
```

## Common Issues

1. **Wrong file extension**: Validation rules must end in `.validationRule-meta.xml`, flows in `.flow-meta.xml`
2. **Invalid XML syntax**: Check for unclosed tags, missing quotes
3. **Missing required fields**: Check Salesforce metadata documentation
4. **Invalid formula**: Check field API names and formula syntax

## Your Task

1. Read the error messages above
2. Fix the affected file(s)
3. When done, say "READY TO DEPLOY"
"""
            elif prompt_style == "aider":
                return f"""Deployment failed with errors:

{error_message}

Fix the files and say "READY TO DEPLOY" when done.
"""
            else:  # default (Claude)
                return f"""## Deployment Failed

The deployment to Salesforce failed with the following error(s):

{error_message}

Please analyze these errors and fix your metadata files. Common issues include:
- Incorrect file extensions (should be .validationRule-meta.xml, .flow-meta.xml)
- Invalid XML syntax
- Missing required elements in the metadata
- Invalid field API names or formula references

Fix the issues and say "READY TO DEPLOY" when you're done.
"""
        else:  # test failures
            if prompt_style == "gemini":
                return f"""# Tests Failed - Please Fix

The Apex tests failed with the following error(s):

```
{error_message}
```

## Your Task

1. Analyze the test failure messages
2. Fix your implementation (validation rule, flow, or Apex code)
3. The system will redeploy and rerun tests automatically
4. When done fixing, say "READY TO TEST"
"""
            elif prompt_style == "aider":
                return f"""Tests failed:

{error_message}

Fix the implementation and say "READY TO TEST" when done.
"""
            else:  # default (Claude)
                return f"""## Tests Failed

The Apex tests failed with the following error(s):

{error_message}

Please analyze these test failures and fix your implementation. The tests verify:
- Validation rules block invalid data correctly
- Flows calculate field values correctly
- Apex code handles edge cases properly

Fix the issues and say "READY TO TEST" when you're done.
"""

    def run_with_feedback(
        self,
        agent_config: CLIAgentConfig,
        task_readme: str,
        model: str | None = None,
        max_iterations: int | None = None,
        on_output: Callable[[str], None] | None = None,
    ) -> CLIRunResult:
        """
        Run a CLI agent with automatic deployment/test feedback loop.
        
        This method:
        1. Asks agent to create files (BUILD phase)
        2. Runs deployment and captures errors
        3. If deployment fails, sends error back to agent
        4. Repeats until deployment succeeds or max iterations
        5. Runs tests and similarly loops on failures
        
        Args:
            agent_config: Configuration for the CLI agent
            task_readme: The task requirements from README.md
            model: Model to use (overrides default)
            max_iterations: Max feedback iterations (defaults to agent config)
            on_output: Callback for real-time output
        
        Returns:
            CLIRunResult with combined execution details
        """
        started_at = datetime.now()
        all_stdout = []
        all_stderr = []
        total_duration = 0.0
        
        # Use agent-specific iteration count if not overridden
        iterations_limit = max_iterations or agent_config.max_feedback_iterations
        
        console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
        console.print(f"[bold cyan]FEEDBACK LOOP MODE (max {iterations_limit} iterations)[/bold cyan]")
        console.print(f"[bold cyan]{'='*60}[/bold cyan]")
        
        # Phase 1: BUILD - Ask agent to create files
        console.print(f"\n[bold magenta]PHASE 1: BUILD[/bold magenta]")
        
        build_prompt = self._build_feedback_initial_prompt(
            task_readme,
            prompt_style=agent_config.prompt_style,
        )
        
        result = self.run_agent(
            agent_config=agent_config,
            prompt=build_prompt,
            model=model,
            on_output=on_output,
            continue_session=False,
            completion_signal="READY TO DEPLOY",
        )
        
        all_stdout.append(result.stdout)
        all_stderr.append(result.stderr)
        total_duration += result.duration_seconds
        
        if result.timed_out:
            console.print("[red]BUILD phase timed out[/red]")
            return self._create_feedback_result(
                agent_config, started_at, total_duration,
                all_stdout, all_stderr, result, timed_out=True
            )
        
        # Normalize metadata files before deployment
        self._normalize_metadata_files(self.work_dir)
        
        # Phase 2: DEPLOY loop
        console.print(f"\n[bold magenta]PHASE 2: DEPLOY (with feedback loop)[/bold magenta]")
        
        deploy_success = False
        iteration = 0
        
        while not deploy_success and iteration < iterations_limit:
            iteration += 1
            console.print(f"\n[dim]Deploy attempt {iteration}/{iterations_limit}[/dim]")
            
            success, stdout, error_msg = self._run_deployment()
            all_stdout.append(stdout)
            
            if success:
                deploy_success = True
                console.print(f"[green]✓ Deployment succeeded on attempt {iteration}[/green]")
            else:
                if iteration >= iterations_limit:
                    console.print(f"[red]✗ Max iterations reached, deployment still failing[/red]")
                    break
                
                # Send error back to agent
                console.print(f"[yellow]Sending deployment error to agent for fixing...[/yellow]")
                
                fix_prompt = self._build_fix_prompt(
                    "deployment",
                    error_msg,
                    prompt_style=agent_config.prompt_style,
                )
                
                # Use --continue for session continuity if supported
                result = self.run_agent(
                    agent_config=agent_config,
                    prompt=fix_prompt,
                    model=model,
                    on_output=on_output,
                    continue_session=agent_config.supports_continue,
                    completion_signal="READY TO DEPLOY",
                )
                
                all_stdout.append(result.stdout)
                all_stderr.append(result.stderr)
                total_duration += result.duration_seconds
                
                if result.timed_out:
                    console.print("[red]Fix phase timed out[/red]")
                    return self._create_feedback_result(
                        agent_config, started_at, total_duration,
                        all_stdout, all_stderr, result, timed_out=True
                    )
                
                # Normalize again after fixes
                self._normalize_metadata_files(self.work_dir)
        
        if not deploy_success:
            console.print("[red]Deployment failed after all attempts[/red]")
            return self._create_feedback_result(
                agent_config, started_at, total_duration,
                all_stdout, all_stderr, result
            )
        
        # Phase 3: TEST loop
        console.print(f"\n[bold magenta]PHASE 3: TEST (with feedback loop)[/bold magenta]")
        
        test_success = False
        test_iteration = 0
        remaining_iterations = iterations_limit - iteration + 1  # Allow remaining iterations for tests
        
        while not test_success and test_iteration < remaining_iterations:
            test_iteration += 1
            console.print(f"\n[dim]Test attempt {test_iteration}/{remaining_iterations}[/dim]")
            
            success, stdout, failure_msg = self._run_tests()
            all_stdout.append(stdout)
            
            if success:
                test_success = True
                console.print(f"[green]✓ All tests passed on attempt {test_iteration}[/green]")
            else:
                if test_iteration >= remaining_iterations:
                    console.print(f"[red]✗ Max iterations reached, tests still failing[/red]")
                    break
                
                # Send failure back to agent
                console.print(f"[yellow]Sending test failures to agent for fixing...[/yellow]")
                
                fix_prompt = self._build_fix_prompt(
                    "test",
                    failure_msg,
                    prompt_style=agent_config.prompt_style,
                )
                
                result = self.run_agent(
                    agent_config=agent_config,
                    prompt=fix_prompt,
                    model=model,
                    on_output=on_output,
                    continue_session=agent_config.supports_continue,
                    completion_signal="READY TO TEST",
                )
                
                all_stdout.append(result.stdout)
                all_stderr.append(result.stderr)
                total_duration += result.duration_seconds
                
                if result.timed_out:
                    console.print("[red]Fix phase timed out[/red]")
                    return self._create_feedback_result(
                        agent_config, started_at, total_duration,
                        all_stdout, all_stderr, result, timed_out=True
                    )
                
                # Normalize and redeploy after fixes
                self._normalize_metadata_files(self.work_dir)
                
                # Redeploy the fixes
                console.print("  [dim]Redeploying fixes...[/dim]")
                deploy_ok, _, deploy_err = self._run_deployment()
                if not deploy_ok:
                    console.print(f"  [yellow]⚠ Redeploy failed: {deploy_err[:100]}[/yellow]")
        
        # Final result
        console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
        if test_success:
            console.print("[bold green]TASK COMPLETE - All tests passed![/bold green]")
        elif deploy_success:
            console.print("[bold yellow]PARTIAL SUCCESS - Deployed but tests failed[/bold yellow]")
        else:
            console.print("[bold red]TASK FAILED - Could not deploy successfully[/bold red]")
        console.print(f"[bold cyan]{'='*60}[/bold cyan]")
        
        return self._create_feedback_result(
            agent_config, started_at, total_duration,
            all_stdout, all_stderr, result
        )

    def _build_feedback_initial_prompt(
        self,
        task_readme: str,
        prompt_style: str = "default",
    ) -> str:
        """Build the initial BUILD prompt for feedback loop mode."""
        if prompt_style == "gemini":
            return f"""# Salesforce Development Task

## Requirements

{task_readme}

## Environment Setup (Already Done)

- Salesforce DX project is ready
- Scratch org is authenticated
- Custom fields exist on the Lead object
- Test classes are already deployed

## YOUR TASK: Create Solution Files

Create the Salesforce metadata files to implement the requirements.

### File Extensions (CRITICAL)

- Validation rules: `.validationRule-meta.xml`
- Flows: `.flow-meta.xml`
- Apex classes: `.cls` + `.cls-meta.xml`
- Apex triggers: `.trigger` + `.trigger-meta.xml`

### When Done

After creating all files, say "READY TO DEPLOY"

The system will automatically deploy and run tests, sending you any errors to fix.
"""
        elif prompt_style == "aider":
            return f"""{task_readme}

Create the required Salesforce metadata files.
Use correct extensions: .validationRule-meta.xml, .flow-meta.xml

Say "READY TO DEPLOY" when done. The system will deploy and test automatically.
"""
        else:  # default (Claude)
            return f"""You are working on a Salesforce development task.

## Task Requirements

{task_readme}

## Your Environment

- You are in a Salesforce DX project directory
- A scratch org is already authenticated and set as default
- Custom fields and test classes are already deployed
- You need to implement the solution

## Salesforce Metadata File Conventions

IMPORTANT: Use the correct file extensions:

- **Validation Rules**: `force-app/main/default/objects/<Object>/validationRules/<Name>.validationRule-meta.xml`
- **Record-Triggered Flows**: `force-app/main/default/flows/<Name>.flow-meta.xml`
- **Apex Classes**: `force-app/main/default/classes/<Name>.cls` + `.cls-meta.xml`
- **Apex Triggers**: `force-app/main/default/triggers/<Name>.trigger` + `.trigger-meta.xml`

## Your Task

Create all the necessary metadata files to implement the requirements.

**DO NOT** run deployment or tests yourself - the system will handle that automatically and send you any errors to fix.

When you have created all required files, say "READY TO DEPLOY".
"""

    def _create_feedback_result(
        self,
        agent_config: CLIAgentConfig,
        started_at: datetime,
        total_duration: float,
        all_stdout: list[str],
        all_stderr: list[str],
        last_result: CLIRunResult,
        timed_out: bool = False,
    ) -> CLIRunResult:
        """Create a CLIRunResult from feedback loop execution."""
        completed_at = datetime.now()
        files_modified = self._get_modified_files()
        
        return CLIRunResult(
            agent_id=agent_config.id,
            scratch_org=self.scratch_org,
            work_dir=self.work_dir,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=total_duration,
            exit_code=last_result.exit_code if last_result else 1,
            stdout="\n".join(all_stdout),
            stderr="\n".join(all_stderr),
            timed_out=timed_out,
            files_modified=files_modified,
        )
    
    def build_prompt(
        self,
        task_readme: str,
        phase: str = "full",
        prompt_style: str = "default",
    ) -> str:
        """Build the prompt to give to the CLI agent.

        Args:
            task_readme: The task requirements from README.md
            phase: One of 'full', 'build', 'deploy', 'test'
            prompt_style: Prompt style - 'default', 'gemini', or 'aider'
        """
        if prompt_style == "gemini":
            return self._build_gemini_prompt(task_readme, phase)
        elif prompt_style == "aider":
            return self._build_aider_prompt(task_readme, phase)

        # Default prompt style (optimized for Claude Code)
        if phase == "build":
            return f"""You are working on a Salesforce development task.

## Task Requirements

{task_readme}

## Your Environment

- You are in a Salesforce DX project directory
- A scratch org is already authenticated and set as default
- Custom fields and test classes are already deployed
- You need to implement the solution (validation rules, flows, Apex classes as needed)

## Salesforce Metadata File Conventions

IMPORTANT: Use the correct file extensions and locations:

- **Validation Rules**: `force-app/main/default/objects/<Object>/validationRules/<RuleName>.validationRule-meta.xml`
- **Record-Triggered Flows**: `force-app/main/default/flows/<FlowName>.flow-meta.xml`
- **Apex Classes**: `force-app/main/default/classes/<ClassName>.cls` + `.cls-meta.xml`
- **Apex Triggers**: `force-app/main/default/triggers/<TriggerName>.trigger` + `.trigger-meta.xml`

## Phase 1: BUILD

Create all the necessary Salesforce metadata files to implement the requirements.
Focus ONLY on creating the files with CORRECT file extensions - do NOT deploy yet.

When you have created all required files, say "BUILD COMPLETE".
"""
        elif phase == "deploy":
            return """## Phase 2: DEPLOY

Now deploy your solution to the scratch org and fix any deployment errors.

Run: sf project deploy start --source-dir force-app

If deployment fails:
1. Read the error messages carefully
2. Fix the metadata files
3. Try deploying again

Repeat until deployment succeeds. When deployment is successful, say "DEPLOY COMPLETE".
"""
        elif phase == "test":
            return """## Phase 3: TEST & VALIDATE

Now run the Apex tests to validate your solution.

Run: sf apex run test --test-level RunLocalTests --result-format human

If tests fail:
1. Read the failure messages carefully
2. Fix your implementation
3. Redeploy: sf project deploy start --source-dir force-app
4. Run tests again

Repeat until all tests pass. When all tests pass, say "TASK COMPLETE".
"""
        else:  # full - original single-phase prompt
            return f"""You are working on a Salesforce development task.

## Task Requirements

{task_readme}

## Your Environment

- You are in a Salesforce DX project directory
- A scratch org is already authenticated and set as default
- Custom fields (`Annual_Revenue__c`, `Lead_Score__c`) and test classes are already deployed
- You need to implement: (1) validation rule and (2) record-triggered flow

## REQUIRED: Create These Files

You MUST create these specific files with ALL logic inline:

1. **Validation Rule** (blocking negative Annual Revenue):
   `force-app/main/default/objects/Lead/validationRules/Annual_Revenue_Positive.validationRule-meta.xml`

2. **Record-Triggered Flow** with scoring logic INLINE (do NOT reference other flows):
   `force-app/main/default/flows/Lead_Scoring.flow-meta.xml`

   The flow must contain ALL scoring logic directly - do NOT use subflows or call external flows.
   Use Decision elements and Assignment elements to calculate the score.

## File Extension Rules (CRITICAL)

- Validation rules: `.validationRule-meta.xml`
- Flows: `.flow-meta.xml`

## Steps to Complete

1. Create the validation rule file
2. Create the flow file with ALL scoring logic inline
3. Deploy: `sf project deploy start --source-dir force-app`
4. If deployment fails, fix files and redeploy
5. Run tests: `sf apex run test --test-level RunLocalTests --result-format human`
6. If tests fail, fix implementation and repeat

## Completion

After all tests pass, say "TASK COMPLETE".
"""

    def _build_gemini_prompt(self, task_readme: str, phase: str = "full") -> str:
        """Build Gemini-optimized prompts with explicit step-by-step instructions."""
        if phase == "build":
            return f"""# Salesforce Development Task

## Requirements
{task_readme}

## Environment Setup (Already Done)
- Salesforce DX project is ready
- Scratch org is authenticated (check with: sf org list)
- Custom fields exist: Annual_Revenue__c, Lead_Score__c on Lead object
- Test classes are deployed

## YOUR TASK: Create Solution Files

Create these EXACT files:

### File 1: Validation Rule
Path: `force-app/main/default/objects/Lead/validationRules/Annual_Revenue_Positive.validationRule-meta.xml`

Create directories first:
```bash
mkdir -p force-app/main/default/objects/Lead/validationRules
```

Then create the file with content that blocks negative Annual Revenue values.

### File 2: Record-Triggered Flow
Path: `force-app/main/default/flows/Lead_Scoring.flow-meta.xml`

The flow MUST:
- Trigger: After Record Created or Updated on Lead
- Calculate Lead_Score__c based on:
  - +10 if Industry = 'Technology' or 'Finance'
  - +20 if Annual_Revenue__c > 1000000
  - +15 if NumberOfEmployees > 100
- ALL logic must be INLINE (no subflows)

## IMPORTANT FILE EXTENSIONS
- Validation rules: `.validationRule-meta.xml` (NOT just .xml)
- Flows: `.flow-meta.xml` (NOT just .flow or .xml)

## When Done
After creating both files, output: BUILD COMPLETE
"""
        elif phase == "deploy":
            return """# Phase 2: Deploy to Salesforce

## Step 1: Deploy
Run this command:
```bash
sf project deploy start --source-dir force-app --wait 10
```

## If Deployment Fails:
1. Read the error message carefully
2. Common issues:
   - Wrong file extension (must be .flow-meta.xml, .validationRule-meta.xml)
   - Invalid XML syntax
   - Missing required elements
3. Fix the file and redeploy

## When Done
After successful deployment, output: DEPLOY COMPLETE
"""
        elif phase == "test":
            return """# Phase 3: Run Tests

## Step 1: Run Apex Tests
```bash
sf apex run test --test-level RunLocalTests --result-format human --wait 10
```

## If Tests Fail:
1. Read the failure messages
2. Check your Flow logic:
   - Is scoring calculated correctly?
   - Are all conditions checked?
3. Check your Validation Rule:
   - Does it block negative values?
4. Fix, redeploy, and test again:
```bash
sf project deploy start --source-dir force-app --wait 10
sf apex run test --test-level RunLocalTests --result-format human --wait 10
```

## When Done
After ALL tests pass, output: TASK COMPLETE
"""
        else:  # full
            return f"""# Salesforce Development Task

## Requirements
{task_readme}

## Environment
- Salesforce DX project ready
- Scratch org authenticated
- Custom fields exist: Annual_Revenue__c, Lead_Score__c on Lead

## Create These Files

### 1. Validation Rule
Path: `force-app/main/default/objects/Lead/validationRules/Annual_Revenue_Positive.validationRule-meta.xml`

Create directory: `mkdir -p force-app/main/default/objects/Lead/validationRules`

### 2. Record-Triggered Flow
Path: `force-app/main/default/flows/Lead_Scoring.flow-meta.xml`

Flow requirements:
- Trigger: After Record Created/Updated on Lead
- Calculate Lead_Score__c:
  - +10 for Technology/Finance industry
  - +20 for Annual_Revenue__c > 1000000
  - +15 for NumberOfEmployees > 100

## Steps
1. Create validation rule file
2. Create flow file
3. Deploy: `sf project deploy start --source-dir force-app`
4. Fix any errors and redeploy
5. Test: `sf apex run test --test-level RunLocalTests --result-format human`
6. Fix any failures and repeat

Output TASK COMPLETE when all tests pass.
"""

    def _build_aider_prompt(self, task_readme: str, phase: str = "full") -> str:
        """Build Aider-optimized prompts focused on file creation."""
        if phase == "build":
            return f"""Create Salesforce metadata files for this task:

{task_readme}

Files to create:
1. force-app/main/default/objects/Lead/validationRules/Annual_Revenue_Positive.validationRule-meta.xml
   - Block negative Annual_Revenue__c values

2. force-app/main/default/flows/Lead_Scoring.flow-meta.xml
   - Record-triggered flow on Lead (after save)
   - Calculate Lead_Score__c: +10 Tech/Finance, +20 Revenue>1M, +15 Employees>100

When done say: BUILD COMPLETE
"""
        elif phase == "deploy":
            return """Deploy the solution:

Run: sf project deploy start --source-dir force-app

Fix any deployment errors and redeploy until successful.

When successful say: DEPLOY COMPLETE
"""
        elif phase == "test":
            return """Run tests and fix failures:

Run: sf apex run test --test-level RunLocalTests --result-format human

If tests fail, fix the implementation, redeploy, and test again.

When all tests pass say: TASK COMPLETE
"""
        else:
            return f"""{task_readme}

Create:
1. Validation rule: force-app/main/default/objects/Lead/validationRules/Annual_Revenue_Positive.validationRule-meta.xml
2. Flow: force-app/main/default/flows/Lead_Scoring.flow-meta.xml

Then deploy (sf project deploy start) and run tests (sf apex run test).
Say TASK COMPLETE when tests pass.
"""

    def run_multi_phase(
        self,
        agent_config: CLIAgentConfig,
        task_readme: str,
        model: str | None = None,
        max_retries: int | None = None,
        on_output: Callable[[str], None] | None = None,
    ) -> CLIRunResult:
        """
        Run a CLI agent with multi-phase prompting for better results.

        Phases:
        1. BUILD - Create the solution files
        2. DEPLOY - Deploy and fix deployment errors
        3. TEST - Run tests and fix failures

        Uses --continue flag for Claude Code to maintain session context
        between phases, ensuring the agent knows what files were created.

        Args:
            agent_config: Configuration for the CLI agent
            task_readme: The task requirements from README.md
            model: Model to use (overrides default)
            max_retries: Max retries per phase (defaults to agent config)
            on_output: Callback for real-time output

        Returns:
            CLIRunResult with combined execution details
        """
        from rich.console import Console
        console = Console()

        started_at = datetime.now()
        all_stdout = []
        all_stderr = []
        total_duration = 0.0
        result = None

        # Use agent-specific retry count if not overridden
        retries_per_phase = max_retries if max_retries is not None else agent_config.max_phase_retries

        phases = [
            ("build", "BUILD COMPLETE"),
            ("deploy", "DEPLOY COMPLETE"),
            ("test", "TASK COMPLETE"),
        ]

        for i, (phase_name, completion_signal) in enumerate(phases):
            phase_timeout = agent_config.phase_timeouts.get(phase_name, 600)
            phase_success = False
            retry_count = 0

            while not phase_success and retry_count <= retries_per_phase:
                if retry_count > 0:
                    console.print(f"\n[yellow]Retry {retry_count}/{retries_per_phase} for {phase_name.upper()}[/yellow]")

                console.print(f"\n[bold magenta]{'='*60}[/bold magenta]")
                console.print(f"[bold magenta]PHASE: {phase_name.upper()} (timeout: {phase_timeout}s)[/bold magenta]")
                console.print(f"[bold magenta]{'='*60}[/bold magenta]")

                # Build prompt using agent's preferred style
                if phase_name == "build":
                    prompt = self.build_prompt(
                        task_readme,
                        phase="build",
                        prompt_style=agent_config.prompt_style,
                    )
                else:
                    prompt = self.build_prompt(
                        "",
                        phase=phase_name,
                        prompt_style=agent_config.prompt_style,
                    )

                # Temporarily override timeout for this phase
                original_timeout = agent_config.timeout_seconds
                agent_config.timeout_seconds = phase_timeout

                try:
                    # Run the agent for this phase
                    # Use --continue for subsequent phases to maintain session context
                    result = self.run_agent(
                        agent_config=agent_config,
                        prompt=prompt,
                        model=model,
                        on_output=on_output,
                        continue_session=(i > 0 or retry_count > 0),  # Continue from previous
                        completion_signal=completion_signal,
                    )
                finally:
                    agent_config.timeout_seconds = original_timeout

                all_stdout.extend(result.stdout.split('\n'))
                all_stderr.extend(result.stderr.split('\n'))
                total_duration += result.duration_seconds

                # Check if phase completed successfully
                if completion_signal.upper() in result.stdout.upper():
                    console.print(f"[green]✓ {phase_name.upper()} phase complete[/green]")
                    phase_success = True
                elif result.timed_out:
                    console.print(f"[red]✗ {phase_name.upper()} phase timed out[/red]")
                    retry_count += 1
                    if retry_count > retries_per_phase:
                        console.print(f"[red]Max retries exceeded for {phase_name.upper()}[/red]")
                        break
                else:
                    # Check if we can detect implicit success (e.g., deployment succeeded)
                    implicit_success = self._check_implicit_phase_success(phase_name, result.stdout)
                    if implicit_success:
                        console.print(f"[green]✓ {phase_name.upper()} phase implicitly complete[/green]")
                        phase_success = True
                    else:
                        console.print(f"[yellow]⚠ {phase_name.upper()} phase ended without completion signal[/yellow]")
                        # Continue anyway - the agent may have finished
                        phase_success = True  # Don't retry if process exited normally

            if not phase_success:
                console.print(f"[red]Phase {phase_name.upper()} failed after all retries[/red]")
                break

        # Get final list of modified files
        completed_at = datetime.now()
        files_modified = self._get_modified_files()

        return CLIRunResult(
            agent_id=agent_config.id,
            scratch_org=self.scratch_org,
            work_dir=self.work_dir,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=total_duration,
            exit_code=result.exit_code if result else 1,
            stdout='\n'.join(all_stdout),
            stderr='\n'.join(all_stderr),
            timed_out=result.timed_out if result else False,
            files_modified=files_modified,
        )

    def _check_implicit_phase_success(self, phase_name: str, stdout: str) -> bool:
        """Check for implicit success indicators when completion signal is missing."""
        stdout_lower = stdout.lower()

        if phase_name == "build":
            # Check if files were created
            return any(indicator in stdout_lower for indicator in [
                "created file",
                "wrote file",
                "writing file",
                ".flow-meta.xml",
                ".validationrule-meta.xml",
            ])
        elif phase_name == "deploy":
            # Check for deployment success indicators
            return any(indicator in stdout_lower for indicator in [
                "deploy succeeded",
                "successfully deployed",
                "deployment complete",
                "source push succeeded",
                "status: succeeded",
            ])
        elif phase_name == "test":
            # Check for test success indicators
            return any(indicator in stdout_lower for indicator in [
                "test run complete",
                "tests passed",
                "0 failures",
                "outcome: pass",
                "all tests passed",
            ])

        return False
    
    def run_agent(
        self,
        agent_config: CLIAgentConfig,
        prompt: str,
        model: str | None = None,
        on_output: Callable[[str], None] | None = None,
        continue_session: bool = False,
        completion_signal: str | None = None,
    ) -> CLIRunResult:
        """
        Run a CLI agent with the given prompt.

        Args:
            agent_config: Configuration for the CLI agent
            prompt: The task prompt to give the agent
            model: Model to use (overrides default)
            on_output: Callback for real-time output
            continue_session: If True, use --continue flag (Claude Code) to maintain session
            completion_signal: Signal to look for to determine completion (default: "TASK COMPLETE")

        Returns:
            CLIRunResult with execution details
        """
        if not self.work_dir or not self.scratch_org:
            raise RuntimeError("Call setup_environment first")

        started_at = datetime.now()

        # Build the command
        cmd = list(agent_config.command)

        # Add model flag if supported
        selected_model = model or agent_config.default_model
        if agent_config.model_flag and selected_model:
            cmd.extend([agent_config.model_flag, selected_model])

        # For Claude Code: use --continue to maintain session context between phases
        if continue_session and agent_config.id == "claude-code":
            cmd.append("--continue")

        # Add prompt flag if supported
        if agent_config.prompt_flag:
            cmd.extend([agent_config.prompt_flag, prompt])

        # Set up environment
        env = os.environ.copy()
        env.update(agent_config.env_vars)
        env["SF_TARGET_ORG"] = self.scratch_org

        # Use provided completion signal or default to "TASK COMPLETE"
        signal_to_check = completion_signal or "TASK COMPLETE"

        console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
        console.print(f"[bold]Running: {agent_config.name}[/bold]")
        if continue_session:
            console.print(f"[dim]Mode: Continuing previous session[/dim]")
        console.print(f"[dim]Command: {' '.join(cmd[:3])}...[/dim]")
        console.print(f"[dim]Working dir: {self.work_dir}[/dim]")
        console.print(f"[dim]Scratch org: {self.scratch_org}[/dim]")
        console.print(f"[dim]Completion signal: {signal_to_check}[/dim]")
        console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")

        stdout_lines = []
        stderr_lines = []
        timed_out = False

        try:
            # For interactive CLIs, we need to handle input/output differently
            if agent_config.prompt_flag is None:
                # Interactive mode - write prompt to stdin
                self._process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=self.work_dir,
                    env=env,
                    bufsize=1,
                )

                # Send prompt
                if self._process.stdin:
                    self._process.stdin.write(prompt + "\n")
                    self._process.stdin.flush()
            else:
                # Non-interactive mode
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=self.work_dir,
                    env=env,
                    bufsize=1,
                )

            # Stream output in real-time with progressive warnings
            start_time = time.time()
            timeout_seconds = agent_config.timeout_seconds
            last_warning_time = 0
            warning_intervals = [
                (0.5, "50% of timeout elapsed"),
                (0.75, "75% of timeout elapsed"),
                (0.9, "90% of timeout elapsed - wrapping up soon"),
            ]
            warnings_shown = set()

            while True:
                elapsed = time.time() - start_time
                elapsed_ratio = elapsed / timeout_seconds if timeout_seconds > 0 else 0

                # Show progressive timeout warnings
                for threshold, message in warning_intervals:
                    if elapsed_ratio >= threshold and threshold not in warnings_shown:
                        remaining = int(timeout_seconds - elapsed)
                        console.print(f"\n[yellow]⏱ {message} ({remaining}s remaining)[/yellow]")
                        warnings_shown.add(threshold)

                # Check timeout
                if elapsed > timeout_seconds:
                    console.print(f"\n[yellow]⏱ Timeout after {timeout_seconds}s[/yellow]")
                    self._process.terminate()
                    timed_out = True
                    break

                # Check if process ended
                if self._process.poll() is not None:
                    break

                # Read output
                if self._process.stdout:
                    line = self._process.stdout.readline()
                    if line:
                        stdout_lines.append(line)
                        if on_output:
                            on_output(line)
                        if self.verbose:
                            console.print(f"[dim]{line.rstrip()}[/dim]")

                        # Check for completion signal (phase-specific or default)
                        if signal_to_check.upper() in line.upper():
                            console.print(f"\n[green]✓ Agent signaled completion ({signal_to_check})[/green]")
                            self._process.terminate()
                            break

                        # Also check for error indicators that might mean we should retry
                        error_indicators = [
                            "deployment failed",
                            "error:",
                            "fatal:",
                            "cannot find",
                            "does not exist",
                        ]
                        line_lower = line.lower()
                        for indicator in error_indicators:
                            if indicator in line_lower:
                                console.print(f"[yellow]⚠ Detected potential error: {line.strip()[:100]}[/yellow]")
                                break

                time.sleep(0.1)

            # Get remaining output
            remaining_stdout, remaining_stderr = self._process.communicate(timeout=10)
            stdout_lines.append(remaining_stdout)
            stderr_lines.append(remaining_stderr)

        except subprocess.TimeoutExpired:
            self._process.kill()
            timed_out = True
        except Exception as e:
            console.print(f"[red]Error running agent: {e}[/red]")
            stderr_lines.append(str(e))

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        # Normalize metadata file extensions (fix common agent mistakes)
        if self.work_dir:
            fixes = self._normalize_metadata_files(self.work_dir)
            if fixes > 0:
                console.print(f"  [yellow]Fixed {fixes} metadata file extension(s)[/yellow]")

        # Get list of modified files
        files_modified = self._get_modified_files()

        return CLIRunResult(
            agent_id=agent_config.id,
            scratch_org=self.scratch_org,
            work_dir=self.work_dir,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            exit_code=self._process.returncode if self._process else -1,
            stdout="".join(stdout_lines),
            stderr="".join(stderr_lines),
            timed_out=timed_out,
            files_modified=files_modified,
        )
    
    def _get_modified_files(self) -> list[str]:
        """Get list of files modified by the agent."""
        if not self.work_dir:
            return []
        
        files = []
        force_app = self.work_dir / "force-app"
        
        if force_app.exists():
            for f in force_app.rglob("*"):
                if f.is_file() and f.suffix in (".cls", ".xml", ".trigger"):
                    files.append(str(f.relative_to(self.work_dir)))
        
        return files
    
    def cleanup(self, delete_org: bool = True, delete_files: bool = True):
        """Clean up scratch org and working directory."""
        if delete_org and self.scratch_org:
            console.print(f"[dim]Deleting scratch org: {self.scratch_org}[/dim]")
            subprocess.run(
                ["sf", "org", "delete", "scratch", "--target-org", self.scratch_org, "--no-prompt"],
                capture_output=True,
            )
        
        if delete_files and self.work_dir and self.work_dir.exists():
            console.print(f"[dim]Cleaning up: {self.work_dir}[/dim]")
            shutil.rmtree(self.work_dir, ignore_errors=True)
    
    def stop(self):
        """Stop the running agent process."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()


def get_available_cli_agents() -> dict[str, CLIAgentConfig]:
    """Get CLI agents that are available on this system."""
    available = {}
    
    for agent_id, config in CLI_AGENTS.items():
        cmd = config.command[0]
        # Check if command exists
        result = subprocess.run(
            ["which", cmd],
            capture_output=True,
        )
        if result.returncode == 0:
            available[agent_id] = config
    
    return available
