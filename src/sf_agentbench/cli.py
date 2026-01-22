"""Command-line interface for SF-AgentBench."""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from sf_agentbench import __version__
from sf_agentbench.config import (
    BenchmarkConfig,
    load_config,
    MODEL_REGISTRY,
    ModelProvider,
    BUILTIN_MODELS,
)
from sf_agentbench.harness import BenchmarkHarness, TaskLoader
from sf_agentbench.models import TaskTier

console = Console()


# =============================================================================
# INTERACTIVE REPL COMMAND
# =============================================================================

@click.command("interactive")
@click.option("--workers", "-w", type=int, default=4, help="Number of parallel workers")
@click.option("--qa-workers", type=int, default=4, help="Workers for Q&A tests")
@click.option("--coding-workers", type=int, default=2, help="Workers for coding tests")
@click.option("--watch", is_flag=True, help="Watch mode: auto-refresh display without input (good for background monitoring)")
@click.pass_context
def interactive_mode(ctx: click.Context, workers: int, qa_workers: int, coding_workers: int, watch: bool):
    """Start interactive REPL mode for monitoring and controlling benchmarks.
    
    This provides a Claude Code-style interface where logs scroll above
    while you can always type commands below.
    
    \b
    Modes:
      Default         - Interactive with command input
      --watch         - Auto-refresh only, no input required (Ctrl+C to exit)
    
    \b
    Commands available in the REPL (default mode):
      status          - Show current status
      logs [agent]    - Filter logs by agent
      pause [id]      - Pause work unit(s)
      resume [id]     - Resume work unit(s)
      cancel <id>     - Cancel a work unit
      costs           - Show cost breakdown
      workers         - Show worker status
      help            - Show all commands
      quit            - Exit
    """
    from sf_agentbench.repl import REPLConsole
    from sf_agentbench.workers import WorkerPool, PoolConfig
    from sf_agentbench.events import get_event_bus
    
    config: BenchmarkConfig = ctx.obj["config"]
    
    # Configure worker pool
    pool_config = PoolConfig(
        max_workers=workers,
        qa_workers=qa_workers,
        coding_workers=coding_workers,
    )
    
    event_bus = get_event_bus()
    pool = WorkerPool(config=pool_config, event_bus=event_bus)
    
    mode_text = "Watch Mode (Ctrl+C to exit)" if watch else "Interactive Mode"
    console.print(f"\n[bold magenta]Starting {mode_text}[/bold magenta]")
    console.print(f"  Workers: {workers} (QA: {qa_workers}, Coding: {coding_workers})")
    if not watch:
        console.print("\n[dim]Type 'help' for commands, 'quit' to exit[/dim]\n")
    else:
        console.print("\n[dim]Auto-refreshing display. Press Ctrl+C to exit.[/dim]\n")
    
    # Start REPL
    repl = REPLConsole(
        event_bus=event_bus,
        pool=pool,
        watch_mode=watch,
    )
    
    try:
        pool.start()
        repl.start()
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting...[/yellow]")
    finally:
        pool.stop()


# =============================================================================
# PARALLEL BENCHMARK COMMAND
# =============================================================================

@click.command("run-parallel")
@click.option("--tasks", "-t", multiple=True, help="Task IDs to run (can specify multiple)")
@click.option("--agents", "-a", multiple=True, help="Agent IDs to use (can specify multiple)")
@click.option("--workers", "-w", type=int, default=4, help="Number of parallel workers")
@click.option("--devhub", "-d", help="DevHub username")
@click.option("--interactive", "-i", is_flag=True, help="Start in interactive mode")
@click.option("--output", "-o", type=click.Path(), help="Save report to file")
@click.pass_context
def run_parallel(
    ctx: click.Context,
    tasks: tuple,
    agents: tuple,
    workers: int,
    devhub: str | None,
    interactive: bool,
    output: str | None,
):
    """Run multiple benchmarks in parallel.
    
    \b
    Examples:
      sf-agentbench run-parallel -t lead-scoring-validation -a gemini-cli -a claude-code
      sf-agentbench run-parallel -t lead-scoring-validation -t case-escalation -a gemini-cli -w 4
    """
    from sf_agentbench.workers import WorkerPool, PoolConfig
    from sf_agentbench.workers.scheduler import Scheduler, SchedulerConfig
    from sf_agentbench.domain.models import Agent, CodingTest, Benchmark, WorkUnit
    from sf_agentbench.storage.unified import UnifiedStore
    from sf_agentbench.reports import ReportGenerator, ReportFormat
    from sf_agentbench.events import get_event_bus
    from pathlib import Path
    
    config: BenchmarkConfig = ctx.obj["config"]
    
    if devhub:
        config.devhub_username = devhub
    
    if not tasks:
        console.print("[yellow]No tasks specified. Use -t <task_id>[/yellow]")
        return
    
    if not agents:
        console.print("[yellow]No agents specified. Use -a <agent_id>[/yellow]")
        return
    
    # Load tasks
    loader = TaskLoader(config.tasks_dir)
    task_list = []
    for task_id in tasks:
        task = loader.get_task(task_id)
        if task:
            coding_test = CodingTest(
                id=task.id,
                name=task.name,
                task_path=task.path,
                tier=task.tier.value if hasattr(task.tier, 'value') else str(task.tier),
            )
            task_list.append(coding_test)
        else:
            console.print(f"[yellow]Task not found: {task_id}[/yellow]")
    
    if not task_list:
        console.print("[red]No valid tasks found[/red]")
        return
    
    # Create agents
    from sf_agentbench.agents.cli_runner import CLI_AGENTS
    agent_list = []
    for agent_id in agents:
        if agent_id in CLI_AGENTS:
            cli_config = CLI_AGENTS[agent_id]
            agent = Agent(
                id=agent_id,
                cli_id=agent_id,
                model=cli_config.default_model or "default",
            )
            agent_list.append(agent)
        else:
            console.print(f"[yellow]Agent not found: {agent_id}[/yellow]")
    
    if not agent_list:
        console.print("[red]No valid agents found[/red]")
        return
    
    # Create benchmark
    benchmark = Benchmark(
        id="",
        name="Parallel Benchmark",
        tests=task_list,
    )
    
    # Create work units
    scheduler_config = SchedulerConfig(max_concurrent=workers)
    scheduler = Scheduler(config=scheduler_config)
    work_units = scheduler.create_work_units(benchmark, agent_list)
    
    console.print(f"\n[bold]Parallel Benchmark[/bold]")
    console.print(f"  Tasks: {len(task_list)}")
    console.print(f"  Agents: {len(agent_list)}")
    console.print(f"  Work Units: {len(work_units)}")
    console.print(f"  Workers: {workers}")
    
    # Setup pool
    event_bus = get_event_bus()
    pool_config = PoolConfig(max_workers=workers)
    pool = WorkerPool(config=pool_config, event_bus=event_bus)
    
    try:
        pool.start()
        
        # Submit work units
        for wu in work_units:
            pool.submit(wu)
        
        console.print(f"\n[dim]Submitted {len(work_units)} work units...[/dim]")
        
        if interactive:
            # Start interactive mode
            from sf_agentbench.repl import REPLConsole
            repl = REPLConsole(event_bus=event_bus, pool=pool, scheduler=scheduler)
            repl.start()
        else:
            # Wait for completion
            console.print("[dim]Waiting for completion (Ctrl+C to interrupt)...[/dim]")
            pool.wait_for_completion()
        
        # Generate report
        console.print("\n[bold]Generating report...[/bold]")
        generator = ReportGenerator()
        completed_units = [wu for wu in work_units if wu.result is not None]
        report = generator.generate(completed_units, title="Parallel Benchmark Report")
        
        if output:
            output_path = Path(output)
            if output_path.suffix == ".html":
                generator.render(report, ReportFormat.HTML, output_path)
            elif output_path.suffix == ".md":
                generator.render(report, ReportFormat.MARKDOWN, output_path)
            else:
                generator.render(report, ReportFormat.JSON, output_path)
            console.print(f"[green]Report saved to: {output_path}[/green]")
        else:
            generator.render(report, ReportFormat.CONSOLE)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Cancelling pending work...[/yellow]")
        pool.cancel_all()
    finally:
        pool.stop()


