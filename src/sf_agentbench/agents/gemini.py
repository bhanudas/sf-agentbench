"""Gemini agent implementation using the new Google GenAI SDK."""

import json
from pathlib import Path

from rich.console import Console

from sf_agentbench.agents.base import BaseAgent, AgentResult, AGENT_TOOLS
from sf_agentbench.agents.auth import get_google_credentials
from sf_agentbench.models import Task

console = Console()


class GeminiAgent(BaseAgent):
    """Agent powered by Google's Gemini models using the new google-genai SDK."""
    
    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        api_key: str | None = None,
        api_key_env: str = "GOOGLE_API_KEY",
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
        
        # Try to get credentials from auth module
        if not self.api_key:
            creds = get_google_credentials()
            if creds and creds.get("type") == "api_key":
                self.api_key = creds["api_key"]
    
    def _get_client(self):
        """Lazy-load the Google GenAI client."""
        if self._client is None:
            try:
                from google import genai
                
                if self.api_key:
                    self._client = genai.Client(api_key=self.api_key)
                else:
                    raise ValueError(
                        "No Google API key found. Run: sf-agentbench auth setup google"
                    )
            except ImportError:
                raise ImportError("Please install google-genai: pip install google-genai")
        return self._client
    
    def _convert_tools_to_genai_format(self):
        """Convert our tools to the new google-genai format."""
        from google.genai import types
        
        tools = []
        for tool in AGENT_TOOLS:
            # Build function declaration
            func_decl = types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"],
            )
            tools.append(func_decl)
        
        return types.Tool(function_declarations=tools)
    
    def solve(
        self,
        task: Task,
        work_dir: Path,
        target_org: str,
    ) -> AgentResult:
        """Solve a benchmark task using Gemini."""
        self.work_dir = work_dir
        self.target_org = target_org
        self.task = task
        self._files_created = []
        self._files_modified = []
        
        if not self.api_key:
            return AgentResult(
                success=False,
                iterations=0,
                error="No Google API key found. Run: sf-agentbench auth setup google",
            )
        
        try:
            from google.genai import types
        except ImportError:
            return AgentResult(
                success=False,
                iterations=0,
                error="Please install google-genai: pip install google-genai",
            )
        
        client = self._get_client()
        tools = self._convert_tools_to_genai_format()
        system_prompt = self._get_system_prompt(task)
        
        total_tokens = 0
        task_complete = False
        agent_output = ""
        
        console.print(f"    [dim]Agent starting with {self.max_iterations} max iterations...[/dim]")
        import sys
        sys.stdout.flush()
        
        # Build conversation history
        contents = [
            types.Content(
                role="user",
                parts=[types.Part(text="Please solve this Salesforce development task. Start by exploring the project structure and reading the requirements.")]
            )
        ]
        
        for iteration in range(self.max_iterations):
            console.print(f"    [dim]Iteration {iteration + 1}/{self.max_iterations}...[/dim]")
            sys.stdout.flush()
            
            try:
                # Generate response
                response = client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        tools=[tools],
                        temperature=0.2,
                    ),
                )
                
                # Track tokens
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    total_tokens += getattr(response.usage_metadata, 'total_token_count', 0)
                
                # Process the response
                tool_calls_made = False
                tool_results = []
                assistant_parts = []
                
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        # Text content
                        if part.text:
                            agent_output += part.text + "\n"
                            assistant_parts.append(types.Part(text=part.text))
                            if self.verbose:
                                text = part.text
                                display = f"{text[:200]}..." if len(text) > 200 else text
                                console.print(f"      [blue]{display}[/blue]")
                        
                        # Function call
                        if part.function_call:
                            tool_calls_made = True
                            fc = part.function_call
                            tool_name = fc.name
                            tool_input = dict(fc.args) if fc.args else {}
                            
                            assistant_parts.append(types.Part(
                                function_call=types.FunctionCall(
                                    name=tool_name,
                                    args=tool_input
                                )
                            ))
                            
                            if self.verbose:
                                console.print(f"      [yellow]→ {tool_name}({json.dumps(tool_input)[:100]})[/yellow]")
                            
                            result = self._execute_tool(tool_name, tool_input)
                            
                            if self.verbose:
                                display = f"{result[:100]}..." if len(result) > 100 else result
                                console.print(f"      [green]← {display}[/green]")
                            
                            tool_results.append({
                                "name": tool_name,
                                "result": result
                            })
                            
                            # Check if task is complete
                            if tool_name == "task_complete":
                                task_complete = True
                
                # Add assistant response to history
                if assistant_parts:
                    contents.append(types.Content(
                        role="model",
                        parts=assistant_parts
                    ))
                
                # Check stop conditions
                if task_complete:
                    console.print(f"    [green]✓ Agent completed in {iteration + 1} iterations[/green]")
                    break
                
                if not tool_calls_made:
                    console.print(f"    [yellow]⚠ Agent stopped without completing[/yellow]")
                    break
                
                # Send tool results back
                if tool_results:
                    function_response_parts = []
                    for tr in tool_results:
                        function_response_parts.append(
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=tr["name"],
                                    response={"result": tr["result"]}
                                )
                            )
                        )
                    
                    contents.append(types.Content(
                        role="user",
                        parts=function_response_parts
                    ))
                    
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
