from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = ROOT / ".agents" / "skills" / "llm-wiki-bootstrap" / "scripts" / "bootstrap_llm_wiki.py"
BOOTSTRAP_LLM_WIKI_ASSET = ROOT / ".agents" / "skills" / "llm-wiki-bootstrap" / "assets" / "llm_wiki.py"
ROOT_LLM_WIKI_SCRIPT = ROOT / "scripts" / "llm_wiki.py"
ROOT_HELPER_LLM_SCRIPT = ROOT / "scripts" / "helper_llm.py"
ROOT_LLM_FULL_INGEST_SCRIPT = ROOT / "scripts" / "llm_full_ingest.py"
ROOT_PIPELINE_CHECK_SCRIPT = ROOT / "scripts" / "pipeline_check.py"


def read_repo_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def load_bootstrap_module():
    spec = importlib.util.spec_from_file_location("bootstrap_llm_wiki", BOOTSTRAP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_llm_wiki_module():
    spec = importlib.util.spec_from_file_location("root_llm_wiki", ROOT_LLM_WIKI_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ClosedIngestPipelineContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bootstrap = load_bootstrap_module()
        cls.llm_wiki = load_llm_wiki_module()

    def test_root_agents_declares_closed_ingest_without_semantic_router(self) -> None:
        text = read_repo_text("AGENTS.md")
        self.assertIn("## Closed Ingest Pipeline", text)
        self.assertIn("`scripts/llm_wiki.py ingest` is source registration only", text)
        self.assertIn("This pipeline closes the lifecycle, not semantic judgment.", text)
        self.assertIn("Accepted claims require explicit review metadata and supporting evidence.", text)
        self.assertIn("Do not use filename, keyword", text)
        self.assertIn("Semantic no-fallback rule", text)
        self.assertIn("## Link Traversal Rules", text)
        self.assertIn("follow at least 2 hops", text)
        self.assertIn("list every page read in traversal order", text)
        self.assertIn("semantic fallback that changes the judgment owner is not", text)

    def test_ingest_skill_has_closed_contract_and_report_format(self) -> None:
        text = read_repo_text(".agents/skills/llm-wiki-ontology-ingest/SKILL.md")
        self.assertIn("## Closed Pipeline Contract", text)
        self.assertIn("This pipeline closes the lifecycle, not semantic judgment.", text)
        self.assertIn("## Completion Report", text)
        self.assertIn("Proposed JSONL records emitted, appended, and skipped_existing", text)
        self.assertIn("do not report the result as completed ontology-backed ingest", text)
        self.assertIn("Semantic no-fallback rule", text)

    def test_operator_skill_does_not_accept_missing_validation_as_success(self) -> None:
        text = read_repo_text(".agents/skills/ontology-pipeline-operator/SKILL.md")
        self.assertIn("validation must check the closed ingest lifecycle", text)
        self.assertIn("Do not report success when validation output is missing.", text)
        self.assertIn("source-registration-only results under", text)

    def test_bootstrap_generates_closed_ingest_contracts(self) -> None:
        ontology_agents = self.bootstrap.ontology_agents_md()
        wiki_only_agents = self.bootstrap.wiki_only_agents_md()
        ontology_readme = self.bootstrap.readme(Path("ExampleOntologyWiki"), "wiki-plus-ontology")
        wiki_only_readme = self.bootstrap.readme(Path("ExampleWiki"), "wiki-only")

        self.assertIn("## Closed Ingest Pipeline", ontology_agents)
        self.assertIn("`scripts/llm_wiki.py ingest` is source registration only", ontology_agents)
        self.assertIn("Accepted claims require explicit review metadata", ontology_agents)
        self.assertIn("Semantic no-fallback rule", ontology_agents)
        self.assertIn("## Closed Wiki Ingest Pipeline", wiki_only_agents)
        self.assertIn("source registration only", wiki_only_agents)
        self.assertIn("Semantic no-fallback rule", wiki_only_agents)
        self.assertIn("## Link Traversal Rules", ontology_agents)
        self.assertIn("## Link Traversal Rules", wiki_only_agents)
        self.assertIn("follow at least 2 hops", ontology_agents)
        self.assertIn("follow at least 2 hops", wiki_only_agents)
        self.assertIn("list every page read in traversal order", ontology_agents)
        self.assertIn("list every page read in traversal order", wiki_only_agents)
        self.assertIn("raw -> register -> warehouse/jsonl when applicable -> wiki projection", ontology_readme)
        self.assertIn("raw -> register -> wiki projection -> meta refresh", wiki_only_readme)

    def test_bootstrap_llm_wiki_script_matches_root_script(self) -> None:
        root_script = ROOT_LLM_WIKI_SCRIPT.read_text(encoding="utf-8")
        asset_script = BOOTSTRAP_LLM_WIKI_ASSET.read_text(encoding="utf-8")

        self.assertEqual(root_script, asset_script)
        self.assertEqual(root_script, self.bootstrap.llm_wiki_py())

    def test_bootstrap_configured_full_ingest_scripts_match_root_scripts(self) -> None:
        self.assertEqual(ROOT_HELPER_LLM_SCRIPT.read_text(encoding="utf-8"), self.bootstrap.helper_llm_py())
        self.assertEqual(ROOT_LLM_FULL_INGEST_SCRIPT.read_text(encoding="utf-8"), self.bootstrap.llm_full_ingest_py())
        self.assertEqual(ROOT_PIPELINE_CHECK_SCRIPT.read_text(encoding="utf-8"), self.bootstrap.pipeline_check_py())

    def test_bootstrap_writes_configured_full_ingest_runtime_for_ontology_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "vault"
            self.bootstrap.scaffold(target, force=False, profile="wiki-plus-ontology")

            self.assertEqual(
                ROOT_HELPER_LLM_SCRIPT.read_text(encoding="utf-8"),
                (target / "scripts" / "helper_llm.py").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                ROOT_LLM_FULL_INGEST_SCRIPT.read_text(encoding="utf-8"),
                (target / "scripts" / "llm_full_ingest.py").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                ROOT_PIPELINE_CHECK_SCRIPT.read_text(encoding="utf-8"),
                (target / "scripts" / "pipeline_check.py").read_text(encoding="utf-8"),
            )
            self.assertTrue((target / "wikiconfig.example.json").exists())
            self.assertIn("wikiconfig.json", (target / ".gitignore").read_text(encoding="utf-8"))
            self.assertTrue((target / "templates" / "answer_receipt_template.md").exists())

    def test_bootstrap_writes_pipeline_manifest_for_ontology_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "vault"
            self.bootstrap.scaffold(target, force=False, profile="wiki-plus-ontology")

            agents = (target / "AGENTS.md").read_text(encoding="utf-8")
            readme = (target / "README.md").read_text(encoding="utf-8")
            manifest = (target / "intelligence" / "manifests" / "pipelines.yaml").read_text(encoding="utf-8")

        self.assertIn("## Closed Ingest Pipeline", agents)
        self.assertIn("source registration only", readme)
        self.assertIn("manifest_as_runtime_executor", manifest)
        self.assertIn("yaml_as_semantic_wiki", manifest)
        self.assertIn("semantic_no_fallback: true", manifest)
        self.assertIn("semantic_fallback_to_deterministic_summary", manifest)
        self.assertNotIn("if_keyword", manifest)
        self.assertNotIn("filename_contains", manifest)

    def test_repo_pipeline_manifest_is_stage_contract_only(self) -> None:
        text = read_repo_text("intelligence/manifests/pipelines.yaml")
        self.assertIn("manifest_as_runtime_executor", text)
        self.assertIn("yaml_as_semantic_wiki", text)
        self.assertIn("semantic_judgment_owner", text)
        self.assertIn("semantic_no_fallback: true", text)
        self.assertIn("semantic_success_without_agent_or_configured_llm_judgment", text)
        self.assertNotIn("if_keyword", text)
        self.assertNotIn("filename_contains", text)

    def test_closed_ingest_docs_and_policies_pin_no_fallback(self) -> None:
        docs = read_repo_text("docs/CLOSED_INGEST_PIPELINE.md")
        policy = read_repo_text("intelligence/policies/truth-boundaries.yaml")

        self.assertIn("## Semantic no-fallback rule", docs)
        self.assertIn("must not become semantic", docs)
        self.assertIn("Transport fallback is different", docs)
        self.assertIn("semantic stage must be reported as failed, partial, or pending", policy)
        self.assertIn("semantic fallback must not change the judgment owner", policy)

    def test_llm_wiki_helpers_remain_structural_and_korean_safe(self) -> None:
        self.assertEqual(self.llm_wiki.slugify("라텔이 좋아하는 생물"), "라텔이-좋아하는-생물")
        self.assertEqual(self.llm_wiki.slugify("Hello, World! 2026"), "hello-world-2026")

        content = """---
title: Example
type: source
status: inbox
tags:
  - source
---

# Example

- First body fact.
"""
        self.assertEqual(self.llm_wiki.extract_summary(content), "First body fact.")

    def test_generated_ingest_reports_registration_only_and_warns_for_nonstandard_raw_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "vault"
            self.bootstrap.scaffold(target, force=False, profile="wiki-plus-ontology")
            source = target / "docs" / "korean-source.txt"
            source.parent.mkdir(parents=True)
            source.write_text("라텔은 벌꿀오소리다.\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(target / "scripts" / "llm_wiki.py"),
                    "ingest",
                    "docs/korean-source.txt",
                    "--title",
                    "라텔 생물",
                ],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Source registration complete.", result.stdout)
            self.assertIn("Full LLM synthesis or ontology-backed ingest is still pending.", result.stdout)
            self.assertIn("source is outside recommended raw source folders", result.stderr)
            self.assertTrue(list((target / "wiki" / "sources").glob("source-*-라텔-생물.md")))

    def test_generated_lint_distinguishes_source_and_synthesis_orphans(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "vault"
            self.bootstrap.scaffold(target, force=False, profile="wiki-plus-ontology")
            source_page = target / "wiki" / "sources" / "source-test.md"
            concept_page = target / "wiki" / "concepts" / "concept-test.md"
            source_page.write_text(
                "---\ntitle: Source Test\ntype: source\nstatus: inbox\ncreated: 2026-05-06\nupdated: 2026-05-06\n---\n\n# Source Test\n",
                encoding="utf-8",
            )
            concept_page.write_text(
                "---\ntitle: Concept Test\ntype: concept\nstatus: active\ncreated: 2026-05-06\nupdated: 2026-05-06\n---\n\n# Concept Test\n",
                encoding="utf-8",
            )

            subprocess.run(
                [sys.executable, str(target / "scripts" / "llm_wiki.py"), "reindex"],
                cwd=target,
                text=True,
                capture_output=True,
                check=True,
            )
            result = subprocess.run(
                [sys.executable, str(target / "scripts" / "llm_wiki.py"), "lint"],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("- Orphan source pages:", result.stdout)
            self.assertIn("- Orphan synthesis pages:", result.stdout)
            self.assertIn("wiki/sources/source-test.md", result.stdout)
            self.assertIn("wiki/concepts/concept-test.md", result.stdout)

    def test_generated_answer_receipt_records_context_without_answer_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "vault"
            self.bootstrap.scaffold(target, force=False, profile="wiki-plus-ontology")
            result = subprocess.run(
                [
                    sys.executable,
                    str(target / "scripts" / "llm_wiki.py"),
                    "answer-receipt",
                    "라텔이 좋아하는 생물은?",
                    "--used-wiki",
                    "wiki/_meta/index.md",
                    "--used-raw",
                    "raw/processed/chat.txt",
                    "--wiki-update",
                    "wiki/analyses/ratel-answer.md",
                    "--uncertainty",
                    "raw 문맥 재확인이 필요함",
                ],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Created answer receipt:", result.stdout)
            self.assertIn("does not perform semantic routing or answer generation", result.stdout)
            receipts = list((target / "wiki" / "analyses").glob("answer-*-라텔이-좋아하는-생물은.md"))
            self.assertEqual(len(receipts), 1)
            content = receipts[0].read_text(encoding="utf-8")
            self.assertIn("kind: answer-receipt", content)
            self.assertIn("라텔이 좋아하는 생물은?", content)
            self.assertIn("- wiki/_meta/index.md", content)
            self.assertIn("- raw/processed/chat.txt", content)
            self.assertIn("- wiki/analyses/ratel-answer.md", content)
            self.assertIn("- raw 문맥 재확인이 필요함", content)


if __name__ == "__main__":
    unittest.main()
