#!/usr/bin/env python3
"""Standalone entrypoint for the LLM Wiki loop runtime.

The runtime lives with this skill and operates a target wiki through --repo-root.
It never installs or overwrites executable files in that target repository.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


def load_sibling(name: str) -> Any:
    path = SCRIPT_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"wiki_loop_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load loop runtime module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


workflow = load_sibling("wiki_workflow")
RUNTIME_NAME = workflow.RUNTIME_NAME
RUNTIME_VERSION = workflow.RUNTIME_VERSION


def preflight(start: Path) -> dict[str, object]:
    root = start.expanduser().resolve()
    if not root.is_dir():
        return {
            "state": "not_ready",
            "runtime": RUNTIME_NAME,
            "runtime_version": RUNTIME_VERSION,
            "reason": f"target repository is not a directory: {root}",
        }
    missing = []
    if not (root / "AGENTS.md").is_file():
        missing.append("AGENTS.md (file)")
    for relative in ("raw", "wiki"):
        if not (root / relative).is_dir():
            missing.append(f"{relative} (directory)")
    reasons = []
    if missing:
        reasons.append("missing required wiki surfaces: " + ", ".join(missing))
    if (root / "warehouse" / "jsonl").exists():
        reasons.append("canonical ontology workspace is incompatible with wiki-only loop")
    legacy_runtime = [
        relative
        for relative in (
            "scripts/wiki_workflow.py",
            "scripts/wiki_batch.py",
            "scripts/pipeline_check.py",
        )
        if (root / relative).is_file()
    ]
    return {
        "state": "not_ready" if reasons else "ready",
        "repo_root": str(root),
        "runtime": RUNTIME_NAME,
        "runtime_version": RUNTIME_VERSION,
        "contract_digest": workflow.procedure_contract_digest(),
        "sqlite": "on" if (root / "scripts" / "wiki_retrieval.py").is_file() else "off",
        "legacy_repo_runtime": legacy_runtime,
        "reasons": reasons,
        "runtime_installation": "not_required",
    }


def dispatch(repo_root: Path, command: str, remainder: list[str]) -> int:
    status = preflight(repo_root)
    if status["state"] != "ready":
        print(json.dumps(status, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    if any(argument == "--root" or argument.startswith("--root=") for argument in remainder):
        print(
            json.dumps(
                {
                    "state": "not_ready",
                    "runtime": RUNTIME_NAME,
                    "runtime_version": RUNTIME_VERSION,
                    "reason": "nested --root is forbidden; use only wiki_loop.py --repo-root",
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    script_name = {
        "workflow": "wiki_workflow.py",
        "batch": "wiki_batch.py",
        "check": "pipeline_check.py",
    }[command]
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / script_name),
            "--root",
            str(status["repo_root"]),
            *remainder,
        ],
        check=False,
    )
    return completed.returncode


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--repo-root", default=".", help="Target wiki repository.")
    result.add_argument(
        "command",
        choices=("preflight", "workflow", "batch", "check"),
        help="preflight or the internal runtime lane to invoke",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args, remainder = parser().parse_known_args(argv)
    if remainder[:1] == ["--"]:
        remainder = remainder[1:]
    if args.command == "preflight":
        if remainder:
            parser().error("preflight does not accept a nested command")
        result = preflight(Path(args.repo_root))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["state"] == "ready" else 1
    return dispatch(Path(args.repo_root), args.command, remainder)


if __name__ == "__main__":
    raise SystemExit(main())