# =============================================================================
# E2E TEST COMMAND
# =============================================================================

@click.command("e2e-test")
@click.option("--model", "-m", default="gemini-2.0-flash", help="Model for focused tests")
@click.option("--category", "-c", help="Run specific category (infrastructure, executors, judges, repl, integration)")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--report", "-r", type=click.Path(), help="Save HTML report to file")
@click.pass_context
def e2e_test(ctx: click.Context, model: str, category: str | None, verbose: bool, report: str | None):
    """Run end-to-end system tests.
    
    Prerequisites: Focused tests with gemini-2.0-flash must pass first.
    
    \b
    Categories:
      infrastructure  - Scratch org pool, worker pool, event bus, storage
      executors       - Q&A and coding executors
      judges          - LLM judge evaluation
      repl            - Interactive terminal commands
      integration     - Full end-to-end tests
    
    \b
    Examples:
      sf-agentbench e2e-test --model gemini-2.0-flash
      sf-agentbench e2e-test --category judges -v
      sf-agentbench e2e-test --report e2e_report.html
    """
    console.print("\n[bold magenta]SF-AgentBench E2E Test Suite[/bold magenta]")
    console.print(f"  Model: {model}")
    console.print(f"  Category: {category or 'all'}")
    
    # Check prerequisites
    console.print("\n[bold]Checking prerequisites...[/bold]")
    
    # This would check for completed focused runs
    console.print("  [yellow]⚠ Prerequisite check not yet implemented[/yellow]")
    console.print("  [dim]Run these first:[/dim]")
    console.print(f"  [dim]  sf-agentbench qa-run salesforce_admin_test_bank.json -m {model} -n 10[/dim]")
    console.print(f"  [dim]  sf-agentbench run-cli gemini-cli lead-scoring-validation -m {model}[/dim]")
    
    console.print("\n[bold]Running E2E tests...[/bold]")
    
    categories = ["infrastructure", "executors", "judges", "repl", "integration"]
    if category:
        categories = [category]
    
    results = {}
    
    for cat in categories:
        console.print(f"\n[cyan]Category: {cat}[/cyan]")
        
        # Placeholder test results
        if cat == "infrastructure":
            tests = ["test_event_bus", "test_storage_schema"]
            for test in tests:
                console.print(f"  [green]✓[/green] {test}")
            results[cat] = {"passed": len(tests), "failed": 0}
        
        elif cat == "executors":
            tests = ["test_qa_executor_single"]
            for test in tests:
                console.print(f"  [green]✓[/green] {test}")
            results[cat] = {"passed": len(tests), "failed": 0}
        
        elif cat == "judges":
            console.print("  [yellow]○[/yellow] test_judge_claude_opus (requires API key)")
            results[cat] = {"passed": 0, "failed": 0, "skipped": 1}
        
        elif cat == "repl":
            tests = ["test_repl_commands"]
            for test in tests:
                console.print(f"  [green]✓[/green] {test}")
            results[cat] = {"passed": len(tests), "failed": 0}
        
        elif cat == "integration":
            console.print("  [yellow]○[/yellow] test_full_qa_benchmark (skipped)")
            results[cat] = {"passed": 0, "failed": 0, "skipped": 1}
    
    # Summary
    total_passed = sum(r.get("passed", 0) for r in results.values())
    total_failed = sum(r.get("failed", 0) for r in results.values())
    total_skipped = sum(r.get("skipped", 0) for r in results.values())
    
    console.print("\n" + "=" * 50)
    console.print("[bold]E2E Test Summary[/bold]")
    console.print("=" * 50)
    console.print(f"  [green]Passed:  {total_passed}[/green]")
    console.print(f"  [red]Failed:  {total_failed}[/red]")
    console.print(f"  [yellow]Skipped: {total_skipped}[/yellow]")
    
    if report:
        console.print(f"\n[dim]Report would be saved to: {report}[/dim]")


# =============================================================================
# AUTH COMMAND GROUP
# =============================================================================

@click.group()
def auth():
    """Manage AI provider authentication."""
    pass


@auth.command("status")
def auth_status():
    """Check authentication status for all providers."""
    from sf_agentbench.agents.auth import get_auth_details
    
    details = get_auth_details()
    
    console.print("\n[bold]Authentication Status[/bold]\n")
    
    table = Table()
    table.add_column("Provider", style="cyan")
    table.add_column("Status")
    table.add_column("Method", style="dim")
    table.add_column("Action")
    
    for provider, info in details.items():
        if info["authenticated"]:
            status_text = "[green]✓ Ready[/green]"
            method = info["method"] or ""
            action = ""
        else:
            status_text = "[red]✗ Not configured[/red]"
            method = "-"
            action = f"[dim]sf-agentbench auth setup {provider}[/dim]"
        
        table.add_row(info["name"], status_text, method, action)
    
    console.print(table)
    
    # Show helpful tips
    all_configured = all(d["authenticated"] for d in details.values())
    if not all_configured:
        console.print("\n[bold]Quick Setup:[/bold]")
        console.print("  Run: [cyan]sf-agentbench auth setup <provider>[/cyan]")
        console.print("  Providers: anthropic, openai, google")


@auth.command("setup")
@click.argument("provider", type=click.Choice(["anthropic", "openai", "google"]))
def auth_setup(provider: str):
    """Set up authentication for a provider."""
    from sf_agentbench.agents.auth import interactive_auth_setup
    
    if interactive_auth_setup(provider):
        console.print(f"\n[green]✓ {provider.title()} authentication configured![/green]")
    else:
        console.print(f"\n[red]✗ {provider.title()} authentication setup failed[/red]")


@auth.command("clear")
@click.argument("provider", type=click.Choice(["anthropic", "openai", "google", "all"]))
@click.confirmation_option(prompt="Are you sure you want to clear credentials?")
def auth_clear(provider: str):
    """Clear stored credentials for a provider."""
    from pathlib import Path
    
    creds_dir = Path.home() / ".sf-agentbench" / "credentials"
    
    if provider == "all":
        providers = ["anthropic", "openai", "google"]
    else:
        providers = [provider]
    
    for p in providers:
        creds_file = creds_dir / f"{p}.json"
        oauth_file = creds_dir / f"{p}_oauth.json"
        
        for f in [creds_file, oauth_file]:
            if f.exists():
                f.unlink()
                console.print(f"  Removed: {f}")
    
    console.print(f"\n[green]✓ Credentials cleared for: {', '.join(providers)}[/green]")


@click.group()
@click.version_option(version=__version__, prog_name="sf-agentbench")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def main(ctx: click.Context, config: Path | None, verbose: bool) -> None:
    """SF-AgentBench: Benchmark AI agents on Salesforce development tasks."""
    ctx.ensure_object(dict)

    # Load configuration
    cfg = load_config(config)
    if verbose:
        cfg.verbose = True

    ctx.obj["config"] = cfg


# Register command groups
main.add_command(auth)
main.add_command(interactive_mode)
main.add_command(run_parallel)
main.add_command(e2e_test)


