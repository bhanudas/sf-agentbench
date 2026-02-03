"""Claude agent implementation using Anthropic API."""

import json
from pathlib import Path

from rich.console import Console

from sf_agentbench.agents.base import BaseAgent, AgentResult, AGENT_TOOLS
from sf_agentbench.agents.auth import get_anthropic_credentials
from sf_agentbench.models import Task

console = Console()


class ClaudeAgent(BaseAgent):
    """Agent powered by Anthropic's Claude models."""
    
    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        api_key_env: str = "ANTHROPIC_API_KEY",
        max_iterations: int = 50,
        timeout_seconds: int = 1800,
        verbose: bool = False,
    ):
        super().__init__(
            model=model,
            api_key=api_key,
            api_key_env=api_key_env,
            max_iterations=max_iterations,
            timeout_seconds=timeout_seconds,
            verbose=verbose,
        )
        self._client = None
        
        # Try to get credentials from auth module if not provided
        if not self.api_key:
            self.api_key = get_anthropic_credentials()
    
    def _get_client(self):
        """Lazy-load the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("Please install anthropic: pip install anthropic")
        return self._client
    
    def _convert_tools_to_anthropic_format(self) -> list[dict]:
        """Convert our tools to Anthropic's tool format."""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"]
            }
            for tool in AGENT_TOOLS
        ]
    
    def solve(
        self,
        task: Task,
        work_dir: Path,
        target_org: str,
    ) -> AgentResult:
        """Solve a benchmark task using Claude."""
        self.work_dir = work_dir
        self.target_org = target_org
        self.task = task
        self._files_created = []
        self._files_modified = []
        
        if not self.api_key:
            return AgentResult(
                success=False,
                iterations=0,
                error="No API key provided. Set ANTHROPIC_API_KEY environment variable.",
            )
        
        client = self._get_client()
        tools = self._convert_tools_to_anthropic_format()
        system_prompt = self._get_system_prompt(task)
        
        messages = [
            {"role": "user", "content": "Please solve this Salesforce development task. Start by exploring the project structure and reading the requirements."}
        ]
        
        total_tokens = 0
        task_complete = False
        agent_output = ""
        
        # Failsafe tracking
        consecutive_errors = 0
        consecutive_no_progress = 0
        last_action = None
        repeated_action_count = 0
        
        MAX_CONSECUTIVE_ERRORS = 3
        MAX_NO_PROGRESS = 5
        MAX_REPEATED_ACTIONS = 5
        
        console.print(f"    [dim]Agent starting with {self.max_iterations} max iterations...[/dim]")
        console.print(f"    [dim]Failsafes: {MAX_CONSECUTIVE_ERRORS} errors, {MAX_NO_PROGRESS} no-progress, {MAX_REPEATED_ACTIONS} repeated actions[/dim]")
        
        for iteration in range(self.max_iterations):
            console.print(f"    [dim]Iteration {iteration + 1}/{self.max_iterations}...[/dim]")
            
            try:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=8192,
                    system=system_prompt,
                    tools=tools,
                    messages=messages,
                )
                
                # Reset error counter on successful API call
                consecutive_errors = 0
                
                # Track tokens
                total_tokens += response.usage.input_tokens + response.usage.output_tokens
                
                # Process the response
                assistant_content = []
                tool_results = []
                tool_calls_made = False
                current_action = None
                
                for block in response.content:
                    if block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                        agent_output += block.text + "\n"
                        if self.verbose:
                            console.print(f"      [blue]{block.text[:200]}...[/blue]" if len(block.text) > 200 else f"      [blue]{block.text}[/blue]")
                    
                    elif block.type == "tool_use":
                        tool_calls_made = True
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                        
                        # Execute the tool
                        tool_name = block.name
                        tool_input = block.input
                        
                        # Track current action for repeated action detection
                        current_action = f"{tool_name}:{json.dumps(tool_input, sort_keys=True)}"
                        
                        if self.verbose:
                            console.print(f"      [yellow]→ {tool_name}({json.dumps(tool_input)[:100]})[/yellow]")
                        
                        result = self._execute_tool(tool_name, tool_input)
                        
                        if self.verbose:
                            console.print(f"      [green]← {result[:100]}...[/green]" if len(result) > 100 else f"      [green]← {result}[/green]")
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                        
                        # Check for errors in tool result
                        if "error" in result.lower() or "failed" in result.lower():
                            consecutive_errors += 1
                            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                                console.print(f"    [red]✗ FAILSAFE: {MAX_CONSECUTIVE_ERRORS} consecutive errors, stopping early[/red]")
                                return AgentResult(
                                    success=False,
                                    iterations=iteration + 1,
                                    total_tokens=total_tokens,
                                    files_created=self._files_created,
                                    files_modified=self._files_modified,
                                    error=f"Stopped after {consecutive_errors} consecutive errors",
                                    agent_output=agent_output,
                                )
                        
                        # Check if task is complete
                        if tool_name == "task_complete":
                            task_complete = True
                
                # Add assistant message
                messages.append({"role": "assistant", "content": assistant_content})
                
                # Add tool results if any
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
                
                # Check stop conditions
                if task_complete:
                    console.print(f"    [green]✓ Agent completed in {iteration + 1} iterations[/green]")
                    break
                
                if not tool_calls_made:
                    consecutive_no_progress += 1
                    if consecutive_no_progress >= MAX_NO_PROGRESS:
                        console.print(f"    [red]✗ FAILSAFE: {MAX_NO_PROGRESS} iterations with no tool calls, stopping early[/red]")
                        return AgentResult(
                            success=False,
                            iterations=iteration + 1,
                            total_tokens=total_tokens,
                            files_created=self._files_created,
                            files_modified=self._files_modified,
                            error=f"Stopped after {consecutive_no_progress} iterations with no progress",
                            agent_output=agent_output,
                        )
                    console.print(f"    [yellow]⚠ No tool calls this iteration ({consecutive_no_progress}/{MAX_NO_PROGRESS})[/yellow]")
                else:
                    consecutive_no_progress = 0  # Reset on progress
                
                # Check for repeated actions
                if current_action == last_action:
                    repeated_action_count += 1
                    if repeated_action_count >= MAX_REPEATED_ACTIONS:
                        console.print(f"    [red]✗ FAILSAFE: Same action repeated {MAX_REPEATED_ACTIONS} times, stopping early[/red]")
                        return AgentResult(
                            success=False,
                            iterations=iteration + 1,
                            total_tokens=total_tokens,
                            files_created=self._files_created,
                            files_modified=self._files_modified,
                            error=f"Stopped after repeating same action {repeated_action_count} times",
                            agent_output=agent_output,
                        )
                else:
                    repeated_action_count = 0
                last_action = current_action
                
                if response.stop_reason == "end_turn" and not tool_results:
                    # Agent stopped without calling task_complete
                    console.print(f"    [yellow]⚠ Agent stopped without completing[/yellow]")
                    break
                    
            except Exception as e:
                consecutive_errors += 1
                console.print(f"    [red]✗ Agent error ({consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}): {e}[/red]")
                
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    console.print(f"    [red]✗ FAILSAFE: Too many errors, stopping early[/red]")
                    return AgentResult(
                        success=False,
                        iterations=iteration + 1,
                        total_tokens=total_tokens,
                        files_created=self._files_created,
                        files_modified=self._files_modified,
                        error=str(e),
                        agent_output=agent_output,
                    )
        
        return AgentResult(
            success=task_complete,
            iterations=iteration + 1,
            total_tokens=total_tokens,
            files_created=self._files_created,
            files_modified=self._files_modified,
            agent_output=agent_output,
        )
