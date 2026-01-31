"""Kimi K2 agent implementation using Moonshot AI's Kimi models.

Kimi K2 is OpenAI-compatible, so we use the OpenAI SDK with a custom base URL.
"""

import json
from pathlib import Path

from rich.console import Console

from sf_agentbench.agents.base import BaseAgent, AgentResult, AGENT_TOOLS
from sf_agentbench.agents.auth import get_kimi_credentials
from sf_agentbench.models import Task

console = Console()

# Kimi K2 API base URL (OpenAI-compatible)
# Primary endpoint - can be overridden via KIMI_API_BASE_URL environment variable
KIMI_API_BASE_URL = "https://kimi-k2.ai/api/v1"


class KimiAgent(BaseAgent):
    """Agent powered by Moonshot AI's Kimi K2 models.
    
    Kimi K2 is OpenAI-compatible, allowing us to use the OpenAI SDK
    with a custom base URL for API calls.
    """
    
    def __init__(
        self,
        model: str = "kimi-k2",
        api_key: str | None = None,
        api_key_env: str = "KIMI_API_KEY",
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
            self.api_key = get_kimi_credentials()
    
    def _get_client(self):
        """Lazy-load the OpenAI client configured for Kimi K2 API."""
        if self._client is None:
            try:
                import os
                import openai
                # Allow base URL override via environment variable
                base_url = os.getenv("KIMI_API_BASE_URL", KIMI_API_BASE_URL)
                self._client = openai.OpenAI(
                    api_key=self.api_key,
                    base_url=base_url,
                )
            except ImportError:
                raise ImportError("Please install openai: pip install openai")
        return self._client
    
    def _convert_tools_to_openai_format(self) -> list[dict]:
        """Convert our tools to OpenAI's function calling format.
        
        Kimi K2 is OpenAI-compatible, so we use the same tool format.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            }
            for tool in AGENT_TOOLS
        ]
    
    def solve(
        self,
        task: Task,
        work_dir: Path,
        target_org: str,
    ) -> AgentResult:
        """Solve a benchmark task using Kimi K2."""
        self.work_dir = work_dir
        self.target_org = target_org
        self.task = task
        self._files_created = []
        self._files_modified = []
        
        if not self.api_key:
            return AgentResult(
                success=False,
                iterations=0,
                error="No API key provided. Set KIMI_API_KEY environment variable or store in ~/.sf-agentbench/credentials/kimi.json",
            )
        
        client = self._get_client()
        tools = self._convert_tools_to_openai_format()
        system_prompt = self._get_system_prompt(task)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Please solve this Salesforce development task. Start by exploring the project structure and reading the requirements."}
        ]
        
        total_tokens = 0
        task_complete = False
        agent_output = ""
        
        console.print(f"    [dim]Kimi K2 Agent starting with {self.max_iterations} max iterations...[/dim]")
        
        for iteration in range(self.max_iterations):
            if self.verbose:
                console.print(f"    [dim]Iteration {iteration + 1}[/dim]")
            
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    max_tokens=8192,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                )
                
                # Track tokens
                if response.usage:
                    total_tokens += response.usage.total_tokens
                
                message = response.choices[0].message
                
                # Add assistant message to history
                messages.append(message)
                
                # Process content
                if message.content:
                    agent_output += message.content + "\n"
                    if self.verbose:
                        text = message.content
                        console.print(f"      [blue]{text[:200]}...[/blue]" if len(text) > 200 else f"      [blue]{text}[/blue]")
                
                # Process tool calls
                if message.tool_calls:
                    tool_results = []
                    
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        try:
                            tool_input = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            tool_input = {}
                        
                        if self.verbose:
                            console.print(f"      [yellow]→ {tool_name}({json.dumps(tool_input)[:100]})[/yellow]")
                        
                        result = self._execute_tool(tool_name, tool_input)
                        
                        if self.verbose:
                            console.print(f"      [green]← {result[:100]}...[/green]" if len(result) > 100 else f"      [green]← {result}[/green]")
                        
                        tool_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result,
                        })
                        
                        # Check if task is complete
                        if tool_name == "task_complete":
                            task_complete = True
                    
                    # Add tool results to messages
                    messages.extend(tool_results)
                
                # Check stop conditions
                if task_complete:
                    console.print(f"    [green]✓ Kimi K2 Agent completed in {iteration + 1} iterations[/green]")
                    break
                
                if response.choices[0].finish_reason == "stop" and not message.tool_calls:
                    console.print(f"    [yellow]⚠ Kimi K2 Agent stopped without completing[/yellow]")
                    break
                    
            except Exception as e:
                console.print(f"    [red]✗ Kimi K2 Agent error: {e}[/red]")
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
