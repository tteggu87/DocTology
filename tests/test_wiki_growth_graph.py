from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "scripts" / "wiki_growth_graph.py"
HELPER_PATH = ROOT / "scripts" / "helper_llm.py"
BOOTSTRAP_PATH = ROOT / ".agents" / "skills" / "llm-wiki-bootstrap" / "scripts" / "bootstrap_llm_wiki.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def install_fake_graph(module) -> None:
    class FakeCompiledGraph:
        def __init__(self, nodes, conditional):
            self.nodes = nodes
            self.conditional = conditional

        def invoke(self, state):
            for name in [
                "load_contract",
                "load_memory",
                "require_configured_llm",
                "draft_source_page",
                "validate_draft",
            ]:
                state = self.nodes[name](state)
            route = self.conditional["validate_draft"](state)
            if route == "apply":
                state = self.nodes["apply_source_page"](state)
            return state

    class FakeStateGraph:
        def __init__(self, _schema):
            self.nodes = {}
            self.conditional = {}

        def add_node(self, name, fn):
            self.nodes[name] = fn

        def add_edge(self, *_args):
            return None

        def add_conditional_edges(self, name, route_fn, _mapping):
            self.conditional[name] = route_fn

        def compile(self):
            return FakeCompiledGraph(self.nodes, self.conditional)

    module.require_langgraph = lambda: (FakeStateGraph, "__start__", "__end__")


class WikiGrowthGraphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = load_module(GRAPH_PATH, "wiki_growth_graph_under_test")
        cls.helper = load_module(HELPER_PATH, "helper_for_wiki_growth_graph_test")
        cls.bootstrap = load_module(BOOTSTRAP_PATH, "bootstrap_for_wiki_growth_graph_test")

    def make_vault(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name) / "vault"
        self.bootstrap._scaffold_archived_profile_for_contract_tests(
            root, force=False, profile="wiki-plus-ontology"
        )
        source = root / "raw" / "inbox" / "example.md"
        source.write_text("# Example\n\n라텔은 벌꿀오소리다.\n", encoding="utf-8")
        return tmp, root, source

    def fake_config(self):
        fake_model = self.helper.ModelConfig(
            provider="openai",
            model="fake-model",
            api_key="fake-key",
            api_base="https://example.test/v1",
        )
        return self.helper.HelperLLMConfig(
            source_path="wikiconfig.json",
            enabled=True,
            chat_model=fake_model,
            embeddings_provider=None,
            reranker_provider=None,
            warnings=(),
        )

    def proposed_response(self) -> str:
        return json.dumps(
            {
                "summary": "라텔 관련 source-backed 요약입니다.",
                "key_facts": ["라텔은 벌꿀오소리로 언급된다."],
                "important_claims": [
                    {
                        "claim_text": "라텔은 벌꿀오소리다.",
                        "status": "proposed",
                        "extractor_confidence": "medium",
                        "evidence_excerpt": "라텔은 벌꿀오소리다.",
                    }
                ],
                "uncertainties": ["source 맥락이 짧다."],
                "open_questions": ["라텔이 왜 중요한가?"],
                "affected_pages": [
                    {
                        "page": "[[라텔]]",
                        "action": "source_page_only",
                        "reason": "짧은 언급이라 source page에 보존",
                        "confidence": "medium",
                    }
                ],
                "completion_notes": ["source page only"],
            },
            ensure_ascii=False,
        )

    def test_missing_langgraph_fails_fast_without_writes(self) -> None:
        original_require_langgraph = self.graph.require_langgraph
        self.graph.require_langgraph = lambda: (_ for _ in ()).throw(RuntimeError("LangGraph is required"))
        try:
            tmp, root, _source = self.make_vault()
            with tmp:
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as stderr:
                    code = self.graph.main(
                        [
                            "--root",
                            str(root),
                            "ingest",
                            "raw/inbox/example.md",
                            "--mode",
                            "apply-source-page",
                        ]
                    )

                self.assertEqual(code, 1)
                self.assertIn("LangGraph is required", stderr.getvalue())
                self.assertEqual(list((root / "wiki" / "sources").glob("source-*-example.md")), [])
        finally:
            self.graph.require_langgraph = original_require_langgraph

    def test_missing_helper_config_fails_without_registration_or_handoff(self) -> None:
        original_require_langgraph = self.graph.require_langgraph
        install_fake_graph(self.graph)
        try:
            tmp, root, _source = self.make_vault()
            with tmp:
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    code = self.graph.main(
                        [
                            "--root",
                            str(root),
                            "ingest",
                            "raw/inbox/example.md",
                            "--mode",
                            "apply-source-page",
                        ]
                    )

                self.assertEqual(code, 1)
                self.assertEqual(list((root / "wiki" / "sources").glob("source-*-example.md")), [])
                self.assertFalse((root / "wiki" / "_meta" / "handoff").exists())
        finally:
            self.graph.require_langgraph = original_require_langgraph

    def test_root_config_resolution_works_outside_repo_cwd(self) -> None:
        original_require_langgraph = self.graph.require_langgraph
        original_chat_completion = self.graph.helper_llm.chat_completion
        original_cwd = Path.cwd()
        install_fake_graph(self.graph)
        self.graph.helper_llm.chat_completion = lambda *_args, **_kwargs: self.proposed_response()
        try:
            tmp, root, _source = self.make_vault()
            with tmp:
                (root / "wikiconfig.json").write_text(
                    json.dumps(
                        {
                            "models": [
                                {
                                    "provider": "openai",
                                    "model": "fake-model",
                                    "apiKey": "fake-key",
                                    "apiBase": "https://example.test/v1",
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                os.chdir("/")
                with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()):
                    code = self.graph.main(
                        [
                            "--root",
                            str(root),
                            "ingest",
                            "raw/inbox/example.md",
                            "--mode",
                            "draft",
                        ]
                    )

                self.assertEqual(code, 0)
                payload = json.loads(stdout.getvalue())
                self.assertEqual(payload["lifecycle_status"], "draft_created")
        finally:
            os.chdir(original_cwd)
            self.graph.require_langgraph = original_require_langgraph
            self.graph.helper_llm.chat_completion = original_chat_completion

    def test_export_handoff_is_explicit_and_pending(self) -> None:
        tmp, root, _source = self.make_vault()
        with tmp:
            with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()):
                code = self.graph.main(["--root", str(root), "export-handoff", "raw/inbox/example.md"])

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["semantic_status"], "pending")
            handoff = root / payload["path"]
            text = handoff.read_text(encoding="utf-8")
            self.assertIn("type: handoff", text)
            self.assertIn("semantic_status: pending", text)
            self.assertIn("This is an explicit non-ingest handoff artifact", text)
            self.assertEqual(list((root / "wiki" / "sources").glob("source-*-example.md")), [])

    def test_apply_source_page_closes_source_page_stage_with_fake_graph_and_llm(self) -> None:
        original_require_langgraph = self.graph.require_langgraph
        original_load_config = self.graph.helper_llm.load_helper_config
        original_chat_completion = self.graph.helper_llm.chat_completion
        install_fake_graph(self.graph)
        self.graph.helper_llm.load_helper_config = lambda *_args, **_kwargs: self.fake_config()
        self.graph.helper_llm.chat_completion = lambda *_args, **_kwargs: self.proposed_response()
        try:
            tmp, root, _source = self.make_vault()
            with tmp:
                with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()):
                    code = self.graph.main(
                        [
                            "--root",
                            str(root),
                            "ingest",
                            "raw/inbox/example.md",
                            "--mode",
                            "apply-source-page",
                            "--title",
                            "라텔 예시",
                        ]
                    )

                self.assertEqual(code, 0)
                payload = json.loads(stdout.getvalue())
                self.assertEqual(payload["lifecycle_status"], "partial_source_page_applied")
                self.assertEqual(payload["semantic_status"], "pending_broader_projection")

                source_pages = list((root / "wiki" / "sources").glob("source-*-라텔-예시.md"))
                self.assertEqual(len(source_pages), 1)
                source_text = source_pages[0].read_text(encoding="utf-8")
                self.assertIn("status: pending-wiki-projection", source_text)
                self.assertIn("라텔 관련 source-backed 요약입니다.", source_text)
                self.assertNotIn("TBD", source_text)

                self.assertTrue((root / "wiki" / "_meta" / "ingest_reports").exists())
                self.assertEqual(list((root / "warehouse" / "jsonl").glob("*.tmp")), [])
        finally:
            self.graph.require_langgraph = original_require_langgraph
            self.graph.helper_llm.load_helper_config = original_load_config
            self.graph.helper_llm.chat_completion = original_chat_completion

    def test_accepted_claim_is_rejected_before_registration(self) -> None:
        original_require_langgraph = self.graph.require_langgraph
        original_load_config = self.graph.helper_llm.load_helper_config
        original_chat_completion = self.graph.helper_llm.chat_completion
        install_fake_graph(self.graph)
        self.graph.helper_llm.load_helper_config = lambda *_args, **_kwargs: self.fake_config()
        accepted = json.loads(self.proposed_response())
        accepted["important_claims"][0]["status"] = "accepted"
        self.graph.helper_llm.chat_completion = lambda *_args, **_kwargs: json.dumps(accepted, ensure_ascii=False)
        try:
            tmp, root, _source = self.make_vault()
            with tmp:
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as stderr:
                    code = self.graph.main(
                        [
                            "--root",
                            str(root),
                            "ingest",
                            "raw/inbox/example.md",
                            "--mode",
                            "apply-source-page",
                            "--title",
                            "라텔 예시",
                        ]
                    )

                self.assertEqual(code, 1)
                self.assertIn("non-proposed claims", stderr.getvalue())
                self.assertEqual(list((root / "wiki" / "sources").glob("source-*-라텔-예시.md")), [])
        finally:
            self.graph.require_langgraph = original_require_langgraph
            self.graph.helper_llm.load_helper_config = original_load_config
            self.graph.helper_llm.chat_completion = original_chat_completion


if __name__ == "__main__":
    unittest.main()
