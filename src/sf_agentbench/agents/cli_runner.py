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
    ),
    "gemini-cli": CLIAgentConfig(
        id="gemini-cli", 
        name="Gemini CLI",
        command=["gemini", "-y"],  # -y for auto-accept actions
        prompt_flag="-p",
        model_flag="-m",
        default_model="gemini-2.5-pro",
        timeout_seconds=1800,
    ),
    "aider": CLIAgentConfig(
        id="aider",
        name="Aider",
        command=["aider", "--no-git", "--yes"],
        prompt_flag="--message",
        model_flag="--model",
        default_model=None,
        timeout_seconds=1800,
    ),
    "codex": CLIAgentConfig(
        id="codex",
        name="OpenAI Codex CLI",
        command=["codex"],
        prompt_flag=None,
        model_flag=None,
        timeout_seconds=1800,
    ),
    "cline": CLIAgentConfig(
        id="cline",
        name="Cline",
        command=["cline"],
        prompt_flag=None,
        model_flag=None,
        timeout_seconds=1800,
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
    
    def build_prompt(self, task_readme: str, phase: str = "full") -> str:
        """Build the prompt to give to the CLI agent.
        
        Args:
            task_readme: The task requirements from README.md
            phase: One of 'full', 'build', 'deploy', 'test'
        """
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

    def run_multi_phase(
        self,
        agent_config: CLIAgentConfig,
        task_readme: str,
        model: str | None = None,
        max_retries: int = 3,
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
            max_retries: Max retries per phase
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

        phases = [
            ("build", "BUILD COMPLETE"),
            ("deploy", "DEPLOY COMPLETE"),
            ("test", "TASK COMPLETE"),
        ]

        for i, (phase_name, completion_signal) in enumerate(phases):
            console.print(f"\n[bold magenta]{'='*60}[/bold magenta]")
            console.print(f"[bold magenta]PHASE: {phase_name.upper()}[/bold magenta]")
            console.print(f"[bold magenta]{'='*60}[/bold magenta]")

            if phase_name == "build":
                prompt = self.build_prompt(task_readme, phase="build")
            else:
                prompt = self.build_prompt("", phase=phase_name)

            # Run the agent for this phase
            # Use --continue for subsequent phases to maintain session context
            result = self.run_agent(
                agent_config=agent_config,
                prompt=prompt,
                model=model,
                on_output=on_output,
                continue_session=(i > 0),  # Continue from previous phase
                completion_signal=completion_signal,  # Phase-specific signal
            )

            all_stdout.extend(result.stdout.split('\n'))
            all_stderr.extend(result.stderr.split('\n'))
            total_duration += result.duration_seconds

            # Check if phase completed successfully
            if completion_signal.upper() in result.stdout.upper():
                console.print(f"[green]✓ {phase_name.upper()} phase complete[/green]")
            elif result.timed_out:
                console.print(f"[red]✗ {phase_name.upper()} phase timed out[/red]")
                break
            else:
                console.print(f"[yellow]⚠ {phase_name.upper()} phase ended without completion signal[/yellow]")
                # Continue anyway - the agent may have finished

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

            # Stream output in real-time
            start_time = time.time()

            while True:
                # Check timeout
                if time.time() - start_time > agent_config.timeout_seconds:
                    console.print(f"\n[yellow]⏱ Timeout after {agent_config.timeout_seconds}s[/yellow]")
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
