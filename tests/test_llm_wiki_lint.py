from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = (
    ROOT
    / ".agents"
    / "skills"
    / "llm-wiki-bootstrap"
    / "scripts"
    / "bootstrap_llm_wiki.py"
)


def load_bootstrap():
    spec = importlib.util.spec_from_file_location("bootstrap_for_lint_test", BOOTSTRAP)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PAGE = """---
title: {title}
type: concept
status: active
---

# {title}

{body}
"""


class LlmWikiLintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bootstrap = load_bootstrap()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "vault"
        self.bootstrap.scaffold(self.root, force=False, sqlite_enabled=False)

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.root / "scripts" / "llm_wiki.py"), *arguments],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )

    def write_concept(self, name: str, body: str) -> None:
        (self.root / "wiki" / "concepts" / f"{name}.md").write_text(
            PAGE.format(title=name.title(), body=body), encoding="utf-8"
        )

    def test_meta_index_and_self_link_do_not_hide_orphan(self) -> None:
        self.write_concept("lonely", "[[lonely]]")
        self.assertEqual(self.run_cli("reindex").returncode, 0)

        advisory = self.run_cli("lint")
        strict = self.run_cli("lint", "--strict-orphans")

        self.assertEqual(advisory.returncode, 0, advisory.stdout + advisory.stderr)
        self.assertIn("wiki/concepts/lonely.md", advisory.stdout)
        self.assertEqual(strict.returncode, 1, strict.stdout + strict.stderr)

    def test_non_meta_inbound_link_resolves_orphan(self) -> None:
        self.write_concept("target", "Reusable target.")
        self.write_concept("linker", "See [[target]].")
        self.assertEqual(self.run_cli("reindex").returncode, 0)

        result = self.run_cli("lint")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("wiki/concepts/target.md", result.stdout)
        self.assertIn("wiki/concepts/linker.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
