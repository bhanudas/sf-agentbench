"""Apex execution ACI tools."""

from pathlib import Path
from typing import Any

from sf_agentbench.aci.base import ACITool, ACIToolResult


class SFRunApexTests(ACITool):
    """Run Apex test classes."""

    name = "sf_run_apex_tests"
    description = (
        "Executes Apex test classes in the target org and returns pass/fail results "
        "with code coverage information. Use this to validate business logic."
    )

    def execute(
        self,
        test_classes: list[str] | None = None,
        test_level: str = "RunLocalTests",
        code_coverage: bool = True,
        wait_minutes: int = 10,
        **kwargs: Any,
    ) -> ACIToolResult:
        """
        Run Apex tests.

        Args:
            test_classes: Specific test classes to run (optional)
            test_level: RunSpecifiedTests, RunLocalTests, RunAllTestsInOrg
            code_coverage: Whether to include code coverage (default: True)
            wait_minutes: Minutes to wait for tests

        Returns:
            ACIToolResult with test results and coverage
        """
        args = [
            "apex",
            "run",
            "test",
            "--wait",
            str(wait_minutes),
            "--result-format",
            "json",
        ]

        if test_classes:
            args.extend(["--tests", ",".join(test_classes)])
            args.extend(["--test-level", "RunSpecifiedTests"])
        else:
            args.extend(["--test-level", test_level])

        if code_coverage:
            args.append("--code-coverage")

        result = self._run_sf_command(args)

        if result.data:
            summary = result.data.get("summary", {})
            tests = result.data.get("tests", [])
            coverage = result.data.get("coverage", {})

            # Calculate pass rate
            total = summary.get("testsRan", 0)
            passed = summary.get("passing", 0)
            failed = summary.get("failing", 0)
            skipped = summary.get("skipped", 0)
            pass_rate = (passed / total) if total > 0 else 0.0

            # Calculate overall coverage
            coverage_records = coverage.get("coverage", [])
            total_lines = sum(c.get("totalLines", 0) for c in coverage_records)
            covered_lines = sum(c.get("coveredLines", 0) for c in coverage_records)
            overall_coverage = (covered_lines / total_lines * 100) if total_lines > 0 else 0.0

            result.data = {
                "status": "success" if result.success else "failure",
                "total_tests": total,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "pass_rate": pass_rate,
                "code_coverage_percent": round(overall_coverage, 2),
                "test_results": [
                    {
                        "class_name": t.get("ApexClass", {}).get("Name", "Unknown"),
                        "method_name": t.get("MethodName", "Unknown"),
                        "status": t.get("Outcome", "Unknown").lower(),
                        "message": t.get("Message"),
                        "stack_trace": t.get("StackTrace"),
                        "duration_ms": t.get("RunTime", 0),
                    }
                    for t in tests
                ],
                "coverage_by_class": [
                    {
                        "class_name": c.get("name", "Unknown"),
                        "coverage_percent": round(
                            (c.get("coveredLines", 0) / c.get("totalLines", 1)) * 100, 2
                        ),
                    }
                    for c in coverage_records
                    if c.get("totalLines", 0) > 0
                ],
            }

        return result

    def _get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "test_classes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific test classes to run",
                },
                "test_level": {
                    "type": "string",
                    "description": "Test level to run",
                    "enum": ["RunSpecifiedTests", "RunLocalTests", "RunAllTestsInOrg"],
                    "default": "RunLocalTests",
                },
                "code_coverage": {
                    "type": "boolean",
                    "description": "Include code coverage results",
                    "default": True,
                },
                "wait_minutes": {
                    "type": "integer",
                    "description": "Minutes to wait for tests",
                    "default": 10,
                },
            },
        }


class SFRunAnonymous(ACITool):
    """Execute anonymous Apex code."""

    name = "sf_run_anonymous"
    description = (
        "Executes anonymous Apex code in the target org. "
        "Useful for quick validation, data manipulation, or debugging."
    )

    def execute(
        self,
        apex_code: str | None = None,
        apex_file: str | None = None,
        **kwargs: Any,
    ) -> ACIToolResult:
        """
        Execute anonymous Apex.

        Args:
            apex_code: Apex code to execute as a string
            apex_file: Path to file containing Apex code

        Returns:
            ACIToolResult with execution result
        """
        if not apex_code and not apex_file:
            return ACIToolResult(
                success=False,
                errors=[{"message": "Either apex_code or apex_file must be provided"}],
            )

        args = ["apex", "run"]

        if apex_file:
            args.extend(["--file", apex_file])
        else:
            # Write code to temp file for execution
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", suffix=".apex", delete=False) as f:
                f.write(apex_code)
                temp_path = f.name
            args.extend(["--file", temp_path])

        result = self._run_sf_command(args)

        if result.data:
            compiled = result.data.get("compiled", False)
            success = result.data.get("success", False)
            logs = result.data.get("logs", "")

            result.data = {
                "compiled": compiled,
                "executed": success,
                "logs": logs,
            }

            if not compiled:
                result.errors.append({
                    "type": "compilation_error",
                    "message": result.data.get("compileProblem", "Unknown compilation error"),
                    "line": result.data.get("line"),
                    "column": result.data.get("column"),
                })
            elif not success:
                result.errors.append({
                    "type": "execution_error",
                    "message": result.data.get("exceptionMessage", "Unknown execution error"),
                    "stack_trace": result.data.get("exceptionStackTrace"),
                })

        return result

    def _get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "apex_code": {
                    "type": "string",
                    "description": "Apex code to execute",
                },
                "apex_file": {
                    "type": "string",
                    "description": "Path to file containing Apex code",
                },
            },
            "oneOf": [
                {"required": ["apex_code"]},
                {"required": ["apex_file"]},
            ],
        }
