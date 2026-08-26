from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = (
    ROOT
    / ".agents"
    / "skills"
    / "llm-wiki-bootstrap"
    / "scripts"
    / "bootstrap_llm_wiki.py"
)


def load_bootstrap():
    spec = importlib.util.spec_from_file_location(
        "bootstrap_for_raw_retrieval_test", BOOTSTRAP_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WikiRawRetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bootstrap = load_bootstrap()

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name) / "vault"
        self.bootstrap.scaffold(self.root, force=False, sqlite_enabled=True)

    def raw_path(self, name: str) -> Path:
        return self.root / "raw" / "inbox" / name

    def run_cli(
        self, *arguments: str, expected_returncode: int = 0
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [
                sys.executable,
                str(self.root / "scripts" / "raw_retrieval.py"),
                "--repo-root",
                str(self.root),
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, expected_returncode, result.stderr)
        return result

    def payload(self, *arguments: str) -> dict[str, object]:
        return json.loads(self.run_cli(*arguments).stdout)

    def test_rebuild_and_search_return_canonical_raw_spans(self) -> None:
        source = self.raw_path("large.md")
        source.write_text(
            "# First\n\nOpening.\n\n## Evidence\n\nUnique raw needle and detail.\n",
            encoding="utf-8",
        )

        rebuilt = self.payload("rebuild", "--chunk-bytes", "40")
        found = self.payload("search", "raw needle")

        self.assertEqual(rebuilt["changed_files"], 1)
        self.assertGreaterEqual(rebuilt["chunks"], 2)
        self.assertEqual(found["lane"], "raw")
        self.assertEqual(found["freshness"], "unchecked")
        self.assertFalse(found["canonical"])
        result = found["results"][0]
        self.assertEqual(result["candidate_status"], "source_candidate")
        self.assertEqual(result["path"], "raw/inbox/large.md")
        self.assertIn("Unique raw needle", result["content"])
        encoded = source.read_bytes()
        self.assertEqual(
            result["content"].encode("utf-8"),
            encoded[result["byte_start"] : result["byte_end"]],
        )

        database = self.root / "state" / "raw_index.sqlite"
        with sqlite3.connect(database) as connection:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(raw_chunks)")
            }
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertNotIn("content", columns)
        self.assertNotIn("chunk_embeddings", tables)
        self.assertNotEqual(database, self.root / "state" / "wiki_index.sqlite")

    def test_rebuild_is_incremental_for_add_change_and_remove(self) -> None:
        first = self.raw_path("first.md")
        second = self.raw_path("second.md")
        first.write_text("# First\n\nAlpha.\n", encoding="utf-8")
        second.write_text("# Second\n\nBeta.\n", encoding="utf-8")

        initial = self.payload("rebuild")
        repeated = self.payload("rebuild")
        second.write_text("# Second\n\nBeta changed.\n", encoding="utf-8")
        changed = self.payload("rebuild")
        first.unlink()
        removed = self.payload("rebuild")

        self.assertEqual(initial["changed_files"], 2)
        self.assertEqual(repeated["changed_files"], 0)
        self.assertEqual(repeated["unchanged_files"], 2)
        self.assertEqual(changed["changed_files"], 1)
        self.assertEqual(changed["unchanged_files"], 1)
        self.assertEqual(removed["removed_files"], 1)
        self.assertEqual(removed["documents"], 1)

    def test_status_is_stat_only_and_doctor_detects_same_stat_drift(self) -> None:
        source = self.raw_path("drift.md")
        source.write_text("# Drift\n\nold-token\n", encoding="utf-8")
        self.payload("rebuild")
        original = source.stat()
        source.write_text("# Drift\n\nnew-token\n", encoding="utf-8")
        os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))

        status = self.payload("status")
        stale_candidate = self.payload("search", "old-token")
        doctor = json.loads(self.run_cli("doctor", expected_returncode=1).stdout)

        self.assertEqual(status["state"], "ready")
        self.assertEqual(status["freshness"], "stat")
        self.assertEqual(
            stale_candidate["results"][0]["candidate_status"], "stale_candidate"
        )
        self.assertIn("new-token", stale_candidate["results"][0]["content"])
        self.assertEqual(doctor["state"], "stale")
        self.assertIn(
            "document_checksum:raw/inbox/drift.md", doctor["stale_reasons"]
        )

    def test_missing_index_and_invalid_limits_fail_without_creation(self) -> None:
        database = self.root / "state" / "raw_index.sqlite"
        missing = self.run_cli("status", expected_returncode=2)
        invalid = self.run_cli("search", "term", "--limit", "0", expected_returncode=2)

        self.assertIn("missing", missing.stderr)
        self.assertIn("between 1 and 100", invalid.stderr)
        self.assertFalse(database.exists())

    def test_doctor_detects_fts_payload_tampering(self) -> None:
        self.raw_path("tamper.md").write_text(
            "# Tamper\n\noriginal searchable body\n", encoding="utf-8"
        )
        self.payload("rebuild")
        database = self.root / "state" / "raw_index.sqlite"
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE raw_chunk_fts SET content = 'altered payload' WHERE rowid = 1"
            )
            connection.commit()

        doctor = json.loads(self.run_cli("doctor", expected_returncode=1).stdout)

        self.assertEqual(doctor["state"], "stale")
        self.assertIn("chunk_rows:raw/inbox/tamper.md", doctor["stale_reasons"])


if __name__ == "__main__":
    unittest.main()
