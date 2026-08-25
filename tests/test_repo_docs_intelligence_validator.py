from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = (
    ROOT
    / ".agents"
    / "skills"
    / "repo-docs-intelligence-bootstrap"
    / "scripts"
    / "validate_repo_docs_intelligence.py"
)


def load_validator_module():
    spec = importlib.util.spec_from_file_location("repo_docs_validator", VALIDATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_doc(path: Path, title: str, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "status: Active",
                "source_of_truth: No",
                "last_updated: 2026-06-20",
                "superseded_by: N/A",
                "---",
                "",
                f"# {title}",
                "",
                body,
            ]
        ),
        encoding="utf-8",
    )


class RepoDocsIntelligenceValidatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator_module()

    def run_validator(self, repo_root: Path) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR_PATH),
                "--repo-root",
                str(repo_root),
                "--format",
                "json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def run_validator_command(self, repo_root: Path, *args: str) -> tuple[int, dict]:
        result = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR_PATH),
                "--repo-root",
                str(repo_root),
                "--format",
                "json",
                *args,
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        return result.returncode, json.loads(result.stdout)

    def copy_complete_fixture(self, destination: Path) -> None:
        source = (
            ROOT
            / ".agents"
            / "skills"
            / "repo-docs-intelligence-bootstrap"
            / "evals"
            / "files"
            / "fixture_repo_mapping_manifest_with_wiki"
        )
        shutil.copytree(source, destination, dirs_exist_ok=True)

    def test_repo_map_is_rejected_when_index_links_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_map = root / "docs" / "repo-map"
            write_doc(repo_map / "README.md", "Repo Map", "Only partial map.")
            write_doc(repo_map / "ENTRYPOINTS.md", "Entrypoints")
            write_doc(repo_map / "MODULES.md", "Modules")
            write_doc(repo_map / "DATA_FLOW.md", "Data Flow")
            write_doc(repo_map / "SYMBOL_GRAPH.md", "Symbol Graph")
            write_doc(
                root / "wiki" / "_meta" / "index.md",
                "Repo Memory Index",
                "- `docs/CURRENT_STATE.md`",
            )

            payload = self.run_validator(root)

        codes = {issue["code"] for issue in payload["errors"]}
        self.assertIn("repo_map.readme_missing_link", codes)
        self.assertIn("repo_map.wiki_index_missing", codes)

    def test_repo_map_is_valid_when_required_links_are_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_map = root / "docs" / "repo-map"
            write_doc(
                repo_map / "README.md",
                "Repo Map",
                "\n".join(
                    [
                        "- `docs/repo-map/ENTRYPOINTS.md`",
                        "- `docs/repo-map/MODULES.md`",
                        "- `docs/repo-map/DATA_FLOW.md`",
                        "- `docs/repo-map/SYMBOL_GRAPH.md`",
                    ]
                ),
            )
            write_doc(repo_map / "ENTRYPOINTS.md", "Entrypoints")
            write_doc(repo_map / "MODULES.md", "Modules")
            write_doc(repo_map / "DATA_FLOW.md", "Data Flow")
            write_doc(repo_map / "SYMBOL_GRAPH.md", "Symbol Graph")
            write_doc(
                root / "wiki" / "_meta" / "index.md",
                "Repo Memory Index",
                "- `docs/repo-map/README.md`",
            )

            report = self.validator.ValidationReport(root)
            self.validator.validate_repo_map(root, report)

        self.assertEqual(report.errors, [])

    def test_skill_guidance_describes_bundled_validator_fallback(self) -> None:
        skill_path = (
            ROOT
            / ".agents"
            / "skills"
            / "repo-docs-intelligence-bootstrap"
            / "SKILL.md"
        )
        agents_template_path = (
            ROOT
            / ".agents"
            / "skills"
            / "repo-docs-intelligence-bootstrap"
            / "assets"
            / "AGENTS.template.md"
        )

        skill_text = skill_path.read_text(encoding="utf-8")
        agents_template_text = agents_template_path.read_text(encoding="utf-8")

        self.assertIn("repository-local validator", skill_text)
        self.assertIn("bundled skill validator", skill_text)
        self.assertIn("--finalize", skill_text)
        self.assertIn("--verify-finalized", skill_text)
        self.assertIn("bundled skill validator", agents_template_text)
        self.assertIn("--finalize", agents_template_text)

    def test_repo_memory_contract_prefers_portable_markdown_links(self) -> None:
        skill_root = (
            ROOT / ".agents" / "skills" / "repo-docs-intelligence-bootstrap"
        )
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        agents_text = (skill_root / "assets" / "AGENTS.template.md").read_text(
            encoding="utf-8"
        )
        index_text = (
            skill_root / "assets" / "wiki" / "_meta" / "index.template.md"
        ).read_text(encoding="utf-8")
        log_text = (
            skill_root / "assets" / "wiki" / "_meta" / "log.template.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Use portable Markdown links as the default", skill_text)
        self.assertIn("supported legacy input", skill_text)
        self.assertIn("at most 2 additional hops", skill_text)
        self.assertIn("at most 12 pages total", skill_text)
        self.assertIn("descriptive relative Markdown links", agents_text)
        self.assertIn("[Current repository state]", index_text)
        self.assertNotIn("- `docs/CURRENT_STATE.md`", index_text)
        self.assertNotIn("](../../docs/repo-map/README.md)", index_text)
        self.assertNotIn("](../../intelligence/)", index_text)
        self.assertNotIn("](../../intelligence/)", log_text)

    def test_adaptive_document_authority_lifecycle_and_templates(self) -> None:
        skill_root = (
            ROOT / ".agents" / "skills" / "repo-docs-intelligence-bootstrap"
        )
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        agents_text = (skill_root / "assets" / "AGENTS.template.md").read_text(
            encoding="utf-8"
        )
        portal_text = (
            skill_root / "assets" / "docs" / "README.template.md"
        ).read_text(encoding="utf-8")
        template_paths = {
            "adr": skill_root / "assets" / "docs" / "adr" / "ADR.template.md",
            "plan": skill_root
            / "assets"
            / "docs"
            / "plans"
            / "IMPLEMENTATION_PLAN.template.md",
            "evidence": skill_root
            / "assets"
            / "docs"
            / "evidence"
            / "EVIDENCE.template.md",
            "review": skill_root
            / "assets"
            / "docs"
            / "reviews"
            / "REVIEW.template.md",
            "decision": skill_root
            / "assets"
            / "wiki"
            / "decisions"
            / "decision.template.md",
        }

        for path in template_paths.values():
            self.assertTrue(path.is_file(), path)

        self.assertIn("Adaptive Documentation Authority Lifecycle", skill_text)
        self.assertIn("live code, registered entrypoints, and tests", skill_text)
        self.assertIn("current canonical docs and accepted ADRs", skill_text)
        self.assertIn("implementation plans, evidence, and reviews", skill_text)
        self.assertIn("optional search indexes", skill_text)
        self.assertIn("Do not create `docs/adr/`", skill_text)
        self.assertIn("New repositories may use `docs/adr/`", skill_text)
        self.assertIn("Existing flat ADR files", skill_text)
        self.assertIn("do not migrate them or rename existing manifest keys", skill_text)
        self.assertNotIn(
            "Then classify older material into:\n\n- `docs/adr/`", skill_text
        )
        self.assertIn("without moving it merely", skill_text)
        self.assertIn("active ADR index or location", portal_text)
        self.assertIn("only when those optional surfaces exist", portal_text)
        self.assertNotIn("- `docs/adr/`", portal_text)
        self.assertNotIn("- `docs/reviews/`", portal_text)
        for trigger in (
            "Small behavior or wording change",
            "Reusable investigation or comparison",
            "Durable structural, authority, or compatibility decision",
            "Multi-stage or multi-file implementation",
            "Performance, security, compatibility, or completion claim",
            "Internal or external patch review",
        ):
            self.assertIn(trigger, skill_text)

        adr_text = template_paths["adr"].read_text(encoding="utf-8")
        for field in (
            "source_of_truth: true",
            "decision_id:",
            "decision_status:",
            "implementation_status:",
            "date:",
            "last_updated:",
            "superseded_by:",
            "implementation_plan:",
            "implementation_evidence:",
            "related:",
        ):
            self.assertIn(field, adr_text)
        self.assertIn("separate from `implementation_status`", adr_text)
        for status in (
            "proposed",
            "accepted",
            "implemented",
            "superseded",
            "rejected",
            "deferred",
            "not_started",
            "in_progress",
            "verified",
            "partial",
        ):
            self.assertIn(status, adr_text)

        evidence_text = template_paths["evidence"].read_text(encoding="utf-8")
        for evidence_contract in (
            "target_fingerprint:",
            "## Environment",
            "## Commands And Results",
            "## Limitations",
            "Do not copy large logs",
        ):
            self.assertIn(evidence_contract, evidence_text)

        decision_text = template_paths["decision"].read_text(encoding="utf-8")
        self.assertIn("source_of_truth: false", decision_text)
        self.assertIn("canonical_decision:", decision_text)
        self.assertIn("derived and non-canonical", decision_text)
        self.assertIn("authority order", agents_text)
        self.assertIn("Do not pre-create optional", agents_text)

        lifecycle_section = skill_text.split(
            "## Adaptive Documentation Authority Lifecycle", 1
        )[1].split("## Repo Memory Link Contract", 1)[0]
        lifecycle_contract = "\n".join(
            [
                lifecycle_section,
                agents_text,
                portal_text,
                *(path.read_text(encoding="utf-8") for path in template_paths.values()),
            ]
        )
        for domain_term in ("BUILD", "ASK", "CHECK", "Pack", "MCP", "ontology"):
            self.assertNotIn(domain_term, lifecycle_contract)

    def test_wiki_markdown_links_resolve_relative_to_each_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_doc(root / "docs" / "CURRENT_STATE.md", "Current State")
            write_doc(
                root / "wiki" / "_meta" / "index.md",
                "Repo Memory Index",
                "- [Current state](../../docs/CURRENT_STATE.md)\n"
                "- [Analysis](../analyses/runtime.md)",
            )
            write_doc(
                root / "wiki" / "analyses" / "runtime.md",
                "Runtime",
                "Legacy [[runtime-note]] remains readable.",
            )

            report = self.validator.ValidationReport(root)
            self.validator.validate_wiki_memory(root, report)

        self.assertEqual(report.errors, [])

    def test_wiki_markdown_links_reject_broken_and_outside_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_doc(
                root / "wiki" / "_meta" / "index.md",
                "Repo Memory Index",
                "- [Missing](../analyses/missing.md)\n"
                "- [Outside](../../../outside.md)",
            )

            report = self.validator.ValidationReport(root)
            self.validator.validate_wiki_memory(root, report)

        codes = {issue["code"] for issue in report.errors}
        self.assertIn("wiki.broken_markdown_link", codes)
        self.assertIn("wiki.markdown_link_outside_repo", codes)

    def test_wiki_link_scan_ignores_code_and_supports_parentheses_and_references(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_doc(root / "docs" / "guide_(v2).md", "Guide")
            write_doc(
                root / "wiki" / "_meta" / "index.md",
                "Repo Memory Index",
                "\n".join(
                    [
                        "`[Inline example](../missing-inline.md)`",
                        "```markdown",
                        "[Fenced example](../missing-fenced.md)",
                        "```",
                        "[Guide](../../docs/guide_(v2).md)",
                        "[Missing reference][missing]",
                        "",
                        "[missing]: ../../docs/missing.md",
                    ]
                ),
            )

            report = self.validator.ValidationReport(root)
            self.validator.validate_wiki_memory(root, report)

        broken = [
            issue
            for issue in report.errors
            if issue["code"] == "wiki.broken_markdown_link"
        ]
        self.assertEqual(len(broken), 1)
        self.assertIn("../../docs/missing.md", broken[0]["message"])

    def test_wiki_link_scan_ignores_footnotes_and_indented_code_and_unescapes_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_doc(root / "docs" / "guide_(v3).md", "Guide")
            write_doc(
                root / "wiki" / "_meta" / "index.md",
                "Repo Memory Index",
                "\n".join(
                    [
                        "Claim.[^1]",
                        "",
                        "[^1]: Supporting prose, not a path.",
                        "",
                        "    [Indented example](../missing-indented.md)",
                        "",
                        r"[Escaped guide](../../docs/guide_\(v3\).md)",
                    ]
                ),
            )

            report = self.validator.ValidationReport(root)
            self.validator.validate_wiki_memory(root, report)

        self.assertEqual(report.errors, [])

    def test_wiki_link_scan_checks_nested_lists_and_nested_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_doc(
                root / "wiki" / "_meta" / "index.md",
                "Repo Memory Index",
                "\n".join(
                    [
                        "- Sources:",
                        "    - [Missing nested](../missing-nested.md)",
                        "\t- [Missing tab](../missing-tab.md)",
                        "- [See [details]](../missing-details.md)",
                        "- Source:",
                        "",
                        "    [Missing continuation](../missing-continuation.md)",
                        "    > [Missing quote](../missing-quote.md)",
                        "1. Ordered source:",
                        "",
                        "    [Missing ordered](../missing-ordered.md)",
                    ]
                ),
            )

            report = self.validator.ValidationReport(root)
            self.validator.validate_wiki_memory(root, report)

        broken_targets = {
            target
            for issue in report.errors
            if issue["code"] == "wiki.broken_markdown_link"
            for target in (
                "../missing-nested.md",
                "../missing-tab.md",
                "../missing-details.md",
                "../missing-continuation.md",
                "../missing-quote.md",
                "../missing-ordered.md",
            )
            if target in issue["message"]
        }
        self.assertEqual(
            broken_targets,
            {
                "../missing-nested.md",
                "../missing-tab.md",
                "../missing-details.md",
                "../missing-continuation.md",
                "../missing-quote.md",
                "../missing-ordered.md",
            },
        )

    def test_finalize_requires_changed_files_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_complete_fixture(root)

            returncode, payload = self.run_validator_command(root, "--finalize")

        self.assertEqual(returncode, 1)
        codes = {issue["code"] for issue in payload["errors"]}
        self.assertIn("drift.changed_files_missing", codes)

    def test_finalize_writes_and_verifies_state_bound_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_complete_fixture(root)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Test"], check=True
            )
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "fixture"], check=True
            )
            changed_files = root / "changed-files.txt"
            changed_files.write_text(
                "docs/IMPACT_SUMMARY.md\nwiki/_meta/log.md\n",
                encoding="utf-8",
            )
            impact_path = root / "docs" / "IMPACT_SUMMARY.md"
            impact_path.write_text(
                impact_path.read_text(encoding="utf-8").replace(
                    "- Created the unified memory profile fixture.",
                    "- Updated `docs/IMPACT_SUMMARY.md`.\n- Updated `wiki/_meta/log.md`.",
                ),
                encoding="utf-8",
            )
            with (root / "wiki" / "_meta" / "log.md").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write("\n- final gate fixture update\n")

            returncode, payload = self.run_validator_command(
                root,
                "--changed-files",
                str(changed_files),
                "--finalize",
            )
            self.assertEqual(returncode, 0, payload)
            self.assertEqual(payload["finalize"]["status"], "written")
            receipt = root / "state" / "repo_docs_finalize.json"
            self.assertTrue(receipt.exists())

            returncode, payload = self.run_validator_command(
                root,
                "--changed-files",
                str(changed_files),
                "--verify-finalized",
            )
            self.assertEqual(returncode, 0, payload)
            self.assertEqual(payload["finalize"]["status"], "verified")

            with (root / "wiki" / "_meta" / "log.md").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write("\n- mutation after review\n")
            returncode, payload = self.run_validator_command(
                root,
                "--changed-files",
                str(changed_files),
                "--verify-finalized",
            )

        self.assertEqual(returncode, 1)
        codes = {issue["code"] for issue in payload["errors"]}
        self.assertIn("finalize.receipt_stale", codes)

    def test_finalize_rejects_unlisted_changed_file_in_impact_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_complete_fixture(root)
            changed_files = root / "changed-files.txt"
            changed_files.write_text("wiki/_meta/log.md\n", encoding="utf-8")

            returncode, payload = self.run_validator_command(
                root,
                "--changed-files",
                str(changed_files),
                "--finalize",
            )

        self.assertEqual(returncode, 1)
        codes = {issue["code"] for issue in payload["errors"]}
        self.assertIn("finalize.impact_summary_changed_files_missing", codes)

    def test_impact_summary_path_coverage_is_exact_and_rejects_placeholders(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            impact = root / "docs" / "IMPACT_SUMMARY.md"
            write_doc(
                impact,
                "Impact Summary",
                "\n".join(
                    [
                        "## Changed",
                        "- Updated `ba.py`.",
                        "",
                        "## Checked Not Changed",
                        "TODO",
                        "",
                        "## Remaining Drift",
                        "- None recorded.",
                        "",
                        "## Validator Summary",
                        "- Expected pass.",
                    ]
                ),
            )
            report = self.validator.ValidationReport(root)
            self.validator.validate_finalize_contract(root, ["a.py"], report)

        codes = {issue["code"] for issue in report.errors}
        self.assertIn("finalize.impact_summary_changed_files_missing", codes)
        self.assertIn("finalize.impact_summary_placeholder", codes)

    def test_registered_entrypoint_must_be_visible_in_repo_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pkg").mkdir(parents=True)
            (root / "pkg" / "cli.py").write_text(
                "def main():\n    return 0\n", encoding="utf-8"
            )
            (root / "pyproject.toml").write_text(
                '[project]\nname = "sample"\nversion = "0.1.0"\n\n'
                '[project.scripts]\nsample = "pkg.cli:main"\n',
                encoding="utf-8",
            )
            write_doc(
                root / "docs" / "CURRENT_STATE.md",
                "Current State",
                "`sample = pkg.cli:main`",
            )
            write_doc(
                root / "docs" / "repo-map" / "ENTRYPOINTS.md",
                "Entrypoints",
                "No CLI listed.",
            )

            report = self.validator.ValidationReport(root)
            self.validator.validate_registered_entrypoints(root, report)

        codes = {issue["code"] for issue in report.warnings}
        self.assertIn("docs.entrypoint_registration_missing", codes)

    def test_registered_entrypoint_must_also_be_visible_in_current_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pkg").mkdir(parents=True)
            (root / "pkg" / "cli.py").write_text(
                "def main():\n    return 0\n", encoding="utf-8"
            )
            (root / "pyproject.toml").write_text(
                '[project]\nname = "sample"\nversion = "0.1.0"\n\n'
                '[project.scripts]\nsample = "pkg.cli:main"\n',
                encoding="utf-8",
            )
            write_doc(
                root / "docs" / "CURRENT_STATE.md",
                "Current State",
                "No exact registration.",
            )
            write_doc(
                root / "docs" / "repo-map" / "ENTRYPOINTS.md",
                "Entrypoints",
                "Run `sample`; registration is `pkg.cli:main`.",
            )

            report = self.validator.ValidationReport(root)
            self.validator.validate_registered_entrypoints(root, report)

        warning_paths = {issue.get("path") for issue in report.warnings}
        self.assertIn("docs/CURRENT_STATE.md", warning_paths)

    def test_entrypoint_docs_require_exact_command_and_target_evidence(self) -> None:
        text = "The application uses `pkg.cli:main` internally."
        self.assertFalse(
            self.validator.entrypoint_is_documented(text, "app", "pkg.cli:main")
        )
        self.assertTrue(
            self.validator.entrypoint_is_documented(
                "Run `app`; registration is `pkg.cli:main`.",
                "app",
                "pkg.cli:main",
            )
        )

    def test_poetry_table_gui_script_and_dotted_target_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pkg").mkdir()
            (root / "pkg" / "cli.py").write_text(
                "class Commands:\n    @staticmethod\n    def run():\n        return 0\n",
                encoding="utf-8",
            )
            (root / "pyproject.toml").write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "sample"',
                        'version = "0.1.0"',
                        "",
                        "[project.gui-scripts]",
                        'sample-gui = "pkg.cli:Commands.run"',
                        "",
                        "[tool.poetry.scripts]",
                        'sample-poetry = { reference = "pkg.cli:Commands.run", type = "console" }',
                    ]
                ),
                encoding="utf-8",
            )

            scripts = self.validator.extract_console_scripts(root)
            report = self.validator.ValidationReport(root)
            self.validator.validate_registered_entrypoints(root, report)

        self.assertEqual(
            scripts,
            [
                ("sample-gui", "pkg.cli:Commands.run"),
                ("sample-poetry", "pkg.cli:Commands.run"),
            ],
        )
        self.assertEqual(report.errors, [])

    def test_unprovable_imported_dotted_target_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cli.py"
            path.write_text("from somewhere import Commands\n", encoding="utf-8")
            self.assertFalse(
                self.validator.module_exposes_symbol(path, "Commands.nonexistent")
            )

    def test_fingerprint_tracks_symlink_target_and_dirty_git_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one.txt").write_text("same\n", encoding="utf-8")
            (root / "two.txt").write_text("same\n", encoding="utf-8")
            link = root / "link.txt"
            link.symlink_to("one.txt")
            first_link = self.validator.state_fingerprint(root, ["link.txt"])
            link.unlink()
            link.symlink_to("two.txt")
            second_link = self.validator.state_fingerprint(root, ["link.txt"])
            self.assertNotEqual(first_link, second_link)

            submodule = root / "submodule"
            subprocess.run(["git", "init", "-q", str(submodule)], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(submodule),
                    "config",
                    "user.email",
                    "test@example.com",
                ],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(submodule), "config", "user.name", "Test"], check=True
            )
            (submodule / "state.txt").write_text("clean\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(submodule), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(submodule), "commit", "-qm", "fixture"], check=True
            )
            clean = self.validator.state_fingerprint(root, ["submodule"])
            (submodule / "state.txt").write_text("dirty\n", encoding="utf-8")
            dirty = self.validator.state_fingerprint(root, ["submodule"])
            self.assertNotEqual(clean, dirty)

    def test_receipt_schema_is_verified_before_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt_path = root / "state" / "repo_docs_finalize.json"
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(
                json.dumps(
                    {
                        "version": 999,
                        "status": "failed",
                        "finalized_at": "not-a-date",
                        "state_fingerprint": "fingerprint",
                        "changed_files": [],
                    }
                ),
                encoding="utf-8",
            )
            report = self.validator.ValidationReport(root)
            self.validator.verify_finalize_receipt(
                receipt_path, [], "fingerprint", report
            )

        codes = {issue["code"] for issue in report.errors}
        self.assertIn("finalize.receipt_schema_invalid", codes)

    def test_receipt_timestamp_requires_timezone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt_path = root / "receipt.json"
            receipt_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "status": "passed",
                        "finalized_at": "2026-08-24T12:00:00",
                        "state_fingerprint": "fingerprint",
                        "changed_files": [],
                    }
                ),
                encoding="utf-8",
            )
            report = self.validator.ValidationReport(root)
            self.validator.verify_finalize_receipt(
                receipt_path, [], "fingerprint", report
            )

        codes = {issue["code"] for issue in report.errors}
        self.assertIn("finalize.receipt_schema_invalid", codes)

    def test_finalize_changed_files_must_match_git_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Test"], check=True
            )
            (root / "a.txt").write_text("a\n", encoding="utf-8")
            (root / "b.txt").write_text("b\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(root), "add", "a.txt", "b.txt"], check=True
            )
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "fixture"], check=True
            )
            (root / "a.txt").write_text("changed a\n", encoding="utf-8")
            (root / "b.txt").write_text("changed b\n", encoding="utf-8")
            changed_files_path = Path(tmp).parent / f"{root.name}-changed-files.txt"
            changed_files_path.write_text("a.txt\n", encoding="utf-8")
            self.addCleanup(changed_files_path.unlink, missing_ok=True)

            report = self.validator.ValidationReport(root)
            self.validator.validate_git_changed_file_coverage(
                root,
                ["a.txt"],
                changed_files_path,
                root / "state" / "repo_docs_finalize.json",
                report,
            )

        codes = {issue["code"] for issue in report.errors}
        self.assertIn("finalize.changed_files_incomplete", codes)

    def test_git_coverage_supports_repo_profile_below_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            git_root = Path(tmp)
            profile_root = git_root / "profile"
            profile_root.mkdir()
            subprocess.run(["git", "init", "-q", str(git_root)], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(git_root),
                    "config",
                    "user.email",
                    "test@example.com",
                ],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(git_root), "config", "user.name", "Test"], check=True
            )
            (profile_root / "inside.txt").write_text("inside\n", encoding="utf-8")
            (git_root / "outside.txt").write_text("outside\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(git_root), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(git_root), "commit", "-qm", "fixture"], check=True
            )
            (profile_root / "inside.txt").write_text(
                "changed inside\n", encoding="utf-8"
            )
            (git_root / "outside.txt").write_text("changed outside\n", encoding="utf-8")

            observed, status = self.validator.collect_git_changed_files(profile_root)

        self.assertEqual(status, "ok")
        self.assertEqual(observed, {"inside.txt"})


if __name__ == "__main__":
    unittest.main()
