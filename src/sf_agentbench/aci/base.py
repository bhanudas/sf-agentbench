"""Base classes for ACI tools."""

import json
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


@dataclass
class ACIToolResult:
    """Result of an ACI tool execution."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    raw_output: str = ""
    exit_code: int = 0

    def to_json(self) -> str:
        """Convert result to JSON string."""
        return json.dumps(
            {
                "success": self.success,
                "data": self.data,
                "errors": self.errors,
            },
            indent=2,
        )


class ACITool(ABC):
    """Base class for all ACI tools."""

    name: str = "base_tool"
    description: str = "Base ACI tool"

    def __init__(
        self,
        sf_cli_path: str = "sf",
        target_org: str | None = None,
        project_dir: Path | None = None,
        verbose: bool = False,
    ):
        self.sf_cli_path = sf_cli_path
        self.target_org = target_org
        self.project_dir = project_dir or Path.cwd()
        self.verbose = verbose

    @abstractmethod
    def execute(self, **kwargs: Any) -> ACIToolResult:
        """Execute the tool with given parameters."""
        pass

    def _run_sf_command(
        self,
        args: list[str],
        json_output: bool = True,
        cwd: Path | None = None,
    ) -> ACIToolResult:
        """Run a Salesforce CLI command and return structured result."""
        cmd = [self.sf_cli_path] + args

        if json_output:
            cmd.append("--json")

        if self.target_org:
            cmd.extend(["--target-org", self.target_org])

        if self.verbose:
            console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd or self.project_dir,
                timeout=600,  # 10 minute timeout
            )

            raw_output = result.stdout + result.stderr

            if json_output and result.stdout.strip():
                try:
                    output_data = json.loads(result.stdout)
                    return self._parse_sf_json_output(output_data, result.returncode, raw_output)
                except json.JSONDecodeError:
                    return ACIToolResult(
                        success=False,
                        errors=[{"message": "Failed to parse JSON output", "raw": raw_output}],
                        raw_output=raw_output,
                        exit_code=result.returncode,
                    )
            else:
                return ACIToolResult(
                    success=result.returncode == 0,
                    data={"output": result.stdout},
                    raw_output=raw_output,
                    exit_code=result.returncode,
                )

        except subprocess.TimeoutExpired:
            return ACIToolResult(
                success=False,
                errors=[{"message": "Command timed out after 600 seconds"}],
                exit_code=-1,
            )
        except FileNotFoundError:
            return ACIToolResult(
                success=False,
                errors=[{"message": f"Salesforce CLI not found at: {self.sf_cli_path}"}],
                exit_code=-1,
            )
        except Exception as e:
            return ACIToolResult(
                success=False,
                errors=[{"message": f"Unexpected error: {str(e)}"}],
                exit_code=-1,
            )

    def _parse_sf_json_output(
        self, output: dict[str, Any], exit_code: int, raw_output: str
    ) -> ACIToolResult:
        """Parse standard Salesforce CLI JSON output format."""
        status = output.get("status", 1)
        result_data = output.get("result", {})
        warnings = output.get("warnings", [])

        if status == 0:
            return ACIToolResult(
                success=True,
                data=result_data,
                errors=[],
                raw_output=raw_output,
                exit_code=exit_code,
            )
        else:
            errors = []
            if "message" in output:
                errors.append({"message": output["message"]})
            if "name" in output:
                errors.append({"error_type": output["name"]})
            if warnings:
                for warning in warnings:
                    errors.append({"warning": warning})

            return ACIToolResult(
                success=False,
                data=result_data,
                errors=errors,
                raw_output=raw_output,
                exit_code=exit_code,
            )

    def get_tool_schema(self) -> dict[str, Any]:
        """Return the tool schema for agent consumption."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self._get_parameters_schema(),
        }

    @abstractmethod
    def _get_parameters_schema(self) -> dict[str, Any]:
        """Return the parameters schema for this tool."""
        pass
