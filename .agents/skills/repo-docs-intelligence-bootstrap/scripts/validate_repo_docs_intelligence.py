#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import urllib.parse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 compatibility
    try:
        import tomli as tomllib
    except ImportError:  # pragma: no cover
        tomllib = None

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

REPO_MAP_DOCS: Final = [
    "README.md",
    "ENTRYPOINTS.md",
    "MODULES.md",
    "DATA_FLOW.md",
    "SYMBOL_GRAPH.md",
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
FINALIZE_RECEIPT_VERSION: Final = 1
DEFAULT_FINALIZE_RECEIPT: Final = "state/repo_docs_finalize.json"
PLACEHOLDER_PREFIXES: Final = ("list ", "record ", "describe ", "replace ")
PLACEHOLDER_VALUES: Final = {"todo", "tbd", "n/a", "na", "placeholder", "replace me"}
DECISION_STATUSES: Final = {
    "proposed",
    "accepted",
    "implemented",
    "superseded",
    "rejected",
    "deferred",
}
IMPLEMENTATION_STATUSES: Final = {
    "not_started",
    "in_progress",
    "verified",
    "partial",
}
PLAN_STATUSES: Final = {"active", "completed", "superseded", "deferred"}


class ValidationReport:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.errors: list[dict[str, str]] = []
        self.warnings: list[dict[str, str]] = []
        self.finalize: dict[str, object] | None = None

    def add_error(self, code: str, message: str, path: Path | None = None) -> None:
        self.errors.append(self._make_issue("error", code, message, path))

    def add_warning(self, code: str, message: str, path: Path | None = None) -> None:
        self.warnings.append(self._make_issue("warning", code, message, path))

    def promote_warnings(self) -> None:
        for issue in self.warnings:
            promoted = dict(issue)
            promoted["level"] = "error"
            promoted["code"] = f"finalize.{issue['code']}"
            self.errors.append(promoted)
        self.warnings.clear()

    def _make_issue(
        self, level: str, code: str, message: str, path: Path | None
    ) -> dict[str, str]:
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
        if self.finalize is not None:
            print("\nFinalize:")
            for key, value in self.finalize.items():
                print(f"- {key}: {value}")

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
                "finalize": self.finalize,
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


def parse_lifecycle_metadata(text: str) -> dict[str, object]:
    """Parse lifecycle frontmatter without requiring PyYAML."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    frontmatter: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        frontmatter.append(line)
    else:
        return {}

    if yaml is not None:
        try:
            loaded = yaml.safe_load("\n".join(frontmatter)) or {}
            if isinstance(loaded, dict):
                return {normalize_key(str(key)): value for key, value in loaded.items()}
        except Exception:
            pass

    def strip_comment(value: str) -> str:
        quote: str | None = None
        escaped = False
        for index, character in enumerate(value):
            if escaped:
                escaped = False
                continue
            if character == "\\" and quote == '"':
                escaped = True
                continue
            if character in {"'", '"'}:
                quote = None if quote == character else character if quote is None else quote
            elif character == "#" and quote is None and (
                index == 0 or value[index - 1].isspace()
            ):
                return value[:index].rstrip()
        return value.strip()

    def split_inline_list(value: str) -> list[str]:
        items: list[str] = []
        start = 0
        quote: str | None = None
        for index, character in enumerate(value):
            if character in {"'", '"'}:
                quote = None if quote == character else character if quote is None else quote
            elif character == "," and quote is None:
                items.append(value[start:index])
                start = index + 1
        items.append(value[start:])
        return [strip_comment(item).strip().strip("\"'") for item in items if strip_comment(item).strip()]

    metadata: dict[str, object] = {}
    active_list: str | None = None
    for line in frontmatter:
        list_item = re.match(r"^\s+-\s+(.+?)\s*$", line)
        if list_item and active_list is not None:
            value = strip_comment(list_item.group(1)).strip().strip("\"'")
            current = metadata.setdefault(active_list, [])
            if isinstance(current, list):
                current.append(value)
            continue
        match = re.match(r"^([^\s][^:]*):\s*(.*?)\s*$", line)
        if not match:
            continue
        key = normalize_key(match.group(1))
        raw_value = strip_comment(match.group(2))
        active_list = None
        if not raw_value:
            metadata[key] = []
            active_list = key
        elif raw_value.startswith("[") and raw_value.endswith("]"):
            inner = raw_value[1:-1].strip()
            metadata[key] = split_inline_list(inner) if inner else []
        elif raw_value.lower() in {"null", "none", "~"}:
            metadata[key] = None
        elif raw_value.lower() in {"true", "false"}:
            metadata[key] = raw_value.lower() == "true"
        else:
            metadata[key] = raw_value.strip("\"'")
    return metadata


def metadata_values(value: object) -> list[str]:
    if value is None or value is False:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "n/a", "na", "[]"}:
        return []
    return [text]


def resolve_lifecycle_reference(
    repo_root: Path, source_path: Path, raw_reference: str
) -> Path | None:
    reference = raw_reference.strip().strip("`")
    markdown_link = re.fullmatch(r"\[[^]]*]\((.+)\)", reference)
    if markdown_link:
        reference = markdown_link.group(1).strip()
    wikilink = re.fullmatch(r"\[\[([^]|]+)(?:\|[^]]+)?]]", reference)
    if wikilink:
        stem = Path(wikilink.group(1)).stem
        matches = [
            candidate.resolve()
            for root_name in ("docs", "wiki")
            for candidate in (repo_root / root_name).rglob("*.md")
            if candidate.stem == stem
        ]
        return matches[0] if len(matches) == 1 else None
    if reference.startswith(("http://", "https://", "mailto:")):
        return None
    reference = urllib.parse.unquote(reference.split("#", 1)[0].split("?", 1)[0])
    if not reference:
        return None
    candidate = Path(reference)
    candidates = (
        [candidate.resolve()]
        if candidate.is_absolute()
        else [(source_path.parent / candidate).resolve(), (repo_root / candidate).resolve()]
    )
    resolved_root = repo_root.resolve()
    for resolved in candidates:
        try:
            resolved.relative_to(resolved_root)
        except ValueError:
            continue
        if resolved.exists():
            return resolved
    return None


def scan_markdown_refs(text: str) -> list[str]:
    refs: list[str] = []
    for candidate in re.findall(r"`([^`]+)`", text):
        candidate = candidate.strip()
        if candidate.startswith(("http://", "https://")):
            continue
        if (
            candidate == "AGENTS.md"
            or "/" in candidate
            or candidate.endswith(PATHLIKE_EXTENSIONS)
        ):
            refs.append(candidate)
    return sorted(set(refs))


def strip_markdown_code(text: str) -> str:
    """Remove fenced and inline code so examples are not treated as live links."""
    visible: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    list_content_indents: list[int] = []

    def indent_width(value: str) -> int:
        width = 0
        for character in value:
            width = width + 1 if character == " " else width + (4 - width % 4)
        return width

    for line in text.splitlines():
        fence = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})", line)
        if fence:
            marker = fence.group(1)
            if fence_character is None:
                fence_character = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_length:
                fence_character = None
                fence_length = 0
            visible.append("")
            continue
        if fence_character is not None:
            visible.append("")
            continue
        if not line.strip():
            visible.append("")
            continue

        leading = re.match(r"^[ \t]*", line)
        leading_text = leading.group(0) if leading else ""
        indentation = indent_width(leading_text)
        indented = line[len(leading_text) :]
        list_marker = re.match(r"([-+*]|\d+[.)])([ \t]+)", indented)
        if list_marker:
            while list_content_indents and indentation < list_content_indents[-1]:
                list_content_indents.pop()
            content_indent = indentation + len(list_marker.group(1)) + indent_width(
                list_marker.group(2)
            )
            list_content_indents.append(content_indent)
            visible.append(line)
            continue

        while list_content_indents and indentation < list_content_indents[-1]:
            list_content_indents.pop()
        if list_content_indents:
            content_indent = list_content_indents[-1]
            if indentation >= content_indent + 4:
                visible.append("")
                continue
            visible.append(line)
            continue
        if indentation >= 4:
            visible.append("")
            continue
        visible.append(re.sub(r"(`+)(?:(?!\1).)*\1", "", line))
    return "\n".join(visible)


def markdown_inline_destinations(text: str) -> list[str]:
    destinations: list[str] = []
    position = 0
    while position < len(text):
        if text[position] != "[":
            position += 1
            continue
        label_depth = 1
        escaped = False
        label_end: int | None = None
        index = position + 1
        while index < len(text) and text[index] != "\n":
            character = text[index]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "[":
                label_depth += 1
            elif character == "]":
                label_depth -= 1
                if label_depth == 0:
                    label_end = index
                    break
            index += 1
        if label_end is None or label_end + 1 >= len(text) or text[label_end + 1] != "(":
            position += 1
            continue
        start = label_end + 2
        depth = 1
        escaped = False
        for index in range(start, len(text)):
            character = text[index]
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    destinations.append(text[start:index])
                    position = index + 1
                    break
        else:
            position = label_end + 1
    return destinations


def markdown_reference_destinations(text: str) -> list[str]:
    destinations: list[str] = []
    pattern = re.compile(
        r"^[ \t]{0,3}\[(?!\^)[^\]\n]+\]:[ \t]*(?:<([^>\n]+)>|([^\s]+))",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        destinations.append(match.group(1) or match.group(2))
    return destinations


def scan_local_markdown_links(text: str) -> list[str]:
    """Return local inline/reference Markdown destinations, excluding URLs and anchors."""
    visible = strip_markdown_code(text)
    links: list[str] = []
    destinations = markdown_inline_destinations(visible)
    destinations.extend(markdown_reference_destinations(visible))
    for raw_target in destinations:
        target = raw_target.strip()
        if target.startswith("<") and ">" in target:
            target = target[1 : target.index(">")]
        else:
            target = target.split(maxsplit=1)[0]
        target = target.replace(r"\(", "(").replace(r"\)", ")")
        parsed = urllib.parse.urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        links.append(urllib.parse.unquote(parsed.path))
    return sorted(set(links))


def validate_wiki_markdown_links(
    path: Path, repo_root: Path, report: ValidationReport
) -> None:
    """Validate default Repo Docs links without rejecting legacy wikilinks."""
    resolved_root = repo_root.resolve()
    for target in scan_local_markdown_links(path.read_text(encoding="utf-8")):
        candidate = (
            resolved_root / target.lstrip("/")
            if target.startswith("/")
            else path.parent / target
        ).resolve()
        try:
            candidate.relative_to(resolved_root)
        except ValueError:
            report.add_error(
                "wiki.markdown_link_outside_repo",
                f"Local Markdown link `{target}` resolves outside the repository.",
                path,
            )
            continue
        if not candidate.exists():
            report.add_error(
                "wiki.broken_markdown_link",
                f"Local Markdown link `{target}` does not resolve from `{path.relative_to(repo_root)}`.",
                path,
            )


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


def load_list_section(
    path: Path, key: str, report: ValidationReport
) -> list[dict[str, object]] | None:
    data = load_yaml(path, report)
    if data is None:
        return None
    if not isinstance(data, dict):
        report.add_error("yaml.invalid_root", "YAML root must be a mapping.", path)
        return None
    section = data.get(key)
    if section is None:
        report.add_error(
            "yaml.missing_section", f"Missing top-level `{key}` section.", path
        )
        return None
    items: list[dict[str, object]] = []
    if isinstance(section, list):
        for item in section:
            if not isinstance(item, dict):
                report.add_error(
                    "yaml.invalid_item",
                    f"Each item in `{key}` must be a mapping.",
                    path,
                )
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
            report.add_error(
                "yaml.missing_key",
                f"Missing required `{key_field}` field in item.",
                path,
            )
            continue
        key = str(value)
        if key in result:
            report.add_error(
                "yaml.duplicate_key", f"Duplicate `{key_field}` value `{key}`.", path
            )
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


def validate_markdown_refs(
    path: Path, repo_root: Path, report: ValidationReport
) -> None:
    for ref in scan_markdown_refs(path.read_text(encoding="utf-8")):
        if ":" in ref and not ref.startswith(
            ("docs/", "intelligence/", "scripts/", "AGENTS.md")
        ):
            continue
        if not (repo_root / ref).exists():
            report.add_error(
                "docs.broken_reference",
                f"Referenced path `{ref}` does not exist.",
                path,
            )


def validate_archive_banners(archive_dir: Path, report: ValidationReport) -> None:
    for path in archive_dir.rglob("*.md"):
        top = "\n".join(path.read_text(encoding="utf-8").splitlines()[:8])
        if "Status: Archived" not in top or "Source of Truth: No" not in top:
            report.add_error(
                "docs.archive_banner_missing",
                "Archived docs must include `Status: Archived` and `Source of Truth: No` near the top.",
                path,
            )


def validate_repo_map(repo_root: Path, report: ValidationReport) -> None:
    repo_map_dir = repo_root / "docs" / "repo-map"
    if not repo_map_dir.exists():
        return
    if not repo_map_dir.is_dir():
        report.add_error(
            "repo_map.invalid_path",
            "`docs/repo-map` must be a directory.",
            repo_map_dir,
        )
        return

    for name in REPO_MAP_DOCS:
        path = repo_map_dir / name
        if not path.exists():
            report.add_error(
                "repo_map.missing_doc",
                f"Missing repo-map doc `docs/repo-map/{name}`.",
                path,
            )
            continue
        validate_doc_metadata(path, report)
        validate_markdown_refs(path, repo_root, report)

    readme_path = repo_map_dir / "README.md"
    if readme_path.exists():
        readme_text = readme_path.read_text(encoding="utf-8")
        for name in REPO_MAP_DOCS:
            if name == "README.md":
                continue
            expected = f"docs/repo-map/{name}"
            if expected not in readme_text:
                report.add_error(
                    "repo_map.readme_missing_link",
                    f"Repo-map README must link `{expected}`.",
                    readme_path,
                )

    wiki_index_path = repo_root / "wiki" / "_meta" / "index.md"
    if wiki_index_path.exists():
        wiki_index_text = wiki_index_path.read_text(encoding="utf-8")
        if "docs/repo-map/README.md" not in wiki_index_text:
            report.add_error(
                "repo_map.wiki_index_missing",
                "Wiki index must link `docs/repo-map/README.md` when a repo-map exists.",
                wiki_index_path,
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
    if tomllib is not None:
        try:
            data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        scripts: dict[str, object] = {}
        project = data.get("project") if isinstance(data, dict) else None
        if isinstance(project, dict):
            for section in ("scripts", "gui-scripts"):
                values = project.get(section)
                if isinstance(values, dict):
                    scripts.update(values)
        tool = data.get("tool") if isinstance(data, dict) else None
        poetry = tool.get("poetry") if isinstance(tool, dict) else None
        poetry_scripts = poetry.get("scripts") if isinstance(poetry, dict) else None
        if isinstance(poetry_scripts, dict):
            scripts.update(poetry_scripts)
        normalized_scripts = [
            (str(name), normalize_script_target(target))
            for name, target in scripts.items()
        ]
        normalized_scripts = [
            (name, target) for name, target in normalized_scripts if target
        ]
        if normalized_scripts:
            return sorted(normalized_scripts)

    text = pyproject_path.read_text(encoding="utf-8")
    scripts: list[tuple[str, str]] = []
    for section in ("project.scripts", "project.gui-scripts", "tool.poetry.scripts"):
        match = re.search(
            rf"^\[{re.escape(section)}\]\s*$([\s\S]*?)(?=^\[|\Z)", text, re.MULTILINE
        )
        if not match:
            continue
        for line in match.group(1).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            target = value.strip().strip("\"'")
            if target.startswith("{"):
                reference = re.search(r"reference\s*=\s*[\"']([^\"']+)[\"']", target)
                target = reference.group(1) if reference else ""
            if target:
                scripts.append((name.strip().strip("\"'"), target))
    return sorted(set(scripts))


def normalize_script_target(target: object) -> str:
    if isinstance(target, str):
        return target
    if isinstance(target, dict):
        reference = target.get("reference")
        return str(reference) if reference else ""
    return ""


def entrypoint_is_documented(text: str, script_name: str, target: str) -> bool:
    code_spans = {value.strip().lower() for value in re.findall(r"`([^`]+)`", text)}
    script_name = script_name.lower()
    target = target.lower()
    command_present = any(
        value == script_name
        or re.search(rf"(^|\s){re.escape(script_name)}(\s|=|$)", value)
        for value in code_spans
    )
    target_present = any(
        value == target or re.search(rf"(^|=|\s){re.escape(target)}($|\s)", value)
        for value in code_spans
    )
    return command_present and target_present


def module_exposes_symbol(path: Path, symbol: str) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return False
    parts = symbol.split(".")
    nodes: list[ast.stmt] = tree.body
    for index, part in enumerate(parts):
        matching: ast.AST | None = None
        for node in nodes:
            names: set[str] = set()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                names.update(
                    target.id for target in targets if isinstance(target, ast.Name)
                )
            elif isinstance(node, ast.Import):
                names.update(
                    alias.asname or alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                names.update(alias.asname or alias.name for alias in node.names)
            if part in names:
                matching = node
                break
        if matching is None:
            return False
        if index == len(parts) - 1:
            return True
        if not isinstance(matching, ast.ClassDef):
            return False  # A strict static gate cannot prove deeper attributes on imports or assignments.
        nodes = matching.body
    return True


def validate_registered_entrypoints(repo_root: Path, report: ValidationReport) -> None:
    scripts = extract_console_scripts(repo_root)
    if not scripts:
        return

    current_state_path = repo_root / "docs" / "CURRENT_STATE.md"
    repo_map_path = repo_root / "docs" / "repo-map" / "ENTRYPOINTS.md"
    surfaces = [path for path in (current_state_path, repo_map_path) if path.exists()]

    for script_name, target in scripts:
        module_file, symbol = resolve_python_target(repo_root, target)
        if module_file is None or symbol is None:
            report.add_error(
                "entrypoint.target_unresolved",
                f"Registered entrypoint `{script_name} = {target}` does not resolve inside the repository.",
                repo_root / "pyproject.toml",
            )
        elif not module_exposes_symbol(module_file, symbol):
            report.add_error(
                "entrypoint.symbol_missing",
                f"Registered entrypoint `{script_name} = {target}` does not define `{symbol}`.",
                module_file,
            )

        for path in surfaces:
            if entrypoint_is_documented(
                path.read_text(encoding="utf-8"), script_name, target
            ):
                continue
            report.add_warning(
                "docs.entrypoint_registration_missing",
                f"Registered entrypoint `{script_name} = {target}` is not documented in `{path.relative_to(repo_root)}`.",
                path,
            )


def collect_live_legacy_dependencies(repo_root: Path) -> list[Path]:
    legacy_paths: set[Path] = set()
    for path in repo_root.rglob("*.py"):
        if any(part.startswith(".") for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for module_name in re.findall(
            r"^\s*from\s+([A-Za-z0-9_\.]+)\s+import\s+", text, re.MULTILINE
        ):
            if "legacy" not in module_name.lower():
                continue
            resolved = resolve_module_file(repo_root, module_name)
            if resolved is not None:
                legacy_paths.add(resolved)
        for module_name in re.findall(
            r"^\s*import\s+([A-Za-z0-9_\.]+)", text, re.MULTILINE
        ):
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
    missing = [
        section
        for section, options in aliases.items()
        if not any(option in text for option in options)
    ]
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


def validate_current_state_visibility(
    current_state_path: Path, repo_root: Path, report: ValidationReport
) -> None:
    text = current_state_path.read_text(encoding="utf-8")
    transitional_section = extract_markdown_section(text, "Transitional Facts").lower()
    current_truth_section = extract_markdown_section(text, "Current Truth").lower()
    visibility_sections = "\n".join(
        part for part in (transitional_section, current_truth_section) if part
    )

    unreported_legacy_paths: list[str] = []
    for legacy_path in collect_live_legacy_dependencies(repo_root):
        relative = legacy_path.relative_to(repo_root).as_posix().lower()
        mentioned = relative in visibility_sections
        has_visibility_hint = any(
            hint in visibility_sections for hint in LEGACY_VISIBILITY_HINTS
        )
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


def resolve_python_target(
    repo_root: Path, implementation: str
) -> tuple[Path | None, str | None]:
    if ":" not in implementation:
        return None, None
    module_path, symbol = implementation.split(":", 1)
    return resolve_module_file(repo_root, module_path), symbol


def validate_implementation_link(
    implementation: object, report: ValidationReport, path: Path
) -> None:
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
        report.add_warning(
            "docs.missing",
            "No docs directory found; skipping docs validation.",
            docs_dir,
        )
        return

    for name in CURRENT_DOCS:
        path = docs_dir / name
        if not path.exists():
            report.add_warning(
                "docs.optional_missing",
                f"Expected current doc `docs/{name}` is missing.",
                path,
            )
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
    validate_repo_map(repo_root, report)
    validate_registered_entrypoints(repo_root, report)


def collect_lifecycle_documents(
    repo_root: Path,
) -> dict[str, list[tuple[Path, dict[str, object]]]]:
    documents: dict[str, list[tuple[Path, dict[str, object]]]] = {
        "adr": [],
        "plan": [],
        "evidence": [],
        "review": [],
        "wiki_decision": [],
    }
    docs_dir = repo_root / "docs"
    if docs_dir.exists():
        for path in docs_dir.rglob("*.md"):
            relative_parts = path.relative_to(docs_dir).parts
            if "archive" in relative_parts:
                continue
            metadata = parse_lifecycle_metadata(path.read_text(encoding="utf-8"))
            document_type = normalize_key(str(metadata.get("type", "")))
            directory_role = relative_parts[0].lower() if len(relative_parts) > 1 else ""
            is_index = path.name.lower() in {"readme.md", "index.md"}
            flat_adr = len(relative_parts) == 1 and bool(
                re.match(r"^ADR(?:[-_]|\d)", path.stem.upper())
            )
            if (
                metadata.get("decision_id")
                or document_type == "adr"
                or flat_adr
                or (directory_role == "adr" and not is_index)
            ):
                documents["adr"].append((path, metadata))
            elif (
                metadata.get("plan_id")
                or document_type == "implementation_plan"
                or (directory_role == "plans" and not is_index)
            ):
                documents["plan"].append((path, metadata))
            elif (
                metadata.get("evidence_id")
                or document_type == "evidence"
                or (directory_role == "evidence" and not is_index)
            ):
                documents["evidence"].append((path, metadata))
            elif (
                metadata.get("review_id")
                or document_type == "review"
                or (directory_role == "reviews" and not is_index)
            ):
                documents["review"].append((path, metadata))

    decisions_dir = repo_root / "wiki" / "decisions"
    if decisions_dir.exists():
        for path in decisions_dir.rglob("*.md"):
            metadata = parse_lifecycle_metadata(path.read_text(encoding="utf-8"))
            document_type = normalize_key(str(metadata.get("type", "")))
            if path.name.lower() not in {"readme.md", "index.md"} or (
                metadata.get("canonical_decision") or document_type == "decision"
            ):
                documents["wiki_decision"].append((path, metadata))
    return documents


def validate_unique_lifecycle_ids(
    documents: list[tuple[Path, dict[str, object]]],
    field: str,
    kind: str,
    report: ValidationReport,
) -> None:
    observed: dict[str, Path] = {}
    for path, metadata in documents:
        values = metadata_values(metadata.get(field))
        if not values:
            report.add_error(
                f"lifecycle.{kind}_id_missing",
                f"Activated {kind} document is missing `{field}`.",
                path,
            )
            continue
        identity = values[0]
        if identity in observed:
            report.add_error(
                f"lifecycle.{kind}_id_duplicate",
                f"Duplicate {kind} identity `{identity}` also appears in "
                f"`{observed[identity].relative_to(report.repo_root)}`.",
                path,
            )
        else:
            observed[identity] = path


def validate_lifecycle_references(
    repo_root: Path,
    source_path: Path,
    field: str,
    value: object,
    report: ValidationReport,
    *,
    allowed_targets: set[Path] | None = None,
) -> list[Path]:
    resolved: list[Path] = []
    for reference in metadata_values(value):
        target = resolve_lifecycle_reference(repo_root, source_path, reference)
        if target is None:
            report.add_error(
                "lifecycle.reference_unresolved",
                f"`{field}` reference `{reference}` does not resolve inside the repository.",
                source_path,
            )
            continue
        if allowed_targets is not None and target not in allowed_targets:
            report.add_error(
                "lifecycle.reference_wrong_kind",
                f"`{field}` reference `{reference}` does not target an activated lifecycle document of the required kind.",
                source_path,
            )
            continue
        resolved.append(target)
    return resolved


def validate_adr_lifecycle(
    repo_root: Path,
    documents: dict[str, list[tuple[Path, dict[str, object]]]],
    report: ValidationReport,
) -> None:
    adrs = documents["adr"]
    validate_unique_lifecycle_ids(adrs, "decision_id", "decision", report)
    adr_paths = {path.resolve() for path, _ in adrs}
    plan_paths = {path.resolve() for path, _ in documents["plan"]}
    evidence_paths = {path.resolve() for path, _ in documents["evidence"]}

    for path, metadata in adrs:
        decision_status = normalize_key(str(metadata.get("decision_status", "")))
        implementation_status = normalize_key(
            str(metadata.get("implementation_status", ""))
        )
        if decision_status not in DECISION_STATUSES:
            report.add_error(
                "lifecycle.decision_status_invalid",
                "ADR `decision_status` must be one of: "
                + ", ".join(sorted(DECISION_STATUSES))
                + ".",
                path,
            )
        if implementation_status not in IMPLEMENTATION_STATUSES:
            report.add_error(
                "lifecycle.implementation_status_invalid",
                "ADR `implementation_status` must be one of: "
                + ", ".join(sorted(IMPLEMENTATION_STATUSES))
                + ".",
                path,
            )
        if normalize_truth_value(metadata.get("source_of_truth", False)) not in {
            "yes",
            "true",
        }:
            report.add_error(
                "lifecycle.adr_not_canonical",
                "Activated ADRs must declare `source_of_truth: true`.",
                path,
            )

        supersession_refs = metadata_values(metadata.get("superseded_by"))
        if decision_status == "superseded" and not supersession_refs:
            report.add_error(
                "lifecycle.supersession_missing",
                "A superseded ADR must resolve `superseded_by` to another ADR.",
                path,
            )
        superseded_targets = validate_lifecycle_references(
            repo_root,
            path,
            "superseded_by",
            metadata.get("superseded_by"),
            report,
            allowed_targets=adr_paths,
        )
        if path.resolve() in superseded_targets:
            report.add_error(
                "lifecycle.supersession_self_reference",
                "An ADR cannot supersede itself.",
                path,
            )

        validate_lifecycle_references(
            repo_root,
            path,
            "implementation_plan",
            metadata.get("implementation_plan"),
            report,
            allowed_targets=plan_paths,
        )
        evidence_targets = validate_lifecycle_references(
            repo_root,
            path,
            "implementation_evidence",
            metadata.get("implementation_evidence"),
            report,
            allowed_targets=evidence_paths,
        )
        implementation_targets = validate_lifecycle_references(
            repo_root,
            path,
            "implementation_refs",
            metadata.get("implementation_refs"),
            report,
        )
        if decision_status == "implemented":
            if not implementation_targets:
                report.add_error(
                    "lifecycle.implemented_without_implementation",
                    "An implemented ADR must link implementation code or canonical docs; a plan alone is not proof.",
                    path,
                )
            if implementation_status != "verified" or not evidence_targets:
                report.add_error(
                    "lifecycle.implemented_without_verification",
                    "An implemented ADR must use `implementation_status: verified` and link verification evidence.",
                    path,
                )
        elif implementation_status == "verified" and not evidence_targets:
            report.add_error(
                "lifecycle.verified_without_evidence",
                "A verified implementation status requires linked implementation evidence.",
                path,
            )


def validate_plan_lifecycle(
    documents: list[tuple[Path, dict[str, object]]], report: ValidationReport
) -> None:
    validate_unique_lifecycle_ids(documents, "plan_id", "plan", report)
    stale_statuses = {"completed", "superseded", "deferred"}
    for path, metadata in documents:
        status = normalize_key(str(metadata.get("status", "")))
        if status not in PLAN_STATUSES:
            report.add_error(
                "lifecycle.plan_status_invalid",
                "Plan `status` must be one of: "
                + ", ".join(sorted(PLAN_STATUSES))
                + ".",
                path,
            )
        next_action = extract_markdown_section(
            path.read_text(encoding="utf-8"), "Current Next Action"
        )
        normalized_action = re.sub(r"^[\s>*-]+", "", next_action).strip().lower()
        has_action = bool(normalized_action) and normalized_action.rstrip(".") not in {
            "none",
            "none recorded",
            "not applicable",
            "n/a",
        }
        if status == "active" and not has_action:
            report.add_error(
                "lifecycle.active_plan_next_action_missing",
                "An active plan must name exactly one current next action.",
                path,
            )
        actionable_items = re.findall(
            r"^\s*(?:[-*+]|\d+[.)])[ \t]+\S", next_action, re.MULTILINE
        )
        if status == "active" and len(actionable_items) > 1:
            report.add_error(
                "lifecycle.active_plan_multiple_next_actions",
                "An active plan must name exactly one current next action.",
                path,
            )
        if status in stale_statuses and has_action:
            report.add_error(
                "lifecycle.stale_plan_has_next_action",
                f"A {status} plan cannot present a current next action.",
                path,
            )


def validate_wiki_decision_lifecycle(
    repo_root: Path,
    documents: dict[str, list[tuple[Path, dict[str, object]]]],
    report: ValidationReport,
) -> None:
    evidence_paths = {path.resolve() for path, _ in documents["evidence"]}
    canonical_docs = {
        path.resolve()
        for path in (repo_root / "docs").rglob("*.md")
        if normalize_truth_value(
            parse_lifecycle_metadata(path.read_text(encoding="utf-8")).get(
                "source_of_truth", False
            )
        )
        in {"yes", "true"}
    } if (repo_root / "docs").exists() else set()
    canonical_docs.update(path.resolve() for path, _ in documents["adr"])

    for path, metadata in documents["wiki_decision"]:
        if normalize_truth_value(metadata.get("source_of_truth", False)) not in {
            "no",
            "false",
        }:
            report.add_error(
                "lifecycle.wiki_decision_canonical",
                "Wiki decisions must declare `source_of_truth: false`.",
                path,
            )
        canonical_targets = validate_lifecycle_references(
            repo_root,
            path,
            "canonical_decision",
            metadata.get("canonical_decision"),
            report,
            allowed_targets=canonical_docs,
        )
        if not canonical_targets:
            report.add_error(
                "lifecycle.wiki_decision_source_missing",
                "A wiki decision must resolve its canonical ADR or decision source.",
                path,
            )
        implementation_status = normalize_key(
            str(metadata.get("implementation_status_mirror", "not_started"))
        )
        if implementation_status not in IMPLEMENTATION_STATUSES:
            report.add_error(
                "lifecycle.wiki_decision_status_invalid",
                "Wiki decision `implementation_status_mirror` is invalid.",
                path,
            )
        evidence_targets = validate_lifecycle_references(
            repo_root,
            path,
            "evidence_refs",
            metadata.get("evidence_refs"),
            report,
            allowed_targets=evidence_paths,
        )
        if implementation_status != "not_started" and not evidence_targets:
            report.add_error(
                "lifecycle.wiki_decision_evidence_missing",
                "A wiki decision that claims implementation progress must link relevant evidence.",
                path,
            )


def validate_lifecycle_portal(
    repo_root: Path,
    documents: dict[str, list[tuple[Path, dict[str, object]]]],
    report: ValidationReport,
) -> None:
    portal = repo_root / "docs" / "README.md"
    current_canonical_docs = [
        (path, parse_lifecycle_metadata(path.read_text(encoding="utf-8")))
        for name in CURRENT_DOCS
        if name != "README.md"
        and (path := repo_root / "docs" / name).exists()
        and normalize_truth_value(
            parse_lifecycle_metadata(path.read_text(encoding="utf-8")).get(
                "source_of_truth", False
            )
        )
        in {"yes", "true"}
    ]
    categories = {
        "decision": documents["adr"],
        "evidence": documents["evidence"],
        "review": documents["review"],
        "wiki_decision": documents["wiki_decision"],
    }
    active_categories = {name: docs for name, docs in categories.items() if docs}
    if not active_categories and not current_canonical_docs:
        return
    if not portal.exists():
        report.add_error(
            "lifecycle.portal_missing",
            "Activated lifecycle documents require `docs/README.md` as their portal.",
            portal,
        )
        return
    portal_targets = {
        target
        for reference in scan_local_markdown_links(portal.read_text(encoding="utf-8"))
        if (target := resolve_lifecycle_reference(repo_root, portal, reference))
        is not None
    }
    missing_current_docs = [
        path
        for path, _ in current_canonical_docs
        if path.resolve() not in portal_targets
    ]
    if missing_current_docs:
        report.add_error(
            "lifecycle.portal_current_docs_missing",
            "The docs portal must link active canonical current docs: "
            + ", ".join(path.name for path in missing_current_docs)
            + ".",
            portal,
        )
    for name, category_documents in active_categories.items():
        document_paths = {path.resolve() for path, _ in category_documents}
        document_parents = {path.resolve().parent for path, _ in category_documents}
        exposed = any(
            target in document_paths
            or (
                target in document_parents
                and target != portal.parent.resolve()
            )
            or (
                target.parent in document_parents
                and target.parent != portal.parent.resolve()
            )
            for target in portal_targets
        )
        if not exposed:
            report.add_error(
                f"lifecycle.portal_{name}_index_missing",
                f"The docs portal must link the activated {name.replace('_', ' ')} index or location.",
                portal,
            )


def validate_document_lifecycle(repo_root: Path, report: ValidationReport) -> None:
    documents = collect_lifecycle_documents(repo_root)
    validate_adr_lifecycle(repo_root, documents, report)
    validate_plan_lifecycle(documents["plan"], report)
    validate_unique_lifecycle_ids(
        documents["evidence"], "evidence_id", "evidence", report
    )
    validate_unique_lifecycle_ids(documents["review"], "review_id", "review", report)
    validate_wiki_decision_lifecycle(repo_root, documents, report)
    validate_lifecycle_portal(repo_root, documents, report)


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
        report.add_warning(
            "intelligence.glossary_missing",
            "Missing `intelligence/glossary.yaml`.",
            glossary_path,
        )

    actions_path = intelligence_dir / "manifests" / "actions.yaml"
    entities_path = intelligence_dir / "manifests" / "entities.yaml"
    datasets_path = intelligence_dir / "manifests" / "datasets.yaml"
    capabilities_path = intelligence_dir / "registry" / "capabilities.yaml"

    actions = (
        load_list_section(actions_path, "actions", report)
        if actions_path.exists()
        else None
    )
    if actions is None and not actions_path.exists():
        report.add_warning(
            "intelligence.actions_missing",
            "Missing `intelligence/manifests/actions.yaml`.",
            actions_path,
        )
    action_map = keyed_items(actions, "key", report, actions_path)

    entities = (
        load_list_section(entities_path, "entities", report)
        if entities_path.exists()
        else None
    )
    entity_map = keyed_items(entities, "key", report, entities_path)

    datasets = (
        load_list_section(datasets_path, "datasets", report)
        if datasets_path.exists()
        else None
    )
    if datasets is None and not datasets_path.exists():
        report.add_warning(
            "intelligence.datasets_missing",
            "Missing `intelligence/manifests/datasets.yaml`.",
            datasets_path,
        )
    dataset_map = keyed_items(datasets, "dataset_key", report, datasets_path)

    capabilities = (
        load_list_section(capabilities_path, "capabilities", report)
        if capabilities_path.exists()
        else None
    )
    if capabilities is None and not capabilities_path.exists():
        report.add_warning(
            "intelligence.capabilities_missing",
            "Missing `intelligence/registry/capabilities.yaml`.",
            capabilities_path,
        )
    capability_map = keyed_items(capabilities, "key", report, capabilities_path)

    for capability_key, item in capability_map.items():
        if str(item.get("status", "")).lower() in {"active", "implemented"}:
            validate_implementation_link(
                item.get("implementation"), report, capabilities_path
            )

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
            validate_implementation_link(
                item.get("implementation"), report, actions_path
            )
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
                    report.add_error(
                        "handlers.invalid_step",
                        "Each handler chain step must be a mapping.",
                        handler_path,
                    )
                    continue
                action_key = step.get("action")
                if not action_key:
                    report.add_error(
                        "handlers.missing_action",
                        "Handler chain step is missing an action.",
                        handler_path,
                    )
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
        validate_wiki_markdown_links(path, repo_root, report)
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


def validate_changed_files(
    repo_root: Path,
    changed_files_path: Path | None,
    report: ValidationReport,
    *,
    strict: bool = False,
) -> list[str]:
    def missing_input(code: str, message: str, path: Path | None = None) -> None:
        if strict:
            report.add_error(code, message, path)
        else:
            report.add_warning(code, message, path)

    if changed_files_path is None:
        missing_input(
            "drift.changed_files_missing",
            "No `--changed-files` input provided; drift suspicion checks were limited.",
        )
        return []
    if not changed_files_path.exists():
        missing_input(
            "drift.changed_files_not_found",
            f"Changed files list `{changed_files_path}` does not exist.",
            changed_files_path,
        )
        return []

    changed = [
        line.strip().replace("\\", "/")
        for line in changed_files_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not changed:
        missing_input(
            "drift.changed_files_empty",
            "Changed files list is empty; drift suspicion checks were limited.",
            changed_files_path,
        )
        return []

    def is_normalized_repo_path(value: str) -> bool:
        if Path(value).is_absolute() or re.match(r"^[A-Za-z]:/", value):
            return False
        if ".." in Path(value).parts or value.startswith("./") or "//" in value:
            return False
        return Path(value).as_posix() == value and "/./" not in f"/{value}/"

    invalid = sorted({path for path in changed if not is_normalized_repo_path(path)})
    if invalid:
        report.add_error(
            "drift.changed_files_invalid",
            "Changed files must be normalized repository-relative paths: "
            + ", ".join(invalid)
            + ".",
            changed_files_path,
        )
    duplicates = sorted(path for path, count in Counter(changed).items() if count > 1)
    if duplicates:
        report.add_error(
            "drift.changed_files_duplicate",
            "Changed files list contains duplicate path(s): "
            + ", ".join(duplicates)
            + ".",
            changed_files_path,
        )
    changed = sorted(set(changed))

    canonical_repo_memory_changed = any(
        path.startswith(("docs/", "intelligence/")) or path == "AGENTS.md"
        for path in changed
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
    entrypoint_changed = any(
        path.endswith(entrypoint_names) or path.startswith(("scripts/", "bin/"))
        for path in changed
    )
    if entrypoint_changed and "docs/CURRENT_STATE.md" not in changed:
        report.add_warning(
            "drift.current_state_missing",
            "Entrypoint-related files changed but `docs/CURRENT_STATE.md` was not part of the changed file list.",
            repo_root / "docs" / "CURRENT_STATE.md",
        )
    repo_map_dir_exists = (repo_root / "docs" / "repo-map").exists()
    if (
        repo_map_dir_exists
        and entrypoint_changed
        and "docs/repo-map/ENTRYPOINTS.md" not in changed
    ):
        report.add_warning(
            "drift.repo_map_entrypoints_missing",
            "Entrypoint-related files changed but `docs/repo-map/ENTRYPOINTS.md` was not part of the changed file list.",
            repo_root / "docs" / "repo-map" / "ENTRYPOINTS.md",
        )

    code_map_changed = any(
        path in {"docs/repo-map/MODULES.md", "docs/repo-map/SYMBOL_GRAPH.md"}
        for path in changed
    )
    broad_code_changes = [
        path
        for path in changed
        if path.endswith((".py", ".ts", ".tsx", ".rs", ".go"))
        and not path.startswith(("docs/", "intelligence/", "wiki/", "tests/"))
    ]
    if repo_map_dir_exists and len(broad_code_changes) >= 3 and not code_map_changed:
        report.add_warning(
            "drift.repo_map_code_map_missing",
            "Broad code changes occurred without `docs/repo-map/MODULES.md` or `docs/repo-map/SYMBOL_GRAPH.md` in the changed file list.",
            repo_root / "docs" / "repo-map",
        )

    if (
        "intelligence/manifests/actions.yaml" in changed
        and "intelligence/registry/capabilities.yaml" not in changed
    ):
        report.add_warning(
            "drift.capability_sync_missing",
            "`actions.yaml` changed without a matching `capabilities.yaml` change in the changed file list.",
            repo_root / "intelligence" / "registry" / "capabilities.yaml",
        )

    if (
        any(path.startswith("intelligence/handlers/") for path in changed)
        and "intelligence/manifests/actions.yaml" not in changed
    ):
        report.add_warning(
            "drift.handler_sync_missing",
            "Handler files changed without `actions.yaml` in the changed file list.",
            repo_root / "intelligence" / "manifests" / "actions.yaml",
        )

    if canonical_repo_memory_changed and not any(
        path.startswith("wiki/") for path in changed
    ):
        report.add_warning(
            "drift.wiki_memory_sync_missing",
            "Docs, intelligence, or AGENTS changed without a wiki memory update in the changed file list.",
            repo_root / "wiki",
        )
    return changed


def extract_impact_section(text: str, section: str) -> str:
    aliases = {
        "changed": ("Changed",),
        "checked not changed": (
            "Checked Not Changed",
            "Checked-Not-Changed",
            "Checked But Did Not Need Changes",
        ),
        "remaining drift": ("Remaining Drift",),
        "validator summary": ("Validator Summary",),
    }
    for heading in aliases[section]:
        body = extract_markdown_section(text, heading)
        if body:
            return body
    return ""


def is_placeholder_section(body: str, section: str) -> bool:
    normalized = re.sub(r"^[\s>*-]+", "", body.strip().lower())
    if not normalized or normalized.startswith(PLACEHOLDER_PREFIXES):
        return True
    for raw_line in normalized.splitlines():
        line = re.sub(r"^[\s>*-]+", "", raw_line).strip().rstrip(".")
        if not line or line.startswith("<!--"):
            continue
        if line in PLACEHOLDER_VALUES or line.startswith(PLACEHOLDER_PREFIXES):
            return True
        if section != "remaining drift" and line in {"none", "none recorded"}:
            return True
    return False


def validate_finalize_contract(
    repo_root: Path, changed: list[str], report: ValidationReport
) -> None:
    impact_path = repo_root / "docs" / "IMPACT_SUMMARY.md"
    if not impact_path.exists():
        report.add_error(
            "finalize.impact_summary_missing",
            "`--finalize` requires `docs/IMPACT_SUMMARY.md`.",
            impact_path,
        )
        return

    text = impact_path.read_text(encoding="utf-8")
    sections = {
        name: extract_impact_section(text, name)
        for name in IMPACT_SUMMARY_REQUIRED_SECTIONS
    }
    incomplete = [
        name for name, body in sections.items() if is_placeholder_section(body, name)
    ]
    if incomplete:
        report.add_error(
            "finalize.impact_summary_placeholder",
            "Finalize requires non-placeholder impact summary sections: "
            + ", ".join(incomplete)
            + ".",
            impact_path,
        )

    documented_paths = {
        value.strip().replace("\\", "/")
        for value in re.findall(r"`([^`]+)`", sections["changed"])
    }
    uncovered = [path for path in changed if path not in documented_paths]
    if uncovered:
        report.add_error(
            "finalize.impact_summary_changed_files_missing",
            "Impact summary `Changed` must name every changed file: "
            + ", ".join(uncovered)
            + ".",
            impact_path,
        )


def state_fingerprint(repo_root: Path, changed: list[str]) -> str:
    files: list[dict[str, str]] = []
    for relative in changed:
        path = repo_root / relative
        if path.is_symlink():
            digest = (
                "symlink:"
                + hashlib.sha256(
                    str(path.readlink()).encode("utf-8", errors="surrogateescape")
                ).hexdigest()
            )
            mode = oct(path.lstat().st_mode & 0o777)
        elif path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            mode = oct(path.stat().st_mode & 0o777)
        elif path.exists():
            try:
                revision = subprocess.run(
                    ["git", "-C", str(path), "rev-parse", "HEAD"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                status = subprocess.run(
                    ["git", "-C", str(path), "status", "--porcelain=v2", "-z"],
                    capture_output=True,
                    check=False,
                )
                if revision.returncode == 0 and status.returncode == 0:
                    submodule_state = (
                        revision.stdout.strip().encode("utf-8") + b"\0" + status.stdout
                    )
                    digest = "git-dir:" + hashlib.sha256(submodule_state).hexdigest()
                else:
                    digest = "<non-file>"
            except OSError:
                digest = "<non-file>"
            mode = oct(path.stat().st_mode & 0o777)
        else:
            try:
                baseline = subprocess.run(
                    ["git", "-C", str(repo_root), "show", f"HEAD:./{relative}"],
                    capture_output=True,
                    check=False,
                )
                digest = (
                    "deleted:" + hashlib.sha256(baseline.stdout).hexdigest()
                    if baseline.returncode == 0
                    else "<deleted-or-missing>"
                )
            except OSError:
                digest = "<deleted-or-missing>"
            mode = "<deleted>"
        files.append({"path": relative, "sha256": digest, "mode": mode})
    payload = json.dumps(
        files, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def collect_git_changed_files(repo_root: Path) -> tuple[set[str] | None, str]:
    try:
        probe = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None, "git_unavailable"
    if probe.returncode != 0:
        return None, "not_git"
    try:
        git_root = Path(probe.stdout.strip()).resolve()
    except Exception:
        return None, "git_root_invalid"
    try:
        repo_root.resolve().relative_to(git_root)
    except ValueError:
        return None, "git_root_mismatch"

    try:
        tracked = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "diff",
                "--relative",
                "--name-only",
                "-z",
                "HEAD",
                "--",
                ".",
            ],
            capture_output=True,
            check=False,
        )
        if tracked.returncode != 0:
            tracked = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "diff",
                    "--cached",
                    "--relative",
                    "--name-only",
                    "-z",
                    "--",
                    ".",
                ],
                capture_output=True,
                check=False,
            )
        untracked = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "ls-files",
                "--others",
                "--exclude-standard",
                "-z",
                "--",
            ],
            capture_output=True,
            check=False,
        )
    except OSError:
        return None, "git_unavailable"
    if tracked.returncode != 0 or untracked.returncode != 0:
        return None, "git_status_failed"

    return (
        {
            value.decode("utf-8", errors="surrogateescape").replace("\\", "/")
            for value in (tracked.stdout + untracked.stdout).split(b"\0")
            if value
        },
        "ok",
    )


def validate_git_changed_file_coverage(
    repo_root: Path,
    changed: list[str],
    changed_files_path: Path | None,
    receipt_path: Path,
    report: ValidationReport,
) -> None:
    observed, status = collect_git_changed_files(repo_root)
    if observed is None:
        if status != "not_git":
            report.add_error(
                "finalize.git_state_unavailable",
                f"Could not collect strict Git changed-file state ({status}).",
                repo_root,
            )
        return
    exclusions: set[str] = set()
    for path in (changed_files_path, receipt_path):
        if path is None:
            continue
        try:
            exclusions.add(path.resolve().relative_to(repo_root.resolve()).as_posix())
        except ValueError:
            pass
    observed -= exclusions
    declared = set(changed)
    omitted = sorted(observed - declared)
    extra = sorted(declared - observed)
    if omitted:
        report.add_error(
            "finalize.changed_files_incomplete",
            "Changed files list omits current Git change(s): "
            + ", ".join(omitted)
            + ".",
            changed_files_path,
        )
    if extra:
        report.add_error(
            "finalize.changed_files_not_current",
            "Changed files list includes path(s) that are not current Git changes: "
            + ", ".join(extra)
            + ".",
            changed_files_path,
        )


def write_finalize_receipt(
    receipt_path: Path, changed: list[str], fingerprint: str
) -> None:
    receipt = {
        "version": FINALIZE_RECEIPT_VERSION,
        "status": "passed",
        "finalized_at": datetime.now(timezone.utc).isoformat(),
        "state_fingerprint": fingerprint,
        "changed_files": changed,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt_path.with_suffix(receipt_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(receipt_path)


def verify_finalize_receipt(
    receipt_path: Path,
    changed: list[str],
    fingerprint: str,
    report: ValidationReport,
) -> None:
    if not receipt_path.exists():
        report.add_error(
            "finalize.receipt_missing", "Finalize receipt does not exist.", receipt_path
        )
        return
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception as exc:
        report.add_error(
            "finalize.receipt_invalid",
            f"Finalize receipt could not be parsed: {exc}",
            receipt_path,
        )
        return
    if not isinstance(receipt, dict):
        report.add_error(
            "finalize.receipt_invalid",
            "Finalize receipt root must be an object.",
            receipt_path,
        )
        return
    if (
        receipt.get("version") != FINALIZE_RECEIPT_VERSION
        or receipt.get("status") != "passed"
    ):
        report.add_error(
            "finalize.receipt_schema_invalid",
            "Finalize receipt has an unsupported version or non-passed status.",
            receipt_path,
        )
        return
    finalized_at = receipt.get("finalized_at")
    try:
        if not isinstance(finalized_at, str):
            raise ValueError("missing finalized_at")
        parsed_finalized_at = datetime.fromisoformat(
            finalized_at.replace("Z", "+00:00")
        )
        if parsed_finalized_at.tzinfo is None:
            raise ValueError("finalized_at must include a timezone")
    except ValueError:
        report.add_error(
            "finalize.receipt_schema_invalid",
            "Finalize receipt has an invalid `finalized_at` timestamp.",
            receipt_path,
        )
        return
    if (
        receipt.get("changed_files") != changed
        or receipt.get("state_fingerprint") != fingerprint
    ):
        report.add_error(
            "finalize.receipt_stale",
            "Finalize receipt is stale because the changed-file list or file contents changed.",
            receipt_path,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate docs/intelligence alignment in a repository."
    )
    parser.add_argument(
        "--repo-root", required=True, help="Repository root to validate."
    )
    parser.add_argument(
        "--format", default="text", choices=("text", "json"), help="Output format."
    )
    parser.add_argument(
        "--changed-files",
        help="Optional path to a newline-delimited changed files list for drift suspicion checks.",
    )
    finalize_group = parser.add_mutually_exclusive_group()
    finalize_group.add_argument(
        "--finalize",
        action="store_true",
        help="Require a warning-free final gate and write a state-bound completion receipt.",
    )
    finalize_group.add_argument(
        "--verify-finalized",
        action="store_true",
        help="Require the final gate and verify that an existing completion receipt is current.",
    )
    parser.add_argument(
        "--receipt",
        default=DEFAULT_FINALIZE_RECEIPT,
        help=f"Finalize receipt path relative to repo root (default: {DEFAULT_FINALIZE_RECEIPT}).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    report = ValidationReport(repo_root)

    if not repo_root.exists():
        report.add_error("repo.missing", "Repository root does not exist.", repo_root)
    elif not repo_root.is_dir():
        report.add_error(
            "repo.invalid", "Repository root must be a directory.", repo_root
        )
    else:
        final_gate = args.finalize or args.verify_finalized
        changed_files_path = (
            Path(args.changed_files).resolve() if args.changed_files else None
        )
        changed = validate_changed_files(
            repo_root,
            changed_files_path,
            report,
            strict=final_gate,
        )
        validate_docs(repo_root, report)
        validate_intelligence(repo_root, report)
        validate_wiki_memory(repo_root, report)
        validate_document_lifecycle(repo_root, report)
        if final_gate:
            receipt_argument = Path(args.receipt)
            receipt_path = (repo_root / receipt_argument).resolve()
            try:
                receipt_path.relative_to(repo_root)
            except ValueError:
                report.add_error(
                    "finalize.receipt_outside_repo",
                    "Finalize receipt must stay inside the repository root.",
                    receipt_path,
                )
            validate_finalize_contract(repo_root, changed, report)
            validate_git_changed_file_coverage(
                repo_root,
                changed,
                changed_files_path,
                receipt_path,
                report,
            )
            report.promote_warnings()
            fingerprint = state_fingerprint(repo_root, changed)
            report.finalize = {
                "mode": "verify" if args.verify_finalized else "write",
                "receipt": report._display_path(receipt_path),
                "state_fingerprint": fingerprint,
                "changed_file_count": len(changed),
                "status": "failed" if report.errors else "passed",
            }
            if not report.errors:
                if args.verify_finalized:
                    verify_finalize_receipt(receipt_path, changed, fingerprint, report)
                    report.finalize["status"] = (
                        "failed" if report.errors else "verified"
                    )
                else:
                    write_finalize_receipt(receipt_path, changed, fingerprint)
                    report.finalize["status"] = "written"

    if args.format == "json":
        print(report.as_json())
    else:
        report.print_text()
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
