#!/usr/bin/env python3
"""Run a read-only Repo Docs compatibility inventory and validator dogfood pass."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


CANONICAL_DOCS = (
    "README.md",
    "CURRENT_STATE.md",
    "ARCHITECTURE.md",
    "LAYERS.md",
    "SKILLS_INTEGRATION.md",
    "ROADMAP.md",
    "IMPACT_SUMMARY.md",
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


def repository_entries(root: Path) -> list[Path]:
    """Return every repository entry except Git's private storage."""
    return sorted(
        path for path in root.rglob("*") if ".git" not in path.relative_to(root).parts
    )


def documentation_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    agents = root / "AGENTS.md"
    if agents.is_file():
        paths.append(agents)
    for directory in (root / "docs", root / "wiki", root / "intelligence"):
        if directory.is_dir():
            paths.extend(path for path in directory.rglob("*") if path.is_file())
    return sorted(set(paths))


def fingerprint(root: Path) -> str:
    """Fingerprint all entry names, kinds, sizes, modes, mtimes, and link targets."""
    digest = hashlib.sha256()
    for path in repository_entries(root):
        relative = path.relative_to(root).as_posix()
        stat = path.lstat()
        if path.is_symlink():
            detail = f"link:{path.readlink()}"
        elif path.is_dir():
            detail = "directory"
        else:
            content_digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    content_digest.update(chunk)
            detail = (
                f"file:{stat.st_size}:{stat.st_mtime_ns}:{content_digest.hexdigest()}"
            )
        digest.update(f"{relative}\0{stat.st_mode}\0{detail}\n".encode("utf-8"))
    return digest.hexdigest()


def count_markdown(paths: list[Path]) -> int:
    return sum(path.suffix.lower() == ".md" for path in paths)


def inventory(root: Path) -> dict[str, object]:
    docs = root / "docs"
    wiki = root / "wiki"
    canonical = [name for name in CANONICAL_DOCS if (docs / name).is_file()]
    flat_adrs = sorted(docs.glob("ADR*.md")) if docs.is_dir() else []
    plan_paths = set(docs.glob("*PLAN*.md")) if docs.is_dir() else set()
    if (docs / "plans").is_dir():
        plan_paths.update((docs / "plans").rglob("*.md"))
    evidence = (
        list((docs / "evidence").rglob("*.md")) if (docs / "evidence").is_dir() else []
    )
    reviews = (
        list((docs / "reviews").rglob("*.md")) if (docs / "reviews").is_dir() else []
    )
    repo_map = (
        list((docs / "repo-map").rglob("*.md")) if (docs / "repo-map").is_dir() else []
    )
    decisions = (
        list((wiki / "decisions").rglob("*.md"))
        if (wiki / "decisions").is_dir()
        else []
    )
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in documentation_files(root)
        if path.suffix.lower() == ".md"
    )

    def relative(paths: list[Path] | set[Path]) -> list[str]:
        return sorted(path.relative_to(root).as_posix() for path in paths)

    return {
        "canonical_docs": {
            "count": len(canonical),
            "expected": len(CANONICAL_DOCS),
            "paths": [f"docs/{name}" for name in canonical],
        },
        "flat_adrs": {"count": len(flat_adrs), "paths": relative(flat_adrs)},
        "plans": {"count": len(plan_paths), "paths": relative(plan_paths)},
        "evidence": {"count": count_markdown(evidence), "paths": relative(evidence)},
        "reviews": {"count": count_markdown(reviews), "paths": relative(reviews)},
        "repo_map": {"count": count_markdown(repo_map), "paths": relative(repo_map)},
        "wiki_decisions": {
            "count": count_markdown(decisions),
            "paths": relative(decisions),
        },
        "legacy_wikilinks": len(re.findall(r"\[\[[^\]]+\]\]", text)),
    }