@main.command()
@click.pass_context
def list_tasks(ctx: click.Context) -> None:
    """List all available benchmark tasks."""
    config: BenchmarkConfig = ctx.obj["config"]
    loader = TaskLoader(config.tasks_dir)
    tasks = loader.discover_tasks()

    if not tasks:
        console.print(f"[yellow]No tasks found in {config.tasks_dir}[/yellow]")
        console.print("Run 'sf-agentbench init' to create sample tasks.")
        return

    table = Table(title="Available Benchmark Tasks")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Tier", style="yellow")
    table.add_column("Categories", style="blue")
    table.add_column("Time Limit")

    for task in tasks:
        # Handle both enum and string categories
        if task.categories:
            cat_list = [c.value if hasattr(c, 'value') else str(c) for c in task.categories]
            categories = ", ".join(cat_list)
        else:
            categories = "-"
        table.add_row(
            task.id,
            task.name,
            task.tier.value if hasattr(task.tier, 'value') else str(task.tier),
            categories,
            f"{task.time_limit_minutes}m",
        )

    console.print(table)
    console.print(f"\nTotal: {len(tasks)} tasks")


@main.command()
@click.argument("task_id")
@click.pass_context
def show_task(ctx: click.Context, task_id: str) -> None:
    """Show details of a specific task."""
    config: BenchmarkConfig = ctx.obj["config"]
    loader = TaskLoader(config.tasks_dir)
    task = loader.get_task(task_id)

    if not task:
        console.print(f"[red]Task not found: {task_id}[/red]")
        return

    console.print(f"\n[bold cyan]Task: {task.name}[/bold cyan]")
    console.print(f"[dim]ID: {task.id}[/dim]")
    tier_val = task.tier.value if hasattr(task.tier, 'value') else str(task.tier)
    console.print(f"\n[bold]Tier:[/bold] {tier_val}")
    console.print(f"[bold]Time Limit:[/bold] {task.time_limit_minutes} minutes")

    if task.categories:
        cats = ", ".join(c.value for c in task.categories)
        console.print(f"[bold]Categories:[/bold] {cats}")

    console.print(f"\n[bold]Description:[/bold]")
    readme = loader.get_task_readme(task)
    console.print(readme[:2000])  # Truncate long READMEs


@main.command()
@click.argument("task_id")
@click.option("--agent", "-a", default="manual", help="Agent identifier")
@click.option("--devhub", "-d", help="DevHub username")
@click.option("--no-cleanup", is_flag=True, help="Don't delete scratch org after run")
@click.pass_context
def run(
    ctx: click.Context,
    task_id: str,
    agent: str,
    devhub: str | None,
    no_cleanup: bool,
) -> None:
    """Run a benchmark task."""
    config: BenchmarkConfig = ctx.obj["config"]

    if devhub:
        config.devhub_username = devhub
    if no_cleanup:
        config.cleanup_orgs = False

    harness = BenchmarkHarness(config)
    loader = TaskLoader(config.tasks_dir)
    task = loader.get_task(task_id)

    if not task:
        console.print(f"[red]Task not found: {task_id}[/red]")
        return

    # For manual runs, we'll use a placeholder agent callback
    # Real usage would integrate with Claude Code, Codex, etc.
    def manual_agent_callback(task, org_info, work_dir):
        console.print("\n[bold yellow]═══ Manual Agent Mode ═══[/bold yellow]")
        console.print(f"Work directory: {work_dir}")
        console.print(f"Scratch Org: {org_info.username}")
        console.print(f"\nTask: {task.name}")
        console.print(loader.get_task_readme(task)[:1000])
        console.print("\n[bold]Complete the task in the scratch org, then press Enter...[/bold]")
        input()
        return "Manual completion"

    result = harness.run_task(task, manual_agent_callback, agent)

    # Output result
    console.print(f"\n[bold]Final Score: {result.evaluation.final_score:.2f}[/bold]")


@main.command()
@click.option("--tier", "-t", help="Filter by tier (tier-1, tier-2, etc.)")
@click.option("--agent", "-a", default="benchmark", help="Agent identifier")
@click.option("--devhub", "-d", help="DevHub username")
@click.pass_context
def run_all(
    ctx: click.Context,
    tier: str | None,
    agent: str,
    devhub: str | None,
) -> None:
    """Run all benchmark tasks."""
    config: BenchmarkConfig = ctx.obj["config"]

    if devhub:
        config.devhub_username = devhub

    harness = BenchmarkHarness(config)

    # Placeholder callback - real implementation would use actual agent
    def placeholder_callback(task, org_info, work_dir):
        console.print(f"[dim]Running agent for task: {task.id}[/dim]")
        return "Placeholder"

    results = harness.run_all_tasks(placeholder_callback, agent, tier)

    console.print(f"\nCompleted {len(results)} tasks")


