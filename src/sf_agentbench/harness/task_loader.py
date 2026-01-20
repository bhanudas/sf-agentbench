"""Task loading and discovery."""

from pathlib import Path
from typing import Iterator

import yaml

from sf_agentbench.models import Task, TaskTier, TaskCategory


class TaskLoader:
    """Loads and manages benchmark tasks."""

    def __init__(self, tasks_dir: Path):
        self.tasks_dir = tasks_dir
        self._tasks: dict[str, Task] = {}

    def discover_tasks(self) -> list[Task]:
        """Discover all tasks in the tasks directory."""
        tasks = []

        if not self.tasks_dir.exists():
            return tasks

        # Look for task directories with task.yaml files
        for task_dir in self.tasks_dir.rglob("task.yaml"):
            try:
                task = self._load_task(task_dir)
                tasks.append(task)
                self._tasks[task.id] = task
            except Exception as e:
                print(f"Warning: Failed to load task from {task_dir}: {e}")

        return sorted(tasks, key=lambda t: (t.tier, t.id))

    def _load_task(self, task_yaml_path: Path) -> Task:
        """Load a single task from its YAML definition."""
        task_dir = task_yaml_path.parent

        with open(task_yaml_path) as f:
            data = yaml.safe_load(f)

        # Parse tier
        tier_str = data.get("tier", "tier-1")
        tier = TaskTier(tier_str)

        # Parse categories (handle both valid enum values and unknown strings)
        categories = []
        for c in data.get("categories", []):
            try:
                categories.append(TaskCategory(c))
            except ValueError:
                # Keep as string if not a valid enum value
                pass

        # Resolve paths relative to task directory
        scratch_def = data.get("scratch_def")
        scratch_def_path = task_dir / scratch_def if scratch_def else None

        data_plan = data.get("data_plan")
        data_plan_path = task_dir / data_plan if data_plan else None

        expected_metadata = data.get("expected_metadata")
        expected_metadata_path = task_dir / expected_metadata if expected_metadata else None

        return Task(
            id=data.get("id", task_dir.name),
            name=data.get("name", task_dir.name),
            description=data.get("description", ""),
            tier=tier,
            categories=categories,
            path=task_dir,
            time_limit_minutes=data.get("time_limit_minutes", 30),
            scratch_def_path=scratch_def_path,
            requires_data=data.get("requires_data", False),
            data_plan_path=data_plan_path,
            evaluation_tests=data.get("evaluation_tests", []),
            expected_metadata_path=expected_metadata_path,
        )

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        if task_id in self._tasks:
            return self._tasks[task_id]

        # Try to discover if not loaded
        self.discover_tasks()
        return self._tasks.get(task_id)

    def get_tasks_by_tier(self, tier: TaskTier) -> list[Task]:
        """Get all tasks of a specific tier."""
        if not self._tasks:
            self.discover_tasks()

        return [t for t in self._tasks.values() if t.tier == tier]

    def get_tasks_by_category(self, category: TaskCategory) -> list[Task]:
        """Get all tasks with a specific category."""
        if not self._tasks:
            self.discover_tasks()

        return [t for t in self._tasks.values() if category in t.categories]

    def iter_tasks(self) -> Iterator[Task]:
        """Iterate over all discovered tasks."""
        if not self._tasks:
            self.discover_tasks()

        yield from self._tasks.values()

    def get_task_readme(self, task: Task) -> str:
        """Get the README content for a task."""
        readme_path = task.path / "README.md"
        if readme_path.exists():
            return readme_path.read_text()
        return task.description
