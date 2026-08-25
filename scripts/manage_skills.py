#!/usr/bin/env python3
"""Validate or install DocTology's three public skills."""

from __future__ import annotations

import argparse
import filecmp
import shutil
import tempfile
from pathlib import Path


SKILLS = (
    "llm-wiki-bootstrap",
    "llm-wiki-loop",
    "repo-docs-intelligence-bootstrap",
)
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".agents" / "skills"


def validate_source() -> list[str]:
    errors: list[str] = []
    actual = sorted(path.name for path in SOURCE.iterdir() if path.is_dir())
    if actual != sorted(SKILLS):
        errors.append(f"active skills must be exactly {', '.join(SKILLS)}; found {actual}")
    for name in SKILLS:
        skill = SOURCE / name
        if not (skill / "SKILL.md").is_file():
            errors.append(f"missing {skill.relative_to(ROOT) / 'SKILL.md'}")
    return errors


def same_tree(left: Path, right: Path) -> bool:
    if not right.is_dir():
        return False
    comparison = filecmp.dircmp(left, right, ignore=["__pycache__", ".DS_Store"])
    if comparison.left_only or comparison.right_only or comparison.funny_files:
        return False
    if any(not filecmp.cmp(left / name, right / name, shallow=False) for name in comparison.common_files):
        return False
    return all(same_tree(left / name, right / name) for name in comparison.common_dirs)


def install(target: Path, dry_run: bool) -> int:
    errors = validate_source()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    target = target.expanduser().resolve()
    if target == SOURCE or SOURCE in target.parents:
        print(f"ERROR: target must not be the canonical source tree: {target}")
        return 1
    for name in SKILLS:
        source = SOURCE / name
        destination = target / name
        if same_tree(source, destination):
            print(f"CURRENT {name}")
            continue
        print(f"{'WOULD_SYNC' if dry_run else 'SYNCED'} {name} -> {destination}")
        if dry_run:
            continue
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{name}-", dir=target) as temporary:
            staged = Path(temporary) / name
            shutil.copytree(source, staged, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
            backup = Path(temporary) / f"{name}.previous"
            if destination.exists() or destination.is_symlink():
                destination.replace(backup)
            try:
                staged.replace(destination)
            except Exception:
                if (backup.exists() or backup.is_symlink()) and not (
                    destination.exists() or destination.is_symlink()
                ):
                    backup.replace(destination)
                raise
            if backup.exists() or backup.is_symlink():
                if backup.is_dir() and not backup.is_symlink():
                    shutil.rmtree(backup)
                else:
                    backup.unlink()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "install"))
    parser.add_argument("--target", type=Path, default=Path.home() / ".codex" / "skills")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.command == "check":
        errors = validate_source()
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print("OK: exactly three self-contained DocTology skills")
        return 0
    return install(args.target, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
