"""Scratch Org management ACI tools."""

from datetime import datetime, timedelta
from typing import Any

from sf_agentbench.aci.base import ACITool, ACIToolResult


class SFOrgCreate(ACITool):
    """Create a new Scratch Org."""

    name = "sf_org_create"
    description = (
        "Creates a new Scratch Org from the project's scratch org definition file. "
        "Returns the org username and other connection details."
    )

    def execute(
        self,
        definition_file: str = "config/project-scratch-def.json",
        alias: str | None = None,
        duration_days: int = 1,
        set_default: bool = True,
        wait_minutes: int = 10,
        devhub_username: str | None = None,
        **kwargs: Any,
    ) -> ACIToolResult:
        """
        Create a Scratch Org.

        Args:
            definition_file: Path to scratch org definition file
            alias: Alias for the new org
            duration_days: Duration in days (1-30)
            set_default: Set as default org
            wait_minutes: Minutes to wait for creation
            devhub_username: DevHub username (uses default if not specified)

        Returns:
            ACIToolResult with org details
        """
        args = [
            "org",
            "create",
            "scratch",
            "--definition-file",
            definition_file,
            "--duration-days",
            str(duration_days),
            "--wait",
            str(wait_minutes),
        ]

        if alias:
            args.extend(["--alias", alias])

        if set_default:
            args.append("--set-default")

        if devhub_username:
            args.extend(["--target-dev-hub", devhub_username])

        # Don't pass target_org for org creation
        old_target = self.target_org
        self.target_org = None

        result = self._run_sf_command(args)

        self.target_org = old_target

        if result.success and result.data:
            # SF CLI returns nested structure with authFields
            auth_fields = result.data.get("authFields", {})
            
            result.data = {
                "org_id": result.data.get("orgId") or auth_fields.get("orgId"),
                "username": result.data.get("username") or auth_fields.get("username"),
                "instance_url": auth_fields.get("instanceUrl") or result.data.get("instanceUrl", ""),
                "login_url": auth_fields.get("loginUrl") or result.data.get("loginUrl", ""),
                "status": "active",
                "expires_at": (
                    datetime.utcnow() + timedelta(days=duration_days)
                ).isoformat(),
            }

        return result

    def _get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "definition_file": {
                    "type": "string",
                    "description": "Path to scratch org definition file",
                    "default": "config/project-scratch-def.json",
                },
                "alias": {
                    "type": "string",
                    "description": "Alias for the new org",
                },
                "duration_days": {
                    "type": "integer",
                    "description": "Duration in days (1-30)",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 30,
                },
                "set_default": {
                    "type": "boolean",
                    "description": "Set as default org",
                    "default": True,
                },
                "wait_minutes": {
                    "type": "integer",
                    "description": "Minutes to wait for creation",
                    "default": 10,
                },
                "devhub_username": {
                    "type": "string",
                    "description": "DevHub username",
                },
            },
        }


class SFOrgDelete(ACITool):
    """Delete a Scratch Org."""

    name = "sf_org_delete"
    description = "Deletes a Scratch Org. Used for cleanup after benchmark runs."

    def execute(
        self,
        target_org: str | None = None,
        no_prompt: bool = True,
        **kwargs: Any,
    ) -> ACIToolResult:
        """
        Delete a Scratch Org.

        Args:
            target_org: Username or alias of org to delete
            no_prompt: Skip confirmation prompt

        Returns:
            ACIToolResult with deletion status
        """
        args = ["org", "delete", "scratch"]

        if target_org:
            args.extend(["--target-org", target_org])
        elif self.target_org:
            args.extend(["--target-org", self.target_org])
        else:
            return ACIToolResult(
                success=False,
                errors=[{"message": "No target org specified for deletion"}],
            )

        if no_prompt:
            args.append("--no-prompt")

        # Don't use instance target_org for this command
        old_target = self.target_org
        self.target_org = None

        result = self._run_sf_command(args)

        self.target_org = old_target

        if result.success:
            result.data = {"status": "deleted", "org": target_org or old_target}

        return result

    def _get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target_org": {
                    "type": "string",
                    "description": "Username or alias of org to delete",
                },
                "no_prompt": {
                    "type": "boolean",
                    "description": "Skip confirmation prompt",
                    "default": True,
                },
            },
        }


class SFOrgOpen(ACITool):
    """Get login URL for a Scratch Org."""

    name = "sf_org_open"
    description = (
        "Returns the login URL for the Scratch Org. "
        "Useful for debugging or manual verification."
    )

    def execute(
        self,
        path: str | None = None,
        url_only: bool = True,
        **kwargs: Any,
    ) -> ACIToolResult:
        """
        Get org login URL.

        Args:
            path: Specific path to open (e.g., "/lightning/setup/")
            url_only: Return URL only without opening browser

        Returns:
            ACIToolResult with login URL
        """
        args = ["org", "open"]

        if path:
            args.extend(["--path", path])

        if url_only:
            args.append("--url-only")

        result = self._run_sf_command(args)

        if result.success and result.data:
            result.data = {
                "url": result.data.get("url"),
                "org_id": result.data.get("orgId"),
                "username": result.data.get("username"),
            }

        return result

    def _get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Specific path to open in the org",
                },
                "url_only": {
                    "type": "boolean",
                    "description": "Return URL only without opening browser",
                    "default": True,
                },
            },
        }


class SFOrgList(ACITool):
    """List all orgs."""

    name = "sf_org_list"
    description = "Lists all authenticated orgs including DevHub and Scratch Orgs."

    def execute(
        self,
        all_orgs: bool = False,
        skip_connection_status: bool = True,
        **kwargs: Any,
    ) -> ACIToolResult:
        """
        List orgs.

        Args:
            all_orgs: Include all orgs (not just scratch orgs)
            skip_connection_status: Skip checking connection status (faster)

        Returns:
            ACIToolResult with org list
        """
        args = ["org", "list"]

        if all_orgs:
            args.append("--all")

        if skip_connection_status:
            args.append("--skip-connection-status")

        # Don't use target org
        old_target = self.target_org
        self.target_org = None

        result = self._run_sf_command(args)

        self.target_org = old_target

        if result.success and result.data:
            scratch_orgs = result.data.get("scratchOrgs", [])
            other_orgs = result.data.get("nonScratchOrgs", [])

            result.data = {
                "scratch_orgs": [
                    {
                        "alias": o.get("alias"),
                        "username": o.get("username"),
                        "org_id": o.get("orgId"),
                        "instance_url": o.get("instanceUrl"),
                        "status": o.get("status"),
                        "dev_hub": o.get("devHubUsername"),
                        "expires": o.get("expirationDate"),
                    }
                    for o in scratch_orgs
                ],
                "other_orgs": [
                    {
                        "alias": o.get("alias"),
                        "username": o.get("username"),
                        "org_id": o.get("orgId"),
                        "instance_url": o.get("instanceUrl"),
                        "is_dev_hub": o.get("isDevHub", False),
                    }
                    for o in other_orgs
                ],
            }

        return result

    def _get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "all_orgs": {
                    "type": "boolean",
                    "description": "Include all org types",
                    "default": False,
                },
                "skip_connection_status": {
                    "type": "boolean",
                    "description": "Skip connection status check",
                    "default": True,
                },
            },
        }
