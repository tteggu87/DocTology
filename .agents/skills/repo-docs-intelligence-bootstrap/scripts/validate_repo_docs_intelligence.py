#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Final

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


CURRENT_DOCS: Final = [
    "README.md",
    "CURRENT_STATE.md",
    "ARCHITECTURE.md",
    "LAYERS.md",
    "SKILLS_INTEGRATION.md",
    "ROADMAP.md",
    "IMPACT_SUMMARY.md",
]

WIKI_MEMORY_PATHS: Final = [
    "wiki/_meta/index.md",
    "wiki/_meta/log.md",
    "wiki/analyses",
    "wiki/sources",
    "wiki/concepts",
    "wiki/projects",
]

PATHLIKE_EXTENSIONS = (".md", ".yaml", ".yml", ".sql", ".py")
IMPACT_SUMMARY_REQUIRED_SECTIONS = (
    "changed",
    "checked not changed",
    "remaining drift",
    "validator summary",
)
LEGACY_VISIBILITY_HINTS = (
    "intentional legacy",
    "transitional",
    "still live",
    "still imported",
    "runtime dependency",
    "legacy support",
)
NEGATING_HINTS = (
    "none recorded",
    "not recorded",
    "not clearly",
    "does not clearly",
    "not yet",
)


class ValidationReport:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.errors: list[dict[str, str]] = []
        self.warnings: list[dict[str, str]] = []

    def add_error(self, code: str, message: str, path: Path | None = None) -> None:
        self.errors.append(self._make_issue("error", code, message, path))

    def add_warning(self, code: str, message: str, path: Path | None = None) -> None:
        self.warnings.append(self._make_issue("warning", code, message, path))

    def _make_issue(self, level: str, code: str, message: str, path: Path | None) -> dict[str, str]:
        issue = {"level": level, "code": code, "message": message}
        if path is not None:
            issue["path"] = self._display_path(path)
        return issue

    def _display_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.repo_root.resolve()).as_posix()
        except Exception:
            return path.as_posix()

    def print_text(self) -> None:
        print(f"Repo root: {self.repo_root}")
        print(f"Errors: {len(self.errors)}")
        print(f"Warnings: {len(self.warnings)}")
        if self.errors:
            print("\nErrors:")
            for issue in self.errors:
                location = f" ({issue['path']})" if "path" in issue else ""
                print(f"- [{issue['code']}] {issue['message']}{location}")
        if self.warnings:
            print("\nWarnings:")
            for issue in self.warnings:
                location = f" ({issue['path']})" if "path" in issue else ""
                print(f"- [{issue['code']}] {issue['message']}{location}")

    def as_json(self) -> str:
        return json.dumps(
            {
                "repo_root": str(self.repo_root),
                "summary": {
                    "status": "failed" if self.errors else "passed",
                    "errors": len(self.errors),
                    "warnings": len(self.warnings),
                },
                "errors": self.errors,
                "warnings": self.warnings,
            },
            indent=2,
        )


def normalize_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def normalize_truth_value(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value).strip().lower()


def parse_doc_metadata(text: str) -> dict[str, str]:
    lines = text.splitlines()
    metadata: dict[str, str] = {}
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" not in line:
                continue
            key, raw_value = line.split(":", 1)
            metadata[normalize_key(key)] = raw_value.strip()
        if metadata:
            return metadata

    for line in lines[:12]:
        match = re.match(r"-\s*([^:]+):\s*(.+)", line.strip())
        if match:
            metadata[normalize_key(match.group(1))] = match.group(2).strip()
    return metadata


def scan_markdown_refs(text: str) -> list[str]:
    refs: list[str] = []
    for candidate in re.findall(r"`([^`]+)`", text):
        candidate = candidate.strip()
        if candidate.startswith(("http://", "https://")):
            continue
        if candidate == "AGENTS.md" or "/" in candidate or candidate.endswith(PATHLIKE_EXTENSIONS):
            refs.append(candidate)
    return sorted(set(refs))


def load_yaml(path: Path, report: ValidationReport) -> object | None:
    if not path.exists():
        return None
    if yaml is None:
        report.add_error(
            "yaml.missing_dependency",
            "PyYAML is required to validate YAML manifests in this repository.",
            path,
        )
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        report.add_error("yaml.parse_failed", f"Failed to parse YAML: {exc}", path)
        return None


def section_key_field(key: str) -> str:
    key_fields = {
        "terms": "term",
        "datasets": "dataset_key",
    }
    return key_fields.get(key, "key")


