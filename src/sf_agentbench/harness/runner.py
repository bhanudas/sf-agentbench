"""Main benchmark harness for running tasks."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from sf_agentbench.config import BenchmarkConfig
from sf_agentbench.harness.org_manager import ScratchOrgManager
from sf_agentbench.harness.task_loader import TaskLoader
from sf_agentbench.models import (
    Task,
    TaskResult,
    EvaluationResult,
    ScratchOrgInfo,
)
from sf_agentbench.storage import ResultsStore
from sf_agentbench.logging import BenchmarkLogger, init_logger

console = Console()


# Type for agent callback function
AgentCallback = Callable[[Task, ScratchOrgInfo, Path], str]


class BenchmarkHarness:
    """Main orchestrator for running benchmark tasks."""

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.task_loader = TaskLoader(config.tasks_dir)
        self.org_manager = ScratchOrgManager(
            config=config.scratch_org,
            devhub_username=config.devhub_username,
            sf_cli_path=config.sf_cli_path,
            verbose=config.verbose,
        )
        self._results: list[TaskResult] = []
        self.results_store = ResultsStore(config.results_dir)
        
        # Initialize logger
        self.logger = init_logger(
            logs_dir=config.logs_dir,
            verbose=config.verbose,
        )

    def discover_tasks(self) -> list[Task]:
        """Discover all available benchmark tasks."""
        return self.task_loader.discover_tasks()

    def run_task(
        self,
        task: Task,
        agent_callback: AgentCallback,
        agent_id: str = "unknown",
    ) -> TaskResult:
        """
        Run a single benchmark task.

        Args:
            task: The task to run
            agent_callback: Function that takes (Task, ScratchOrgInfo, work_dir)
                           and returns the agent's output/logs
            agent_id: Identifier for the agent being evaluated

        Returns:
            TaskResult with evaluation scores
        """
        run_id = str(uuid.uuid4())[:8]
        started_at = datetime.utcnow()
        
        # Initialize run-specific logger
        self.logger = init_logger(
            logs_dir=self.config.logs_dir,
            run_id=run_id,
            verbose=self.config.verbose,
        )
        
        tier_str = task.tier.value if hasattr(task.tier, 'value') else str(task.tier)
        self.logger.task_start(task.id, task.name, tier_str)
        self.logger.info(f"Agent: {agent_id}")
        self.logger.info(f"Run ID: {run_id}")

        console.print(f"\n[bold blue]═══ Running Task: {task.name} ═══[/bold blue]")
        console.print(f"[dim]ID: {task.id} | Tier: {task.tier} | Agent: {agent_id}[/dim]")

        result = TaskResult(
            task_id=task.id,
            task_name=task.name,
            agent_id=agent_id,
            started_at=started_at,
        )

        try:
            # Create work directory for agent
            work_dir = self._create_work_directory(task, run_id)
            self.logger.info(f"Work directory: {work_dir}")

            # Create and set up Scratch Org
            self.logger.info("Creating scratch org...")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description="Creating Scratch Org...", total=None)
                org_info = self.org_manager.create_org_for_task(task, run_id)

            result.scratch_org = org_info
            self.logger.org_created(org_info.username, org_info.org_id)

            # Set up org with prerequisites
            self.org_manager.setup_org(task, org_info)

            # Run the agent
            console.print("\n[bold cyan]Running Agent...[/bold cyan]")
            agent_output = agent_callback(task, org_info, work_dir)
            result.agent_output = agent_output

            # Evaluate the agent's work
            console.print("\n[bold cyan]Evaluating Results...[/bold cyan]")
            self.logger.info("Starting evaluation pipeline...")
            from sf_agentbench.evaluators import EvaluationPipeline

            pipeline = EvaluationPipeline(
                config=self.config,
                target_org=org_info.username,
                project_dir=work_dir,
            )

            evaluation = pipeline.evaluate(task, work_dir)
            result.evaluation = evaluation

            # Calculate final score
            evaluation.calculate_final_score(
                deployment_weight=self.config.evaluation_weights.deployment,
                test_weight=self.config.evaluation_weights.functional_tests,
                static_weight=self.config.evaluation_weights.static_analysis,
                metadata_weight=self.config.evaluation_weights.metadata_diff,
                rubric_weight=self.config.evaluation_weights.rubric,
            )
            
            # Log evaluation results
            self.logger.evaluation_complete(
                scores={
                    "Deployment": evaluation.deployment_score,
                    "Tests": evaluation.test_score,
                    "Static Analysis": evaluation.static_analysis_score,
                    "Metadata": evaluation.metadata_score,
                    "Rubric": evaluation.rubric_score,
                },
                final_score=evaluation.final_score,
            )

        except Exception as e:
            console.print(f"[red]Error during task execution: {e}[/red]")
            self.logger.error(f"Task execution failed: {e}")
            result.error = str(e)

        finally:
            result.completed_at = datetime.utcnow()
            result.duration_seconds = (
                result.completed_at - result.started_at
            ).total_seconds()

            # Cleanup org if configured
            if self.config.cleanup_orgs and result.scratch_org:
                try:
                    self.logger.info("Cleaning up scratch org...")
                    self.org_manager.delete_org(result.scratch_org)
                    self.logger.org_deleted(result.scratch_org.username)
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to cleanup org: {e}[/yellow]")
                    self.logger.warning(f"Failed to cleanup org: {e}")
            
            # Log final results
            final_score = result.evaluation.final_score if result.evaluation else 0.0
            self.logger.task_end(task.id, final_score, result.duration_seconds)
            self.logger.info(f"Log file: {self.logger.get_log_path()}")

        # Store and display result
        self._results.append(result)
        self._display_result(result)

        return result

    def run_all_tasks(
        self,
        agent_callback: AgentCallback,
        agent_id: str = "unknown",
        tier_filter: str | None = None,
    ) -> list[TaskResult]:
        """
        Run all discovered tasks.

        Args:
            agent_callback: Function that runs the agent
            agent_id: Identifier for the agent
            tier_filter: Optional tier to filter tasks (e.g., "tier-1")

        Returns:
            List of TaskResults
        """
        tasks = self.discover_tasks()

        if tier_filter:
            from sf_agentbench.models import TaskTier
            tier = TaskTier(tier_filter)
            tasks = [t for t in tasks if t.tier == tier]

        console.print(f"\n[bold]Running {len(tasks)} benchmark tasks[/bold]")

        results = []
        for i, task in enumerate(tasks, 1):
            console.print(f"\n[dim]Task {i}/{len(tasks)}[/dim]")
            result = self.run_task(task, agent_callback, agent_id)
            results.append(result)

        self._display_summary(results)
        return results

    def _create_work_directory(self, task: Task, run_id: str) -> Path:
        """Create a working directory for the agent."""
        work_dir = self.config.results_dir / task.id / run_id
        work_dir.mkdir(parents=True, exist_ok=True)

        # Copy task files to work directory
        import shutil

        # Copy force-app if exists
        src_force_app = task.path / "force-app"
        if src_force_app.exists():
            shutil.copytree(src_force_app, work_dir / "force-app", dirs_exist_ok=True)

        # Copy sfdx-project.json if exists
        src_project = task.path / "sfdx-project.json"
        if src_project.exists():
            shutil.copy(src_project, work_dir / "sfdx-project.json")

        # Copy config directory
        src_config = task.path / "config"
        if src_config.exists():
            shutil.copytree(src_config, work_dir / "config", dirs_exist_ok=True)

        # Write README for agent
        readme = self.task_loader.get_task_readme(task)
        (work_dir / "README.md").write_text(readme)

        return work_dir

    def _display_result(self, result: TaskResult) -> None:
        """Display a task result."""
        console.print("\n[bold]Task Result:[/bold]")

        if result.error:
            console.print(f"  [red]✗ Error: {result.error}[/red]")
        else:
            eval_result = result.evaluation
            console.print(f"  Deployment Score:    {eval_result.deployment_score:.2f}")
            console.print(f"  Test Score:          {eval_result.test_score:.2f}")
            console.print(f"  Static Analysis:     {eval_result.static_analysis_score:.2f}")
            console.print(f"  Metadata Accuracy:   {eval_result.metadata_score:.2f}")
            console.print(f"  Rubric Score:        {eval_result.rubric_score:.2f}")
            console.print(f"  [bold]Final Score:       {eval_result.final_score:.2f}[/bold]")

        console.print(f"  Duration: {result.duration_seconds:.1f}s")

    def _display_summary(self, results: list[TaskResult]) -> None:
        """Display summary of all results."""
        console.print("\n[bold blue]═══ Benchmark Summary ═══[/bold blue]")

        completed = [r for r in results if r.is_complete]
        failed = [r for r in results if r.error]

        console.print(f"  Total Tasks:    {len(results)}")
        console.print(f"  Completed:      {len(completed)}")
        console.print(f"  Failed:         {len(failed)}")

        if completed:
            avg_score = sum(r.evaluation.final_score for r in completed) / len(completed)
            console.print(f"  Average Score:  {avg_score:.2f}")

        # Save results
        self._save_results(results)

    def _save_results(self, results: list[TaskResult]) -> None:
        """Save results to the persistent store."""
        saved_ids = []
        for result in results:
            run_id = self.results_store.save_run(result)
            saved_ids.append(run_id)
        
        console.print(f"\n[dim]Saved {len(saved_ids)} run(s) to database[/dim]")
        
        # Also export summary JSON for backwards compatibility
        summary_file = self.config.results_dir / "benchmark_results.json"
        self.results_store.export_to_json(summary_file)