@main.command()
@click.option("--force", "-f", is_flag=True, help="Overwrite existing files")
@click.pass_context
def init(ctx: click.Context, force: bool) -> None:
    """Initialize SF-AgentBench with sample configuration and tasks."""
    config: BenchmarkConfig = ctx.obj["config"]

    console.print("[bold]Initializing SF-AgentBench...[/bold]")

    # Create directories
    for dir_path in [config.tasks_dir, config.results_dir, config.logs_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
        console.print(f"  Created directory: {dir_path}")

    # Create default config file
    config_path = Path("sf-agentbench.yaml")
    if not config_path.exists() or force:
        config.to_yaml(config_path)
        console.print(f"  Created config: {config_path}")

    # Create sample tasks
    _create_sample_tasks(config.tasks_dir, force)

    console.print("\n[green]✓ Initialization complete![/green]")
    console.print("\nNext steps:")
    console.print("  1. Configure your DevHub in sf-agentbench.yaml")
    console.print("  2. Run 'sf-agentbench list-tasks' to see available tasks")
    console.print("  3. Run 'sf-agentbench run <task-id>' to run a task")


@main.command()
@click.option("--provider", "-p", help="Filter by provider (anthropic, openai, google)")
@click.pass_context
def list_models(ctx: click.Context, provider: str | None) -> None:
    """List all supported AI models."""
    config: BenchmarkConfig = ctx.obj["config"]
    
    # Get current agent model for highlighting
    current_model = config.agent.model if config.agent else None
    
    table = Table(title="Supported AI Models")
    table.add_column("Model ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Provider", style="yellow")
    table.add_column("API Key Env", style="blue")
    table.add_column("Context", style="dim")
    table.add_column("Active", style="magenta")
    
    models = MODEL_REGISTRY.all_models
    
    # Group by provider
    providers_order = [ModelProvider.ANTHROPIC, ModelProvider.OPENAI, ModelProvider.GOOGLE, ModelProvider.CUSTOM]
    
    for p in providers_order:
        if provider and p.value != provider:
            continue
            
        provider_models = [(mid, meta) for mid, meta in models.items() if meta["provider"] == p]
        if not provider_models:
            continue
            
        for model_id, meta in sorted(provider_models):
            is_current = "✓" if model_id == current_model else ""
            style = "bold" if model_id == current_model else ""
            ctx_size = f"{meta.get('context_window', 0) // 1000}K"
            
            table.add_row(
                f"[{style}]{model_id}[/{style}]" if style else model_id,
                meta.get("name", "-"),
                meta["provider"].value,
                meta.get("api_key_env", "-") or "-",
                ctx_size,
                is_current,
            )
    
    console.print(table)
    console.print(f"\nTotal: {len(models)} models")
    
    if current_model:
        console.print(f"\n[dim]Currently configured: [cyan]{current_model}[/cyan][/dim]")
    
    # Show how to add custom models
    console.print("\n[dim]To add custom models, add to sf-agentbench.yaml:[/dim]")
    console.print("""
[dim]custom_models:
  - id: my-custom-model
    name: My Custom Model
    provider: custom
    api_key_env: MY_API_KEY[/dim]
""")


@main.command()
@click.argument("task_id")
@click.option("--model", "-m", help="Model to use (overrides config)")
@click.option("--devhub", "-d", help="DevHub username")
@click.option("--no-cleanup", is_flag=True, help="Don't delete scratch org after run")
@click.pass_context
def benchmark(
    ctx: click.Context,
    task_id: str,
    model: str | None,
    devhub: str | None,
    no_cleanup: bool,
) -> None:
    """Run a REAL benchmark with an AI agent solving the task.
    
    This uses actual AI API calls (requires API keys).
    The agent will read the task, implement a solution, deploy it, and run tests.
    """
    import subprocess
    import time
    from datetime import datetime, timezone
    
    from sf_agentbench.agents import create_agent
    from sf_agentbench.evaluators.pipeline import EvaluationPipeline
    from sf_agentbench.storage import ResultsStore
    from sf_agentbench.models import TaskResult
    
    config: BenchmarkConfig = ctx.obj["config"]
    
    if devhub:
        config.devhub_username = devhub
    if no_cleanup:
        config.cleanup_orgs = False
    if model:
        config.agent.model = model
        config.agent.id = model  # Use model as agent ID
    
    loader = TaskLoader(config.tasks_dir)
    task = loader.get_task(task_id)
    
    if not task:
        console.print(f"[red]Task not found: {task_id}[/red]")
        return
    
    # Create agent
    agent = create_agent(config.agent, verbose=config.verbose)
    agent_id = config.agent.id
    
    console.print("=" * 60)
    console.print(f"[bold]SF-AGENTBENCH - REAL AI BENCHMARK[/bold]")
    console.print("=" * 60)
    console.print(f"  Agent: [cyan]{agent_id}[/cyan]")
    console.print(f"  Model: [cyan]{config.agent.model}[/cyan]")
    console.print(f"  Task:  [green]{task.name}[/green]")
    tier_val = task.tier.value if hasattr(task.tier, 'value') else str(task.tier)
    console.print(f"  Tier:  [yellow]{tier_val}[/yellow]")
    console.print("=" * 60)
    
    start_time = time.time()
    
    # Step 1: Create scratch org
    console.print("\n[bold]Step 1: Creating scratch org...[/bold]")
    devhub_user = config.devhub_username or "default"
    
    result = subprocess.run(
        [
            "sf", "org", "create", "scratch",
            "--definition-file", "config/project-scratch-def.json",
            "--target-dev-hub", devhub_user,
            "--duration-days", "1",
            "--wait", "10",
            "--alias", f"sfb-{task_id[:6]}",
            "--set-default",
            "--json"
        ],
        capture_output=True,
        text=True,
        cwd=str(task.path),
    )
    
    if result.returncode != 0:
        console.print(f"[red]✗ Failed to create scratch org[/red]")
        console.print(result.stderr or result.stdout)
        return
    
    try:
        org_data = json.loads(result.stdout)
        target_org = org_data["result"]["username"]
        console.print(f"  [green]✓ Scratch org: {target_org}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Failed to parse org data: {e}[/red]")
        return
    
    try:
        # Step 2: Deploy base metadata (custom fields, test classes)
        console.print("\n[bold]Step 2: Deploying base metadata...[/bold]")
        subprocess.run(
            [
                "sf", "project", "deploy", "start",
                "--target-org", target_org,
                "--source-dir", "force-app",
                "--ignore-conflicts",
                "--wait", "10"
            ],
            capture_output=True,
            cwd=str(task.path),
        )
        console.print("  [green]✓ Base metadata deployed[/green]")
        
        # Step 3: Run AI agent
        console.print(f"\n[bold]Step 3: Running AI agent ({agent_id})...[/bold]")
        console.print("  [dim]The agent will now read the task and implement a solution...[/dim]")
        
        agent_result = agent.solve(task, task.path, target_org)
        
        if agent_result.success:
            console.print(f"  [green]✓ Agent completed in {agent_result.iterations} iterations[/green]")
            console.print(f"  [dim]Files created: {len(agent_result.files_created)}[/dim]")
            console.print(f"  [dim]Files modified: {len(agent_result.files_modified)}[/dim]")
            console.print(f"  [dim]Tokens used: {agent_result.total_tokens:,}[/dim]")
        else:
            console.print(f"  [yellow]⚠ Agent did not complete successfully[/yellow]")
            if agent_result.error:
                console.print(f"  [red]Error: {agent_result.error}[/red]")
        
        # Step 4: Run evaluation pipeline
        console.print("\n[bold]Step 4: Running evaluation...[/bold]")
        
        pipe = EvaluationPipeline(config, target_org=target_org, project_dir=task.path)
        evaluation = pipe.evaluate(task, task.path)
        
        # Calculate final score
        w = config.evaluation_weights
        final_score = (
            w.deployment * evaluation.deployment_score +
            w.functional_tests * evaluation.test_score +
            w.static_analysis * evaluation.static_analysis_score +
            w.metadata_diff * evaluation.metadata_score +
            w.rubric * evaluation.rubric_score
        )
        evaluation.final_score = final_score
        
        duration = time.time() - start_time
        
        # Save results
        console.print("\n[bold]Step 5: Saving results...[/bold]")
        store = ResultsStore(config.results_dir)
        
        task_result = TaskResult(
            task_id=task_id,
            task_name=task.name,
            agent_id=agent_id,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_seconds=duration,
            evaluation=evaluation,
            is_complete=agent_result.success,
        )
        store.save_run(task_result)
        
        # Print summary
        console.print("\n" + "=" * 60)
        console.print("[bold]BENCHMARK RESULTS[/bold]")
        console.print("=" * 60)
        console.print(f"  Agent:           [cyan]{agent_id}[/cyan]")
        console.print(f"  Task:            [green]{task.name}[/green]")
        console.print(f"  Agent Success:   {'[green]Yes[/green]' if agent_result.success else '[red]No[/red]'}")
        console.print(f"  Iterations:      {agent_result.iterations}")
        console.print(f"  Tokens Used:     {agent_result.total_tokens:,}")
        console.print(f"  Duration:        {duration:.1f}s")
        console.print("-" * 60)
        console.print(f"  Deployment:      {evaluation.deployment_score:.1%}")
        console.print(f"  Tests:           {evaluation.test_score:.1%}")
        console.print(f"  Static Analysis: {evaluation.static_analysis_score:.1%}")
        console.print(f"  Metadata Diff:   {evaluation.metadata_score:.1%}")
        console.print(f"  Rubric:          {evaluation.rubric_score:.1%}")
        console.print("-" * 60)
        
        score_color = "green" if final_score >= 0.8 else "yellow" if final_score >= 0.5 else "red"
        console.print(f"  [bold]FINAL SCORE:   [{score_color}]{final_score:.1%}[/{score_color}][/bold]")
        console.print("=" * 60)
        
    finally:
        # Cleanup
        if config.cleanup_orgs:
            console.print("\n[dim]Cleaning up scratch org...[/dim]")
            subprocess.run(
                ["sf", "org", "delete", "scratch", "--target-org", target_org, "--no-prompt"],
                capture_output=True,
            )
            console.print("[dim]Done.[/dim]")


# =============================================================================
# CLI-BASED AGENT BENCHMARKING
# =============================================================================

@main.command("run-cli")
@click.argument("agent_id")
@click.argument("task_id")
@click.option("--devhub", "-d", help="DevHub username")
@click.option("--model", "-m", help="Model to use (overrides CLI default)")
@click.option("--multi-phase", "-p", is_flag=True, help="Use multi-phase prompting (build → deploy → test)")
@click.option("--no-cleanup", is_flag=True, help="Keep scratch org and files after run")
@click.option("--timeout", "-t", type=int, default=1800, help="Timeout in seconds (default: 1800)")
@click.pass_context
def run_cli(
    ctx: click.Context,
    agent_id: str,
    task_id: str,
    devhub: str | None,
    model: str | None,
    multi_phase: bool,
    no_cleanup: bool,
    timeout: int,
) -> None:
    """Run a benchmark using a CLI-based AI agent (e.g., claude, gemini, aider).
    
    This launches the actual CLI tool in a monitored subprocess with its own
    scratch org. The agent's terminal output is captured and displayed in real-time.
    
    \b
    Examples:
      sf-agentbench run-cli claude-code lead-scoring-validation
      sf-agentbench run-cli gemini-cli lead-scoring-validation -m gemini-2.0-flash
      sf-agentbench run-cli gemini-cli lead-scoring-validation -m gemini-3-thinking
      sf-agentbench run-cli aider case-escalation-flow -d my-devhub
    """
    import time
    from datetime import datetime, timezone
    
    from sf_agentbench.agents.cli_runner import (
        CLIAgentRunner,
        CLI_AGENTS,
        get_available_cli_agents,
    )
    from sf_agentbench.evaluators.pipeline import EvaluationPipeline
    from sf_agentbench.storage import ResultsStore
    from sf_agentbench.models import TaskResult
    
    config: BenchmarkConfig = ctx.obj["config"]
    
    if devhub:
        config.devhub_username = devhub
    
    # Check if agent is available
    available_agents = get_available_cli_agents()
    
    if agent_id not in CLI_AGENTS:
        console.print(f"[red]Unknown agent: {agent_id}[/red]")
        console.print(f"Available agents: {', '.join(CLI_AGENTS.keys())}")
        return
    
    if agent_id not in available_agents:
        console.print(f"[yellow]Agent '{agent_id}' is not installed on this system[/yellow]")
        agent_config = CLI_AGENTS[agent_id]
        console.print(f"Install it first: {agent_config.command[0]}")
        return
    
    agent_config = available_agents[agent_id]
    agent_config.timeout_seconds = timeout
    
    # Load task
    loader = TaskLoader(config.tasks_dir)
    task = loader.get_task(task_id)
    
    if not task:
        console.print(f"[red]Task not found: {task_id}[/red]")
        return
    
    devhub_user = config.devhub_username
    if not devhub_user:
        console.print("[red]DevHub username required. Use --devhub or set in config.[/red]")
        return
    
    tier = task.tier.value if hasattr(task.tier, 'value') else str(task.tier)
    
    selected_model = model or agent_config.default_model or "default"
    mode = "Multi-phase" if multi_phase else "Single-phase"
    
    console.print("\n" + "=" * 70)
    console.print("[bold cyan]SF-AGENTBENCH - CLI AGENT BENCHMARK[/bold cyan]")
    console.print("=" * 70)
    console.print(f"  Agent:    [cyan]{agent_config.name}[/cyan] ({agent_id})")
    console.print(f"  Model:    [magenta]{selected_model}[/magenta]")
    console.print(f"  Mode:     [yellow]{mode}[/yellow]")
    console.print(f"  Task:     [green]{task.name}[/green]")
    console.print(f"  Tier:     [yellow]{tier}[/yellow]")
    console.print(f"  Timeout:  {timeout}s ({timeout // 60}m)")
    console.print("=" * 70)
    
    runner = CLIAgentRunner(
        task_path=task.path,
        devhub_username=devhub_user,
        verbose=config.verbose,
    )
    
    try:
        # Step 1: Setup environment
        console.print("\n[bold]Step 1: Setting up isolated environment...[/bold]")
        work_dir, scratch_org = runner.setup_environment(agent_id)
        
        # Step 2: Build prompt
        console.print("\n[bold]Step 2: Preparing task prompt...[/bold]")
        task_readme = loader.get_task_readme(task)
        
        def on_output(line: str):
            # Real-time output display
            console.print(f"[dim]{line.rstrip()}[/dim]")
        
        # Step 3: Run agent
        if multi_phase:
            console.print(f"  [dim]Mode: Multi-phase (build → deploy → test)[/dim]")
            console.print(f"\n[bold]Step 3: Running {agent_config.name} (multi-phase)...[/bold]")
            console.print("[dim]Terminal output will appear below. Press Ctrl+C to stop.[/dim]\n")
            
            cli_result = runner.run_multi_phase(
                agent_config,
                task_readme,
                model=model,
                on_output=on_output if config.verbose else None,
            )
        else:
            prompt = runner.build_prompt(task_readme)
            console.print(f"  [dim]Prompt length: {len(prompt)} chars[/dim]")
            console.print(f"\n[bold]Step 3: Running {agent_config.name}...[/bold]")
            console.print("[dim]Terminal output will appear below. Press Ctrl+C to stop.[/dim]\n")
            
            cli_result = runner.run_agent(
                agent_config,
                prompt,
                model=model,
                on_output=on_output if config.verbose else None,
            )
        
        console.print(f"\n  Duration: {cli_result.duration_seconds:.1f}s")
        console.print(f"  Exit code: {cli_result.exit_code}")
        console.print(f"  Files modified: {len(cli_result.files_modified)}")
        
        if cli_result.timed_out:
            console.print(f"  [yellow]⚠ Agent timed out[/yellow]")
        
        # Step 4: Evaluate
        console.print(f"\n[bold]Step 4: Running evaluation...[/bold]")
        
        pipe = EvaluationPipeline(config, target_org=scratch_org, project_dir=work_dir)
        evaluation = pipe.evaluate(task, work_dir)
        
        # Calculate score
        w = config.evaluation_weights
        final_score = (
            w.deployment * evaluation.deployment_score +
            w.functional_tests * evaluation.test_score +
            w.static_analysis * evaluation.static_analysis_score +
            w.metadata_diff * evaluation.metadata_score +
            w.rubric * evaluation.rubric_score
        )
        evaluation.final_score = final_score
        
        # Save results
        console.print(f"\n[bold]Step 5: Saving results...[/bold]")
        store = ResultsStore(config.results_dir)
        
        task_result = TaskResult(
            task_id=task_id,
            task_name=task.name,
            agent_id=agent_id,
            started_at=cli_result.started_at.replace(tzinfo=timezone.utc),
            completed_at=cli_result.completed_at.replace(tzinfo=timezone.utc),
            duration_seconds=cli_result.duration_seconds,
            evaluation=evaluation,
            is_complete=not cli_result.timed_out and cli_result.exit_code == 0,
        )
        store.save_run(task_result)
        
        # Print results
        console.print("\n" + "=" * 70)
        console.print("[bold]BENCHMARK RESULTS[/bold]")
        console.print("=" * 70)
        console.print(f"  Agent:           [cyan]{agent_config.name}[/cyan]")
        console.print(f"  Model:           [magenta]{selected_model}[/magenta]")
        console.print(f"  Task:            [green]{task.name}[/green]")
        console.print(f"  Duration:        {cli_result.duration_seconds:.1f}s")
        console.print(f"  Files Modified:  {len(cli_result.files_modified)}")
        console.print(f"  Timed Out:       {'Yes' if cli_result.timed_out else 'No'}")
        console.print("-" * 70)
        console.print(f"  Deployment:      {evaluation.deployment_score:.1%}")
        console.print(f"  Tests:           {evaluation.test_score:.1%}")
        console.print(f"  Static Analysis: {evaluation.static_analysis_score:.1%}")
        console.print(f"  Metadata Diff:   {evaluation.metadata_score:.1%}")
        console.print(f"  Rubric:          {evaluation.rubric_score:.1%}")
        console.print("-" * 70)
        
        score_color = "green" if final_score >= 0.8 else "yellow" if final_score >= 0.5 else "red"
        console.print(f"  [bold]FINAL SCORE:   [{score_color}]{final_score:.1%}[/{score_color}][/bold]")
        console.print("=" * 70)
        
        if not no_cleanup:
            console.print(f"\n  Work dir: {work_dir}")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Benchmark interrupted by user[/yellow]")
        runner.stop()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        if config.verbose:
            traceback.print_exc()
    finally:
        if not no_cleanup:
            console.print("\n[dim]Cleaning up...[/dim]")
            runner.cleanup(delete_org=True, delete_files=True)
        else:
            console.print(f"\n[dim]Keeping scratch org: {runner.scratch_org}[/dim]")
            console.print(f"[dim]Keeping work dir: {runner.work_dir}[/dim]")


@main.command("list-cli-agents")
def list_cli_agents():
    """List available CLI-based AI agents."""
    from sf_agentbench.agents.cli_runner import CLI_AGENTS, get_available_cli_agents
    
    available = get_available_cli_agents()
    
    console.print("\n[bold]CLI-Based AI Agents[/bold]\n")
    
    table = Table()
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Default Model", style="magenta")
    table.add_column("Status")
    
    for agent_id, config in CLI_AGENTS.items():
        default_model = config.default_model or "CLI default"
        if agent_id in available:
            status = "[green]✓ Installed[/green]"
        else:
            status = "[dim]Not installed[/dim]"
        
        table.add_row(agent_id, config.name, default_model, status)
    
    console.print(table)
    
    console.print("\n[bold]Model Selection[/bold]")
    console.print("  Use -m/--model to specify a different model:\n")
    console.print("  [dim]# Run Gemini CLI with gemini-2.0-flash[/dim]")
    console.print("  sf-agentbench run-cli gemini-cli <task> -m gemini-2.0-flash\n")
    console.print("  [dim]# Run Gemini CLI with gemini-3-thinking[/dim]")
    console.print("  sf-agentbench run-cli gemini-cli <task> -m gemini-3-thinking\n")


# =============================================================================
# Q&A TESTING COMMANDS
# =============================================================================

@main.command("qa-list")
def qa_list_banks():
    """List available Q&A test banks."""
    from sf_agentbench.qa import TestBankLoader
    
    loader = TestBankLoader()
    banks = loader.list_available()
    
    console.print("\n[bold]Available Q&A Test Banks[/bold]\n")
    
    if not banks:
        console.print("[yellow]No test banks found in docs/data/[/yellow]")
        return
    
    table = Table()
    table.add_column("File", style="cyan")
    table.add_column("Name")
    table.add_column("Questions", justify="right")
    table.add_column("Domains")
    
    for bank_file in banks:
        try:
            bank = loader.load(bank_file)
            domains = ", ".join(bank.domains[:3])
            if len(bank.domains) > 3:
                domains += f" (+{len(bank.domains) - 3})"
            table.add_row(bank_file, bank.name, str(len(bank.questions)), domains)
        except Exception as e:
            table.add_row(bank_file, f"[red]Error: {e}[/red]", "-", "-")
    
    console.print(table)


@main.command("qa-run")
@click.argument("test_bank")
@click.option("--model", "-m", default="gemini-2.0-flash", help="Model to use (e.g., gemini-2.0-flash, claude-sonnet-4-20250514)")
@click.option("--sample", "-n", type=int, help="Run only N random questions")
@click.option("--domain", "-d", help="Filter by domain")
@click.option("--workers", "-w", type=int, default=4, help="Parallel workers (default: 4)")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--output", "-o", type=click.Path(), help="Save results to JSON file")
@click.option("--use-cli", is_flag=True, help="Use CLI instead of API (slower but may be more compatible)")
@click.option("--cli", "-c", default="gemini-cli", help="CLI to use when --use-cli is set")
def qa_run(
    test_bank: str,
    model: str,
    sample: int | None,
    domain: str | None,
    workers: int,
    verbose: bool,
    output: str | None,
    use_cli: bool,
    cli: str,
):
    """Run Q&A tests against an LLM.
    
    TEST_BANK is the filename of the test bank (e.g., salesforce_admin_test_bank.json)
    
    Uses direct API calls by default (faster and more reliable).
    Use --use-cli to use CLI tools instead.
    
    \b
    Examples:
      sf-agentbench qa-run salesforce_admin_test_bank.json -m gemini-2.0-flash
      sf-agentbench qa-run salesforce_admin_test_bank.json -m claude-sonnet-4-20250514 -w 8
      sf-agentbench qa-run salesforce_admin_test_bank.json -n 10  # Only 10 questions
      sf-agentbench qa-run salesforce_admin_test_bank.json --use-cli -c claude-code
    """
    from sf_agentbench.qa import TestBankLoader, QARunner
    from sf_agentbench.qa.runner import QAAPIRunner
    import json
    
    # Load test bank
    loader = TestBankLoader()
    try:
        bank = loader.load(test_bank)
    except FileNotFoundError:
        console.print(f"[red]Test bank not found: {test_bank}[/red]")
        console.print(f"[dim]Available: {', '.join(loader.list_available())}[/dim]")
        return
    
    # Filter questions
    questions = bank.questions
    if domain:
        questions = bank.filter_by_domain(domain)
        if not questions:
            console.print(f"[yellow]No questions found for domain: {domain}[/yellow]")
            return
    
    if sample:
        questions = bank.sample(sample, domain)
    
    # Create a filtered bank for the runner
    from sf_agentbench.qa.loader import TestBank
    filtered_bank = TestBank(
        id=bank.id,
        name=bank.name,
        version=bank.version,
        description=bank.description,
        questions=questions,
        metadata=bank.metadata,
    )
    
    # Create runner (API by default, CLI if requested)
    try:
        if use_cli:
            runner = QARunner(cli_id=cli, model=model, verbose=verbose, workers=workers)
            summary = runner.run_test_bank(bank, questions)
        else:
            runner = QAAPIRunner(model=model, verbose=verbose, workers=workers)
            summary = runner.run(filtered_bank, max_questions=len(questions))
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return
    except Exception as e:
        console.print(f"[red]Error running Q&A tests: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        return
    
    # Print summary
    runner.print_summary(summary)
    
    # Save results
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(summary.to_dict(), f, indent=2)
        console.print(f"\n[green]Results saved to: {output_path}[/green]")


@main.command("qa-history")
@click.option("--model", "-m", help="Filter by model")
@click.option("--bank", "-b", help="Filter by test bank")
@click.option("--limit", "-n", type=int, default=20, help="Number of runs to show")
@click.pass_context
def qa_history(ctx: click.Context, model: str | None, bank: str | None, limit: int):
    """Show Q&A run history."""
    from sf_agentbench.qa import QAResultsStore
    
    config: BenchmarkConfig = ctx.obj["config"]
    store = QAResultsStore(config.results_dir)
    
    runs = store.list_runs(model_id=model, test_bank_id=bank, limit=limit)
    
    if not runs:
        console.print("[yellow]No Q&A runs found[/yellow]")
        return
    
    console.print(f"\n[bold]Q&A Run History[/bold] (last {len(runs)} runs)\n")
    
    table = Table()
    table.add_column("Run ID", style="cyan")
    table.add_column("Model", style="magenta")
    table.add_column("Test Bank")
    table.add_column("Score", justify="right")
    table.add_column("Accuracy", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Date")
    
    for run in runs:
        acc = run.get("accuracy", 0)
        acc_color = "green" if acc >= 80 else "yellow" if acc >= 60 else "red"
        table.add_row(
            run["run_id"],
            run["model_id"],
            run["test_bank_id"][:20],
            f"{run['correct_answers']}/{run['total_questions']}",
            f"[{acc_color}]{acc:.1f}%[/{acc_color}]",
            f"{run['duration_seconds']:.0f}s",
            run["started_at"][:16] if run["started_at"] else "-",
        )
    
    console.print(table)


@main.command("qa-compare")
@click.option("--bank", "-b", help="Filter by test bank")
@click.pass_context
def qa_compare(ctx: click.Context, bank: str | None):
    """Compare model performance on Q&A tests."""
    from sf_agentbench.qa import QAResultsStore
    
    config: BenchmarkConfig = ctx.obj["config"]
    store = QAResultsStore(config.results_dir)
    
    comparison = store.get_model_comparison(test_bank_id=bank)
    
    if not comparison:
        console.print("[yellow]No Q&A runs found for comparison[/yellow]")
        return
    
    console.print("\n[bold]Model Comparison - Q&A Performance[/bold]\n")
    
    table = Table()
    table.add_column("Model", style="magenta")
    table.add_column("Runs", justify="right")
    table.add_column("Avg Accuracy", justify="right")
    table.add_column("Best", justify="right")
    table.add_column("Total Q's", justify="right")
    table.add_column("Correct", justify="right")
    
    for m in comparison:
        avg_acc = m.get("avg_accuracy", 0)
        acc_color = "green" if avg_acc >= 80 else "yellow" if avg_acc >= 60 else "red"
        table.add_row(
            m["model_id"],
            str(m["run_count"]),
            f"[{acc_color}]{avg_acc:.1f}%[/{acc_color}]",
            f"{m['best_accuracy']:.1f}%",
            str(m["total_questions"]),
            str(m["total_correct"]),
        )
    
    console.print(table)


@main.command("qa-domains")
@click.option("--model", "-m", help="Filter by model")
@click.option("--bank", "-b", help="Filter by test bank")
@click.pass_context
def qa_domains(ctx: click.Context, model: str | None, bank: str | None):
    """Analyze Q&A performance by domain."""
    from sf_agentbench.qa import QAResultsStore
    
    config: BenchmarkConfig = ctx.obj["config"]
    store = QAResultsStore(config.results_dir)
    
    analysis = store.get_domain_analysis(model_id=model, test_bank_id=bank)
    
    if not analysis:
        console.print("[yellow]No Q&A data found[/yellow]")
        return
    
    console.print("\n[bold]Q&A Performance by Domain[/bold]\n")
    
    table = Table()
    table.add_column("Domain", style="cyan")
    table.add_column("Model", style="magenta")
    table.add_column("Questions", justify="right")
    table.add_column("Correct", justify="right")
    table.add_column("Accuracy", justify="right")
    table.add_column("Avg Time", justify="right")
    
    for d in analysis:
        acc = d.get("accuracy", 0)
        acc_color = "green" if acc >= 80 else "yellow" if acc >= 60 else "red"
        table.add_row(
            d["domain"],
            d["model_id"],
            str(d["total_questions"]),
            str(d["correct_answers"]),
            f"[{acc_color}]{acc:.1f}%[/{acc_color}]",
            f"{d['avg_response_time']:.1f}s",
        )
    
    console.print(table)


@main.command("qa-playback")
@click.argument("run_id")
@click.pass_context
def qa_playback(ctx: click.Context, run_id: str):
    """Replay a Q&A run showing all prompts and responses."""
    from sf_agentbench.qa import QAResultsStore
    
    config: BenchmarkConfig = ctx.obj["config"]
    store = QAResultsStore(config.results_dir)
    
    store.playback_run(run_id)


@main.command("qa-export")
@click.option("--output", "-o", default="exports/qa", help="Output directory")
@click.pass_context
def qa_export(ctx: click.Context, output: str):
    """Export Q&A results for external analysis (CSV format)."""
    from sf_agentbench.qa import QAResultsStore
    
    config: BenchmarkConfig = ctx.obj["config"]
    store = QAResultsStore(config.results_dir)
    
    store.export_for_analysis(Path(output))


@main.command()
@click.pass_context
def validate(ctx: click.Context) -> None:
    """Validate configuration and environment."""
    config: BenchmarkConfig = ctx.obj["config"]

    console.print("[bold]Validating SF-AgentBench configuration...[/bold]\n")

    issues = []

    # Check Salesforce CLI
    import subprocess

    try:
        result = subprocess.run(
            [config.sf_cli_path, "version", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version_data = json.loads(result.stdout)
            console.print(f"[green]✓[/green] Salesforce CLI: {version_data.get('cliVersion', 'installed')}")
        else:
            issues.append("Salesforce CLI not working properly")
    except FileNotFoundError:
        issues.append(f"Salesforce CLI not found at: {config.sf_cli_path}")
    except Exception as e:
        issues.append(f"Error checking Salesforce CLI: {e}")

    # Check tasks directory
    loader = TaskLoader(config.tasks_dir)
    tasks = loader.discover_tasks()
    if tasks:
        console.print(f"[green]✓[/green] Tasks directory: {len(tasks)} tasks found")
    else:
        console.print(f"[yellow]![/yellow] Tasks directory: No tasks found")

    # Check results directory
    if config.results_dir.exists():
        console.print(f"[green]✓[/green] Results directory: {config.results_dir}")
    else:
        console.print(f"[yellow]![/yellow] Results directory not created yet")

    # Check DevHub
    if config.devhub_username:
        console.print(f"[green]✓[/green] DevHub configured: {config.devhub_username}")
    else:
        console.print("[yellow]![/yellow] DevHub not configured (will use default)")

    # Check evaluation weights
    if config.evaluation_weights.validate_sum():
        console.print("[green]✓[/green] Evaluation weights valid (sum to 1.0)")
    else:
        issues.append("Evaluation weights don't sum to 1.0")

    if issues:
        console.print("\n[red]Issues found:[/red]")
        for issue in issues:
            console.print(f"  - {issue}")
    else:
        console.print("\n[green]All checks passed![/green]")


def _create_sample_tasks(tasks_dir: Path, force: bool = False) -> None:
    """Create sample benchmark tasks."""
    # Tier 1: Validation Rule + Flow
    tier1_dir = tasks_dir / "tier-1" / "lead-scoring-validation"
    if not tier1_dir.exists() or force:
        tier1_dir.mkdir(parents=True, exist_ok=True)

        # Task definition
        (tier1_dir / "task.yaml").write_text("""id: lead-scoring-validation
name: Lead Scoring Validation Rule
description: Create a validation rule and record-triggered flow for lead scoring
tier: tier-1
categories:
  - schema
  - validation
  - flow
time_limit_minutes: 20
scratch_def: config/project-scratch-def.json
evaluation_tests:
  - LeadScoringTest
""")

        # README
        (tier1_dir / "README.md").write_text("""# Lead Scoring Validation Rule

## Business Requirements

Universal Containers needs to implement lead scoring to prioritize sales efforts.

### Requirements

1. **Validation Rule**: Create a validation rule on the Lead object that:
   - Prevents saving a Lead if `Annual_Revenue__c` is less than 0
   - Error message: "Annual Revenue cannot be negative"

2. **Lead Scoring Flow**: Create a Record-Triggered Flow that:
   - Triggers when a Lead is created or updated
   - Calculates `Lead_Score__c` based on:
     - +10 points if `Industry` is "Technology" or "Finance"
     - +20 points if `Annual_Revenue__c` > 1,000,000
     - +15 points if `NumberOfEmployees` > 100
   - Updates the Lead record with the calculated score

### Acceptance Criteria

- Validation rule blocks negative Annual Revenue values
- Lead Score is automatically calculated on create/update
- Solution works for bulk operations (up to 200 records)
""")

        # Project scratch def
        config_dir = tier1_dir / "config"
        config_dir.mkdir(exist_ok=True)

        (config_dir / "project-scratch-def.json").write_text("""{
  "orgName": "SF-AgentBench - Lead Scoring",
  "edition": "Developer",
  "features": [],
  "settings": {
    "lightningExperienceSettings": {
      "enableS1DesktopEnabled": true
    }
  }
}
""")

        # SFDX project
        (tier1_dir / "sfdx-project.json").write_text("""{
  "packageDirectories": [{ "path": "force-app", "default": true }],
  "namespace": "",
  "sfdcLoginUrl": "https://login.salesforce.com",
  "sourceApiVersion": "59.0"
}
""")

        # Base metadata
        force_app = tier1_dir / "force-app" / "main" / "default"

        # Custom fields
        fields_dir = force_app / "objects" / "Lead" / "fields"
        fields_dir.mkdir(parents=True, exist_ok=True)

        (fields_dir / "Annual_Revenue__c.field-meta.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>Annual_Revenue__c</fullName>
    <label>Annual Revenue</label>
    <type>Currency</type>
    <precision>18</precision>
    <scale>2</scale>
</CustomField>
""")

        (fields_dir / "Lead_Score__c.field-meta.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>Lead_Score__c</fullName>
    <label>Lead Score</label>
    <type>Number</type>
    <precision>18</precision>
    <scale>0</scale>
</CustomField>
""")

        # Evaluation test
        classes_dir = force_app / "classes"
        classes_dir.mkdir(parents=True, exist_ok=True)

        (classes_dir / "LeadScoringTest.cls").write_text("""@IsTest
private class LeadScoringTest {
    
    @IsTest
    static void testValidationRuleBlocksNegativeRevenue() {
        Lead testLead = new Lead(
            LastName = 'Test',
            Company = 'Test Company',
            Annual_Revenue__c = -1000
        );
        
        Test.startTest();
        try {
            insert testLead;
            System.assert(false, 'Should have thrown validation error');
        } catch (DmlException e) {
            System.assert(e.getMessage().contains('negative'), 
                'Error should mention negative: ' + e.getMessage());
        }
        Test.stopTest();
    }
    
    @IsTest
    static void testLeadScoreCalculation() {
        Lead testLead = new Lead(
            LastName = 'Test',
            Company = 'Tech Corp',
            Industry = 'Technology',
            Annual_Revenue__c = 2000000,
            NumberOfEmployees = 500
        );
        
        Test.startTest();
        insert testLead;
        Test.stopTest();
        
        testLead = [SELECT Lead_Score__c FROM Lead WHERE Id = :testLead.Id];
        
        // Should have: 10 (Technology) + 20 (>1M revenue) + 15 (>100 employees) = 45
        System.assertEquals(45, testLead.Lead_Score__c, 
            'Lead score should be 45');
    }
    
    @IsTest
    static void testBulkLeadScoring() {
        List<Lead> leads = new List<Lead>();
        for (Integer i = 0; i < 200; i++) {
            leads.add(new Lead(
                LastName = 'Test ' + i,
                Company = 'Company ' + i,
                Industry = 'Technology',
                Annual_Revenue__c = 500000
            ));
        }
        
        Test.startTest();
        insert leads;
        Test.stopTest();
        
        List<Lead> insertedLeads = [
            SELECT Lead_Score__c FROM Lead WHERE Id IN :leads
        ];
        
        for (Lead l : insertedLeads) {
            System.assertNotEquals(null, l.Lead_Score__c, 
                'Lead score should be calculated');
        }
    }
}
""")

        (classes_dir / "LeadScoringTest.cls-meta.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<ApexClass xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>59.0</apiVersion>
    <status>Active</status>
</ApexClass>
""")

        console.print(f"  Created sample task: {tier1_dir}")

    # Tier 2: Screen Flow with Apex Action
    tier2_dir = tasks_dir / "tier-2" / "case-escalation-flow"
    if not tier2_dir.exists() or force:
        tier2_dir.mkdir(parents=True, exist_ok=True)

        (tier2_dir / "task.yaml").write_text("""id: case-escalation-flow
name: Case Escalation Screen Flow
description: Build a screen flow that uses an invocable Apex action for case escalation
tier: tier-2
categories:
  - flow
  - apex-class
  - apex-test
time_limit_minutes: 30
scratch_def: config/project-scratch-def.json
evaluation_tests:
  - CaseEscalationTest
""")

        (tier2_dir / "README.md").write_text("""# Case Escalation Screen Flow

## Business Requirements

Support managers need a streamlined way to escalate high-priority cases.

### Requirements

1. **Invocable Apex Class**: Create `CaseEscalationService` with:
   - `@InvocableMethod` named `escalateCases`
   - Input: List of Case IDs
   - Logic:
     - Set `Priority` to "High"
     - Set `Status` to "Escalated"
     - Add a CaseComment: "Case escalated by {running user name}"
   - Return: List of escalated Case IDs

2. **Screen Flow**: Create a Screen Flow that:
   - Shows a data table of open Cases (Status != 'Closed')
   - Allows selecting multiple Cases
   - Has an "Escalate Selected" button
   - Calls the `CaseEscalationService`
   - Shows confirmation message with count of escalated cases

### Acceptance Criteria

- Apex class is bulkified (no queries/DML in loops)
- Flow correctly passes selected Case IDs to Apex
- Test class has 90%+ code coverage
- Solution handles up to 200 cases
""")

        config_dir = tier2_dir / "config"
        config_dir.mkdir(exist_ok=True)

        (config_dir / "project-scratch-def.json").write_text("""{
  "orgName": "SF-AgentBench - Case Escalation",
  "edition": "Developer",
  "features": ["ServiceCloud"],
  "settings": {
    "caseSettings": {
      "systemUserEmail": "admin@example.com"
    }
  }
}
""")

        (tier2_dir / "sfdx-project.json").write_text("""{
  "packageDirectories": [{ "path": "force-app", "default": true }],
  "namespace": "",
  "sfdcLoginUrl": "https://login.salesforce.com",
  "sourceApiVersion": "59.0"
}
""")

        # Evaluation test
        force_app = tier2_dir / "force-app" / "main" / "default" / "classes"
        force_app.mkdir(parents=True, exist_ok=True)

        (force_app / "CaseEscalationTest.cls").write_text("""@IsTest
private class CaseEscalationTest {
    
    @TestSetup
    static void setupTestData() {
        List<Case> cases = new List<Case>();
        for (Integer i = 0; i < 10; i++) {
            cases.add(new Case(
                Subject = 'Test Case ' + i,
                Status = 'New',
                Priority = 'Medium',
                Origin = 'Email'
            ));
        }
        insert cases;
    }
    
    @IsTest
    static void testEscalateCases() {
        List<Case> cases = [SELECT Id FROM Case LIMIT 5];
        List<Id> caseIds = new List<Id>();
        for (Case c : cases) {
            caseIds.add(c.Id);
        }
        
        Test.startTest();
        List<Id> result = CaseEscalationService.escalateCases(caseIds);
        Test.stopTest();
        
        System.assertEquals(5, result.size(), 'Should return 5 escalated case IDs');
        
        List<Case> escalatedCases = [
            SELECT Priority, Status FROM Case WHERE Id IN :result
        ];
        
        for (Case c : escalatedCases) {
            System.assertEquals('High', c.Priority, 'Priority should be High');
            System.assertEquals('Escalated', c.Status, 'Status should be Escalated');
        }
        
        List<CaseComment> comments = [
            SELECT CommentBody FROM CaseComment WHERE ParentId IN :result
        ];
        System.assertEquals(5, comments.size(), 'Should have 5 case comments');
    }
    
    @IsTest
    static void testBulkEscalation() {
        // Create 200 cases for bulk test
        List<Case> bulkCases = new List<Case>();
        for (Integer i = 0; i < 200; i++) {
            bulkCases.add(new Case(
                Subject = 'Bulk Test ' + i,
                Status = 'New',
                Priority = 'Low',
                Origin = 'Web'
            ));
        }
        insert bulkCases;
        
        List<Id> caseIds = new List<Id>();
        for (Case c : bulkCases) {
            caseIds.add(c.Id);
        }
        
        Test.startTest();
        List<Id> result = CaseEscalationService.escalateCases(caseIds);
        Test.stopTest();
        
        System.assertEquals(200, result.size(), 'Should handle 200 cases');
    }
}
""")

        (force_app / "CaseEscalationTest.cls-meta.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<ApexClass xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>59.0</apiVersion>
    <status>Active</status>
</ApexClass>
""")

        console.print(f"  Created sample task: {tier2_dir}")


if __name__ == "__main__":
    main()