def load_list_section(path: Path, key: str, report: ValidationReport) -> list[dict[str, object]] | None:
    data = load_yaml(path, report)
    if data is None:
        return None
    if not isinstance(data, dict):
        report.add_error("yaml.invalid_root", "YAML root must be a mapping.", path)
        return None
    section = data.get(key)
    if section is None:
        report.add_error("yaml.missing_section", f"Missing top-level `{key}` section.", path)
        return None
    items: list[dict[str, object]] = []
    if isinstance(section, list):
        for item in section:
            if not isinstance(item, dict):
                report.add_error("yaml.invalid_item", f"Each item in `{key}` must be a mapping.", path)
                continue
            items.append(item)
        return items
    if isinstance(section, dict):
        for item_key, raw_item in section.items():
            if raw_item is None:
                raw_item = {}
            if not isinstance(raw_item, dict):
                report.add_error(
                    "yaml.invalid_item",
                    f"Each mapping value in `{key}` must be a mapping.",
                    path,
                )
                continue
            item = dict(raw_item)
            key_field = section_key_field(key)
            if not item.get(key_field):
                item[key_field] = str(item_key)
            items.append(item)
        return items
    report.add_error(
        "yaml.invalid_section",
        f"`{key}` must be either a list of mappings or a mapping of keys to mappings.",
        path,
    )
    return None


def keyed_items(
    items: list[dict[str, object]] | None,
    key_field: str,
    report: ValidationReport,
    path: Path,
) -> dict[str, dict[str, object]]:
    if not items:
        return {}
    result: dict[str, dict[str, object]] = {}
    for item in items:
        value = item.get(key_field)
        if not value:
            report.add_error("yaml.missing_key", f"Missing required `{key_field}` field in item.", path)
            continue
        key = str(value)
        if key in result:
            report.add_error("yaml.duplicate_key", f"Duplicate `{key_field}` value `{key}`.", path)
            continue
        result[key] = item
    return result


def validate_doc_metadata(path: Path, report: ValidationReport) -> None:
    metadata = parse_doc_metadata(path.read_text(encoding="utf-8"))
    missing = [key for key in ("status", "source_of_truth") if key not in metadata]
    if missing:
        report.add_error(
            "docs.missing_metadata",
            f"Missing required metadata fields: {', '.join(missing)}.",
            path,
        )
        return
    source_value = normalize_truth_value(metadata["source_of_truth"])
    if source_value not in {"yes", "no", "true", "false"}:
        report.add_error(
            "docs.invalid_source_of_truth",
            "Source of truth metadata must be Yes/No or true/false.",
            path,
        )


def validate_markdown_refs(path: Path, repo_root: Path, report: ValidationReport) -> None:
    for ref in scan_markdown_refs(path.read_text(encoding="utf-8")):
        if ":" in ref and not ref.startswith(("docs/", "intelligence/", "scripts/", "AGENTS.md")):
            continue
        if not (repo_root / ref).exists():
            report.add_error("docs.broken_reference", f"Referenced path `{ref}` does not exist.", path)


def validate_archive_banners(archive_dir: Path, report: ValidationReport) -> None:
    for path in archive_dir.rglob("*.md"):
        top = "\n".join(path.read_text(encoding="utf-8").splitlines()[:8])
        if "Status: Archived" not in top or "Source of Truth: No" not in top:
            report.add_error(
                "docs.archive_banner_missing",
                "Archived docs must include `Status: Archived` and `Source of Truth: No` near the top.",
                path,
            )


def resolve_module_file(repo_root: Path, module_path: str) -> Path | None:
    module_parts = module_path.split(".")
    candidates = [
        repo_root.joinpath(*module_parts).with_suffix(".py"),
        repo_root.joinpath(*module_parts, "__init__.py"),
        repo_root / "src" / Path(*module_parts).with_suffix(".py"),
        repo_root / "src" / Path(*module_parts) / "__init__.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def extract_console_scripts(repo_root: Path) -> list[tuple[str, str]]:
    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.exists():
        return []
    text = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r"^\[project\.scripts\]\s*$([\s\S]*?)(?=^\[|\Z)", text, re.MULTILINE)
    if not match:
        return []

    scripts: list[tuple[str, str]] = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        scripts.append((name.strip(), value.strip().strip("\"'")))
    return scripts


