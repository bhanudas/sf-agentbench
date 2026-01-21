"""Base agent interface for SF-AgentBench."""

import os
import subprocess
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sf_agentbench.models import Task


@dataclass
class AgentResult:
    """Result from an agent's attempt to solve a task."""
    
    success: bool
    iterations: int
    total_tokens: int = 0
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    error: str | None = None
    agent_output: str = ""


# Tool definitions that agents can use
AGENT_TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file in the project directory",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file relative to the project root"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates parent directories if needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file relative to the project root"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_directory",
        "description": "List files and directories in a path",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to list, relative to project root. Use '.' for root."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "sf_deploy",
        "description": "Deploy Salesforce metadata to the scratch org using 'sf project deploy start'",
        "parameters": {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Path to deploy, usually 'force-app'"
                }
            },
            "required": ["source_path"]
        }
    },
    {
        "name": "sf_run_tests",
        "description": "Run Apex tests in the scratch org",
        "parameters": {
            "type": "object",
            "properties": {
                "test_class": {
                    "type": "string",
                    "description": "Name of the test class to run"
                }
            },
            "required": ["test_class"]
        }
    },
    {
        "name": "task_complete",
        "description": "Signal that you have completed the task. Call this when done.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Brief summary of what was implemented"
                }
            },
            "required": ["summary"]
        }
    }
]


