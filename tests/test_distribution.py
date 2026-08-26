from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "scripts" / "manage_skills.py"
SKILLS = {"llm-wiki-bootstrap", "llm-wiki-loop", "repo-docs-intelligence-bootstrap"}


class DistributionTests(unittest.TestCase):
    def run_manager(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MANAGER), *args], cwd=ROOT, text=True,
            capture_output=True, check=False,
        )

    def test_check_accepts_exact_public_inventory(self) -> None:
        result = self.run_manager("check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            {path.name for path in (ROOT / ".agents" / "skills").iterdir() if path.is_dir()},
            SKILLS,
        )

    def test_install_is_complete_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "skills"
            first = self.run_manager("install", "--target", str(target))
            second = self.run_manager("install", "--target", str(target))
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual({path.name for path in target.iterdir()}, SKILLS)
            self.assertEqual(second.stdout.count("CURRENT "), 3)
            loop = target / "llm-wiki-loop"
            self.assertTrue((loop / "scripts" / "wiki_loop.py").is_file())
            skill_text = (loop / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn('"<SKILL_DIR>/scripts/wiki_loop.py"', skill_text)
            self.assertNotIn("python scripts/wiki_loop.py", skill_text)

    def test_install_rejects_canonical_source_as_target(self) -> None:
        source = ROOT / ".agents" / "skills"
        result = self.run_manager("install", "--target", str(source))
        self.assertEqual(result.returncode, 1)
        self.assertIn("must not be the canonical source tree", result.stdout)

    def test_install_replaces_file_or_symlink_destination(self) -> None:
        for kind in ("file", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary) / "skills"
                target.mkdir()
                destination = target / "llm-wiki-bootstrap"
                if kind == "file":
                    destination.write_text("stale", encoding="utf-8")
                else:
                    destination.symlink_to(target / "missing-skill")
                result = self.run_manager("install", "--target", str(target))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue((destination / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
