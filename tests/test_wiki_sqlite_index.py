from __future__ import annotations

import importlib.util
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
        "bootstrap_for_sqlite_index_test", BOOTSTRAP_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WikiSqliteIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bootstrap = load_bootstrap()

    def scaffold(self, root: Path, profile: str = "wiki-only") -> None:
        self.bootstrap.scaffold(root, force=False, profile=profile)

    def rebuild(self, root: Path, threshold: int | None = None) -> Path:
        command = [
            sys.executable,
            str(root / "scripts" / "reindex_sqlite_operational.py"),
            "--repo-root",
            str(root),
        ]
        if threshold is not None:
            command.extend(["--chunk-threshold", str(threshold)])
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Rebuilt derived SQLite index", result.stdout)
        return root / "state" / "wiki_index.sqlite"

    def test_wiki_only_sqlite_choice_controls_retrieval_files(self) -> None:
        for sqlite_enabled in (True, False):
            with (
                self.subTest(sqlite_enabled=sqlite_enabled),
                tempfile.TemporaryDirectory() as tmp,
            ):
                root = Path(tmp) / "vault"
                self.bootstrap.scaffold(
                    root,
                    force=False,
                    sqlite_enabled=sqlite_enabled,
                )
                self.assertFalse((root / "warehouse" / "jsonl").exists())
                self.assertFalse((root / "intelligence").exists())
                agents = (root / "AGENTS.md").read_text(encoding="utf-8")
                readme = (root / "README.md").read_text(encoding="utf-8")
                self.assertIn("Markdown", agents)
                self.assertIn("Coverage-Preserving Ingest", agents)
                self.assertIn("--coverage-mode summary", agents)
                self.assertTrue(
                    (root / "templates" / "coverage_receipt_template.md").is_file()
                )
                self.assertTrue((root / "wiki" / "_meta" / "ingest_reports").is_dir())
                if not sqlite_enabled:
                    self.assertFalse(
                        (root / "scripts" / "reindex_sqlite_operational.py").exists()
                    )
                    self.assertFalse((root / "scripts" / "wiki_retrieval.py").exists())
                    self.assertFalse((root / "scripts" / "raw_retrieval.py").exists())
                    self.assertFalse(
                        (
                            root
                            / "templates"
                            / "llm-wiki-three-layer"
                            / "sqlite_operational.schema.sql"
                        ).exists()
                    )
                    self.assertIn("without the optional SQLite", readme)
                    self.assertIn("not_enabled", agents)
                    self.assertIn("not_enabled", readme)
                    continue
                self.assertTrue(
                    (root / "scripts" / "reindex_sqlite_operational.py").is_file()
                )
                self.assertTrue((root / "scripts" / "wiki_retrieval.py").is_file())
                self.assertTrue((root / "scripts" / "raw_retrieval.py").is_file())
                self.assertTrue(
                    (
                        root
                        / "templates"
                        / "llm-wiki-three-layer"
                        / "sqlite_operational.schema.sql"
                    ).is_file()
                )
                self.assertIn(
                    "state/*.sqlite", (root / ".gitignore").read_text(encoding="utf-8")
                )
                for document in (agents, readme):
                    self.assertIn("Markdown", document)
                    self.assertIn("64 KiB", document)
                    self.assertIn("ONNX", document)
                    self.assertIn("RRF", document)
                    self.assertIn("--mode both", document)
                    self.assertIn("same-size", document.lower())
                    self.assertIn("doctor", document.lower())
                    self.assertIn("refresh", document.lower())
                    self.assertIn("zero API tokens", document)
                    self.assertIn("wiki_complete", document)
                    self.assertIn("retrieval_ready", document)
                    self.assertIn("raw-fallback", document)
                    self.assertIn("separate", document.lower())
                self.assertIn("no `warehouse/jsonl/`", agents)

    def test_force_switch_from_sqlite_on_to_off_removes_managed_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.bootstrap.scaffold(root, force=False, sqlite_enabled=True)
            database = self.rebuild(root)
            self.assertTrue(database.exists())

            self.bootstrap.scaffold(root, force=True, sqlite_enabled=False)

            self.assertFalse(database.exists())
            self.assertFalse((root / "scripts" / "wiki_retrieval.py").exists())
            self.assertFalse(
                (root / "scripts" / "reindex_sqlite_operational.py").exists()
            )
            self.assertFalse(
                (
                    root
                    / "templates"
                    / "llm-wiki-three-layer"
                    / "sqlite_operational.schema.sql"
                ).exists()
            )
            readme = (root / "README.md").read_text(encoding="utf-8")
            self.assertIn("without the optional SQLite", readme)

    def test_small_page_stays_one_chunk_and_records_metadata_fts_links_sources_tags(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold(root)
            (root / "wiki" / "sources" / "source-one.md").write_text(
                "# Source One\n", encoding="utf-8"
            )
            (root / "wiki" / "concepts" / "target.md").write_text(
                "# Target\n", encoding="utf-8"
            )
            (root / "wiki" / "concepts" / "small.md").write_text(
                '---\ntitle: Small\ntags:\n  - retrieval\nsources:\n  - "[[source-one]]"\n---\n# Small\nNeedle text [[target]] and [[missing-page]].\n',
                encoding="utf-8",
            )
            db_path = self.rebuild(root)
            with sqlite3.connect(db_path) as db:
                document_id = db.execute(
                    "SELECT id FROM documents WHERE path = 'wiki/concepts/small.md'"
                ).fetchone()[0]
                chunk = db.execute(
                    "SELECT line_start, byte_start, byte_end, content_hash FROM chunks WHERE document_id = ?",
                    (document_id,),
                ).fetchall()
                self.assertEqual(len(chunk), 1)
                self.assertEqual(chunk[0][0:2], (1, 0))
                self.assertGreater(chunk[0][2], 0)
                self.assertEqual(len(chunk[0][3]), 64)
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) FROM chunk_fts WHERE chunk_fts MATCH 'Needle'"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    dict(db.execute("SELECT key, value FROM index_metadata"))[
                        "truth_source"
                    ],
                    "markdown",
                )
                small_page_id = db.execute(
                    "SELECT id FROM pages WHERE path = 'wiki/concepts/small.md'"
                ).fetchone()[0]
                self.assertEqual(
                    set(
                        db.execute(
                            "SELECT status FROM page_links WHERE from_page_id = ?",
                            (small_page_id,),
                        )
                    ),
                    {("resolved",), ("unresolved",)},
                )
                self.assertEqual(
                    db.execute(
                        "SELECT tag FROM tags WHERE page_id = ?", (small_page_id,)
                    ).fetchone()[0],
                    "retrieval",
                )
                self.assertEqual(
                    db.execute(
                        "SELECT source_id FROM page_sources WHERE page_id = ?",
                        (small_page_id,),
                    ).fetchone()[0],
                    "source-one",
                )
            self.rebuild(root)

    def test_large_heading_page_splits_with_heading_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold(root)
            content = (
                "# Large\n" + ("alpha " * 7000) + "\n## Details\n" + ("beta " * 7000)
            )
            self.assertGreater(len(content.encode("utf-8")), 65536)
            (root / "wiki" / "concepts" / "large.md").write_text(
                content, encoding="utf-8"
            )
            db_path = self.rebuild(root)
            with sqlite3.connect(db_path) as db:
                rows = db.execute(
                    "SELECT heading_path, byte_start, byte_end FROM chunks ORDER BY chunk_index"
                ).fetchall()
                self.assertGreater(len(rows), 1)
                self.assertTrue(
                    any(heading == "Large > Details" for heading, _, _ in rows)
                )
                self.assertTrue(all(end - start <= 65536 for _, start, end in rows))

    def test_peer_headings_do_not_inherit_the_previous_peer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold(root)
            (root / "wiki" / "concepts" / "peers.md").write_text(
                "# First\n" + ("alpha " * 80) + "\n# Second\n" + ("beta " * 80),
                encoding="utf-8",
            )
            db_path = self.rebuild(root, threshold=120)
            with sqlite3.connect(db_path) as db:
                headings = {
                    row[0]
                    for row in db.execute(
                        "SELECT heading_path FROM chunks WHERE heading_path != ''"
                    )
                }
            self.assertIn("First", headings)
            self.assertIn("Second", headings)
            self.assertNotIn("First > Second", headings)

    def test_headingless_oversized_page_uses_paragraph_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold(root)
            content = ("first paragraph " * 20) + "\n\n" + ("second paragraph " * 20)
            (root / "wiki" / "concepts" / "headingless.md").write_text(
                content, encoding="utf-8"
            )
            db_path = self.rebuild(root, threshold=300)
            with sqlite3.connect(db_path) as db:
                rows = db.execute(
                    "SELECT heading_path, byte_start, byte_end, content FROM chunks ORDER BY chunk_index"
                ).fetchall()
                self.assertGreater(len(rows), 1)
                self.assertTrue(all(heading == "" for heading, *_ in rows))
                self.assertTrue(all(end - start <= 300 for _, start, end, _ in rows))
                self.assertEqual("".join(row[3] for row in rows), content)

    def test_fallback_page_ids_include_normalized_wiki_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold(root)
            (root / "wiki" / "concepts" / "shared.md").write_text(
                "# Concept Shared\n", encoding="utf-8"
            )
            (root / "wiki" / "entities" / "shared.md").write_text(
                "# Entity Shared\n", encoding="utf-8"
            )
            db_path = self.rebuild(root)
            with sqlite3.connect(db_path) as db:
                rows = db.execute(
                    "SELECT id, path FROM pages WHERE path LIKE '%/shared.md' ORDER BY path"
                ).fetchall()
            self.assertEqual(
                [row[1] for row in rows],
                ["wiki/concepts/shared.md", "wiki/entities/shared.md"],
            )
            self.assertEqual(len({row[0] for row in rows}), 2)
            self.assertTrue(all(row[0].startswith("page-") for row in rows))

    def test_fallback_page_ids_do_not_collapse_distinct_unicode_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold(root)
            for name in ("한글", "한국", "A", "Ａ"):
                (root / "wiki" / "concepts" / f"{name}.md").write_text(
                    f"# {name}\n", encoding="utf-8"
                )
            db_path = self.rebuild(root)
            with sqlite3.connect(db_path) as db:
                rows = db.execute(
                    "SELECT id FROM pages WHERE path IN (?, ?, ?, ?)",
                    (
                        "wiki/concepts/한글.md",
                        "wiki/concepts/한국.md",
                        "wiki/concepts/A.md",
                        "wiki/concepts/Ａ.md",
                    ),
                ).fetchall()
            self.assertEqual(len(rows), 4)
            self.assertEqual(len({row[0] for row in rows}), 4)

    def test_headingless_split_uses_precomputed_utf8_offsets(self) -> None:
        source = (
            ROOT
            / ".agents"
            / "skills"
            / "llm-wiki-bootstrap"
            / "scripts"
            / "reindex_sqlite_operational.py"
        ).read_text(encoding="utf-8")
        self.assertIn("byte_offsets", source)
        self.assertNotIn('text[:offset].encode("utf-8")', source)
        self.assertNotIn('page.text.count("\\n", 0,', source)


if __name__ == "__main__":
    unittest.main()
