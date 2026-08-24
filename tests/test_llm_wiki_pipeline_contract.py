from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = ROOT / ".agents" / "skills" / "llm-wiki-bootstrap" / "scripts" / "bootstrap_llm_wiki.py"
ROOT_LLM_WIKI_SCRIPT = ROOT / "scripts" / "llm_wiki.py"


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

    def test_ingest_skill_is_a_capability_aware_operator(self) -> None:
        text = read_repo_text(".agents/skills/llm-wiki-ontology-ingest/SKILL.md")
        self.assertIn("workspace contracts and runtime files", text)
        self.assertIn("this skill inspects those capabilities", text)
        self.assertIn("owns reusable ontology truth and provenance conventions", text)
        self.assertIn("**`llm-first-ontology`**", text)
        self.assertIn("**`wiki-plus-ontology`**", text)
        self.assertIn("**`wiki-only`**", text)
        self.assertIn("Do not classify a lane from source filenames, keywords", text)
        self.assertIn("select only commands whose files exist", text)
        self.assertIn("do not assume `scripts/llm_full_ingest.py`", text)
        self.assertNotIn(
            "run `python scripts/llm_full_ingest.py raw/inbox/source.md --apply`",
            text,
        )

    def test_ingest_skill_reuses_repo_owned_procedure_and_batch_gates(self) -> None:
        text = read_repo_text(".agents/skills/llm-wiki-ontology-ingest/SKILL.md")
        self.assertIn("## Completion Posture", text)
        self.assertIn("Reuse `state/wiki_runs/`", text)
        self.assertIn("`state/wiki_batches/`", text)
        self.assertIn("start a run with `scripts/wiki_workflow.py`", text)
        self.assertIn("Exactly one writer", text)
        self.assertIn("`scripts/pipeline_check.py --strict --batch <manifest>`", text)
        self.assertIn("representative-question receipts", text)
        self.assertIn("final corpus fingerprint", text)
        self.assertIn("bounded to three attempts per stable blocker", text)
        for posture in ("`ready`", "`partial`", "`not_ready`", "`blocked`"):
            self.assertIn(posture, text)

    def test_ingest_skill_improvement_loop_is_proposal_only(self) -> None:
        text = read_repo_text(".agents/skills/llm-wiki-ontology-ingest/SKILL.md")
        self.assertIn("### 9. Learn By Proposal, Never By Self-Modification", text)
        self.assertIn("at least three independent runs", text)
        self.assertIn("same procedure contract digest", text)
        self.assertIn("repeated retries inside one run count once", text)
        self.assertIn("symptom stated without raw/private source excerpts", text)
        self.assertIn("expected tests, scope, risk, and `status: proposed`", text)
        self.assertIn("A human must review and approve", text)
        self.assertIn("Do not add automatic canary deployment", text)
        self.assertIn("runtime self-modification", text)
        self.assertIn("automatic truth", text)

    def test_operator_skill_does_not_accept_missing_validation_as_success(self) -> None:
        text = read_repo_text(".agents/skills/ontology-pipeline-operator/SKILL.md")
        self.assertIn("validation must check the closed ingest lifecycle", text)
        self.assertIn("Do not report success when validation output is missing.", text)
        self.assertIn("source-registration-only results under", text)

    def test_bootstrap_generates_managed_wiki_contracts(self) -> None:
        strict_agents = self.bootstrap.agents_md("llm-first-ontology")
        ontology_agents = self.bootstrap.ontology_agents_md()
        wiki_only_agents = self.bootstrap.wiki_only_agents_md()
        for contract in (strict_agents, ontology_agents, wiki_only_agents):
            self.assertIn("<!-- LLM_WIKI_CONTRACT_START -->", contract)
            self.assertIn("<!-- LLM_WIKI_CONTRACT_END -->", contract)
            self.assertIn("## Query Workflow", contract)
            self.assertIn("## Link Traversal Rules", contract)
            self.assertIn("follow at least 2 hops", contract)
            self.assertIn("list every page read in traversal order", contract)
            self.assertIn("overlapping scope", contract)
            self.assertIn("## Procedure And Batch Completion Gate", contract)
            self.assertIn("final review bound to the latest mutation fingerprint", contract)
            self.assertIn("exactly one writer", contract)

        self.assertIn("## Strict LLM-First Semantic Rule", strict_agents)
        self.assertIn("Deterministic code must not generate semantic answer drafts", strict_agents)
        self.assertIn("## Wiki Page Roles And Promotion Thresholds", strict_agents)
        self.assertIn("## Source Registration And Semantic Promotion Workflow", strict_agents)
        for contract in (ontology_agents, wiki_only_agents):
            self.assertIn("## Page Creation And Promotion Thresholds", contract)
            self.assertIn("## Source Ingest Workflow", contract)

    def test_bootstrap_llm_wiki_script_is_self_contained(self) -> None:
        generated_script = self.bootstrap.llm_wiki_py()

        self.assertIn("source registration only", generated_script)
        self.assertIn("def ingest_source", generated_script)
        self.assertIn("def rebuild_index", generated_script)
        self.assertIn("def lint_wiki", generated_script)

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "vault"
            self.bootstrap.scaffold(target, force=False, profile="wiki-only")
            self.assertEqual(
                generated_script,
                (target / "scripts" / "llm_wiki.py").read_text(encoding="utf-8"),
            )

    def test_bootstrap_writes_llm_first_runtime_for_default_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "vault"
            self.bootstrap.scaffold(target, force=False, profile="llm-first-ontology")

            agents = (target / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("## Strict LLM-First Semantic Rule", agents)
            self.assertIn("<!-- LLM_WIKI_CONTRACT_START -->", agents)
            self.assertTrue((target / "wikiconfig.example.json").exists())
            self.assertIn("wikiconfig.json", (target / ".gitignore").read_text(encoding="utf-8"))
            for relative_path in (
                "intelligence/contract_index.yaml",
                "intelligence/policies/semantic_boundary.yaml",
                "intelligence/policies/proposal_lifecycle.yaml",
                "intelligence/manifests/semantic_workflows.yaml",
                "scripts/llm_compile_source.py",
                "scripts/llm_query.py",
                "scripts/query_analysis.py",
                "scripts/proposal_review.py",
                "scripts/pipeline_check.py",
                "scripts/wiki_workflow.py",
                "scripts/wiki_batch.py",
                "scripts/reindex_sqlite_operational.py",
                "scripts/refresh_duckdb_analytics.py",
                "scripts/verify_three_layer_drift.py",
                "templates/llm-wiki-three-layer/sqlite_operational.schema.sql",
                "templates/llm-wiki-three-layer/duckdb_analytical.schema.sql",
                "warehouse/jsonl/compile_proposals.jsonl",
                "warehouse/jsonl/review_events.jsonl",
                "wiki/_meta/representative_questions.json",
            ):
                self.assertTrue((target / relative_path).exists(), relative_path)

    def test_all_profiles_generate_procedure_and_batch_gate_runtime(self) -> None:
        for profile in ("wiki-only", "wiki-plus-ontology", "llm-first-ontology"):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "vault"
                self.bootstrap.scaffold(target, force=False, profile=profile)
                for relative_path in (
                    "scripts/pipeline_check.py",
                    "scripts/wiki_workflow.py",
                    "scripts/wiki_batch.py",
                    "wiki/_meta/representative_questions.json",
                ):
                    self.assertTrue((target / relative_path).exists(), relative_path)
                self.assertTrue((target / "state" / "wiki_runs").is_dir())
                self.assertTrue((target / "state" / "wiki_batches").is_dir())
                agents = (target / "AGENTS.md").read_text(encoding="utf-8")
                self.assertIn("## Procedure And Batch Completion Gate", agents)

    def test_bootstrap_writes_legacy_ontology_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "vault"
            self.bootstrap.scaffold(target, force=False, profile="wiki-plus-ontology")

            agents = (target / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("## Link Traversal Rules", agents)
            self.assertTrue((target / "intelligence" / "glossary.yaml").exists())
            self.assertTrue((target / "intelligence" / "manifests" / "datasets.yaml").exists())
            self.assertTrue((target / "intelligence" / "manifests" / "actions.yaml").exists())
            self.assertTrue((target / "scripts" / "reindex_sqlite_operational.py").exists())
            self.assertTrue((target / "warehouse" / "jsonl" / "claims.jsonl").exists())

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

    def test_generated_ingest_registers_source_and_records_pending_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "vault"
            self.bootstrap.scaffold(target, force=False, profile="wiki-plus-ontology")
            source = target / "raw" / "inbox" / "korean-source.txt"
            source.write_text("라텔은 벌꿀오소리다.\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(target / "scripts" / "llm_wiki.py"),
                    "ingest",
                    "raw/inbox/korean-source.txt",
                    "--title",
                    "Ratel Biology",
                ],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Created source page:", result.stdout)
            source_pages = list((target / "wiki" / "sources").glob("source-*-ratel-biology.md"))
            self.assertEqual(len(source_pages), 1)
            self.assertIn("raw/inbox/korean-source.txt", source_pages[0].read_text(encoding="utf-8"))
            self.assertIn(
                "Pending LLM synthesis or ontology-backed ingest",
                (target / "wiki" / "_meta" / "log.md").read_text(encoding="utf-8"),
            )

    def test_generated_reindex_links_pages_and_clears_orphans(self) -> None:
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
            self.assertIn("- Orphan pages: 0", result.stdout)
            index = (target / "wiki" / "_meta" / "index.md").read_text(encoding="utf-8")
            self.assertIn("[[source-test]]", index)
            self.assertIn("[[concept-test]]", index)

    def test_generated_query_analysis_saves_durable_answer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "vault"
            self.bootstrap.scaffold(target, force=False, profile="llm-first-ontology")
            result = subprocess.run(
                [
                    sys.executable,
                    str(target / "scripts" / "query_analysis.py"),
                    "--question",
                    "라텔이 좋아하는 생물은?",
                    "--source",
                    "[[source-ratel]]",
                    "--evidence-mix",
                    '{"wiki": 1, "source": 1}',
                ],
                cwd=target,
                input="라텔은 꿀벌과 관련된 먹이원을 선호한다.",
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            analysis_path = target / payload["analysis_path"]
            self.assertTrue(analysis_path.exists())
            content = analysis_path.read_text(encoding="utf-8")
            self.assertIn("analysis_method: chat_agent_llm", content)
            self.assertIn("라텔이 좋아하는 생물은?", content)
            self.assertIn("라텔은 꿀벌과 관련된 먹이원을 선호한다.", content)
            self.assertIn("- wiki: 1", content)
            self.assertIn("- [[source-ratel]]", content)
            self.assertIn(analysis_path.stem, (target / "wiki" / "_meta" / "index.md").read_text(encoding="utf-8"))
            self.assertIn(analysis_path.stem, (target / "wiki" / "_meta" / "log.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
