"""Deployment-related ACI tools."""

from pathlib import Path
from typing import Any

from sf_agentbench.aci.base import ACITool, ACIToolResult


class SFDeploy(ACITool):
    """Deploy metadata from local project to Salesforce org."""

    name = "sf_deploy"
    description = (
        "Deploys metadata from the local SFDX project to the target Salesforce org. "
        "Returns deployment status with details of deployed components or errors."
    )

    def execute(
        self,
        source_path: str = "force-app",
        wait_minutes: int = 10,
        ignore_warnings: bool = False,
        run_tests: str | None = None,
        **kwargs: Any,
    ) -> ACIToolResult:
        """
        Deploy metadata to Salesforce.

        Args:
            source_path: Path to source directory (default: force-app)
            wait_minutes: Minutes to wait for deployment (default: 10)
            ignore_warnings: Whether to ignore warnings (default: False)
            run_tests: Test level - NoTestRun, RunSpecifiedTests, RunLocalTests, RunAllTestsInOrg

        Returns:
            ACIToolResult with deployment status and details
        """
        args = [
            "project",
            "deploy",
            "start",
            "--source-dir",
            source_path,
            "--wait",
            str(wait_minutes),
        ]

        if ignore_warnings:
            args.append("--ignore-warnings")

        if run_tests:
            args.extend(["--test-level", run_tests])

        result = self._run_sf_command(args)

        # Parse deployment-specific details
        if result.success and result.data:
            deployed = result.data.get("files", [])
            result.data = {
                "status": "success",
                "deployed_count": len(deployed),
                "components": [
                    {
                        "type": f.get("type", "Unknown"),
                        "name": f.get("fullName", f.get("filePath", "Unknown")),
                        "state": f.get("state", "Changed"),
                    }
                    for f in deployed
                ],
            }
        elif not result.success:
            # Extract deployment errors
            errors = []
            if "componentFailures" in result.data:
                for failure in result.data["componentFailures"]:
                    errors.append({
                        "component_type": failure.get("componentType", "Unknown"),
                        "component_name": failure.get("fullName", "Unknown"),
                        "line": failure.get("lineNumber"),
                        "column": failure.get("columnNumber"),
                        "message": failure.get("problem", "Unknown error"),
                        "error_code": failure.get("problemType"),
                    })
            result.errors = errors or result.errors

        return result

    def _get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Path to source directory to deploy",
                    "default": "force-app",
                },
                "wait_minutes": {
                    "type": "integer",
                    "description": "Minutes to wait for deployment",
                    "default": 10,
                },
                "ignore_warnings": {
                    "type": "boolean",
                    "description": "Whether to ignore warnings",
                    "default": False,
                },
                "run_tests": {
                    "type": "string",
                    "description": "Test level to run",
                    "enum": ["NoTestRun", "RunSpecifiedTests", "RunLocalTests", "RunAllTestsInOrg"],
                },
            },
        }


class SFRetrieve(ACITool):
    """Retrieve metadata from Salesforce org to local project."""

    name = "sf_retrieve"
    description = (
        "Retrieves metadata from the target Salesforce org to the local SFDX project. "
        "Useful for pulling configuration or comparing against expected state."
    )

    def execute(
        self,
        source_path: str = "force-app",
        metadata: list[str] | None = None,
        manifest: str | None = None,
        wait_minutes: int = 10,
        **kwargs: Any,
    ) -> ACIToolResult:
        """
        Retrieve metadata from Salesforce.

        Args:
            source_path: Path to output directory (default: force-app)
            metadata: List of metadata types to retrieve (e.g., ["ApexClass", "ApexTrigger"])
            manifest: Path to package.xml manifest file
            wait_minutes: Minutes to wait for retrieval

        Returns:
            ACIToolResult with retrieved components
        """
        args = [
            "project",
            "retrieve",
            "start",
            "--output-dir",
            source_path,
            "--wait",
            str(wait_minutes),
        ]

        if metadata:
            args.extend(["--metadata", ",".join(metadata)])
        elif manifest:
            args.extend(["--manifest", manifest])

        result = self._run_sf_command(args)

        if result.success and result.data:
            retrieved = result.data.get("files", [])
            result.data = {
                "status": "success",
                "retrieved_count": len(retrieved),
                "components": [
                    {
                        "type": f.get("type", "Unknown"),
                        "name": f.get("fullName", f.get("filePath", "Unknown")),
                    }
                    for f in retrieved
                ],
            }

        return result

    def _get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Output directory for retrieved metadata",
                    "default": "force-app",
                },
                "metadata": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of metadata types to retrieve",
                },
                "manifest": {
                    "type": "string",
                    "description": "Path to package.xml manifest",
                },
                "wait_minutes": {
                    "type": "integer",
                    "description": "Minutes to wait for retrieval",
                    "default": 10,
                },
            },
        }
