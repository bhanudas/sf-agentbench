"""E2E test runner with prerequisite checks and category-based execution.

Run with: pytest tests/e2e/ -v
Or: sf-agentbench e2e-test
"""

import json
import os
import pytest
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class E2ETestResult:
    """Result from a single E2E test."""
    
    name: str
    category: str
    passed: bool
    duration_seconds: float = 0.0
    error: str | None = None
    details: dict = field(default_factory=dict)


@dataclass
class E2EReport:
    """Complete E2E test report."""
    
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    
    results: list[E2ETestResult] = field(default_factory=list)
    
    @property
    def total(self) -> int:
        return len(self.results)
    
    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)
    
    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)
    
    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0
    
    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "results": [
                {
                    "name": r.name,
                    "category": r.category,
                    "passed": r.passed,
                    "duration_seconds": r.duration_seconds,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


class E2EPrerequisiteError(Exception):
    """Raised when E2E prerequisites are not met."""
    pass


class E2ETestRunner:
    """Orchestrates end-to-end system validation."""
    
    CATEGORIES = ["infrastructure", "executors", "judges", "repl", "integration"]
    
    REQUIRED_PASS_RATES = {
        "infrastructure": 1.0,  # 100%
        "executors": 1.0,
        "judges": 0.95,
        "repl": 1.0,
        "integration": 0.90,
    }
    
    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        results_dir: Path | None = None,
    ):
        """Initialize the E2E test runner.
        
        Args:
            model: Model to use for focused tests
            results_dir: Directory to check for prerequisites
        """
        self.model = model
        self.results_dir = results_dir or Path("results")
        self.report = E2EReport()
    
    def check_prerequisites(self) -> bool:
        """Verify focused tests passed before running E2E.
        
        Returns:
            True if prerequisites are met
        
        Raises:
            E2EPrerequisiteError if prerequisites not met
        """
        # Check for Q&A results
        qa_db = self.results_dir / "qa_results.db"
        if not qa_db.exists():
            raise E2EPrerequisiteError(
                f"No Q&A results found. Run: sf-agentbench qa-run salesforce_admin_test_bank.json -m {self.model} -n 10"
            )
        
        # Check for coding results
        benchmark_db = self.results_dir / "benchmark_results.db"
        # We don't require this for now
        
        return True
    
    def run_category(self, category: str) -> list[E2ETestResult]:
        """Run all tests in a category.
        
        Args:
            category: Category name
        
        Returns:
            List of test results
        """
        results = []
        
        if category == "infrastructure":
            results.extend(self._run_infrastructure_tests())
        elif category == "executors":
            results.extend(self._run_executor_tests())
        elif category == "judges":
            results.extend(self._run_judge_tests())
        elif category == "repl":
            results.extend(self._run_repl_tests())
        elif category == "integration":
            results.extend(self._run_integration_tests())
        
        return results
    
    def run_all(self, skip_prerequisites: bool = False) -> E2EReport:
        """Run all E2E tests in dependency order.
        
        Args:
            skip_prerequisites: Skip prerequisite checks
        
        Returns:
            E2EReport with all results
        """
        if not skip_prerequisites:
            try:
                self.check_prerequisites()
            except E2EPrerequisiteError as e:
                print(f"Warning: {e}")
                print("Continuing anyway...")
        
        for category in self.CATEGORIES:
            results = self.run_category(category)
            self.report.results.extend(results)
        
        self.report.completed_at = datetime.utcnow()
        return self.report
    
    def _run_infrastructure_tests(self) -> list[E2ETestResult]:
        """Run infrastructure tests."""
        results = []
        
        # Test event bus
        results.append(self._test_event_bus())
        
        # Test storage schema
        results.append(self._test_storage_schema())
        
        # Test worker pool (basic)
        results.append(self._test_worker_pool_basic())
        
        return results
    
    def _test_event_bus(self) -> E2ETestResult:
        """Test event bus pub/sub."""
        import time
        start = time.time()
        
        try:
            from sf_agentbench.events import EventBus, LogEvent, LogLevel
            
            bus = EventBus()
            received_events = []
            
            @bus.subscribe(LogEvent)
            def handler(event):
                received_events.append(event)
            
            # Publish events
            bus.publish(LogEvent(level=LogLevel.INFO, source="test", message="test1"))
            bus.publish(LogEvent(level=LogLevel.INFO, source="test", message="test2"))
            
            # Verify
            assert len(received_events) == 2
            assert received_events[0].message == "test1"
            
            return E2ETestResult(
                name="test_event_bus",
                category="infrastructure",
                passed=True,
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return E2ETestResult(
                name="test_event_bus",
                category="infrastructure",
                passed=False,
                duration_seconds=time.time() - start,
                error=str(e),
            )
    
    def _test_storage_schema(self) -> E2ETestResult:
        """Test unified storage schema."""
        import tempfile
        import time
        start = time.time()
        
        try:
            from sf_agentbench.storage.unified import UnifiedStore
            from sf_agentbench.domain.models import Benchmark, Agent
            
            with tempfile.TemporaryDirectory() as tmpdir:
                store = UnifiedStore(Path(tmpdir) / "test.db")
                
                # Create and save benchmark
                benchmark = Benchmark(id="test-1", name="Test Benchmark")
                store.save_benchmark(benchmark)
                
                # Create and save agent
                agent = Agent(id="test-agent", cli_id="test", model="test-model")
                store.save_agent(agent)
                
                # Retrieve
                loaded = store.get_benchmark("test-1")
                assert loaded is not None
                assert loaded.name == "Test Benchmark"
                
                loaded_agent = store.get_agent("test-agent")
                assert loaded_agent is not None
                assert loaded_agent.model == "test-model"
                
                return E2ETestResult(
                    name="test_storage_schema",
                    category="infrastructure",
                    passed=True,
                    duration_seconds=time.time() - start,
                )
        except Exception as e:
            return E2ETestResult(
                name="test_storage_schema",
                category="infrastructure",
                passed=False,
                duration_seconds=time.time() - start,
                error=str(e),
            )
    
    def _test_worker_pool_basic(self) -> E2ETestResult:
        """Test basic worker pool operations."""
        import time
        start = time.time()
        
        try:
            from sf_agentbench.workers import WorkerPool, PoolConfig
            from sf_agentbench.events import EventBus
            
            bus = EventBus()
            pool = WorkerPool(
                config=PoolConfig(max_workers=2),
                event_bus=bus,
            )
            
            # Start and stop
            pool.start()
            assert pool.is_running
            assert pool.worker_count == 2
            
            pool.stop()
            assert not pool.is_running
            
            return E2ETestResult(
                name="test_worker_pool_basic",
                category="infrastructure",
                passed=True,
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return E2ETestResult(
                name="test_worker_pool_basic",
                category="infrastructure",
                passed=False,
                duration_seconds=time.time() - start,
                error=str(e),
            )
    
    def _run_executor_tests(self) -> list[E2ETestResult]:
        """Run executor tests."""
        results = []
        
        # Test QA executor answer extraction
        results.append(self._test_qa_answer_extraction())
        
        return results
    
    def _test_qa_answer_extraction(self) -> E2ETestResult:
        """Test QA executor answer extraction."""
        import time
        start = time.time()
        
        try:
            from sf_agentbench.executors.qa_executor import QAExecutor
            
            executor = QAExecutor()
            
            # Test various response formats
            test_cases = [
                ("A", "A"),
                ("B. Because it's correct", "B"),
                ("The answer is C", "C"),
                ("D\n\nExplanation follows", "D"),
                ("  E  ", "E"),
            ]
            
            for response, expected in test_cases:
                result = executor._extract_answer(response)
                assert result == expected, f"Expected {expected}, got {result} for '{response}'"
            
            return E2ETestResult(
                name="test_qa_answer_extraction",
                category="executors",
                passed=True,
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return E2ETestResult(
                name="test_qa_answer_extraction",
                category="executors",
                passed=False,
                duration_seconds=time.time() - start,
                error=str(e),
            )
    
    def _run_judge_tests(self) -> list[E2ETestResult]:
        """Run judge tests."""
        results = []
        
        # Test rubric loading
        results.append(self._test_rubric_loading())
        
        # Test judge parsing
        results.append(self._test_judge_response_parsing())
        
        return results
    
    def _test_rubric_loading(self) -> E2ETestResult:
        """Test rubric YAML loading."""
        import time
        start = time.time()
        
        try:
            from sf_agentbench.judges.base import Rubric
            
            rubric_path = Path("rubrics/salesforce_best_practices.yaml")
            if rubric_path.exists():
                rubric = Rubric.from_yaml(rubric_path)
                
                assert rubric.name == "Salesforce Best Practices"
                assert len(rubric.criteria) > 0
                
                # Test formatting
                formatted = rubric.format_for_prompt()
                assert "Bulkification" in formatted
            
            return E2ETestResult(
                name="test_rubric_loading",
                category="judges",
                passed=True,
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return E2ETestResult(
                name="test_rubric_loading",
                category="judges",
                passed=False,
                duration_seconds=time.time() - start,
                error=str(e),
            )
    
    def _test_judge_response_parsing(self) -> E2ETestResult:
        """Test judge response JSON parsing."""
        import time
        start = time.time()
        
        try:
            from sf_agentbench.judges.base import Judge, Rubric
            from sf_agentbench.judges.claude_judge import ClaudeJudge
            
            # Mock rubric
            rubric = Rubric(
                name="Test",
                criteria=[
                    {"name": "Quality", "weight": 1.0},
                ],
            )
            
            # Test response parsing
            sample_response = '''
            {
                "criteria": [
                    {"name": "Quality", "score": 0.85, "reasoning": "Good code", "line_refs": [1, 2]}
                ],
                "overall_feedback": "Well done",
                "strengths": ["Clean code"],
                "improvements": ["Add comments"]
            }
            '''
            
            # We need to test the parse_response method without API call
            class MockJudge(ClaudeJudge):
                def __init__(self):
                    # Skip parent init
                    self.model = "test"
                    self.temperature = 0.0
                    self.max_tokens = 1000
                    self.verbose = False
            
            judge = MockJudge()
            result = judge.parse_response(sample_response, rubric)
            
            assert result.parsed_successfully
            assert len(result.criteria) == 1
            assert result.criteria[0].score == 0.85
            
            return E2ETestResult(
                name="test_judge_response_parsing",
                category="judges",
                passed=True,
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return E2ETestResult(
                name="test_judge_response_parsing",
                category="judges",
                passed=False,
                duration_seconds=time.time() - start,
                error=str(e),
            )
    
    def _run_repl_tests(self) -> list[E2ETestResult]:
        """Run REPL tests."""
        results = []
        
        # Test command parsing
        results.append(self._test_command_parsing())
        
        return results
    
    def _test_command_parsing(self) -> E2ETestResult:
        """Test REPL command parsing."""
        import time
        start = time.time()
        
        try:
            from sf_agentbench.repl.commands import CommandParser
            
            parser = CommandParser()
            
            # Test various commands
            test_cases = [
                ("status", "status", [], {}),
                ("logs agent-1", "logs", ["agent-1"], {}),
                ("pause wu-123", "pause", ["wu-123"], {}),
                ("logs --level error", "logs", [], {"level": "error"}),
                ("cancel work-unit-id", "cancel", ["work-unit-id"], {}),
            ]
            
            for input_str, expected_name, expected_args, expected_opts in test_cases:
                cmd = parser.parse(input_str)
                assert cmd.name == expected_name, f"Expected {expected_name}, got {cmd.name}"
                assert cmd.args == expected_args, f"Expected {expected_args}, got {cmd.args}"
            
            return E2ETestResult(
                name="test_command_parsing",
                category="repl",
                passed=True,
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return E2ETestResult(
                name="test_command_parsing",
                category="repl",
                passed=False,
                duration_seconds=time.time() - start,
                error=str(e),
            )
    
    def _run_integration_tests(self) -> list[E2ETestResult]:
        """Run integration tests."""
        results = []
        
        # Test fixture loading
        results.append(self._test_fixture_loading())
        
        return results
    
    def _test_fixture_loading(self) -> E2ETestResult:
        """Test loading test fixtures."""
        import time
        start = time.time()
        
        try:
            fixtures_dir = Path("tests/fixtures")
            
            # Check sample code
            good_apex = fixtures_dir / "sample_code" / "good_apex.cls"
            if good_apex.exists():
                content = good_apex.read_text()
                assert "LeadScoringService" in content
            
            # Check test bank
            test_bank = fixtures_dir / "qa" / "mini_test_bank.json"
            if test_bank.exists():
                data = json.loads(test_bank.read_text())
                assert len(data["questions"]) == 5
            
            return E2ETestResult(
                name="test_fixture_loading",
                category="integration",
                passed=True,
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return E2ETestResult(
                name="test_fixture_loading",
                category="integration",
                passed=False,
                duration_seconds=time.time() - start,
                error=str(e),
            )
    
    def generate_html_report(self, output_path: Path) -> None:
        """Generate an HTML report."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>E2E Test Report</title>
    <style>
        body {{ font-family: system-ui; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
        h1 {{ color: #9b59b6; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; flex: 1; }}
        .stat h2 {{ margin: 0; font-size: 36px; }}
        .stat p {{ margin: 5px 0 0; color: #666; }}
        .passed {{ color: #27ae60; }}
        .failed {{ color: #e74c3c; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f4f4f4; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
        .badge-pass {{ background: #d4edda; color: #155724; }}
        .badge-fail {{ background: #f8d7da; color: #721c24; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 E2E Test Report</h1>
        <p>Generated: {self.report.completed_at or datetime.utcnow()}</p>
        
        <div class="summary">
            <div class="stat">
                <h2>{self.report.total}</h2>
                <p>Total Tests</p>
            </div>
            <div class="stat">
                <h2 class="passed">{self.report.passed}</h2>
                <p>Passed</p>
            </div>
            <div class="stat">
                <h2 class="failed">{self.report.failed}</h2>
                <p>Failed</p>
            </div>
            <div class="stat">
                <h2>{self.report.pass_rate * 100:.0f}%</h2>
                <p>Pass Rate</p>
            </div>
        </div>
        
        <table>
            <tr>
                <th>Test</th>
                <th>Category</th>
                <th>Status</th>
                <th>Duration</th>
            </tr>
"""
        
        for result in self.report.results:
            status_class = "badge-pass" if result.passed else "badge-fail"
            status_text = "PASS" if result.passed else "FAIL"
            
            html += f"""
            <tr>
                <td>{result.name}</td>
                <td>{result.category}</td>
                <td><span class="badge {status_class}">{status_text}</span></td>
                <td>{result.duration_seconds:.3f}s</td>
            </tr>
"""
        
        html += """
        </table>
    </div>
</body>
</html>
"""
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)


# Pytest test functions

@pytest.fixture
def e2e_runner():
    """Create an E2E test runner."""
    return E2ETestRunner()


def test_infrastructure(e2e_runner):
    """Test infrastructure components."""
    results = e2e_runner.run_category("infrastructure")
    assert all(r.passed for r in results), f"Failed: {[r.name for r in results if not r.passed]}"


def test_executors(e2e_runner):
    """Test executor components."""
    results = e2e_runner.run_category("executors")
    assert all(r.passed for r in results), f"Failed: {[r.name for r in results if not r.passed]}"


def test_judges(e2e_runner):
    """Test judge components."""
    results = e2e_runner.run_category("judges")
    passed = sum(1 for r in results if r.passed)
    assert passed / len(results) >= 0.95


def test_repl(e2e_runner):
    """Test REPL components."""
    results = e2e_runner.run_category("repl")
    assert all(r.passed for r in results), f"Failed: {[r.name for r in results if not r.passed]}"


def test_integration(e2e_runner):
    """Test integration components."""
    results = e2e_runner.run_category("integration")
    passed = sum(1 for r in results if r.passed)
    assert passed / len(results) >= 0.90
