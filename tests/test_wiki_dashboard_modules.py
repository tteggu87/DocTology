from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime"
SKILL_ROOT = ROOT / ".agents" / "skills" / "llm-wiki-loop"


def load(name):
    spec = importlib.util.spec_from_file_location(f"extracted_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


documents = load("wiki_dashboard_documents")
folders = load("wiki_dashboard_folders")


class RuntimeOwnershipTests(unittest.TestCase):
    def test_runtime_adapter_binds_the_actual_skill_gate_paths(self):
        adapter = load("wiki_loop_adapter")
        self.assertEqual(adapter.SKILL_ROOT, SKILL_ROOT)
        self.assertEqual(adapter.ENTRYPOINT, SKILL_ROOT / "scripts" / "wiki_loop.py")
        self.assertEqual(adapter.CONTRACT, SKILL_ROOT / "SKILL.md")
        self.assertTrue(adapter.ENTRYPOINT.is_file())
        self.assertTrue(adapter.CONTRACT.is_file())
        self.assertIs(adapter.workflow, adapter.loop.workflow)
        self.assertTrue(hasattr(adapter.batch, "batch_status"))

    def test_loop_skill_contains_gates_not_runtime_or_dashboard_assets(self):
        self.assertFalse((SKILL_ROOT / "dashboard").exists())
        self.assertFalse((SKILL_ROOT / "evals").exists())
        self.assertFalse(any((SKILL_ROOT / "scripts").glob("wiki_dashboard*")))
        for source in SKILL_ROOT.rglob("*.py"):
            text = source.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"(?m)^\s*(?:from|import)\s+runtime(?:[.\s]|$)")


class GateError(Exception):
    pass


class Gate:
    WorkflowError = GateError
    PROCEDURE_ORDER = ("source_inventory_completed",)

    def __init__(self, marker="one"):
        self.marker = marker
        self.project_calls = []

    def file_digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def frontmatter_values(self, path):
        text = path.read_text(encoding="utf-8")
        values = {}
        for line in text.splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                values[key] = value
        return values

    def project_status(self, root, run):
        self.project_calls.append((root, run["run_id"]))
        return {"completed_stages": [], "wiki_complete": False, "run_status": "running",
                "stale_stages": [], "blockers": ["PROCEDURE_STAGE_MISSING"]}

    def validate_full_coverage_receipt(self, *args):
        raise AssertionError("incomplete run must not validate a receipt")


class BatchError(Exception):
    pass


class Batch:
    BatchError = BatchError

    def __init__(self):
        self.calls = []

    def batch_status(self, root, batch_id):
        self.calls.append((root, batch_id))
        return {"status": "certified", "certification": {"status": "pass"}, "sources": []}


class DocumentCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for relative, text in {
            "raw/source.md": "# Source\nOriginal Korean evidence\n",
            "wiki/page.md": "# Page\nKorean evidence\n[[raw/source]]\n[Also source](../raw/source.md)\n",
            "wiki/_meta/ingest_reports/ingest-source.md": (
                "raw_path: raw/source.md\nstatus: applied\ncoverage_mode: full\n"
                "source_sha256: " + hashlib.sha256(b"# Source\nOriginal Korean evidence\n").hexdigest() + "\n"
                "source_units_total: 1\nsource_units_projected: 1\nsource_units_omitted: 0\n"
                "source_units_deferred: 0\nwiki/page.md\n"
            ),
            "docs/readme.md": "# Documentation\nPage evidence\n",
            "AGENTS.md": "# Vault rules\n",
        }.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        run_dir = self.root / "state/wiki_runs"
        run_dir.mkdir(parents=True)
        (run_dir / "source.json").write_text(json.dumps({"source": "raw/source.md", "run_id": "r1", "updated_at": "1"}), encoding="utf-8")
        self.gate = Gate()
        self.batch = Batch()
        self.catalog = documents.DocumentCatalog(self.gate, self.batch)

    def tearDown(self):
        self.temp.cleanup()

    def test_pure_helpers_preserve_root_guards_json_and_titles(self):
        self.assertEqual(documents.inside(self.root, "raw/source.md"), self.root / "raw/source.md")
        with self.assertRaisesRegex(ValueError, "허용된"):
            documents.inside(self.root, "docs/readme.md")
        outside = self.root.parent / "outside.md"
        outside.write_text("private", encoding="utf-8")
        link = self.root / "raw/outside.md"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaisesRegex(ValueError, "밖"):
            documents.inside(self.root, "raw/outside.md")
        self.assertEqual([path.name for path in documents.files(self.root, "raw/**/*.md")], ["source.md"])
        record = self.root / "record.json"
        record.write_text('{"ok": true}', encoding="utf-8")
        self.assertEqual(documents.read_json(record), {"ok": True})
        record.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "형식"):
            documents.read_json(record)
        self.assertEqual(documents.title("# Heading  \n", "fallback"), "Heading")

    def test_catalog_document_views_candidates_and_snapshot_use_injected_gates(self):
        inventory = self.catalog.document_inventory(self.root, "wiki")
        self.assertEqual(set(inventory), {"raw/source.md", "wiki/_meta/ingest_reports/ingest-source.md", "wiki/page.md"})
        self.assertIn("AGENTS.md", self.catalog.preparation_document_inventory(self.root, "wiki"))
        self.assertEqual(self.catalog.preparation_document_payload(self.root, "wiki", "AGENTS.md")["title"], "Vault rules")
        payload = self.catalog.document_payload(self.root, "wiki", "wiki/page.md")
        self.assertEqual(payload["links"], [{"id": "raw/source.md", "title": "Source", "kind": "source"}])
        self.assertEqual(payload["rawSources"], [{"id": "raw/source.md", "title": "Source"}])
        self.assertEqual(self.catalog.document_kind("docs/readme.md"), "document")
        self.assertEqual(self.catalog.receipt_source_map(self.root, inventory), {"wiki/page.md": {"raw/source.md"}})
        self.assertEqual(self.catalog.coverage(self.root, "raw/source.md", documents.files(self.root, "wiki/_meta/ingest_reports/ingest-*.md"))["valid"], True)
        candidates = self.catalog.lexical_candidates(self.root, "wiki", "Korean evidence")
        self.assertEqual([row["id"] for row in candidates], ["wiki/page.md", "raw/source.md"])
        self.assertEqual(candidates[1]["rawSources"], [{"id": "raw/source.md", "title": "Source"}])
        graph = self.catalog.graph(self.root, documents.files(self.root, "wiki/**/*.md") + documents.files(self.root, "raw/**/*.md"))
        self.assertIn({"source": "wiki/page.md", "target": "raw/source.md"}, graph["edges"])
        snapshot = self.catalog.snapshot(self.root)
        self.assertEqual(snapshot["sources"][0]["stage"], "reading")
        self.assertEqual(snapshot["sources"][0]["references"], ["wiki/page.md"])
        self.assertEqual(self.gate.project_calls, [(self.root, "r1")])

    def test_each_instance_retains_its_own_authoritative_dependencies(self):
        first, second = Gate("first"), Gate("second")
        one = documents.DocumentCatalog(first, Batch())
        two = documents.DocumentCatalog(second, Batch())
        one.snapshot(self.root)
        self.assertEqual(first.project_calls, [(self.root, "r1")])
        self.assertEqual(second.project_calls, [])
        two.snapshot(self.root)
        self.assertEqual(second.project_calls, [(self.root, "r1")])
        self.assertIs(one.workflow, first)
        self.assertIs(two.workflow, second)

    def test_public_catalog_methods_are_available_without_dashboard_import(self):
        expected = {"coverage", "graph", "project_pages", "document_inventory", "preparation_document_inventory",
                    "preparation_document_payload", "document_kind", "document_links", "receipt_source_map",
                    "raw_sources_for", "document_payload", "lexical_candidates", "snapshot"}
        self.assertTrue(all(callable(getattr(self.catalog, name)) for name in expected))
        self.assertFalse(hasattr(documents, "workflow"))
        self.assertFalse(hasattr(documents, "batch"))


class FolderModuleTests(unittest.TestCase):
    def test_native_picker_remains_patchable_through_stdlib_objects(self):
        self.assertIs(folders.sys, sys)
        self.assertIs(folders.subprocess, subprocess)
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(folders.sys, "platform", "darwin"), mock.patch.object(
            folders.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, directory + "\n", "")
        ) as run:
            self.assertEqual(folders.choose_workspace_folder(), {"cancelled": False, "root": str(Path(directory).resolve())})
        self.assertEqual(run.call_args.args[0][:2], ["/usr/bin/osascript", "-e"])
        self.assertEqual(run.call_args.kwargs["timeout"], 120)

    def test_browser_is_bounded_and_excludes_hidden_and_symlinked_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Visible").mkdir()
            (root / ".hidden").mkdir()
            target = root / "target"
            target.mkdir()
            try:
                (root / "linked").symlink_to(target, target_is_directory=True)
            except OSError:
                pass
            result = folders.browse_folders({"path": directory}, None)
        self.assertEqual([item["name"] for item in result["directories"]], ["target", "Visible"])
        self.assertFalse(result["truncated"])


if __name__ == "__main__":
    unittest.main()
