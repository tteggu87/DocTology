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
COMMANDS = ("preflight", "workflow", "batch", "check")
CHILD_SCRIPTS = {
    "workflow": "wiki_workflow.py",
    "batch": "wiki_batch.py",
    "check": "pipeline_check.py",
}


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
    script_name = CHILD_SCRIPTS[command]
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


def help_request(argv: list[str]) -> tuple[str, list[str]] | None:
    """Return a lane and its arguments when a lane-specific help was requested."""
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--repo-root":
            index += 2
            continue
        if token.startswith("--repo-root=") or token in {"-h", "--help"}:
            index += 1
            continue
        if token in COMMANDS:
            remainder = argv[index + 1 :]
            return (token, remainder) if any(
                argument in {"-h", "--help"} for argument in remainder
            ) else None
        return None
    return None


def show_help(command: str, remainder: list[str]) -> int:
    if command == "preflight":
        print(
            "usage: wiki_loop.py [--repo-root TARGET_REPO] preflight\n\n"
            "Validate one exact wiki-only target before running the loop.\n\n"
            "The target must contain AGENTS.md, raw/, and wiki/."
        )
        return 0
    module = workflow if command == "workflow" else load_sibling(
        "wiki_batch" if command == "batch" else "pipeline_check"
    )
    try:
        module.build_parser(prog=f"wiki_loop.py {command}").parse_args(remainder)
    except SystemExit as exc:
        return int(exc.code)
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    result.add_argument("--repo-root", default=".", help="Target wiki repository.")
    result.add_argument(
        "command",
        choices=COMMANDS,
        help="preflight or the internal runtime lane to invoke",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    requested_help = help_request(arguments)
    if requested_help is not None:
        return show_help(*requested_help)
    args, remainder = parser().parse_known_args(arguments)
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
