"""Logging configuration for SF-AgentBench."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class BenchmarkLogger:
    """Centralized logging for benchmark runs."""

    def __init__(
        self,
        logs_dir: Path,
        run_id: Optional[str] = None,
        verbose: bool = False,
    ):
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.verbose = verbose
        
        # Create run-specific log file
        self.log_file = self.logs_dir / f"run_{self.run_id}.log"
        
        # Set up logging
        self.logger = logging.getLogger(f"sf-agentbench-{self.run_id}")
        self.logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        
        # Clear existing handlers
        self.logger.handlers = []
        
        # File handler - always log everything to file
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Console handler - only if verbose
        if verbose:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)
            console_formatter = logging.Formatter('%(levelname)-8s | %(message)s')
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

    def info(self, message: str) -> None:
        """Log info message."""
        self.logger.info(message)

    def debug(self, message: str) -> None:
        """Log debug message."""
        self.logger.debug(message)

    def warning(self, message: str) -> None:
        """Log warning message."""
        self.logger.warning(message)

    def error(self, message: str) -> None:
        """Log error message."""
        self.logger.error(message)

    def section(self, title: str) -> None:
        """Log a section header."""
        self.logger.info("=" * 60)
        self.logger.info(title)
        self.logger.info("=" * 60)

    def task_start(self, task_id: str, task_name: str, tier: str) -> None:
        """Log task start."""
        self.section(f"TASK: {task_name}")
        self.info(f"Task ID: {task_id}")
        self.info(f"Tier: {tier}")

    def task_end(self, task_id: str, score: float, duration: float) -> None:
        """Log task end."""
        self.info(f"Task {task_id} completed")
        self.info(f"Final Score: {score:.2f} ({score*100:.0f}%)")
        self.info(f"Duration: {duration:.1f}s")
        self.info("-" * 60)

    def org_created(self, username: str, org_id: str) -> None:
        """Log org creation."""
        self.info(f"Scratch org created: {username}")
        self.debug(f"Org ID: {org_id}")

    def org_deleted(self, username: str) -> None:
        """Log org deletion."""
        self.info(f"Scratch org deleted: {username}")

    def deployment(self, success: bool, component_count: int = 0, errors: list = None) -> None:
        """Log deployment result."""
        if success:
            self.info(f"Deployment successful: {component_count} components")
        else:
            self.error(f"Deployment failed with {len(errors or [])} errors")
            for err in (errors or [])[:5]:
                self.debug(f"  - {err}")

    def tests(self, passed: int, total: int, coverage: float = 0) -> None:
        """Log test results."""
        self.info(f"Tests: {passed}/{total} passed ({passed/total*100:.0f}%)")
        if coverage > 0:
            self.debug(f"Code coverage: {coverage:.0f}%")

    def evaluation_layer(self, layer: str, score: float, details: str = "") -> None:
        """Log evaluation layer result."""
        self.info(f"Layer {layer}: {score:.2f}")
        if details:
            self.debug(f"  {details}")

    def evaluation_complete(self, scores: dict, final_score: float) -> None:
        """Log final evaluation results."""
        self.section("EVALUATION COMPLETE")
        for layer, score in scores.items():
            self.info(f"  {layer}: {score:.2f}")
        self.info("-" * 40)
        self.info(f"  FINAL SCORE: {final_score:.2f} ({final_score*100:.0f}%)")

    def sf_command(self, command: str, success: bool, output: str = "") -> None:
        """Log Salesforce CLI command execution."""
        status = "SUCCESS" if success else "FAILED"
        self.debug(f"SF CLI [{status}]: {command}")
        if not success and output:
            self.debug(f"  Output: {output[:500]}")

    def get_log_path(self) -> Path:
        """Get the path to the current log file."""
        return self.log_file


# Global logger instance
_logger: Optional[BenchmarkLogger] = None


def get_logger() -> Optional[BenchmarkLogger]:
    """Get the global logger instance."""
    return _logger


def init_logger(logs_dir: Path, run_id: str = None, verbose: bool = False) -> BenchmarkLogger:
    """Initialize and return a new logger."""
    global _logger
    _logger = BenchmarkLogger(logs_dir, run_id, verbose)
    return _logger