class BaseAgent(ABC):
    """Base class for AI agents that solve Salesforce development tasks."""
    
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        api_key_env: str | None = None,
        max_iterations: int = 50,
        timeout_seconds: int = 1800,
        verbose: bool = False,
    ):
        self.model = model
        self.api_key = api_key or (os.getenv(api_key_env) if api_key_env else None)
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.verbose = verbose
        
        # Set during solve()
        self.work_dir: Path | None = None
        self.target_org: str | None = None
        self.task: Task | None = None
        
        # Track files touched
        self._files_created: list[str] = []
        self._files_modified: list[str] = []
    
    @abstractmethod
    def solve(
        self,
        task: Task,
        work_dir: Path,
        target_org: str,
    ) -> AgentResult:
        """
        Solve a benchmark task.
        
        Args:
            task: The benchmark task to solve
            work_dir: Working directory (the task's project folder)
            target_org: Username of the scratch org to deploy to
            
        Returns:
            AgentResult with success status and metadata
        """
        pass
    
    def _get_system_prompt(self, task: Task) -> str:
        """Generate the system prompt for the agent."""
        return f"""You are an expert Salesforce developer tasked with implementing a solution.

## Task: {task.name}

{task.description}

## Project Structure
You are working in a Salesforce DX project. The main source directory is `force-app/main/default/`.

## Key Directories
- `force-app/main/default/classes/` - Apex classes
- `force-app/main/default/flows/` - Flow definitions (XML)
- `force-app/main/default/objects/` - Custom objects and fields
- `force-app/main/default/triggers/` - Apex triggers

## Available Tools
You have tools to:
1. Read and write files
2. List directory contents
3. Deploy to Salesforce (`sf_deploy`)
4. Run Apex tests (`sf_run_tests`)
5. Signal completion (`task_complete`)

## Guidelines
1. First, explore the existing project structure to understand what's already there
2. Read the README.md for detailed requirements
3. Implement the solution by creating/modifying necessary files
4. Deploy your changes to verify they work
5. Run tests to validate your implementation
6. Call `task_complete` when done

## Important
- Create proper Salesforce metadata XML files
- Follow Salesforce best practices
- Ensure your code is bulkified
- All Apex classes need accompanying .cls-meta.xml files
- Flow files use .flow-meta.xml extension

Begin by exploring the project and reading the requirements."""

    def _execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool and return the result."""
        if self.work_dir is None:
            return "Error: work_dir not set"
        
        try:
            if tool_name == "read_file":
                return self._tool_read_file(arguments["path"])
            elif tool_name == "write_file":
                return self._tool_write_file(arguments["path"], arguments["content"])
            elif tool_name == "list_directory":
                return self._tool_list_directory(arguments["path"])
            elif tool_name == "sf_deploy":
                return self._tool_sf_deploy(arguments["source_path"])
            elif tool_name == "sf_run_tests":
                return self._tool_sf_run_tests(arguments["test_class"])
            elif tool_name == "task_complete":
                return self._tool_task_complete(arguments["summary"])
            else:
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"
    
    def _tool_read_file(self, path: str) -> str:
        """Read a file from the work directory."""
        file_path = self.work_dir / path
        if not file_path.exists():
            return f"File not found: {path}"
        if not file_path.is_file():
            return f"Not a file: {path}"
        try:
            return file_path.read_text()
        except Exception as e:
            return f"Error reading file: {e}"
    
    def _tool_write_file(self, path: str, content: str) -> str:
        """Write a file to the work directory."""
        file_path = self.work_dir / path
        
        # Track if creating or modifying
        is_new = not file_path.exists()
        
        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            file_path.write_text(content)
            if is_new:
                self._files_created.append(path)
            else:
                self._files_modified.append(path)
            return f"Successfully wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"Error writing file: {e}"
    
    def _tool_list_directory(self, path: str) -> str:
        """List directory contents."""
        dir_path = self.work_dir / path
        if not dir_path.exists():
            return f"Directory not found: {path}"
        if not dir_path.is_dir():
            return f"Not a directory: {path}"
        
        try:
            items = []
            for item in sorted(dir_path.iterdir()):
                prefix = "[DIR] " if item.is_dir() else "[FILE]"
                items.append(f"{prefix} {item.name}")
            return "\n".join(items) if items else "(empty directory)"
        except Exception as e:
            return f"Error listing directory: {e}"
    
    def _tool_sf_deploy(self, source_path: str) -> str:
        """Deploy to Salesforce scratch org."""
        if not self.target_org:
            return "Error: No target org set"
        
        try:
            result = subprocess.run(
                [
                    "sf", "project", "deploy", "start",
                    "--target-org", self.target_org,
                    "--source-dir", source_path,
                    "--wait", "10",
                    "--json"
                ],
                capture_output=True,
                text=True,
                cwd=self.work_dir,
                timeout=600,
            )
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    deployed = data.get("result", {}).get("deployedSource", [])
                    return f"Deployment successful! Deployed {len(deployed)} components."
                except:
                    return "Deployment successful!"
            else:
                try:
                    data = json.loads(result.stdout)
                    errors = data.get("result", {}).get("details", {}).get("componentFailures", [])
                    if errors:
                        error_msgs = [f"- {e.get('problemType', 'Error')}: {e.get('problem', 'Unknown')}" for e in errors[:5]]
                        return f"Deployment failed:\n" + "\n".join(error_msgs)
                except:
                    pass
                return f"Deployment failed: {result.stderr or result.stdout}"
        except subprocess.TimeoutExpired:
            return "Deployment timed out after 10 minutes"
        except Exception as e:
            return f"Deployment error: {e}"
    
    def _tool_sf_run_tests(self, test_class: str) -> str:
        """Run Apex tests."""
        if not self.target_org:
            return "Error: No target org set"
        
        try:
            result = subprocess.run(
                [
                    "sf", "apex", "run", "test",
                    "--target-org", self.target_org,
                    "--class-names", test_class,
                    "--result-format", "json",
                    "--wait", "10"
                ],
                capture_output=True,
                text=True,
                cwd=self.work_dir,
                timeout=600,
            )
            
            try:
                data = json.loads(result.stdout)
                summary = data.get("result", {}).get("summary", {})
                passing = summary.get("passing", 0)
                failing = summary.get("failing", 0)
                total = summary.get("testsRan", 0)
                
                if failing == 0:
                    return f"All tests passed! {passing}/{total} tests successful."
                else:
                    # Get failure details
                    tests = data.get("result", {}).get("tests", [])
                    failures = [t for t in tests if t.get("Outcome") == "Fail"]
                    failure_msgs = []
                    for f in failures[:3]:
                        failure_msgs.append(f"- {f.get('MethodName', 'Unknown')}: {f.get('Message', 'Failed')}")
                    return f"Tests: {passing}/{total} passed, {failing} failed:\n" + "\n".join(failure_msgs)
            except:
                if result.returncode == 0:
                    return "Tests completed (couldn't parse details)"
                return f"Test execution failed: {result.stderr or result.stdout}"
        except subprocess.TimeoutExpired:
            return "Test execution timed out"
        except Exception as e:
            return f"Test error: {e}"
    
    def _tool_task_complete(self, summary: str) -> str:
        """Mark the task as complete."""
        return f"TASK_COMPLETE: {summary}"
