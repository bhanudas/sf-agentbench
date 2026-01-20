"""Command-line interface for SF-AgentBench."""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from sf_agentbench import __version__
from sf_agentbench.config import BenchmarkConfig, load_config
from sf_agentbench.harness import BenchmarkHarness, TaskLoader
from sf_agentbench.models import TaskTier

console = Console()


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
    console.print(f"\n[bold]Tier:[/bold] {task.tier.value}")
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
