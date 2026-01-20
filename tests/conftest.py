"""Pytest configuration and fixtures for SF-AgentBench tests."""

import pytest
from pathlib import Path

from sf_agentbench.config import BenchmarkConfig
from sf_agentbench.models import Task, TaskTier


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary SFDX project structure."""
    # Create basic structure
    force_app = tmp_path / "force-app" / "main" / "default"
    force_app.mkdir(parents=True)

    # Create sfdx-project.json
    (tmp_path / "sfdx-project.json").write_text("""
{
  "packageDirectories": [{"path": "force-app", "default": true}],
  "namespace": "",
  "sourceApiVersion": "59.0"
}
""")

    # Create scratch org definition
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "project-scratch-def.json").write_text("""
{
  "orgName": "Test Org",
  "edition": "Developer"
}
""")

    return tmp_path


@pytest.fixture
def sample_task(tmp_path):
    """Create a sample task for testing."""
    task_dir = tmp_path / "tasks" / "test-task"
    task_dir.mkdir(parents=True)

    # Create task.yaml
    (task_dir / "task.yaml").write_text("""
id: test-task
name: Test Task
description: A sample test task
tier: tier-1
categories:
  - apex-class
time_limit_minutes: 15
""")

    # Create README
    (task_dir / "README.md").write_text("""
# Test Task

This is a test task for testing purposes.
""")

    # Create basic force-app structure
    force_app = task_dir / "force-app" / "main" / "default" / "classes"
    force_app.mkdir(parents=True)

    (force_app / "TestClass.cls").write_text("""
public class TestClass {
    public String getMessage() {
        return 'Hello, World!';
    }
}
""")

    (force_app / "TestClass.cls-meta.xml").write_text("""
<?xml version="1.0" encoding="UTF-8"?>
<ApexClass xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>59.0</apiVersion>
    <status>Active</status>
</ApexClass>
""")

    return Task(
        id="test-task",
        name="Test Task",
        description="A sample test task",
        tier=TaskTier.TIER_1,
        path=task_dir,
    )


@pytest.fixture
def default_config(tmp_path):
    """Create a default configuration for testing."""
    config = BenchmarkConfig(
        tasks_dir=tmp_path / "tasks",
        results_dir=tmp_path / "results",
        logs_dir=tmp_path / "logs",
        cleanup_orgs=True,
    )

    # Create directories
    config.tasks_dir.mkdir(parents=True, exist_ok=True)
    config.results_dir.mkdir(parents=True, exist_ok=True)
    config.logs_dir.mkdir(parents=True, exist_ok=True)

    return config
