from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOGFOOD = (
    ROOT
    / ".agents"
    / "skills"
    / "repo-docs-intelligence-bootstrap"
    / "scripts"
    / "repo_docs_dogfood.py"
)
SURFACES = (
    "canonical_docs",
    "flat_adrs",
    "plans",
    "evidence",
    "reviews",
    "repo_map",
    "wiki_decisions",
)


class RepoDocsDogfoodTests(unittest.TestCase):
    def make_repo(self, root: Path) -> None:
        for name in (
            "README.md",
            "CURRENT_STATE.md",
            "ARCHITECTURE.md",
            "LAYERS.md",
            "SKILLS_INTEGRATION.md",
            "ROADMAP.md",
            "IMPACT_SUMMARY.md",
        ):
            path = root / "docs" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "---\nstatus: active\nsource_of_truth: false\n---\n# Doc\n",
                encoding="utf-8",
            )
        for relative in (
            "docs/ADR_FLAT.md",
            "docs/LEGACY_PLAN.md",
            "docs/evidence/legacy.md",
            "docs/reviews/legacy.md",
            "docs/repo-map/README.md",
            "docs/repo-map/ENTRYPOINTS.md",
            "docs/repo-map/MODULES.md",
            "docs/repo-map/DATA_FLOW.md",
            "docs/repo-map/SYMBOL_GRAPH.md",
            "wiki/decisions/legacy.md",
        ):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            body = (
                "---\nsource_of_truth: false\n---\n"
                if "wiki/decisions" in relative
                else ""
            )
            path.write_text(f"{body}# Legacy [[memory]]\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "runtime.py").write_text("VALUE = 1\n", encoding="utf-8")

    def make_validator(
        self,
        root: Path,
        *,
        returncode: int,
        error_code: str | None = None,
        mutation: str = "",
    ) -> Path:
        validator = root.parent / f"validator-{returncode}-{bool(mutation)}.py"
        errors = [] if error_code is None else [{"code": error_code}]
        status = "passed" if returncode == 0 else "failed"
        validator.write_text(
            "import json\nimport os\nfrom pathlib import Path\nimport sys\n"
            "root = Path(sys.argv[sys.argv.index('--repo-root') + 1])\n"
            f"{mutation}\n"
            f"print(json.dumps({{'summary': {{'status': '{status}'}}, "
            f"'errors': {errors!r}, 'warnings': []}}))\n"
            f"raise SystemExit({returncode})\n",
            encoding="utf-8",
        )
        return validator

    def run_dogfood(
        self, root: Path, validator: Path, *extra: str
    ) -> subprocess.CompletedProcess[str]:
        requirements = [
            item for surface in SURFACES for item in ("--require-surface", surface)
        ]
        return subprocess.run(
            [
                sys.executable,
                "-S",
                str(DOGFOOD),
                "--repo-root",
                str(root),
                "--validator",
                str(validator),
                *requirements,
                *extra,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_inventory_is_read_only_and_validates_all_legacy_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            self.make_repo(root)
            validator = self.make_validator(root, returncode=0)
            before = {
                path: path.read_bytes() for path in root.rglob("*") if path.is_file()
            }

            result = self.run_dogfood(root, validator)
            after = {
                path: path.read_bytes() for path in root.rglob("*") if path.is_file()
            }

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["surface_validation"]["status"], "passed")
        self.assertTrue(
            all(payload["inventory"][surface]["paths"] for surface in SURFACES)
        )
        self.assertEqual(before, after)

    def test_validator_failure_fails_unless_code_is_explicitly_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            self.make_repo(root)
            validator = self.make_validator(
                root, returncode=1, error_code="wiki.broken_markdown_link"
            )

            failed = self.run_dogfood(root, validator)
            accepted = self.run_dogfood(
                root,
                validator,
                "--allow-validator-error-code",
                "wiki.broken_markdown_link",
            )

        self.assertEqual(failed.returncode, 1)
        self.assertEqual(json.loads(failed.stdout)["status"], "failed")
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout)["status"], "passed_with_cautions")

    def test_mutation_outside_documentation_fails_read_only_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            self.make_repo(root)
            validator = self.make_validator(
                root,
                returncode=0,
                mutation=(
                    "(root / 'src' / 'runtime.py').write_text('VALUE = 2\\n')\n"
                    "(root / 'new-dir').mkdir()"
                ),
            )

            result = self.run_dogfood(root, validator)

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertFalse(payload["read_only"])

    def test_equal_size_mutation_with_restored_mtime_fails_read_only_check(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            self.make_repo(root)
            validator = self.make_validator(
                root,
                returncode=0,
                mutation=(
                    "path = root / 'src' / 'runtime.py'\n"
                    "stat = path.stat()\n"
                    "path.write_text('VALUE = 2\\n')\n"
                    "os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))"
                ),
            )

            result = self.run_dogfood(root, validator)

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertFalse(payload["read_only"])


if __name__ == "__main__":
    unittest.main()