def collect_live_legacy_dependencies(repo_root: Path) -> list[Path]:
    legacy_paths: set[Path] = set()
    for path in repo_root.rglob("*.py"):
        if any(part.startswith(".") for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for module_name in re.findall(r"^\s*from\s+([A-Za-z0-9_\.]+)\s+import\s+", text, re.MULTILINE):
            if "legacy" not in module_name.lower():
                continue
            resolved = resolve_module_file(repo_root, module_name)
            if resolved is not None:
                legacy_paths.add(resolved)
        for module_name in re.findall(r"^\s*import\s+([A-Za-z0-9_\.]+)", text, re.MULTILINE):
            if "legacy" not in module_name.lower():
                continue
            primary_name = module_name.split(",", 1)[0].strip()
            resolved = resolve_module_file(repo_root, primary_name)
            if resolved is not None:
                legacy_paths.add(resolved)
    return sorted(legacy_paths)


def validate_impact_summary_sections(path: Path, report: ValidationReport) -> None:
    text = path.read_text(encoding="utf-8").lower()
    aliases = {
        "changed": ("## changed",),
        "checked not changed": (
            "## checked not changed",
            "## checked-not-changed",
            "## checked but did not need changes",
        ),
        "remaining drift": ("## remaining drift",),
        "validator summary": ("## validator summary",),
    }
    missing = [section for section, options in aliases.items() if not any(option in text for option in options)]
    if missing:
        report.add_error(
            "docs.impact_summary_incomplete",
            "Impact summary is missing required sections: " + ", ".join(missing) + ".",
            path,
        )


def extract_markdown_section(text: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def validate_current_state_visibility(current_state_path: Path, repo_root: Path, report: ValidationReport) -> None:
    text = current_state_path.read_text(encoding="utf-8")
    normalized_text = text.lower()
    transitional_section = extract_markdown_section(text, "Transitional Facts").lower()
    current_truth_section = extract_markdown_section(text, "Current Truth").lower()
    visibility_sections = "\n".join(part for part in (transitional_section, current_truth_section) if part)

    missing_console_scripts: list[str] = []
    for script_name, target in extract_console_scripts(repo_root):
        target_path = ""
        if ":" in target:
            module_name, _symbol = target.split(":", 1)
            module_file = resolve_module_file(repo_root, module_name)
            if module_file is not None:
                target_path = module_file.relative_to(repo_root).as_posix().lower()
        script_name_lc = script_name.lower()
        if script_name_lc in normalized_text:
            continue
        if target.lower() in normalized_text:
            continue
        if target_path and target_path in normalized_text:
            continue
        missing_console_scripts.append(script_name)

    if missing_console_scripts:
        report.add_warning(
            "docs.current_state_missing_console_script",
            "Current state docs do not mention console script(s): " + ", ".join(sorted(missing_console_scripts)) + ".",
            current_state_path,
        )

    unreported_legacy_paths: list[str] = []
    for legacy_path in collect_live_legacy_dependencies(repo_root):
        relative = legacy_path.relative_to(repo_root).as_posix().lower()
        mentioned = relative in visibility_sections
        has_visibility_hint = any(hint in visibility_sections for hint in LEGACY_VISIBILITY_HINTS)
        is_negated = any(hint in visibility_sections for hint in NEGATING_HINTS)
        if not mentioned or not has_visibility_hint or is_negated:
            unreported_legacy_paths.append(relative)

    if unreported_legacy_paths:
        report.add_warning(
            "docs.legacy_runtime_dependency_missing",
            "Current state docs do not mention still-live legacy dependency path(s): "
            + ", ".join(unreported_legacy_paths)
            + " under explicit current-vs-legacy visibility sections.",
            current_state_path,
        )


def resolve_python_target(repo_root: Path, implementation: str) -> tuple[Path | None, str | None]:
    if ":" not in implementation:
        return None, None
    module_path, symbol = implementation.split(":", 1)
    return resolve_module_file(repo_root, module_path), symbol


def validate_implementation_link(implementation: object, report: ValidationReport, path: Path) -> None:
    if not implementation:
        report.add_error("impl.missing", "Missing implementation link.", path)
        return
    text = str(implementation)
    if ":" not in text:
        report.add_error(
            "impl.invalid_format",
            "Implementation links must use `package.module:function` format.",
            path,
        )
        return
    module_file, symbol = resolve_python_target(report.repo_root, text)
    if module_file is None or symbol is None:
        report.add_error(
            "impl.unresolved",
            f"Implementation link `{text}` does not resolve to a Python module inside the repo.",
            path,
        )
        return
    contents = module_file.read_text(encoding="utf-8")
    if not re.search(rf"(async\s+def|def)\s+{re.escape(symbol)}\s*\(", contents):
        report.add_error(
            "impl.symbol_missing",
            f"Implementation link `{text}` does not define `{symbol}` in `{module_file.name}`.",
            path,
        )


def validate_docs(repo_root: Path, report: ValidationReport) -> None:
    docs_dir = repo_root / "docs"
    if not docs_dir.exists():
        report.add_warning("docs.missing", "No docs directory found; skipping docs validation.", docs_dir)
        return

    for name in CURRENT_DOCS:
        path = docs_dir / name
        if not path.exists():
            report.add_warning("docs.optional_missing", f"Expected current doc `docs/{name}` is missing.", path)
            continue
        validate_doc_metadata(path, report)
        validate_markdown_refs(path, repo_root, report)
        if name == "CURRENT_STATE.md":
            validate_current_state_visibility(path, repo_root, report)
        if name == "IMPACT_SUMMARY.md":
            validate_impact_summary_sections(path, report)

    archive_dir = docs_dir / "archive"
    if archive_dir.exists():
        validate_archive_banners(archive_dir, report)


def validate_glossary(glossary_path: Path, report: ValidationReport) -> set[str]:
    terms = load_list_section(glossary_path, "terms", report)
    term_map = keyed_items(terms, "term", report, glossary_path)
    for term_name, item in term_map.items():
        status = str(item.get("status", "")).lower()
        if status == "deprecated":
            has_replacement = bool(item.get("replaced_by"))
            has_aliases = bool(item.get("aliases"))
            has_related = bool(item.get("related_terms"))
            if not (has_replacement or has_aliases or has_related):
                report.add_error(
                    "glossary.deprecated_unmapped",
                    f"Deprecated term `{term_name}` should include aliases, related terms, or `replaced_by`.",
                    glossary_path,
                )
    return set(term_map)


def validate_intelligence(repo_root: Path, report: ValidationReport) -> None:
    intelligence_dir = repo_root / "intelligence"
    if not intelligence_dir.exists():
        report.add_warning(
            "intelligence.missing",
            "No intelligence directory found; skipping intelligence validation.",
            intelligence_dir,
        )
        return

    glossary_terms: set[str] = set()
    glossary_path = intelligence_dir / "glossary.yaml"
    if glossary_path.exists():
        glossary_terms = validate_glossary(glossary_path, report)
    else:
        report.add_warning("intelligence.glossary_missing", "Missing `intelligence/glossary.yaml`.", glossary_path)

    actions_path = intelligence_dir / "manifests" / "actions.yaml"
    entities_path = intelligence_dir / "manifests" / "entities.yaml"
    datasets_path = intelligence_dir / "manifests" / "datasets.yaml"
    capabilities_path = intelligence_dir / "registry" / "capabilities.yaml"

    actions = load_list_section(actions_path, "actions", report) if actions_path.exists() else None
    if actions is None and not actions_path.exists():
        report.add_warning("intelligence.actions_missing", "Missing `intelligence/manifests/actions.yaml`.", actions_path)
    action_map = keyed_items(actions, "key", report, actions_path)

    entities = load_list_section(entities_path, "entities", report) if entities_path.exists() else None
    entity_map = keyed_items(entities, "key", report, entities_path)

    datasets = load_list_section(datasets_path, "datasets", report) if datasets_path.exists() else None
    if datasets is None and not datasets_path.exists():
        report.add_warning("intelligence.datasets_missing", "Missing `intelligence/manifests/datasets.yaml`.", datasets_path)
    dataset_map = keyed_items(datasets, "dataset_key", report, datasets_path)

    capabilities = load_list_section(capabilities_path, "capabilities", report) if capabilities_path.exists() else None
    if capabilities is None and not capabilities_path.exists():
        report.add_warning(
            "intelligence.capabilities_missing",
            "Missing `intelligence/registry/capabilities.yaml`.",
            capabilities_path,
        )
    capability_map = keyed_items(capabilities, "key", report, capabilities_path)

    for capability_key, item in capability_map.items():
        if str(item.get("status", "")).lower() in {"active", "implemented"}:
            validate_implementation_link(item.get("implementation"), report, capabilities_path)

    for action_key, item in action_map.items():
        capability = item.get("capability")
        if str(item.get("status", "")).lower() == "implemented" and not capability:
            report.add_error(
                "actions.missing_capability",
                f"Implemented action `{action_key}` is missing a capability binding.",
                actions_path,
            )
        if capability:
            capability_name = str(capability)
            if not capability_map:
                report.add_error(
                    "actions.capability_registry_missing",
                    f"Action `{action_key}` references capability `{capability_name}` but the registry is missing.",
                    actions_path,
                )
            elif capability_name not in capability_map:
                report.add_error(
                    "actions.capability_unknown",
                    f"Action `{action_key}` references unknown capability `{capability_name}`.",
                    actions_path,
                )
        if item.get("implementation"):
            validate_implementation_link(item.get("implementation"), report, actions_path)
        for dataset_key in item.get("touches_datasets") or []:
            dataset_name = str(dataset_key)
            if not dataset_map:
                report.add_error(
                    "actions.datasets_registry_missing",
                    f"Action `{action_key}` references dataset `{dataset_name}` but `datasets.yaml` is missing.",
                    actions_path,
                )
                break
            if dataset_name not in dataset_map:
                report.add_error(
                    "actions.dataset_unknown",
                    f"Action `{action_key}` references unknown dataset `{dataset_name}`.",
                    actions_path,
                )

    for entity_key, item in entity_map.items():
        for term in item.get("canonical_terms") or []:
            if glossary_terms and str(term) not in glossary_terms:
                report.add_error(
                    "entities.unknown_term",
                    f"Entity `{entity_key}` references unknown canonical term `{term}`.",
                    entities_path,
                )
        for action_key in item.get("used_by_actions") or []:
            if action_map and str(action_key) not in action_map:
                report.add_error(
                    "entities.unknown_action",
                    f"Entity `{entity_key}` references unknown action `{action_key}`.",
                    entities_path,
                )

    for dataset_key, item in dataset_map.items():
        canonical_shape = item.get("canonical_shape")
        if canonical_shape:
            canonical_shape_path = repo_root / str(canonical_shape)
            if not canonical_shape_path.exists():
                report.add_error(
                    "datasets.canonical_shape_missing",
                    f"Dataset `{dataset_key}` references missing canonical shape `{canonical_shape}`.",
                    datasets_path,
                )
        for action_key in item.get("used_by_actions") or []:
            if action_map and str(action_key) not in action_map:
                report.add_error(
                    "datasets.unknown_action",
                    f"Dataset `{dataset_key}` references unknown action `{action_key}`.",
                    datasets_path,
                )

    handlers_dir = intelligence_dir / "handlers"
    if handlers_dir.exists():
        for handler_path in handlers_dir.rglob("*.yaml"):
            data = load_yaml(handler_path, report)
            if not isinstance(data, dict):
                continue
            for action_key in data.get("emitted_by") or []:
                if action_map and str(action_key) not in action_map:
                    report.add_error(
                        "handlers.unknown_emitter",
                        f"Handler references unknown emitter action `{action_key}`.",
                        handler_path,
                    )
                elif not action_map:
                    report.add_error(
                        "handlers.actions_missing",
                        "Handlers exist but `intelligence/manifests/actions.yaml` is missing.",
                        handler_path,
                    )
            for step in data.get("chain") or []:
                if not isinstance(step, dict):
                    report.add_error("handlers.invalid_step", "Each handler chain step must be a mapping.", handler_path)
                    continue
                action_key = step.get("action")
                if not action_key:
                    report.add_error("handlers.missing_action", "Handler chain step is missing an action.", handler_path)
                    continue
                if action_map and str(action_key) not in action_map:
                    report.add_error(
                        "handlers.unknown_action",
                        f"Handler references unknown action `{action_key}`.",
                        handler_path,
                    )
                elif not action_map:
                    report.add_error(
                        "handlers.actions_missing",
                        "Handlers exist but `intelligence/manifests/actions.yaml` is missing.",
                        handler_path,
                    )


def validate_wiki_memory(repo_root: Path, report: ValidationReport) -> None:
    wiki_dir = repo_root / "wiki"
    if not wiki_dir.exists():
        report.add_warning(
            "wiki.memory_missing",
            "No `wiki/` memory layer found; repo-docs bootstrap should create a small derived memory scaffold.",
            wiki_dir,
        )
        return

    for relative in WIKI_MEMORY_PATHS:
        path = repo_root / relative
        if not path.exists():
            report.add_warning(
                "wiki.memory_path_missing",
                f"Expected small wiki memory path `{relative}` is missing.",
                path,
            )

    for path in wiki_dir.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        metadata = parse_doc_metadata(text)
        source_value = normalize_truth_value(metadata.get("source_of_truth", "false"))
        if source_value in {"yes", "true"}:
            report.add_error(
                "wiki.claims_canonical_truth",
                "Wiki memory pages must not mark themselves as source-of-truth; cite docs, intelligence, or code instead.",
                path,
            )
        if "canonical runtime truth" in text.lower() and not (
            "docs/" in text or "intelligence/" in text or "AGENTS.md" in text
        ):
            report.add_error(
                "wiki.runtime_claim_without_canonical_source",
                "Wiki runtime claims must cite canonical docs, intelligence, AGENTS.md, or code paths.",
                path,
            )


def validate_changed_files(repo_root: Path, changed_files_path: Path | None, report: ValidationReport) -> None:
    if changed_files_path is None:
        report.add_warning(
            "drift.changed_files_missing",
            "No `--changed-files` input provided; drift suspicion checks were limited.",
        )
        return
    if not changed_files_path.exists():
        report.add_warning(
            "drift.changed_files_not_found",
            f"Changed files list `{changed_files_path}` does not exist.",
            changed_files_path,
        )
        return

    changed = [
        line.strip().replace("\\", "/")
        for line in changed_files_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not changed:
        report.add_warning(
            "drift.changed_files_empty",
            "Changed files list is empty; drift suspicion checks were limited.",
            changed_files_path,
        )
        return

    canonical_repo_memory_changed = any(
        path.startswith(("docs/", "intelligence/")) or path == "AGENTS.md" for path in changed
    )
    code_changed = any(
        path.endswith((".py", ".sql", ".yaml", ".yml"))
        and not path.startswith(("docs/", "intelligence/", "wiki/"))
        for path in changed
    )
    if code_changed and not canonical_repo_memory_changed:
        report.add_warning(
            "drift.docs_sync_missing",
            "Implementation changed without any canonical docs, intelligence, or AGENTS updates in the changed file list.",
            repo_root,
        )

    entrypoint_names = ("cli.py", "main.py", "serve.py", "server.py", "app.py")
    entrypoint_changed = any(path.endswith(entrypoint_names) or path.startswith(("scripts/", "bin/")) for path in changed)
    if entrypoint_changed and "docs/CURRENT_STATE.md" not in changed:
        report.add_warning(
            "drift.current_state_missing",
            "Entrypoint-related files changed but `docs/CURRENT_STATE.md` was not part of the changed file list.",
            repo_root / "docs" / "CURRENT_STATE.md",
        )

    if "intelligence/manifests/actions.yaml" in changed and "intelligence/registry/capabilities.yaml" not in changed:
        report.add_warning(
            "drift.capability_sync_missing",
            "`actions.yaml` changed without a matching `capabilities.yaml` change in the changed file list.",
            repo_root / "intelligence" / "registry" / "capabilities.yaml",
        )

    if any(path.startswith("intelligence/handlers/") for path in changed) and "intelligence/manifests/actions.yaml" not in changed:
        report.add_warning(
            "drift.handler_sync_missing",
            "Handler files changed without `actions.yaml` in the changed file list.",
            repo_root / "intelligence" / "manifests" / "actions.yaml",
        )

    if canonical_repo_memory_changed and not any(path.startswith("wiki/") for path in changed):
        report.add_warning(
            "drift.wiki_memory_sync_missing",
            "Docs, intelligence, or AGENTS changed without a wiki memory update in the changed file list.",
            repo_root / "wiki",
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate docs/intelligence alignment in a repository.")
    parser.add_argument("--repo-root", required=True, help="Repository root to validate.")
    parser.add_argument("--format", default="text", choices=("text", "json"), help="Output format.")
    parser.add_argument(
        "--changed-files",
        help="Optional path to a newline-delimited changed files list for drift suspicion checks.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    report = ValidationReport(repo_root)

    if not repo_root.exists():
        report.add_error("repo.missing", "Repository root does not exist.", repo_root)
    elif not repo_root.is_dir():
        report.add_error("repo.invalid", "Repository root must be a directory.", repo_root)
    else:
        validate_docs(repo_root, report)
        validate_intelligence(repo_root, report)
        validate_wiki_memory(repo_root, report)
        changed_files = Path(args.changed_files).resolve() if args.changed_files else None
        validate_changed_files(repo_root, changed_files, report)

    if args.format == "json":
        print(report.as_json())
    else:
        report.print_text()
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
