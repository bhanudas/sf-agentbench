"""Reporting module for SF-AgentBench.

Provides report generation with rubric drill-down and comparisons.
"""

from sf_agentbench.reports.generator import ReportGenerator, ReportFormat
from sf_agentbench.reports.comparison import ModelComparison

__all__ = [
    "ReportGenerator",
    "ReportFormat",
    "ModelComparison",
]
