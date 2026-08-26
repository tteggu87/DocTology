from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "repo-docs-intelligence-bootstrap"
CLI = SKILL_ROOT / "scripts" / "repo_docs_retrieval.py"
FAST_QUERY = SKILL_ROOT / "scripts" / "repo_docs_query.sh"
POWERSHELL_QUERY = SKILL_ROOT / "scripts" / "repo_docs_query.ps1"
SEARCH_SQL = SKILL_ROOT / "scripts" / "repo_docs_search.sql"
TRAVERSE_SQL = SKILL_ROOT / "scripts" / "repo_docs_traverse.sql"

SPEC = importlib.util.spec_from_file_location("repo_docs_retrieval_test_module", CLI)
assert SPEC is not None and SPEC.loader is not None
retrieval = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = retrieval
SPEC.loader.exec_module(retrieval)


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
        self.assertEqual(
            result.returncode, expected_returncode, result.stdout + result.stderr
        )
        return result

    def payload(
        self, *arguments: str, expected_returncode: int = 0
    ) -> dict[str, object]:
        return json.loads(
            self.run_cli(*arguments, expected_returncode=expected_returncode).stdout
        )

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
        self.assertEqual(
            metadata["truth_source"], "AGENTS.md, docs/**/*.md, wiki/**/*.md"
        )

    def test_search_uses_fts_and_never_indexes_source_code_bodies(self) -> None:
        source = self.root / "src" / "runtime.py"
        source.parent.mkdir()
        source.write_text("SECRET_SOURCE_NEEDLE = True\n", encoding="utf-8")
        self.run_cli("rebuild")

        hit = self.payload("search", "canonical detail")
        miss = self.payload("search", "SECRET_SOURCE_NEEDLE")

        self.assertEqual(hit["results"][0]["path"], "docs/ARCHITECTURE.md")
        self.assertEqual(
            hit["results"][0]["heading_path"], "Architecture > Runtime boundary"
        )
        self.assertEqual(miss["results"], [])

    def test_long_document_cannot_hide_other_matching_documents(self) -> None:
        (self.root / "AGENTS.md").write_text(
            "# Long\n\n" + ("needle " * 15 + "\n\n") * 220,
            encoding="utf-8",
        )
        (self.root / "docs" / "other.md").write_text(
            "# Other\n\nneedle\n", encoding="utf-8"
        )
        self.payload("rebuild", "--chunk-bytes", "128")

        results = self.payload("search", "needle", "--limit", "10")["results"]

        self.assertIn("AGENTS.md", {row["path"] for row in results})
        self.assertIn("docs/other.md", {row["path"] for row in results})
        self.assertEqual(len(results), len({row["path"] for row in results}))
        self.assertTrue(
            all("line_start" in row and "line_end" in row for row in results)
        )

    def test_search_batch_reuses_one_connection_and_attributes_queries(self) -> None:
        retrieval.rebuild(
            self.root,
            self.root / "state" / "repo_docs_index.sqlite",
            retrieval.DEFAULT_CHUNK_BYTES,
        )
        original = retrieval.open_read_only
        with mock.patch.object(retrieval, "open_read_only", wraps=original) as opened:
            result = retrieval.search_batch(
                self.root,
                self.root / "state" / "repo_docs_index.sqlite",
                ["Needle", "Canonical"],
                10,
            )

        self.assertEqual(opened.call_count, 1)
        self.assertEqual(
            [row["query"] for row in result["queries"]], ["Needle", "Canonical"]
        )
        self.assertEqual(
            len(result["documents"]),
            len({row["path"] for row in result["documents"]}),
        )
        self.assertTrue(all(row["queries"] for row in result["documents"]))

    def test_open_read_only_reads_only_the_sqlite_header(self) -> None:
        database = self.root / "state" / "repo_docs_index.sqlite"
        retrieval.rebuild(self.root, database, retrieval.DEFAULT_CHUNK_BYTES)
        with mock.patch.object(
            Path,
            "read_bytes",
            side_effect=AssertionError("must not read the full database"),
        ):
            connection = retrieval.open_read_only(database)
            connection.close()

    def test_rebuild_deduplicates_links_and_keeps_peer_headings(self) -> None:
        (self.root / "docs" / "README.md").write_text(
            "## First\n\n[Architecture](ARCHITECTURE.md)\n"
            "[Architecture](ARCHITECTURE.md)\n\n## Second\n\nText.\n",
            encoding="utf-8",
        )
        rebuilt = self.payload("rebuild")
        database = self.root / "state" / "repo_docs_index.sqlite"
        with sqlite3.connect(database) as connection:
            headings = [
                row[0]
                for row in connection.execute(
                    "SELECT heading_path FROM chunks "
                    "WHERE document_path = 'docs/README.md' ORDER BY chunk_index"
                )
            ]

        self.assertEqual(rebuilt["links"], 3)
        self.assertIn("First", headings)
        self.assertIn("Second", headings)
        self.assertNotIn("First > Second", headings)

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
            connection.execute(
                "UPDATE chunk_fts SET content = content || ' tampered' WHERE rowid = 1"
            )
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

    def test_stat_status_is_shallow_search_is_available_and_doctor_is_exact(
        self,
    ) -> None:
        self.run_cli("rebuild")
        source = self.root / "docs" / "ARCHITECTURE.md"
        original = source.stat()
        text = source.read_text(encoding="utf-8")
        source.write_text(text.replace("Canonical", "canonical"), encoding="utf-8")
        os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))

        status = self.payload("status")
        search = self.payload("search", "Canonical detail")
        doctor = self.payload("doctor", expected_returncode=1)

        self.assertEqual(status["state"], "ready")
        self.assertEqual(status["freshness"], "stat")
        self.assertTrue(search["results"])
        self.assertEqual(search["freshness"], "unchecked")
        self.assertEqual(doctor["state"], "stale")
        self.assertEqual(doctor["freshness"], "content")
        self.assertIn("corpus_fingerprint", doctor["stale_reasons"])

    def test_rebuild_checks_for_source_changes_at_publication_boundary(self) -> None:
        self.run_cli("rebuild")
        database = self.root / "state" / "repo_docs_index.sqlite"
        baseline = database.read_bytes()
        original_fingerprint = retrieval.corpus_fingerprint_from_disk

        def changing_fingerprint(repo_root):
            path = repo_root / "docs" / "README.md"
            path.write_text(
                path.read_text(encoding="utf-8") + "Changed.\n", encoding="utf-8"
            )
            return original_fingerprint(repo_root)

        with mock.patch.object(
            retrieval,
            "corpus_fingerprint_from_disk",
            side_effect=changing_fingerprint,
        ):
            with self.assertRaisesRegex(
                retrieval.RetrievalError, "changed during rebuild"
            ):
                retrieval.rebuild(
                    self.root,
                    database,
                    retrieval.DEFAULT_CHUNK_BYTES,
                )

        self.assertEqual(database.read_bytes(), baseline)

    def test_chunk_line_ranges_are_inclusive_and_stop_before_next_heading(self) -> None:
        document = retrieval.Document(
            path="docs/ranges.md",
            title="Ranges",
            content_fingerprint="unused",
            byte_size=32,
            text="## First\nline one\n\n## Second\nline two\n",
        )

        chunks = retrieval.chunks_for(document, retrieval.DEFAULT_CHUNK_BYTES)

        self.assertEqual(
            [(row.heading_path, row.line_start, row.line_end) for row in chunks],
            [("First", 1, 3), ("Second", 4, 5)],
        )

    def test_two_megabyte_document_chunks_with_exact_final_line(self) -> None:
        text = "# Large\n" + "0123456789\n" * 190_650
        document = retrieval.Document(
            path="docs/large.md",
            title="Large",
            content_fingerprint="unused",
            byte_size=len(text.encode("utf-8")),
            text=text,
        )

        chunks = retrieval.chunks_for(document, retrieval.DEFAULT_CHUNK_BYTES)

        self.assertGreaterEqual(document.byte_size, 2 * 1024 * 1024)
        self.assertGreater(len(chunks), 20)
        self.assertEqual(chunks[-1].line_end, text.count("\n"))

    def test_rebuild_streams_documents_without_materializing_the_corpus(self) -> None:
        database = self.root / "state" / "repo_docs_index.sqlite"
        with mock.patch.object(
            retrieval,
            "documents",
            side_effect=AssertionError("rebuild must stream source documents"),
        ):
            rebuilt = retrieval.rebuild(
                self.root, database, retrieval.DEFAULT_CHUNK_BYTES
            )

        self.assertEqual(rebuilt["documents"], 4)
        self.assertEqual(retrieval.health(self.root, database)["state"], "ready")

    @unittest.skipUnless(shutil.which("sqlite3"), "sqlite3 CLI is required")
    def test_native_terms_are_literal_and_not_raw_fts_syntax(self) -> None:
        self.run_cli("rebuild")
        native = subprocess.run(
            [
                str(FAST_QUERY),
                "--repo-root",
                str(self.root),
                "search",
                "--terms",
                "Needle OR definitelymissing",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        python = self.payload("search", "Needle OR definitelymissing")

        self.assertEqual(native.returncode, 0, native.stdout + native.stderr)
        self.assertEqual(json.loads(native.stdout)["results"], python["results"])
        self.assertEqual(python["results"], [])

    @unittest.skipUnless(shutil.which("sqlite3"), "sqlite3 CLI is required")
    def test_native_traverse_error_matches_python_failure_exit(self) -> None:
        self.run_cli("rebuild")
        native = subprocess.run(
            [str(FAST_QUERY), "--repo-root", str(self.root), "traverse", "missing"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(native.returncode, 2)
        self.assertIn("error", json.loads(native.stdout))

    @unittest.skipUnless(shutil.which("sqlite3"), "sqlite3 CLI is required")
    def test_native_reader_normalizes_stale_and_malformed_schema_failures(self) -> None:
        database = self.root / "state" / "repo_docs_index.sqlite"
        database.parent.mkdir()
        with sqlite3.connect(database) as connection:
            connection.execute(
                "CREATE TABLE index_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO index_metadata VALUES ('schema_version', 'repo-docs-heading-index-v1')"
            )

        stale = subprocess.run(
            [str(FAST_QUERY), "--repo-root", str(self.root), "search", "Needle"],
            check=False,
            capture_output=True,
            text=True,
        )
        database.write_bytes(b"not sqlite")
        malformed = subprocess.run(
            [str(FAST_QUERY), "--repo-root", str(self.root), "search", "Needle"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(stale.returncode, 2)
        self.assertIn("incompatible", stale.stderr)
        self.assertEqual(malformed.returncode, 2)
        self.assertIn("malformed", malformed.stderr)

    @unittest.skipUnless(shutil.which("sqlite3"), "sqlite3 CLI is required")
    def test_no_trigram_keeps_compact_token_search_available(self) -> None:
        rebuilt = self.payload("rebuild", "--no-trigram")
        database = self.root / "state" / "repo_docs_index.sqlite"
        with sqlite3.connect(database) as connection:
            trigram_rows = connection.execute(
                "SELECT count(*) FROM chunk_trigram"
            ).fetchone()[0]
        native = subprocess.run(
            [str(FAST_QUERY), "--repo-root", str(self.root), "search", "Needle"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(rebuilt["trigram_index"], "disabled")
        self.assertEqual(trigram_rows, 0)
        self.assertEqual(native.returncode, 0, native.stdout + native.stderr)
        self.assertTrue(json.loads(native.stdout)["results"])

    def test_missing_trigram_tokenizer_falls_back_to_compact_index(self) -> None:
        database = self.root / "state" / "repo_docs_index.sqlite"
        unsupported = retrieval.TRIGRAM_SCHEMA.replace(
            "tokenize = 'trigram'", "tokenize = 'definitely_missing_tokenizer'"
        )
        with mock.patch.object(retrieval, "TRIGRAM_SCHEMA", unsupported):
            rebuilt = retrieval.rebuild(
                self.root, database, retrieval.DEFAULT_CHUNK_BYTES
            )

        self.assertEqual(rebuilt["trigram_index"], "disabled")
        self.assertEqual(retrieval.health(self.root, database)["state"], "ready")
        self.assertTrue(retrieval.search(self.root, database, "Needle", 10)["results"])

    def test_native_wrappers_share_one_sql_contract(self) -> None:
        shell = FAST_QUERY.read_text(encoding="utf-8")
        powershell = POWERSHELL_QUERY.read_text(encoding="utf-8")
        for name in (SEARCH_SQL.name, TRAVERSE_SQL.name):
            self.assertIn(name, shell)
            self.assertIn(name, powershell)
        self.assertIn("WITH RECURSIVE", SEARCH_SQL.read_text(encoding="utf-8"))
        self.assertIn("WITH RECURSIVE", TRAVERSE_SQL.read_text(encoding="utf-8"))
        self.assertNotIn("WITH RECURSIVE", shell)
        self.assertNotIn("WITH RECURSIVE", powershell)
        self.assertIn("trap {", powershell)
        self.assertNotIn("[Validate", powershell)
        self.assertIn("TryParse", powershell)

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
        shutil.copy2(
            SKILL_ROOT / "assets" / "AGENTS.template.md", generated / "AGENTS.md"
        )
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
        agents = (SKILL_ROOT / "assets" / "AGENTS.template.md").read_text(
            encoding="utf-8"
        )

        for text in (skill, agents):
            self.assertIn("repo_docs_retrieval.py", text)
            self.assertIn("CodeGraph", text)
            self.assertIn("non-blocking", text)
        retrieval_section = skill[skill.index("## Derived Repo Docs Retrieval") :]
        self.assertIn("disposable", retrieval_section)
        for name in (
            "repo_docs_retrieval.py",
            "repo_docs_query.sh",
            "repo_docs_query.ps1",
            "repo_docs_search.sql",
            "repo_docs_traverse.sql",
        ):
            self.assertIn(name, retrieval_section)
            self.assertTrue((SKILL_ROOT / "scripts" / name).is_file())
        self.assertNotIn("ONNX", retrieval_section)
        self.assertNotIn("RRF", retrieval_section)


if __name__ == "__main__":
    unittest.main()
