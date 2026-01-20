"""Scratch Org lifecycle management."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from sf_agentbench.aci import SFOrgCreate, SFOrgDelete, SFOrgList, SFImportData
from sf_agentbench.aci.deploy import SFDeploy
from sf_agentbench.config import ScratchOrgConfig
from sf_agentbench.models import ScratchOrgInfo, Task

console = Console()


class ScratchOrgManager:
    """Manages Scratch Org lifecycle for benchmark runs."""

    def __init__(
        self,
        config: ScratchOrgConfig,
        devhub_username: str | None = None,
        sf_cli_path: str = "sf",
        verbose: bool = False,
    ):
        self.config = config
        self.devhub_username = devhub_username
        self.sf_cli_path = sf_cli_path
        self.verbose = verbose
        self._active_orgs: dict[str, ScratchOrgInfo] = {}

    def create_org_for_task(
        self,
        task: Task,
        run_id: str | None = None,
    ) -> ScratchOrgInfo:
        """Create a Scratch Org for a benchmark task."""
        run_id = run_id or str(uuid.uuid4())[:8]
        alias = f"sf-agentbench-{task.id}-{run_id}"

        # Determine scratch def path
        scratch_def = task.scratch_def_path
        if not scratch_def or not scratch_def.exists():
            scratch_def = task.path / "config" / "project-scratch-def.json"

        if not scratch_def.exists():
            raise FileNotFoundError(
                f"Scratch org definition not found for task {task.id}. "
                f"Expected at: {scratch_def}"
            )

        console.print(f"[blue]Creating Scratch Org for task:[/blue] {task.id}")

        creator = SFOrgCreate(
            sf_cli_path=self.sf_cli_path,
            project_dir=task.path,
            verbose=self.verbose,
        )

        result = creator.execute(
            definition_file=str(scratch_def.relative_to(task.path)),
            alias=alias,
            duration_days=self.config.default_duration_days,
            set_default=True,
            wait_minutes=self.config.wait_minutes,
            devhub_username=self.devhub_username,
        )

        if not result.success:
            error_msg = "; ".join(e.get("message", str(e)) for e in result.errors)
            raise RuntimeError(f"Failed to create Scratch Org: {error_msg}")

        org_info = ScratchOrgInfo(
            org_id=result.data.get("org_id", ""),
            username=result.data.get("username", ""),
            instance_url=result.data.get("instance_url", ""),
            login_url=result.data.get("login_url"),
            created_at=datetime.utcnow(),
            status="active",
        )

        self._active_orgs[alias] = org_info
        console.print(f"[green]✓ Scratch Org created:[/green] {org_info.username}")

        return org_info

    def setup_org(
        self,
        task: Task,
        org_info: ScratchOrgInfo,
    ) -> bool:
        """Set up a Scratch Org with task prerequisites (data, base metadata)."""
        console.print("[blue]Setting up org prerequisites...[/blue]")

        # Deploy any starter/base metadata
        base_metadata = task.path / "force-app"
        if base_metadata.exists():
            console.print("  Deploying base metadata...")
            deployer = SFDeploy(
                sf_cli_path=self.sf_cli_path,
                target_org=org_info.username,
                project_dir=task.path,
                verbose=self.verbose,
            )
            result = deployer.execute(source_path="force-app")
            if not result.success:
                console.print(f"[yellow]Warning: Base metadata deployment had issues[/yellow]")
                if self.verbose:
                    for error in result.errors:
                        console.print(f"  [dim]{error}[/dim]")

        # Import prerequisite data
        if task.requires_data and task.data_plan_path:
            console.print("  Importing prerequisite data...")
            importer = SFImportData(
                sf_cli_path=self.sf_cli_path,
                target_org=org_info.username,
                project_dir=task.path,
                verbose=self.verbose,
            )
            result = importer.execute(plan=str(task.data_plan_path.relative_to(task.path)))
            if not result.success:
                console.print(f"[yellow]Warning: Data import had issues[/yellow]")
                if self.verbose:
                    for error in result.errors:
                        console.print(f"  [dim]{error}[/dim]")

        console.print("[green]✓ Org setup complete[/green]")
        return True

    def delete_org(self, org_info: ScratchOrgInfo) -> bool:
        """Delete a Scratch Org."""
        console.print(f"[blue]Deleting Scratch Org:[/blue] {org_info.username}")

        deleter = SFOrgDelete(
            sf_cli_path=self.sf_cli_path,
            verbose=self.verbose,
        )

        result = deleter.execute(target_org=org_info.username, no_prompt=True)

        if result.success:
            console.print(f"[green]✓ Org deleted[/green]")
            # Remove from active orgs
            self._active_orgs = {
                k: v for k, v in self._active_orgs.items()
                if v.username != org_info.username
            }
            return True
        else:
            console.print(f"[yellow]Warning: Failed to delete org[/yellow]")
            return False

    def cleanup_all(self) -> None:
        """Delete all active orgs managed by this instance."""
        console.print(f"[blue]Cleaning up {len(self._active_orgs)} scratch org(s)...[/blue]")

        for alias, org_info in list(self._active_orgs.items()):
            try:
                self.delete_org(org_info)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to delete {alias}: {e}[/yellow]")

    def list_active_orgs(self) -> list[ScratchOrgInfo]:
        """List all active orgs managed by this instance."""
        return list(self._active_orgs.values())

    def get_all_scratch_orgs(self) -> list[dict[str, Any]]:
        """Get all Scratch Orgs from the DevHub."""
        lister = SFOrgList(
            sf_cli_path=self.sf_cli_path,
            verbose=self.verbose,
        )

        result = lister.execute(skip_connection_status=True)

        if result.success:
            return result.data.get("scratch_orgs", [])
        return []
