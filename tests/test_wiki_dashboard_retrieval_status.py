from __future__ import annotations

import hashlib
import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "runtime/wiki_dashboard_retrieval_status.py"
spec = importlib.util.spec_from_file_location("dashboard_retrieval_status_test", SCRIPT)
status = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = status
spec.loader.exec_module(status)
INDEXER_SCRIPT = ROOT / ".agents/skills/llm-wiki-bootstrap/scripts/reindex_sqlite_operational.py"
indexer_spec = importlib.util.spec_from_file_location("trusted_bootstrap_indexer_test", INDEXER_SCRIPT)
trusted_indexer = importlib.util.module_from_spec(indexer_spec)
assert indexer_spec and indexer_spec.loader
sys.modules[indexer_spec.name] = trusted_indexer
indexer_spec.loader.exec_module(trusted_indexer)


class RetrievalStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "한글 vault"
        (self.root / "scripts").mkdir(parents=True)
        (self.root / "scripts/wiki_retrieval.py").write_text("# generated\n", encoding="utf-8")
        self.schema = self.root / "templates/llm-wiki-three-layer/sqlite_operational.schema.sql"
        self.schema.parent.mkdir(parents=True)
        self.schema.write_text("-- schema\n", encoding="utf-8")
        (self.root / "wiki/concepts").mkdir(parents=True)
        (self.root / "wiki/concepts/alpha.md").write_text("# Alpha\n", encoding="utf-8")

    def add_database(self, metadata=None, *, fts=True):
        path = self.root / "state/wiki_index.sqlite"
        path.parent.mkdir(exist_ok=True)
        db = sqlite3.connect(path)
        db.execute("CREATE TABLE pages(id TEXT)")
        db.execute("CREATE TABLE chunks(id TEXT)")
        if fts:
            db.execute("CREATE VIRTUAL TABLE chunk_fts USING fts5(value)")
        else:
            db.execute("CREATE TABLE chunk_fts(value TEXT)")
        db.execute("CREATE TABLE chunk_embeddings(id TEXT, vector BLOB)")
        db.execute("CREATE TABLE index_metadata(key TEXT, value TEXT)")
        db.execute("INSERT INTO pages VALUES ('a')")
        db.execute("INSERT INTO chunks VALUES ('a')")
        values = {
            "schema_version": status.SCHEMA_VERSION,
            "schema_fingerprint": hashlib.sha256(self.schema.read_bytes()).hexdigest(),
            # Independent oracle: the generated bootstrap's canonical protocol.
            "source_stat_fingerprint": trusted_indexer.source_stat_fingerprint(self.root),
            "truth_source": "markdown",
            "rebuildable": "true",
        }
        values.update(metadata or {})
        db.executemany("INSERT INTO index_metadata VALUES (?, ?)", values.items())
        db.commit()
        db.close()
        return path

    def snapshot_bytes(self):
        return {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def test_off_missing_and_not_applicable(self):
        (self.root / "scripts/wiki_retrieval.py").unlink()
        off = status.inspect_status(self.root)
        self.assertFalse(off["sqlite"]["configured"])
        self.assertEqual(off["sqlite"]["state"], "off")
        self.assertEqual(off["vectors"]["state"], "unknown")
        (self.root / "scripts/wiki_retrieval.py").write_text("# generated\n", encoding="utf-8")
        index_missing = status.inspect_status(self.root)
        self.assertEqual(index_missing["sqlite"]["state"], "missing")
        self.assertEqual(index_missing["vectors"]["state"], "unknown")
        not_applicable = status.inspect_status(self.root, mode="project")
        self.assertIsNone(not_applicable["sqlite"]["configured"])
        self.assertEqual(not_applicable["sqlite"]["state"], "not_applicable")
        none = status.inspect_status(None)
        self.assertIsNone(none["root"])
        self.assertEqual(none["onnx"]["state"], "not_applicable")

    def test_current_stale_and_read_only(self):
        self.add_database()
        before = self.snapshot_bytes()
        current = status.inspect_status(self.root)
        self.assertEqual(current["sqlite"]["state"], "current")
        self.assertEqual(current["sqlite"]["pages"], 1)
        self.assertEqual(current["sqlite"]["chunks"], 1)
        self.assertTrue(current["sqlite"]["fts"])
        self.assertEqual(before, self.snapshot_bytes())
        (self.root / "wiki/concepts/alpha.md").write_text("# Changed\n", encoding="utf-8")
        stale = status.inspect_status(self.root)
        self.assertEqual(stale["sqlite"]["state"], "stale")
        self.assertEqual(stale["sqlite"]["freshness"], "stat")

    def test_canonical_stat_protocol_ignores_uppercase_suffix(self):
        # Canonical rglob('*.md') is case-sensitive; the probe must match it.
        (self.root / "wiki/concepts/ignored.MD").write_text("# Ignored\n", encoding="utf-8")
        self.add_database()
        result = status.inspect_status(self.root)
        self.assertEqual(result["sqlite"]["state"], "current")

    def test_corrupt_unknown_schema_and_unicode_uri(self):
        path = self.root / "state/wiki_index.sqlite"
        path.parent.mkdir()
        path.write_bytes(b"not sqlite")
        corrupt = status.inspect_status(self.root)
        self.assertEqual(corrupt["sqlite"]["state"], "error")
        path.unlink()
        self.add_database(metadata={"schema_version": "other"})
        unknown = status.inspect_status(self.root)
        self.assertEqual(unknown["sqlite"]["state"], "unknown")
        self.assertIn("schema_version", unknown["sqlite"]["reasons"])

    def test_symlink_and_outside_config_are_not_trusted(self):
        outside = Path(self.temp.name) / "outside.py"
        outside.write_text("# no\n", encoding="utf-8")
        (self.root / "scripts/wiki_retrieval.py").unlink()
        try:
            (self.root / "scripts/wiki_retrieval.py").symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"symlink unsupported: {exc}")
        result = status.inspect_status(self.root)
        self.assertFalse(result["sqlite"]["configured"])
        (self.root / "scripts/wiki_retrieval.py").unlink()
        (self.root / "scripts/wiki_retrieval.py").write_text("# ok", encoding="utf-8")
        db = self.add_database()
        db.unlink()
        db.symlink_to(outside)
        result = status.inspect_status(self.root)
        self.assertEqual(result["sqlite"]["state"], "unknown")
        self.assertIn("db_unsafe", result["sqlite"]["reasons"])

    def test_status_never_loads_generated_target_script(self):
        (self.root / "scripts/wiki_retrieval.py").write_text("raise RuntimeError('loaded')", encoding="utf-8")
        self.add_database()
        result = status.inspect_status(self.root)
        self.assertEqual(result["sqlite"]["state"], "current")

    def test_model_absence_package_probe_and_configured_is_not_inference(self):
        with mock.patch.object(status.importlib.util, "find_spec", return_value=None), mock.patch.dict(os.environ, {}, clear=True):
            absent = status.inspect_status(self.root)
        self.assertEqual(absent["onnx"]["state"], "not_configured")
        self.assertFalse(any(absent["onnx"]["packages"].values()))
        model = self.root / "model.onnx"
        tokenizer = self.root / "tokenizer.json"
        model.write_bytes(b"x")
        tokenizer.write_text("{}", encoding="utf-8")
        with mock.patch.object(status.importlib.util, "find_spec", return_value=object()), mock.patch.dict(os.environ, {"WIKI_ONNX_MODEL": str(model), "WIKI_TOKENIZER": str(tokenizer)}, clear=True):
            ready = status.inspect_status(self.root)
        self.assertEqual(ready["onnx"]["state"], "configured")
        self.assertFalse(ready["onnx"]["inferenceVerified"])
        self.assertNotIn(str(model), repr(ready))

    def test_active_journals_are_refused_without_side_effects(self):
        self.add_database()
        for suffix in ("-wal", "-journal", "-shm"):
            with self.subTest(suffix=suffix):
                sidecar = self.root / f"state/wiki_index.sqlite{suffix}"
                sidecar.write_bytes(b"must remain unchanged")
                before = self.snapshot_bytes()
                result = status.inspect_status(self.root)
                self.assertEqual(result["sqlite"]["state"], "unknown")
                self.assertIn("db_active_journal", result["sqlite"]["reasons"])
                self.assertEqual(before, self.snapshot_bytes())
                sidecar.unlink()
        # A clean immutable read must not create sidecars either.
        before = self.snapshot_bytes()
        self.assertEqual(status.inspect_status(self.root)["sqlite"]["state"], "current")
        self.assertEqual(before, self.snapshot_bytes())

    def test_database_change_during_probe_is_not_current(self):
        self.add_database()
        actual = status._db_stat(self.root / "state/wiki_index.sqlite")
        changed = (*actual[:-1], actual[-1] + 1)
        with mock.patch.object(status, "_db_stat", side_effect=(actual, changed)):
            result = status.inspect_status(self.root)
        self.assertEqual(result["sqlite"]["state"], "unknown")
        self.assertIn("db_changed", result["sqlite"]["reasons"])

    def test_oversized_metadata_is_unknown(self):
        self.add_database(metadata={"oversized": "x" * 129})
        result = status.inspect_status(self.root)
        self.assertEqual(result["sqlite"]["state"], "unknown")
        self.assertIn("metadata_malformed", result["sqlite"]["reasons"])

    def test_vectors_are_stored_only_not_chat_ready(self):
        self.add_database()
        db = sqlite3.connect(self.root / "state/wiki_index.sqlite")
        db.execute("INSERT INTO chunk_embeddings VALUES (?, ?)", ("a", b"not inspected"))
        db.commit()
        db.close()
        result = status.inspect_status(self.root)
        self.assertEqual(result["vectors"], {"state": "stored", "rows": 1})
        self.assertFalse(result["chatMethods"]["vector"])
        self.assertFalse(result["chatMethods"]["fts"])

    def test_tilde_is_not_expanded_and_package_probe_failure_keeps_sqlite(self):
        self.add_database()
        environment = {"WIKI_ONNX_MODEL": "~/not-a-model.onnx", "WIKI_TOKENIZER": "~/not-a-tokenizer.json"}
        with mock.patch.dict(os.environ, environment, clear=True), mock.patch.object(
            status.importlib.util, "find_spec", side_effect=RuntimeError("broken path")
        ), mock.patch.object(status.Path, "expanduser", side_effect=AssertionError("must not expand ~")):
            result = status.inspect_status(self.root)
        self.assertEqual(result["sqlite"]["state"], "current")
        self.assertEqual(result["onnx"]["state"], "unknown")
        self.assertTrue(result["onnx"]["modelConfigured"])
        self.assertFalse(result["onnx"]["modelPresent"])

    def test_scan_limits_fail_unknown(self):
        self.add_database()
        with mock.patch.object(status, "MAX_PATHS", 0):
            result = status.inspect_status(self.root)
        self.assertEqual(result["sqlite"]["state"], "unknown")
        self.assertIn("source_limit", result["sqlite"]["reasons"])


if __name__ == "__main__":
    unittest.main()
