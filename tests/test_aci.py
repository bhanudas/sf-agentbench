"""Tests for Agent-Computer Interface (ACI) tools."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from sf_agentbench.aci.base import ACITool, ACIToolResult
from sf_agentbench.aci.deploy import SFDeploy, SFRetrieve
from sf_agentbench.aci.apex import SFRunApexTests, SFRunAnonymous
from sf_agentbench.aci.data import SFQuery, SFCreateRecord, SFImportData
from sf_agentbench.aci.analysis import SFScanCode
from sf_agentbench.aci.org import SFOrgCreate, SFOrgDelete, SFOrgOpen


class TestACIToolResult:
    """Tests for ACIToolResult."""

    def test_success_result(self):
        """Test successful result."""
        result = ACIToolResult(
            success=True,
            data={"count": 10},
        )

        assert result.success
        assert result.data["count"] == 10
        assert len(result.errors) == 0

    def test_failure_result(self):
        """Test failure result."""
        result = ACIToolResult(
            success=False,
            errors=[{"message": "Deployment failed"}],
            exit_code=1,
        )

        assert not result.success
        assert len(result.errors) == 1
        assert result.exit_code == 1

    def test_to_json(self):
        """Test JSON conversion."""
        result = ACIToolResult(
            success=True,
            data={"test": "value"},
        )

        json_str = result.to_json()
        assert '"success": true' in json_str
        assert '"test": "value"' in json_str


class TestSFDeploy:
    """Tests for SFDeploy tool."""

    def test_tool_metadata(self):
        """Test tool metadata."""
        tool = SFDeploy()

        assert tool.name == "sf_deploy"
        assert "deploy" in tool.description.lower()

    def test_parameters_schema(self):
        """Test parameters schema."""
        tool = SFDeploy()
        schema = tool._get_parameters_schema()

        assert "properties" in schema
        assert "source_path" in schema["properties"]
        assert "wait_minutes" in schema["properties"]

    @patch("subprocess.run")
    def test_execute_success(self, mock_run):
        """Test successful deployment."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"status": 0, "result": {"files": [{"type": "ApexClass", "fullName": "Test"}]}}',
            stderr="",
        )

        tool = SFDeploy(target_org="test@org.com")
        result = tool.execute(source_path="force-app")

        assert result.success
        assert mock_run.called


class TestSFRunApexTests:
    """Tests for SFRunApexTests tool."""

    def test_tool_metadata(self):
        """Test tool metadata."""
        tool = SFRunApexTests()

        assert tool.name == "sf_run_apex_tests"
        assert "test" in tool.description.lower()

    def test_parameters_schema(self):
        """Test parameters schema."""
        tool = SFRunApexTests()
        schema = tool._get_parameters_schema()

        assert "test_classes" in schema["properties"]
        assert "test_level" in schema["properties"]
        assert "code_coverage" in schema["properties"]


class TestSFQuery:
    """Tests for SFQuery tool."""

    def test_tool_metadata(self):
        """Test tool metadata."""
        tool = SFQuery()

        assert tool.name == "sf_query"
        assert "query" in tool.description.lower()

    def test_parameters_schema(self):
        """Test parameters schema."""
        tool = SFQuery()
        schema = tool._get_parameters_schema()

        assert "query" in schema["properties"]
        assert "query" in schema["required"]


class TestSFScanCode:
    """Tests for SFScanCode tool."""

    def test_tool_metadata(self):
        """Test tool metadata."""
        tool = SFScanCode()

        assert tool.name == "sf_scan_code"
        assert "analysis" in tool.description.lower() or "pmd" in tool.description.lower()

    def test_severity_mapping(self):
        """Test severity number to string mapping."""
        tool = SFScanCode()

        assert tool._map_severity(1) == "critical"
        assert tool._map_severity(2) == "high"
        assert tool._map_severity(3) == "medium"
        assert tool._map_severity(4) == "low"
        assert tool._map_severity(5) == "low"

    def test_penalty_calculation(self):
        """Test penalty score calculation."""
        tool = SFScanCode()

        counts = {"critical": 1, "high": 2, "medium": 5, "low": 10}
        penalty = tool._calculate_penalty(counts)

        # 1*3 + 2*2 + 5*1 + 10*0.5 = 3 + 4 + 5 + 5 = 17 * 0.01 = 0.17
        # But capped at max_penalty (0.10)
        assert penalty == 0.10


class TestSFOrgCreate:
    """Tests for SFOrgCreate tool."""

    def test_tool_metadata(self):
        """Test tool metadata."""
        tool = SFOrgCreate()

        assert tool.name == "sf_org_create"
        assert "scratch" in tool.description.lower()

    def test_parameters_schema(self):
        """Test parameters schema."""
        tool = SFOrgCreate()
        schema = tool._get_parameters_schema()

        assert "definition_file" in schema["properties"]
        assert "alias" in schema["properties"]
        assert "duration_days" in schema["properties"]
