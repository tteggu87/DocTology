from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = (
    ROOT
    / ".agents"
    / "skills"
    / "repo-docs-intelligence-bootstrap"
    / "scripts"
    / "validate_repo_docs_intelligence.py"
)


def load_validator_module():
    spec = importlib.util.spec_from_file_location("repo_docs_validator", VALIDATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_doc(path: Path, title: str, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "status: Active",
                "source_of_truth: No",
                "last_updated: 2026-06-20",
                "superseded_by: N/A",
                "---",
                "",
                f"# {title}",
                "",
                body,
            ]
        ),
        encoding="utf-8",
    )


class RepoDocsIntelligenceValidatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator_module()

    def run_validator(self, repo_root: Path) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR_PATH),
                "--repo-root",
                str(repo_root),
                "--format",
                "json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_repo_map_is_rejected_when_index_links_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_map = root / "docs" / "repo-map"
            write_doc(repo_map / "README.md", "Repo Map", "Only partial map.")
            write_doc(repo_map / "ENTRYPOINTS.md", "Entrypoints")
            write_doc(repo_map / "MODULES.md", "Modules")
            write_doc(repo_map / "DATA_FLOW.md", "Data Flow")
            write_doc(repo_map / "SYMBOL_GRAPH.md", "Symbol Graph")
            write_doc(root / "wiki" / "_meta" / "index.md", "Repo Memory Index", "- `docs/CURRENT_STATE.md`")

            payload = self.run_validator(root)

        codes = {issue["code"] for issue in payload["errors"]}
        self.assertIn("repo_map.readme_missing_link", codes)
        self.assertIn("repo_map.wiki_index_missing", codes)

    def test_repo_map_is_valid_when_required_links_are_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_map = root / "docs" / "repo-map"
            write_doc(
                repo_map / "README.md",
                "Repo Map",
                "\n".join(
                    [
                        "- `docs/repo-map/ENTRYPOINTS.md`",
                        "- `docs/repo-map/MODULES.md`",
                        "- `docs/repo-map/DATA_FLOW.md`",
                        "- `docs/repo-map/SYMBOL_GRAPH.md`",
                    ]
                ),
            )
            write_doc(repo_map / "ENTRYPOINTS.md", "Entrypoints")
            write_doc(repo_map / "MODULES.md", "Modules")
            write_doc(repo_map / "DATA_FLOW.md", "Data Flow")
            write_doc(repo_map / "SYMBOL_GRAPH.md", "Symbol Graph")
            write_doc(
                root / "wiki" / "_meta" / "index.md",
                "Repo Memory Index",
                "- `docs/repo-map/README.md`",
            )

            report = self.validator.ValidationReport(root)
            self.validator.validate_repo_map(root, report)

        self.assertEqual(report.errors, [])


if __name__ == "__main__":
    unittest.main()
