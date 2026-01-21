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
        
        console.print(f"    [dim]Agent starting with {self.max_iterations} max iterations...[/dim]")
        
        for iteration in range(self.max_iterations):
            if self.verbose:
                console.print(f"    [dim]Iteration {iteration + 1}[/dim]")
            
            try:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=8192,
                    system=system_prompt,
                    tools=tools,
                    messages=messages,
                )
                
                # Track tokens
                total_tokens += response.usage.input_tokens + response.usage.output_tokens
                
                # Process the response
                assistant_content = []
                tool_results = []
                
                for block in response.content:
                    if block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                        agent_output += block.text + "\n"
                        if self.verbose:
                            console.print(f"      [blue]{block.text[:200]}...[/blue]" if len(block.text) > 200 else f"      [blue]{block.text}[/blue]")
                    
                    elif block.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                        
                        # Execute the tool
                        tool_name = block.name
                        tool_input = block.input
                        
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
                
                if response.stop_reason == "end_turn" and not tool_results:
                    # Agent stopped without calling task_complete
                    console.print(f"    [yellow]⚠ Agent stopped without completing[/yellow]")
                    break
                    
            except Exception as e:
                console.print(f"    [red]✗ Agent error: {e}[/red]")
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
