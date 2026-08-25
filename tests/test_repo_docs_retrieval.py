from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "repo-docs-intelligence-bootstrap"
CLI = SKILL_ROOT / "scripts" / "repo_docs_retrieval.py"


class RepoDocsRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name) / "repo"
        (self.root / "docs").mkdir(parents=True)
        (self.root / "wiki" / "analyses").mkdir(parents=True)
        (self.root / "AGENTS.md").write_text(
            "# Agents\nUse the [documentation portal](docs/README.md).\n",
            encoding="utf-8",
        )
        (self.root / "docs" / "README.md").write_text(
            "# Documentation Portal\n\nNeedle in the portal.\n"
            "See the [architecture contract](ARCHITECTURE.md).\n",
            encoding="utf-8",
        )
        (self.root / "docs" / "ARCHITECTURE.md").write_text(
            "# Architecture\n\n## Runtime boundary\nCanonical detail.\n"
            "See the [derived analysis](../wiki/analyses/retrieval.md).\n",
            encoding="utf-8",
        )
        (self.root / "wiki" / "analyses" / "retrieval.md").write_text(
            "# Retrieval Analysis\nDerived memory only.\n", encoding="utf-8"
        )

    def run_cli(
        self, *arguments: str, expected_returncode: int = 0
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(CLI), "--repo-root", str(self.root), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, expected_returncode, result.stdout + result.stderr)
        return result

    def payload(self, *arguments: str, expected_returncode: int = 0) -> dict[str, object]:
        return json.loads(self.run_cli(*arguments, expected_returncode=expected_returncode).stdout)

    def test_rebuild_indexes_only_repo_docs_markdown_and_heading_chunks(self) -> None:
        source = self.root / "src" / "runtime.py"
        source.parent.mkdir()
        source.write_text("SECRET_SOURCE_NEEDLE = True\n", encoding="utf-8")

        rebuilt = self.payload("rebuild")
        database = self.root / "state" / "repo_docs_index.sqlite"
        with sqlite3.connect(database) as connection:
            paths = {row[0] for row in connection.execute("SELECT path FROM documents")}
            headings = {
                row[0]
                for row in connection.execute(
                    "SELECT heading_path FROM chunks WHERE document_path = 'docs/ARCHITECTURE.md'"
                )
            }
            metadata = dict(connection.execute("SELECT key, value FROM index_metadata"))

        self.assertEqual(rebuilt["state"], "ready")
        self.assertEqual(
            paths,
            {
                "AGENTS.md",
                "docs/ARCHITECTURE.md",
                "docs/README.md",
                "wiki/analyses/retrieval.md",
            },
        )
        self.assertIn("Architecture > Runtime boundary", headings)
        self.assertEqual(metadata["canonical"], "false")
        self.assertEqual(metadata["truth_source"], "AGENTS.md, docs/**/*.md, wiki/**/*.md")

    def test_search_uses_fts_and_never_indexes_source_code_bodies(self) -> None:
        source = self.root / "src" / "runtime.py"
        source.parent.mkdir()
        source.write_text("SECRET_SOURCE_NEEDLE = True\n", encoding="utf-8")
        self.run_cli("rebuild")

        hit = self.payload("search", "canonical detail")
        miss = self.payload("search", "SECRET_SOURCE_NEEDLE")

        self.assertEqual(hit["results"][0]["path"], "docs/ARCHITECTURE.md")
        self.assertEqual(hit["results"][0]["heading_path"], "Architecture > Runtime boundary")
        self.assertEqual(miss["results"], [])

    def test_traverse_follows_resolved_markdown_links_with_hard_bounds(self) -> None:
        self.run_cli("rebuild")

        one_hop = self.payload("traverse", "Documentation Portal", "--hops", "1")
        two_hops = self.payload("traverse", "Documentation Portal", "--hops", "2")
        invalid = self.run_cli(
            "traverse",
            "Documentation Portal",
            "--hops",
            "3",
            expected_returncode=2,
        )

        self.assertEqual(
            {row["path"] for row in one_hop["results"]}, {"docs/ARCHITECTURE.md"}
        )
        self.assertIn(
            "wiki/analyses/retrieval.md", {row["path"] for row in two_hops["results"]}
        )
        self.assertIn("between 1 and 2", invalid.stderr)

    def test_status_and_doctor_detect_stale_markdown_and_tampered_fts(self) -> None:
        self.run_cli("rebuild")
        self.assertEqual(self.payload("status")["state"], "ready")

        architecture = self.root / "docs" / "ARCHITECTURE.md"
        architecture.write_text(
            architecture.read_text(encoding="utf-8") + "Changed.\n", encoding="utf-8"
        )
        self.assertEqual(self.payload("status")["state"], "stale")
        self.run_cli("rebuild")

        database = self.root / "state" / "repo_docs_index.sqlite"
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE chunk_fts SET content = content || ' tampered' WHERE rowid = 1")
            connection.commit()
        doctor = self.payload("doctor", expected_returncode=1)
        self.assertEqual(doctor["state"], "stale")
        self.assertIn("fts_payload", doctor["stale_reasons"])

        self.run_cli("rebuild")
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE chunks SET content = content || ' coherent tamper' WHERE rowid = 1"
            )
            row = connection.execute(
                "SELECT id, content FROM chunks WHERE rowid = 1"
            ).fetchone()
            fingerprint = hashlib.sha256(row[1].encode("utf-8")).hexdigest()
            connection.execute(
                "UPDATE chunks SET content_fingerprint = ? WHERE id = ?",
                (fingerprint, row[0]),
            )
            connection.execute(
                "UPDATE chunk_fts SET content = ? WHERE chunk_id = ?", (row[1], row[0])
            )
            connection.commit()
        coherent_tamper = self.payload("doctor", expected_returncode=1)
        self.assertIn("chunk_rows", coherent_tamper["stale_reasons"])

    def test_off_state_is_valid_and_queries_do_not_create_state(self) -> None:
        database = self.root / "state" / "repo_docs_index.sqlite"

        self.assertEqual(self.payload("status")["state"], "off")
        self.assertEqual(self.payload("doctor")["state"], "off")
        failed = self.run_cli("search", "needle", expected_returncode=2)

        self.assertIn("not enabled", failed.stderr)
        self.assertFalse(database.exists())

    def test_failed_rebuild_preserves_the_prior_disposable_index(self) -> None:
        self.run_cli("rebuild")
        database = self.root / "state" / "repo_docs_index.sqlite"
        baseline = database.read_bytes()

        failed = self.run_cli("rebuild", "--chunk-bytes", "0", expected_returncode=2)

        self.assertIn("must be positive", failed.stderr)
        self.assertEqual(database.read_bytes(), baseline)

    def test_generated_profile_smoke_uses_only_python_standard_library(self) -> None:
        generated = Path(self.temporary_directory.name) / "generated"
        (generated / "scripts").mkdir(parents=True)
        (generated / "docs").mkdir()
        (generated / "wiki").mkdir()
        shutil.copy2(CLI, generated / "scripts" / "repo_docs_retrieval.py")
        shutil.copy2(SKILL_ROOT / "assets" / "AGENTS.template.md", generated / "AGENTS.md")
        shutil.copy2(
            SKILL_ROOT / "assets" / "docs" / "README.template.md",
            generated / "docs" / "README.md",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-S",
                str(generated / "scripts" / "repo_docs_retrieval.py"),
                "--repo-root",
                str(generated),
                "rebuild",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((generated / "state" / "repo_docs_index.sqlite").is_file())

    def test_guidance_keeps_retrieval_derived_and_dependency_light(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        agents = (SKILL_ROOT / "assets" / "AGENTS.template.md").read_text(encoding="utf-8")

        for text in (skill, agents):
            self.assertIn("repo_docs_retrieval.py", text)
            self.assertIn("CodeGraph", text)
            self.assertIn("non-blocking", text)
        retrieval_section = skill[skill.index("## Derived Repo Docs Retrieval") :]
        self.assertIn("disposable", retrieval_section)
        self.assertNotIn("ONNX", retrieval_section)
        self.assertNotIn("RRF", retrieval_section)


if __name__ == "__main__":
    unittest.main()
