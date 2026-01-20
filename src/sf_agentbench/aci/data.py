"""Data operation ACI tools."""

from pathlib import Path
from typing import Any

from sf_agentbench.aci.base import ACITool, ACIToolResult


class SFQuery(ACITool):
    """Execute a SOQL query."""

    name = "sf_query"
    description = (
        "Executes a SOQL query against the target org and returns the results. "
        "Use this to verify data state or retrieve record information."
    )

    def execute(
        self,
        query: str,
        use_tooling_api: bool = False,
        **kwargs: Any,
    ) -> ACIToolResult:
        """
        Execute a SOQL query.

        Args:
            query: SOQL query string
            use_tooling_api: Use Tooling API instead of standard API

        Returns:
            ACIToolResult with query results
        """
        args = ["data", "query", "--query", query]

        if use_tooling_api:
            args.append("--use-tooling-api")

        result = self._run_sf_command(args)

        if result.success and result.data:
            records = result.data.get("records", [])
            total_size = result.data.get("totalSize", len(records))

            # Clean up records (remove attributes)
            cleaned_records = []
            for record in records:
                cleaned = {k: v for k, v in record.items() if k != "attributes"}
                cleaned_records.append(cleaned)

            result.data = {
                "total_size": total_size,
                "done": result.data.get("done", True),
                "records": cleaned_records,
            }

        return result

    def _get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SOQL query to execute",
                },
                "use_tooling_api": {
                    "type": "boolean",
                    "description": "Use Tooling API",
                    "default": False,
                },
            },
            "required": ["query"],
        }


class SFCreateRecord(ACITool):
    """Create a single record."""

    name = "sf_create_record"
    description = (
        "Creates a single record of the specified sObject type. "
        "Returns the ID of the created record."
    )

    def execute(
        self,
        sobject: str,
        values: dict[str, Any],
        **kwargs: Any,
    ) -> ACIToolResult:
        """
        Create a record.

        Args:
            sobject: sObject API name (e.g., "Account", "Contact")
            values: Field values as key-value pairs

        Returns:
            ACIToolResult with created record ID
        """
        # Build values string: "Name='Test' Industry='Tech'"
        values_str = " ".join(f"{k}='{v}'" for k, v in values.items())

        args = [
            "data",
            "create",
            "record",
            "--sobject",
            sobject,
            "--values",
            values_str,
        ]

        result = self._run_sf_command(args)

        if result.success and result.data:
            result.data = {
                "id": result.data.get("id"),
                "success": True,
                "sobject": sobject,
            }

        return result

    def _get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sobject": {
                    "type": "string",
                    "description": "sObject API name (e.g., Account, Contact)",
                },
                "values": {
                    "type": "object",
                    "description": "Field values as key-value pairs",
                    "additionalProperties": True,
                },
            },
            "required": ["sobject", "values"],
        }


class SFImportData(ACITool):
    """Import data from a plan file."""

    name = "sf_import_data"
    description = (
        "Imports data from JSON files using a data plan. "
        "Preserves relationships between records via reference IDs."
    )

    def execute(
        self,
        plan: str | None = None,
        files: list[str] | None = None,
        **kwargs: Any,
    ) -> ACIToolResult:
        """
        Import data using sf data tree import.

        Args:
            plan: Path to data plan JSON file
            files: List of data files to import

        Returns:
            ACIToolResult with import results
        """
        if not plan and not files:
            return ACIToolResult(
                success=False,
                errors=[{"message": "Either plan or files must be provided"}],
            )

        args = ["data", "import", "tree"]

        if plan:
            args.extend(["--plan", plan])
        elif files:
            args.extend(["--files", ",".join(files)])

        result = self._run_sf_command(args)

        if result.success and result.data:
            # Parse import results
            imported = result.data if isinstance(result.data, list) else [result.data]
            result.data = {
                "status": "success",
                "imported_count": len(imported),
                "records": [
                    {
                        "reference_id": r.get("refId"),
                        "id": r.get("id"),
                        "sobject": r.get("type"),
                    }
                    for r in imported
                    if isinstance(r, dict)
                ],
            }

        return result

    def _get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "plan": {
                    "type": "string",
                    "description": "Path to data plan JSON file",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of data files to import",
                },
            },
        }
