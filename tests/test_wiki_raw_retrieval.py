from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
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
REINDEX_PATH = (
    ROOT
    / ".agents"
    / "skills"
    / "llm-wiki-bootstrap"
    / "scripts"
    / "reindex_sqlite_operational.py"
)


def load_bootstrap():
    spec = importlib.util.spec_from_file_location(
        "bootstrap_for_raw_retrieval_test", BOOTSTRAP_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_reindex():
    spec = importlib.util.spec_from_file_location(
        "reindex_for_raw_retrieval_test", REINDEX_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]
    return module


class WikiRawRetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bootstrap = load_bootstrap()
        cls.reindex = load_reindex()

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

    def structure_page(self, text: str, *, title: str = "Structure"):
        encoded = text.encode("utf-8")
        return self.reindex.Page(
            "raw-page-fixture",
            "raw/inbox/structure.md",
            title,
            "source",
            "",
            self.reindex.sha256(encoded),
            text,
            len(encoded),
        )

    def test_structure_builder_preserves_tree_ranges_and_ignores_fences(self) -> None:
        text = (
            "Preamble α.\n\n"
            "# Parent\n\n"
            "```python\n# Not a heading\n```\n\n"
            "### Child\nchild body\n"
            "## Sibling\nsibling body\n"
            "# Tail\ntail body\n"
        )

        nodes = self.reindex.structure_nodes_for_page(self.structure_page(text))

        self.assertEqual(
            [node.title for node in nodes],
            ["Structure", "Parent", "Child", "Sibling", "Tail"],
        )
        self.assertEqual([node.ordinal for node in nodes], list(range(5)))
        self.assertEqual([node.depth for node in nodes], [0, 1, 3, 2, 1])
        self.assertEqual(
            [node.heading_path for node in nodes],
            ["", "Parent", "Parent > Child", "Parent > Sibling", "Tail"],
        )
        self.assertEqual(
            [heading_path for _, _, heading_path in self.reindex.section_spans(text)],
            ["", "Parent", "Parent > Child", "Parent > Sibling", "Tail"],
        )
        self.assertEqual(
            [node.parent_id for node in nodes],
            [
                None,
                nodes[0].node_id,
                nodes[1].node_id,
                nodes[1].node_id,
                nodes[0].node_id,
            ],
        )
        self.assertEqual(
            [(node.line_start, node.line_end) for node in nodes],
            [(1, 2), (3, 8), (9, 10), (11, 12), (13, 14)],
        )
        self.assertEqual(
            [(node.subtree_line_start, node.subtree_line_end) for node in nodes],
            [(1, 14), (3, 12), (9, 10), (11, 12), (13, 14)],
        )

        encoded = text.encode("utf-8")
        self.assertEqual(
            encoded[nodes[0].byte_start : nodes[0].byte_end].decode("utf-8"),
            "Preamble α.\n\n",
        )
        self.assertIn(
            "# Not a heading",
            encoded[nodes[1].byte_start : nodes[1].byte_end].decode("utf-8"),
        )
        self.assertEqual(
            encoded[
                nodes[1].subtree_byte_start : nodes[1].subtree_byte_end
            ].decode("utf-8"),
            text[text.index("# Parent") : text.index("# Tail")],
        )

    def test_structure_builder_keeps_one_root_for_headingless_documents(self) -> None:
        text = "plain α source\nwith no headings\n"

        nodes = self.reindex.structure_nodes_for_page(self.structure_page(text))

        self.assertEqual(len(nodes), 1)
        root = nodes[0]
        self.assertEqual(root.ordinal, 0)
        self.assertEqual(root.depth, 0)
        self.assertIsNone(root.parent_id)
        self.assertEqual(
            (root.byte_start, root.byte_end), (0, len(text.encode("utf-8")))
        )
        self.assertEqual(
            (root.subtree_byte_start, root.subtree_byte_end),
            (root.byte_start, root.byte_end),
        )

    def test_structure_records_are_byte_stable_for_the_same_schema(self) -> None:
        page = self.structure_page("# Same\n\n## Child\nbody\n")

        nodes_v1 = self.reindex.structure_nodes_for_page(
            page, schema_version="test-structure-v1"
        )
        self.assertEqual(
            asdict(nodes_v1[0]),
            {
                "node_id": "structure-node-cb2f45408d73713b2f1266ff",
                "document_id": "document-raw-page-fixture",
                "parent_id": None,
                "ordinal": 0,
                "depth": 0,
                "title": "Structure",
                "heading_path": "",
                "line_start": 1,
                "line_end": 1,
                "byte_start": 0,
                "byte_end": 0,
                "subtree_line_start": 1,
                "subtree_line_end": 4,
                "subtree_byte_start": 0,
                "subtree_byte_end": 22,
            },
        )
        self.assertEqual(
            asdict(nodes_v1[1]),
            {
                "node_id": "structure-node-cb63ab113166ad4f03bed524",
                "document_id": "document-raw-page-fixture",
                "parent_id": "structure-node-cb2f45408d73713b2f1266ff",
                "ordinal": 1,
                "depth": 1,
                "title": "Same",
                "heading_path": "Same",
                "line_start": 1,
                "line_end": 2,
                "byte_start": 0,
                "byte_end": 8,
                "subtree_line_start": 1,
                "subtree_line_end": 4,
                "subtree_byte_start": 0,
                "subtree_byte_end": 22,
            },
        )

        def serialized() -> bytes:
            nodes = self.reindex.structure_nodes_for_page(
                page, schema_version="test-structure-v1"
            )
            return json.dumps(
                [asdict(node) for node in nodes],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")

        self.assertEqual(serialized(), serialized())
        old_ids = [node.node_id for node in nodes_v1]
        new_ids = [
            node.node_id
            for node in self.reindex.structure_nodes_for_page(
                page, schema_version="test-structure-v2"
            )
        ]
        self.assertNotEqual(old_ids, new_ids)

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
