from __future__ import annotations

import hashlib
import io
import importlib.util
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock


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
        "bootstrap_for_sqlite_retrieval_test", BOOTSTRAP_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_module(name: str, path: Path):
    if path.name == "wiki_retrieval.py":
        sys.modules.pop("reindex_sqlite_operational", None)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WikiSqliteRetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bootstrap = load_bootstrap()

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name) / "vault"
        self.bootstrap.scaffold(self.root, force=False, profile="wiki-only")
        concepts = self.root / "wiki" / "concepts"
        (concepts / "alpha.md").write_text(
            "---\ntitle: Alpha\n---\n# Alpha\nUnique needle [[beta]] and [[extra]].\n",
            encoding="utf-8",
        )
        (concepts / "beta.md").write_text(
            "---\ntitle: Beta\n---\n# Beta\nSecond hop [[gamma]].\n",
            encoding="utf-8",
        )
        (concepts / "gamma.md").write_text("# Gamma\nEndpoint.\n", encoding="utf-8")
        (concepts / "extra.md").write_text("# Extra\nSide branch.\n", encoding="utf-8")
        self.run_cli("rebuild")

    def run_cli(
        self, *arguments: str, expected_returncode: int = 0
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [
                sys.executable,
                str(self.root / "scripts" / "wiki_retrieval.py"),
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

    def test_exact_title_and_path_precede_fts_and_include_chunk_spans(self) -> None:
        title = self.payload("search", "Alpha", "--hops", "0")
        path = self.payload("search", "wiki/concepts/alpha.md", "--hops", "0")

        for payload in (title, path):
            first = payload["results"][0]
            self.assertEqual(first["match_kind"], "exact")
            self.assertEqual(first["heading_path"], "")
            self.assertEqual(first["line_start"], 1)
            self.assertGreater(first["byte_end"], first["byte_start"])

    def test_fts_hit_miss_and_default_one_hop_are_bounded(self) -> None:
        hit = self.payload("search", "needle", "--neighbor-limit", "1")
        miss = self.payload("search", "not-present-anywhere")

        self.assertEqual(hit["default_link_hops"], 1)
        self.assertEqual(hit["results"][0]["match_kind"], "fts")
        self.assertEqual(len(hit["results"][0]["neighbors"]), 1)
        self.assertEqual(miss["results"], [])

    def test_two_hop_neighbors_are_explicit_and_globally_capped(self) -> None:
        one_hop = self.payload("neighbors", "Alpha", "--hops", "1", "--limit", "10")
        two_hop = self.payload("neighbors", "Alpha", "--hops", "2", "--limit", "10")
        capped = self.payload("neighbors", "Alpha", "--hops", "2", "--limit", "2")

        self.assertNotIn("Gamma", {row["title"] for row in one_hop["results"]})
        self.assertIn("Gamma", {row["title"] for row in two_hop["results"]})
        self.assertEqual(len(capped["results"]), 2)

    def test_explicit_path_lookup_obeys_depth_and_cap(self) -> None:
        found = self.payload(
            "path", "Alpha", "Gamma", "--max-depth", "2", "--graph-cap", "10"
        )
        missing = self.run_cli(
            "path",
            "Alpha",
            "Gamma",
            "--max-depth",
            "1",
            expected_returncode=1,
        )

        self.assertTrue(found["found"])
        self.assertEqual(
            [row["title"] for row in found["pages"]], ["Alpha", "Beta", "Gamma"]
        )
        self.assertFalse(json.loads(missing.stdout)["found"])

    def test_doctor_detects_drift_and_queries_do_not_mutate_markdown(self) -> None:
        alpha = self.root / "wiki" / "concepts" / "alpha.md"
        before = alpha.read_bytes()
        ready = self.payload("doctor")
        alpha.write_text(
            alpha.read_text(encoding="utf-8") + "Changed.\n", encoding="utf-8"
        )

        drift = self.run_cli("doctor", expected_returncode=1)
        blocked = self.run_cli("search", "needle", expected_returncode=2)

        self.assertEqual(ready["state"], "ready")
        self.assertEqual(json.loads(drift.stdout)["state"], "stale")
        self.assertIn("stale", blocked.stderr)
        self.assertEqual(alpha.read_bytes(), before + b"Changed.\n")

    def test_doctor_detects_missing_fts_rows(self) -> None:
        database = self.root / "state" / "wiki_index.sqlite"
        with sqlite3.connect(database) as connection:
            connection.execute(
                "DELETE FROM chunk_fts WHERE rowid = (SELECT min(rowid) FROM chunk_fts)"
            )
            connection.commit()

        result = self.run_cli("doctor", expected_returncode=1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["state"], "stale")
        self.assertIn("fts_rows", payload["stale_reasons"])

    def test_doctor_detects_payload_tampering_with_unchanged_row_counts(self) -> None:
        database = self.root / "state" / "wiki_index.sqlite"
        mutations = (
            (
                "UPDATE documents SET title = title || ' altered' WHERE rowid = 1",
                "document_rows",
            ),
            (
                "UPDATE chunks SET content = content || ' altered' WHERE rowid = 1",
                "chunk_rows",
            ),
            (
                "UPDATE chunk_fts SET content = content || ' altered' WHERE rowid = 1",
                "fts_rows",
            ),
        )
        for statement, reason in mutations:
            with self.subTest(reason=reason):
                self.run_cli("rebuild")
                with sqlite3.connect(database) as connection:
                    connection.execute(statement)
                    connection.commit()
                result = self.run_cli("doctor", expected_returncode=1)
                self.assertIn(reason, json.loads(result.stdout)["stale_reasons"])

    def test_doctor_detects_link_source_and_tag_projection_tampering(self) -> None:
        alpha = self.root / "wiki" / "concepts" / "alpha.md"
        alpha.write_text(
            "---\ntitle: Alpha\ntags:\n  - retrieval\nsources:\n"
            '  - "[[source-one]]"\n---\n# Alpha\nNeedle [[beta]].\n',
            encoding="utf-8",
        )
        (self.root / "wiki" / "sources" / "source-one.md").write_text(
            "# Source One\n", encoding="utf-8"
        )
        database = self.root / "state" / "wiki_index.sqlite"
        mutations = (
            (
                "UPDATE page_links SET to_link_text = 'altered' WHERE rowid = 1",
                "page_link_rows",
            ),
            (
                "UPDATE page_sources SET source_id = 'altered' WHERE rowid = 1",
                "page_source_rows",
            ),
            ("UPDATE tags SET tag = 'altered' WHERE rowid = 1", "tag_rows"),
        )
        for statement, reason in mutations:
            with self.subTest(reason=reason):
                self.run_cli("rebuild")
                with sqlite3.connect(database) as connection:
                    connection.execute(statement)
                    connection.commit()
                result = self.run_cli("doctor", expected_returncode=1)
                self.assertIn(reason, json.loads(result.stdout)["stale_reasons"])

    def test_query_readiness_does_not_reparse_or_rechunk_markdown(self) -> None:
        sys.path.insert(0, str(self.root / "scripts"))
        self.addCleanup(lambda: sys.path.remove(str(self.root / "scripts")))
        retrieval = load_module(
            f"wiki_retrieval_lightweight_test_{id(self)}",
            self.root / "scripts" / "wiki_retrieval.py",
        )
        with (
            mock.patch.object(
                retrieval.indexer,
                "page_records",
                side_effect=AssertionError("query readiness reparsed Markdown"),
            ),
            mock.patch.object(
                retrieval.indexer,
                "chunks_for_page",
                side_effect=AssertionError("query readiness rechunked Markdown"),
            ),
        ):
            retrieval.require_ready(self.root)

    def test_non_indexed_meta_changes_do_not_make_query_state_stale(self) -> None:
        meta = self.root / "wiki" / "_meta" / "index.md"
        meta.write_text(meta.read_text(encoding="utf-8") + "\nMeta only.\n", encoding="utf-8")
        status = self.payload("status")
        self.assertEqual(status["state"], "ready")

    def test_invalid_threshold_fails_before_empty_corpus_and_preserves_index(self) -> None:
        database = self.root / "state" / "wiki_index.sqlite"
        baseline = database.read_bytes()
        for path in (self.root / "wiki").rglob("*.md"):
            path.unlink()
        failed = self.run_cli(
            "rebuild", "--chunk-threshold", "0", expected_returncode=2
        )
        self.assertIn("chunk threshold must be positive", failed.stderr)
        self.assertEqual(database.read_bytes(), baseline)

    def test_busy_wal_rebuild_refuses_publication_and_preserves_prior_index(self) -> None:
        database = self.root / "state" / "wiki_index.sqlite"
        writer = sqlite3.connect(database, timeout=0)
        self.addCleanup(writer.close)
        self.assertEqual(writer.execute("PRAGMA journal_mode = WAL").fetchone()[0], "wal")
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(
            "UPDATE index_metadata SET value = value WHERE key = 'truth_source'"
        )

        failed = self.run_cli("rebuild", expected_returncode=2)
        self.assertIn("prior index was not replaced", failed.stderr)
        reader = sqlite3.connect(database)
        self.assertGreater(reader.execute("SELECT count(*) FROM pages").fetchone()[0], 0)
        reader.close()

        writer.rollback()
        writer.close()
        rebuilt = self.payload("rebuild")
        self.assertGreater(rebuilt["pages"], 0)
        reader = sqlite3.connect(database)
        self.assertEqual(reader.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        reader.close()

    def test_invalid_limits_fail_before_opening_sqlite(self) -> None:
        (self.root / "state" / "wiki_index.sqlite").unlink()
        cases = (
            ("search", "needle", "--limit", "0"),
            ("search", "needle", "--neighbor-limit", "101"),
            ("search", "needle", "--graph-cap", "-1"),
            ("neighbors", "Alpha", "--limit", "0"),
            ("path", "Alpha", "Gamma", "--graph-cap", "101"),
            ("semantic", "needle", "--limit", "-1"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments, expected_returncode=2)
                self.assertIn("must be between 1 and 100", result.stderr)
                self.assertNotIn("index is missing", result.stderr)

    def test_missing_and_malformed_state_fail_without_creating_an_index(self) -> None:
        database = self.root / "state" / "wiki_index.sqlite"
        database.unlink()
        missing = self.run_cli("status", expected_returncode=2)
        self.assertIn("missing", missing.stderr)
        self.assertFalse(database.exists())

        database.write_text("not sqlite", encoding="utf-8")
        malformed = self.run_cli("doctor", expected_returncode=2)
        self.assertIn("malformed", malformed.stderr)

    def test_cli_rebuild_is_repeatable_without_duplicate_rows(self) -> None:
        first = self.payload("rebuild")
        second = self.payload("rebuild")
        status = self.payload("status")

        self.assertEqual(first["pages"], second["pages"])
        self.assertEqual(first["chunks"], second["chunks"])
        self.assertEqual(status["pages"], first["pages"])
        self.assertEqual(status["chunks"], first["chunks"])

    def test_rebuild_replaces_malformed_schema_and_cleans_failed_temporary_state(
        self,
    ) -> None:
        database = self.root / "state" / "wiki_index.sqlite"
        database.unlink()
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE wrong_schema(value TEXT)")
        rebuilt = self.payload("rebuild")
        self.assertGreater(rebuilt["pages"], 0)
        with sqlite3.connect(database) as connection:
            self.assertIsNone(
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE name = 'wrong_schema'"
                ).fetchone()
            )

        baseline = database.read_bytes()
        with sqlite3.connect(database) as connection:
            alpha_page_id = connection.execute(
                "SELECT id FROM pages WHERE path = 'wiki/concepts/alpha.md'"
            ).fetchone()[0]
        (self.root / "wiki" / "entities" / "duplicate.md").write_text(
            f"---\npage_id: {alpha_page_id}\n---\n# Duplicate\n", encoding="utf-8"
        )
        failed = self.run_cli("rebuild", expected_returncode=2)
        self.assertIn("UNIQUE constraint failed", failed.stderr)
        self.assertEqual(database.read_bytes(), baseline)
        self.assertEqual(list((self.root / "state").glob(".wiki_index.*.tmp*")), [])

    def test_rebuild_recovers_non_sqlite_state_and_preserves_valid_prior_on_publish_failure(
        self,
    ) -> None:
        database = self.root / "state" / "wiki_index.sqlite"
        database.write_text("corrupt non-sqlite derived state", encoding="utf-8")

        rebuilt = self.payload("rebuild")
        self.assertGreater(rebuilt["pages"], 0)
        with sqlite3.connect(database) as connection:
            baseline_pages = connection.execute("SELECT count(*) FROM pages").fetchone()[0]

        sys.path.insert(0, str(self.root / "scripts"))
        self.addCleanup(lambda: sys.path.remove(str(self.root / "scripts")))
        retrieval = load_module(
            f"wiki_retrieval_publish_failure_test_{id(self)}",
            self.root / "scripts" / "wiki_retrieval.py",
        )
        with (
            mock.patch.object(
                retrieval.indexer.os,
                "replace",
                side_effect=PermissionError("publication denied"),
            ),
            self.assertRaises(PermissionError),
        ):
            retrieval.indexer.rebuild(
                self.root, retrieval.indexer.DEFAULT_CHUNK_THRESHOLD
            )
        with sqlite3.connect(database) as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM pages").fetchone()[0],
                baseline_pages,
            )
        self.assertEqual(list((self.root / "state").glob(".wiki_index.*.tmp*")), [])

    def test_lightweight_readiness_skips_vector_blobs_and_closes_connection(self) -> None:
        sys.path.insert(0, str(self.root / "scripts"))
        self.addCleanup(lambda: sys.path.remove(str(self.root / "scripts")))
        retrieval = load_module(
            f"wiki_retrieval_blob_free_test_{id(self)}",
            self.root / "scripts" / "wiki_retrieval.py",
        )
        connection = sqlite3.connect(self.root / "state" / "wiki_index.sqlite")
        connection.row_factory = sqlite3.Row
        chunks = connection.execute("SELECT id, content_hash FROM chunks").fetchall()
        connection.executemany(
            """
            INSERT INTO chunk_embeddings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["content_hash"],
                    "model",
                    "tokenizer",
                    "preprocess",
                    1,
                    b"\x00\x00\x80?",
                    hashlib.sha256(b"\x00\x00\x80?").hexdigest(),
                    "now",
                )
                for row in chunks
            ],
        )
        connection.execute(
            """
            UPDATE index_metadata SET value = ?
            WHERE key = 'semantic_cohort_fingerprint'
            """,
            (retrieval.indexer.semantic_cohort_fingerprint(connection),),
        )
        connection.execute(
            """
            UPDATE index_metadata SET value = ?
            WHERE key = 'semantic_finite_attestation'
            """,
            (retrieval.indexer.semantic_finite_attestation(connection),),
        )
        connection.commit()

        def deny_vector_blob(action, table, column, _database, _trigger):
            if (
                action == sqlite3.SQLITE_READ
                and table == "chunk_embeddings"
                and column == "vector"
            ):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(deny_vector_blob)
        with mock.patch.object(retrieval, "open_index", return_value=connection):
            payload = retrieval.lightweight_health(self.root)
        self.assertEqual(payload["semantic_lane"], "ready")
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_concurrent_markdown_mutation_is_a_controlled_cli_error(self) -> None:
        sys.path.insert(0, str(self.root / "scripts"))
        self.addCleanup(lambda: sys.path.remove(str(self.root / "scripts")))
        retrieval = load_module(
            f"wiki_retrieval_mutation_test_{id(self)}",
            self.root / "scripts" / "wiki_retrieval.py",
        )
        stderr = io.StringIO()
        with (
            mock.patch.object(
                retrieval.indexer,
                "source_stat_fingerprint",
                side_effect=("before", "after"),
            ),
            mock.patch.object(
                sys,
                "argv",
                [
                    "wiki_retrieval.py",
                    "--repo-root",
                    str(self.root),
                    "rebuild",
                ],
            ),
            redirect_stderr(stderr),
        ):
            returncode = retrieval.main()
        self.assertEqual(returncode, 2)
        self.assertIn("Markdown changed during rebuild", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
