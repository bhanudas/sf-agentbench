"""Layer 4: Metadata Configuration Diffing Evaluator."""

from pathlib import Path
from typing import Any

from deepdiff import DeepDiff
from lxml import etree
from rich.console import Console

from sf_agentbench.aci import SFRetrieve
from sf_agentbench.models import MetadataDiffResult, Task

console = Console()


class MetadataDiffEvaluator:
    """Evaluates metadata configuration against expected golden state."""

    def __init__(
        self,
        sf_cli_path: str = "sf",
        target_org: str | None = None,
        project_dir: Path | None = None,
        verbose: bool = False,
    ):
        self.sf_cli_path = sf_cli_path
        self.target_org = target_org
        self.project_dir = project_dir
        self.verbose = verbose

    def evaluate(self, task: Task, work_dir: Path) -> tuple[MetadataDiffResult, float]:
        """
        Compare deployed metadata against expected configuration.

        Args:
            task: The benchmark task
            work_dir: Working directory with agent's solution

        Returns:
            Tuple of (MetadataDiffResult, score)
        """
        console.print("  [dim]Layer 4: Metadata Configuration Diff[/dim]")

        if not task.expected_metadata_path or not task.expected_metadata_path.exists():
            console.print("    [dim]No expected metadata defined, skipping[/dim]")
            return MetadataDiffResult(is_match=True, accuracy_score=1.0), 1.0

        # Retrieve current metadata from org
        retriever = SFRetrieve(
            sf_cli_path=self.sf_cli_path,
            target_org=self.target_org,
            project_dir=work_dir,
            verbose=self.verbose,
        )

        retrieved_dir = work_dir / "retrieved"
        retrieved_dir.mkdir(exist_ok=True)

        result = retriever.execute(source_path=str(retrieved_dir))

        if not result.success:
            console.print("    [yellow]Failed to retrieve metadata for comparison[/yellow]")
            return MetadataDiffResult(is_match=False, accuracy_score=0.0), 0.0

        # Compare metadata files
        diff_result = self._compare_metadata(
            expected_path=task.expected_metadata_path,
            actual_path=retrieved_dir,
        )

        if diff_result.is_match:
            console.print("    [green]✓ Metadata matches expected configuration[/green]")
        else:
            console.print(
                f"    [yellow]Metadata differs from expected "
                f"(accuracy: {diff_result.accuracy_score*100:.1f}%)[/yellow]"
            )

            if self.verbose and diff_result.missing_components:
                console.print("      [dim]Missing:[/dim]")
                for comp in diff_result.missing_components[:5]:
                    console.print(f"        - {comp}")

        return diff_result, diff_result.accuracy_score

    def _compare_metadata(
        self, expected_path: Path, actual_path: Path
    ) -> MetadataDiffResult:
        """Compare expected and actual metadata directories."""
        missing = []
        extra = []
        differences: dict[str, Any] = {}

        # Get all expected metadata files
        expected_files = self._get_metadata_files(expected_path)
        actual_files = self._get_metadata_files(actual_path)

        expected_names = set(expected_files.keys())
        actual_names = set(actual_files.keys())

        # Find missing and extra
        missing = list(expected_names - actual_names)
        extra = list(actual_names - expected_names)

        # Compare common files
        common = expected_names & actual_names
        match_count = 0

        for name in common:
            expected_file = expected_files[name]
            actual_file = actual_files[name]

            if self._compare_xml_files(expected_file, actual_file):
                match_count += 1
            else:
                diff = self._get_xml_diff(expected_file, actual_file)
                if diff:
                    differences[name] = diff

        # Calculate accuracy
        total_expected = len(expected_names)
        if total_expected == 0:
            accuracy = 1.0
        else:
            accuracy = match_count / total_expected

        is_match = len(missing) == 0 and len(differences) == 0

        return MetadataDiffResult(
            is_match=is_match,
            accuracy_score=accuracy,
            missing_components=missing,
            extra_components=extra,
            differences=differences,
        )

    def _get_metadata_files(self, path: Path) -> dict[str, Path]:
        """Get all metadata XML files from a path."""
        files = {}
        if path.is_file():
            files[path.name] = path
        else:
            for f in path.rglob("*-meta.xml"):
                relative = f.relative_to(path)
                files[str(relative)] = f
            for f in path.rglob("*.xml"):
                if "-meta.xml" not in f.name:
                    relative = f.relative_to(path)
                    files[str(relative)] = f
        return files

    def _compare_xml_files(self, expected: Path, actual: Path) -> bool:
        """Compare two XML files semantically."""
        try:
            expected_tree = etree.parse(str(expected))
            actual_tree = etree.parse(str(actual))

            # Normalize and compare
            expected_str = etree.tostring(
                expected_tree, pretty_print=True, encoding="unicode"
            )
            actual_str = etree.tostring(
                actual_tree, pretty_print=True, encoding="unicode"
            )

            # Remove whitespace differences
            expected_normalized = self._normalize_xml(expected_str)
            actual_normalized = self._normalize_xml(actual_str)

            return expected_normalized == actual_normalized

        except Exception:
            # Fall back to text comparison
            return expected.read_text() == actual.read_text()

    def _normalize_xml(self, xml_str: str) -> str:
        """Normalize XML string for comparison."""
        # Remove xmlns declarations (they often vary)
        import re
        normalized = re.sub(r'\s*xmlns[^"]*"[^"]*"', "", xml_str)
        # Normalize whitespace
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _get_xml_diff(self, expected: Path, actual: Path) -> dict[str, Any]:
        """Get differences between two XML files."""
        try:
            expected_dict = self._xml_to_dict(expected)
            actual_dict = self._xml_to_dict(actual)

            diff = DeepDiff(expected_dict, actual_dict, ignore_order=True)
            return dict(diff) if diff else {}

        except Exception as e:
            return {"error": str(e)}

    def _xml_to_dict(self, path: Path) -> dict[str, Any]:
        """Convert XML file to dictionary for comparison."""
        tree = etree.parse(str(path))
        root = tree.getroot()
        return self._element_to_dict(root)

    def _element_to_dict(self, element: Any) -> dict[str, Any]:
        """Convert lxml element to dictionary."""
        result: dict[str, Any] = {}

        # Get tag without namespace
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
        result["_tag"] = tag

        # Add attributes
        if element.attrib:
            result["_attrs"] = dict(element.attrib)

        # Add text content
        if element.text and element.text.strip():
            result["_text"] = element.text.strip()

        # Add children
        children: dict[str, Any] = {}
        for child in element:
            child_dict = self._element_to_dict(child)
            child_tag = child_dict["_tag"]

            if child_tag in children:
                if not isinstance(children[child_tag], list):
                    children[child_tag] = [children[child_tag]]
                children[child_tag].append(child_dict)
            else:
                children[child_tag] = child_dict

        if children:
            result["_children"] = children

        return result