def validate_inventory(root: Path, observed: dict[str, object]) -> list[str]:
    """Apply compatibility-safe checks without imposing new lifecycle metadata."""
    issues: list[str] = []
    for surface in SURFACES:
        details = observed[surface]
        for raw_path in details["paths"]:
            path = root / raw_path
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                issues.append(f"{raw_path}: unreadable Markdown ({exc})")
                continue
            if not text.strip():
                issues.append(f"{raw_path}: empty Markdown")
            elif not re.search(r"^#{1,6}\s+\S", text, re.MULTILINE):
                issues.append(f"{raw_path}: no Markdown heading")
    expected_repo_map = {
        "docs/repo-map/README.md",
        "docs/repo-map/ENTRYPOINTS.md",
        "docs/repo-map/MODULES.md",
        "docs/repo-map/DATA_FLOW.md",
        "docs/repo-map/SYMBOL_GRAPH.md",
    }
    repo_map_paths = set(observed["repo_map"]["paths"])
    if repo_map_paths and not expected_repo_map.issubset(repo_map_paths):
        missing = sorted(expected_repo_map - repo_map_paths)
        issues.append(f"repo_map: missing conventional pages {missing}")
    for raw_path in observed["wiki_decisions"]["paths"]:
        text = (root / raw_path).read_text(encoding="utf-8", errors="replace")
        match = re.search(
            r"^source_of_truth:\s*(\S+)", text, re.MULTILINE | re.IGNORECASE
        )
        if match and match.group(1).lower() not in {"false", "no"}:
            issues.append(f"{raw_path}: derived decision claims canonical truth")
    return issues


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--repo-root", required=True)
    result.add_argument(
        "--validator",
        default=str(Path(__file__).with_name("validate_repo_docs_intelligence.py")),
    )
    result.add_argument(
        "--require-surface", action="append", choices=SURFACES, default=[]
    )
    result.add_argument(
        "--allow-validator-error-code",
        action="append",
        default=[],
        help="Explicit target-drift code allowed as a reported caution; all other errors fail.",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path(args.repo_root).resolve()
    validator = Path(args.validator).resolve()
    if not root.is_dir() or not validator.is_file():
        print(
            json.dumps(
                {"status": "failed", "error": "repo root or validator is missing"}
            )
        )
        return 2
    before = fingerprint(root)
    observed = inventory(root)
    surface_issues = validate_inventory(root, observed)
    result = subprocess.run(
        [sys.executable, str(validator), "--repo-root", str(root), "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )
    after = fingerprint(root)
    try:
        validation = json.loads(result.stdout)
    except json.JSONDecodeError:
        validation = {"summary": {"status": "invalid_output"}, "stderr": result.stderr}
    missing = [
        name
        for name in args.require_surface
        if int(observed[name]["count"]) == 0
        or (
            name == "canonical_docs"
            and observed[name]["count"] != observed[name]["expected"]
        )
    ]
    read_only = before == after
    error_codes = Counter(issue["code"] for issue in validation.get("errors", []))
    reported_codes = set(error_codes)
    allowed_codes = set(args.allow_validator_error_code)
    validator_passed = (
        result.returncode == 0
        and validation.get("summary", {}).get("status") == "passed"
        and not reported_codes
    )
    validator_accepted_drift = (
        result.returncode == 1
        and bool(reported_codes)
        and reported_codes.issubset(allowed_codes)
    )
    validator_status = (
        "passed"
        if validator_passed
        else "accepted_target_drift"
        if validator_accepted_drift
        else "failed"
    )
    overall_passed = (
        read_only
        and not missing
        and not surface_issues
        and validator_status != "failed"
    )
    payload = {
        "repo_root": str(root),
        "status": (
            "passed_with_cautions"
            if overall_passed and validator_status == "accepted_target_drift"
            else "passed"
            if overall_passed
            else "failed"
        ),
        "read_only": read_only,
        "required_surfaces_missing": missing,
        "surface_validation": {
            "status": "passed" if not surface_issues else "failed",
            "issues": surface_issues,
        },
        "inventory": observed,
        "validator": {
            "status": validator_status,
            "returncode": result.returncode,
            "summary": validation.get("summary", {}),
            "error_codes": dict(sorted(error_codes.items())),
            "allowed_error_codes": sorted(allowed_codes),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
