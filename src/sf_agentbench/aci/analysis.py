"""Static analysis ACI tools."""

from pathlib import Path
from typing import Any

from sf_agentbench.aci.base import ACITool, ACIToolResult


class SFScanCode(ACITool):
    """Run static code analysis using Salesforce Code Analyzer."""

    name = "sf_scan_code"
    description = (
        "Runs static code analysis (PMD) on the codebase to detect code smells, "
        "security vulnerabilities, and performance issues."
    )

    def execute(
        self,
        target: str = "force-app",
        category: str | None = None,
        severity_threshold: int = 1,
        **kwargs: Any,
    ) -> ACIToolResult:
        """
        Run code analysis.

        Args:
            target: Directory or file to scan (default: force-app)
            category: Specific category to scan (e.g., "Security", "Performance")
            severity_threshold: Minimum severity to report (1=critical to 4=low)

        Returns:
            ACIToolResult with violations found
        """
        args = [
            "scanner",
            "run",
            "--target",
            target,
            "--format",
            "json",
        ]

        if category:
            args.extend(["--category", category])

        args.extend(["--severity-threshold", str(severity_threshold)])

        result = self._run_sf_command(args)

        if result.data:
            # Parse violations from scanner output
            violations = []
            severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

            # Scanner returns array of file results
            file_results = result.data if isinstance(result.data, list) else []

            for file_result in file_results:
                file_path = file_result.get("fileName", "Unknown")
                file_violations = file_result.get("violations", [])

                for v in file_violations:
                    severity = self._map_severity(v.get("severity", 3))
                    severity_counts[severity] += 1

                    violations.append({
                        "rule": v.get("ruleName", "Unknown"),
                        "severity": severity,
                        "file": file_path,
                        "line": v.get("line", 0),
                        "column": v.get("column"),
                        "message": v.get("message", ""),
                        "category": v.get("category", ""),
                        "url": v.get("url"),
                    })

            # Calculate penalty score
            penalty = self._calculate_penalty(severity_counts)

            result.data = {
                "total_violations": len(violations),
                "critical_count": severity_counts["critical"],
                "high_count": severity_counts["high"],
                "medium_count": severity_counts["medium"],
                "low_count": severity_counts["low"],
                "penalty_score": round(penalty, 4),
                "violations": violations,
            }
            result.success = True

        return result

    def _map_severity(self, severity_num: int) -> str:
        """Map numeric severity to string."""
        mapping = {1: "critical", 2: "high", 3: "medium", 4: "low", 5: "low"}
        return mapping.get(severity_num, "medium")

    def _calculate_penalty(
        self,
        counts: dict[str, int],
        critical_weight: float = 3.0,
        high_weight: float = 2.0,
        medium_weight: float = 1.0,
        low_weight: float = 0.5,
        max_penalty: float = 0.10,
    ) -> float:
        """Calculate penalty score from violations."""
        raw_penalty = (
            counts["critical"] * critical_weight * 0.01
            + counts["high"] * high_weight * 0.01
            + counts["medium"] * medium_weight * 0.01
            + counts["low"] * low_weight * 0.01
        )
        return min(raw_penalty, max_penalty)

    def _get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Directory or file to scan",
                    "default": "force-app",
                },
                "category": {
                    "type": "string",
                    "description": "Specific category to scan",
                    "enum": [
                        "Best Practices",
                        "Code Style",
                        "Design",
                        "Documentation",
                        "Error Prone",
                        "Performance",
                        "Security",
                    ],
                },
                "severity_threshold": {
                    "type": "integer",
                    "description": "Minimum severity (1=critical to 4=low)",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 4,
                },
            },
        }
