"""Tests for SF-AgentBench configuration."""

import pytest
from pathlib import Path

from sf_agentbench.config import (
    BenchmarkConfig,
    ScratchOrgConfig,
    EvaluationWeights,
    PMDConfig,
    RubricConfig,
    load_config,
)


class TestEvaluationWeights:
    """Tests for EvaluationWeights configuration."""

    def test_default_weights_sum_to_one(self):
        """Test that default weights sum to 1.0."""
        weights = EvaluationWeights()
        assert weights.validate_sum()

    def test_custom_weights_validation(self):
        """Test weight validation."""
        # Valid weights
        weights = EvaluationWeights(
            deployment=0.3,
            functional_tests=0.3,
            static_analysis=0.2,
            metadata_diff=0.1,
            rubric=0.1,
        )
        assert weights.validate_sum()

        # Invalid weights
        weights = EvaluationWeights(
            deployment=0.5,
            functional_tests=0.5,
            static_analysis=0.5,
            metadata_diff=0.5,
            rubric=0.5,
        )
        assert not weights.validate_sum()


class TestBenchmarkConfig:
    """Tests for BenchmarkConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = BenchmarkConfig.default()

        assert config.tasks_dir == Path("tasks")
        assert config.results_dir == Path("results")
        assert config.sf_cli_path == "sf"
        assert config.parallel_runs == 1
        assert config.cleanup_orgs is True

    def test_config_to_yaml(self, tmp_path):
        """Test saving config to YAML."""
        config = BenchmarkConfig.default()
        yaml_path = tmp_path / "config.yaml"

        config.to_yaml(yaml_path)

        assert yaml_path.exists()
        content = yaml_path.read_text()
        assert "tasks_dir" in content
        assert "evaluation_weights" in content

    def test_config_from_yaml(self, tmp_path):
        """Test loading config from YAML."""
        yaml_content = """
tasks_dir: custom_tasks
results_dir: custom_results
verbose: true
parallel_runs: 3
"""
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text(yaml_content)

        config = BenchmarkConfig.from_yaml(yaml_path)

        assert config.tasks_dir == Path("custom_tasks")
        assert config.results_dir == Path("custom_results")
        assert config.verbose is True
        assert config.parallel_runs == 3


class TestScratchOrgConfig:
    """Tests for ScratchOrgConfig."""

    def test_default_scratch_org_config(self):
        """Test default scratch org config."""
        config = ScratchOrgConfig()

        assert config.default_duration_days == 1
        assert config.edition == "Developer"
        assert config.wait_minutes == 10
        assert config.use_snapshots is False


class TestPMDConfig:
    """Tests for PMDConfig."""

    def test_default_pmd_config(self):
        """Test default PMD config."""
        config = PMDConfig()

        assert config.enabled is True
        assert config.max_penalty == 0.10
        assert config.critical_weight == 3.0


class TestRubricConfig:
    """Tests for RubricConfig."""

    def test_default_rubric_config(self):
        """Test default rubric config."""
        config = RubricConfig()

        assert config.enabled is True
        assert config.temperature == 0.0
        assert config.num_evaluations == 1


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_default(self):
        """Test loading default config when no file exists."""
        config = load_config(None)

        assert config is not None
        assert isinstance(config, BenchmarkConfig)

    def test_load_config_from_path(self, tmp_path):
        """Test loading config from specific path."""
        yaml_content = """
tasks_dir: my_tasks
verbose: true
"""
        config_path = tmp_path / "my-config.yaml"
        config_path.write_text(yaml_content)

        config = load_config(config_path)

        assert config.tasks_dir == Path("my_tasks")
        assert config.verbose is True
