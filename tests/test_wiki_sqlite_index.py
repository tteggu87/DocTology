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
LOOP_SKILL_PATH = ROOT / ".agents" / "skills" / "llm-wiki-loop" / "SKILL.md"


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
                self.assertIn("Certified Source Ingest", agents)
                self.assertIn("llm-wiki-loop", agents)
                for name in (
                    "wiki_workflow.py",
                    "wiki_batch.py",
                    "pipeline_check.py",
                ):
                    self.assertFalse((root / "scripts" / name).exists())
                self.assertFalse(
                    (root / "templates" / "coverage_receipt_template.md").exists()
                )
                self.assertFalse(
                    (root / "wiki" / "_meta" / "representative_questions.json").exists()
                )
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

    def test_generated_and_loop_guidance_keep_structure_navigation_optional(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.bootstrap.scaffold(root, force=False, sqlite_enabled=True)
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            readme = (root / "README.md").read_text(encoding="utf-8")

        for document in (agents, readme):
            normalized = " ".join(document.split())
            self.assertIn("tree <raw-path>", normalized)
            self.assertIn("ancestors <node-id>", normalized)
            self.assertIn("subtree <node-id>", normalized)
            self.assertIn("optional planning", normalized)
            self.assertIn("canonical Markdown before synthesis", normalized)
            self.assertIn("state: stale", normalized)
            self.assertIn("never rebuild", normalized)
            self.assertIn("rebuild --exact", normalized)
            self.assertIn("reading Markdown directly", normalized)

        loop_skill = LOOP_SKILL_PATH.read_text(encoding="utf-8")
        normalized_loop = " ".join(loop_skill.split())
        self.assertIn("only when they help plan", normalized_loop)
        self.assertIn("Reopen canonical Markdown before any synthesis", normalized_loop)
        self.assertIn("SQLite is off, unavailable, or stale", normalized_loop)
        self.assertIn("fall back to direct Markdown reading", normalized_loop)
        self.assertIn("do not create a tree coverage ledger", normalized_loop)
        self.assertIn("existing heading/bounded-chunk inventory", normalized_loop)

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

    def test_small_headed_page_chunks_preamble_and_heading_and_records_metadata(
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
                chunks = db.execute(
                    "SELECT c.heading_path, c.line_start, c.byte_start, c.byte_end, "
                    "c.content_hash, c.node_id, n.title "
                    "FROM chunks c JOIN structure_nodes n ON n.node_id = c.node_id "
                    "WHERE c.document_id = ? ORDER BY c.chunk_index",
                    (document_id,),
                ).fetchall()
                self.assertEqual([row[0] for row in chunks], ["", "Small"])
                self.assertEqual(chunks[0][1:3], (1, 0))
                self.assertTrue(all(row[3] > row[2] for row in chunks))
                self.assertTrue(all(len(row[4]) == 64 for row in chunks))
                self.assertEqual([row[6] for row in chunks], ["Small", "Small"])
                self.assertNotEqual(chunks[0][5], chunks[1][5])
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) FROM chunk_fts WHERE chunk_fts MATCH 'Needle'"
                    ).fetchone()[0],
                    1,
                )
                metadata = dict(db.execute("SELECT key, value FROM index_metadata"))
                self.assertEqual(metadata["truth_source"], "markdown")
                self.assertEqual(metadata["schema_version"], "wiki-heading-index-v9")
                self.assertEqual(
                    metadata["structure_schema_version"], "markdown-structure-v1"
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

    def test_small_ppt_style_page_chunks_every_slide_heading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold(root)
            content = (
                "# Slide 1\nFirst point.\n"
                "# Slide 2\nSecond point.\n"
                "# Slide 3\nThird point.\n"
            )
            self.assertLess(len(content.encode("utf-8")), 8192)
            (root / "wiki" / "concepts" / "slides.md").write_text(
                content, encoding="utf-8"
            )

            db_path = self.rebuild(root)

            with sqlite3.connect(db_path) as db:
                rows = db.execute(
                    "SELECT c.heading_path, c.content, c.node_id, n.heading_path "
                    "FROM chunks c JOIN structure_nodes n ON n.node_id = c.node_id "
                    "JOIN documents d ON d.id = c.document_id "
                    "WHERE d.path = 'wiki/concepts/slides.md' ORDER BY chunk_index"
                ).fetchall()
                node_count = db.execute(
                    "SELECT count(*) FROM structure_nodes n "
                    "JOIN documents d ON d.id = n.document_id "
                    "WHERE d.path = 'wiki/concepts/slides.md'"
                ).fetchone()[0]
                metadata = dict(db.execute("SELECT key, value FROM index_metadata"))
            self.assertEqual(
                [row[0] for row in rows], ["Slide 1", "Slide 2", "Slide 3"]
            )
            self.assertEqual([row[0] for row in rows], [row[3] for row in rows])
            self.assertEqual(len({row[2] for row in rows}), 3)
            self.assertEqual(node_count, 4)
            self.assertEqual(metadata["chunk_threshold_bytes"], "8192")

    def test_v8_index_is_rebuilt_instead_of_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold(root)
            db_path = self.rebuild(root)
            with sqlite3.connect(db_path) as db:
                db.execute(
                    "UPDATE index_metadata SET value = 'wiki-heading-index-v8' "
                    "WHERE key = 'schema_version'"
                )
                db.execute("CREATE TABLE legacy_v8_marker(value TEXT)")
                db.commit()

            self.rebuild(root)

            with sqlite3.connect(db_path) as db:
                tables = {
                    row[0]
                    for row in db.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                metadata = dict(db.execute("SELECT key, value FROM index_metadata"))
            self.assertNotIn("legacy_v8_marker", tables)
            self.assertIn("structure_nodes", tables)
            self.assertEqual(metadata["schema_version"], "wiki-heading-index-v9")

    def test_large_heading_page_splits_with_heading_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold(root)
            content = (
                "# Large\n" + ("alpha " * 7000) + "\n## Details\n" + ("beta " * 7000)
            )
            self.assertGreater(len(content.encode("utf-8")), 8192)
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
                self.assertTrue(all(end - start <= 8192 for _, start, end in rows))

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
