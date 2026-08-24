#!/usr/bin/env python3
"""Minimal local tooling for an Obsidian-first LLM Wiki.

The `ingest` command performs source registration only.
It does not run ontology-backed extraction or full wiki synthesis.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = ROOT / "wiki"
META_DIR = WIKI_DIR / "_meta"
RAW_DIR = ROOT / "raw"
TEMPLATE_PATH = ROOT / "templates" / "source_page_template.md"
ANSWER_RECEIPT_TEMPLATE_PATH = ROOT / "templates" / "answer_receipt_template.md"

VALID_PAGE_DIRS = [
    "analyses",
    "concepts",
    "entities",
    "people",
    "projects",
    "sources",
    "timelines",
]

MAX_PAGE_LINES = 200
LOG_ROTATION_THRESHOLD = 500
RECOMMENDED_RAW_SOURCE_DIRS = [
    RAW_DIR / "inbox",
    RAW_DIR / "processed",
    RAW_DIR / "notes",
]


def today() -> str:
    return dt.date.today().isoformat()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^0-9a-z가-힣ㄱ-ㅎㅏ-ㅣ]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-") or "untitled"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def bullet_list(items: list[str], *, empty: str = "None recorded.") -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {item}" for item in items)


def iter_markdown_pages() -> list[Path]:
    return sorted(
        path
        for path in WIKI_DIR.rglob("*.md")
        if path.is_file()
    )


def page_title_from_content(path: Path, content: str) -> str:
    match = re.search(r'^title:\s*"?(.*?)"?\s*$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    heading = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if heading:
        return heading.group(1).strip()
    return path.stem.replace("-", " ").title()


def page_type_from_path(path: Path) -> str:
    try:
        return path.relative_to(WIKI_DIR).parts[0]
    except ValueError:
        return "unknown"


def strip_frontmatter(content: str) -> str:
    return re.sub(r"\A---\s*\n.*?\n---\s*\n?", "", content, count=1, flags=re.DOTALL)


def refresh_frontmatter_updated(content: str) -> str:
    match = re.match(r"\A---\n(.*?)\n---\n?", content, flags=re.DOTALL)
    if not match:
        return content

    frontmatter = match.group(1)
    if re.search(r"^updated:\s*.*$", frontmatter, flags=re.MULTILINE):
        frontmatter = re.sub(
            r"^updated:\s*.*$",
            f"updated: {today()}",
            frontmatter,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        frontmatter = frontmatter.rstrip() + f"\nupdated: {today()}"

    return "---\n" + frontmatter.rstrip() + "\n---\n" + content[match.end():]


def extract_summary(content: str) -> str:
    lines = [line.strip() for line in strip_frontmatter(content).splitlines()]
    for line in lines:
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            return line[2:].strip()
        return line
    return "No summary yet."


def has_frontmatter(content: str) -> bool:
    return content.startswith("---\n")


def wikilinks(content: str) -> list[str]:
    return re.findall(r"\[\[([^\]|#]+)", content)


def page_lookup() -> dict[str, Path]:
    lookup: dict[str, Path] = {}
    for path in iter_markdown_pages():
        lookup[path.stem] = path
    return lookup


def indexed_page_stems() -> set[str]:
    path = META_DIR / "index.md"
    if not path.exists():
        return set()
    return set(re.findall(r"^- \[\[([^\]]+)\]\]", read_text(path), re.MULTILINE))


def existing_created_date(path: Path) -> str | None:
    if not path.exists():
        return None
    match = re.search(r"^created:\s*(\d{4}-\d{2}-\d{2})\s*$", read_text(path), re.MULTILINE)
    return match.group(1) if match else None


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def is_recommended_raw_source(path: Path) -> bool:
    return any(is_under(path, source_dir) for source_dir in RECOMMENDED_RAW_SOURCE_DIRS)


def rebuild_index() -> Path:
    pages_by_section: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for path in iter_markdown_pages():
        rel = path.relative_to(WIKI_DIR)
        content = read_text(path)
        if rel == Path("_meta/index.md"):
            continue
        title = page_title_from_content(path, content)
        summary = extract_summary(content)
        section = page_type_from_path(path)
        pages_by_section[section].append((path.stem, title, summary))

    index_path = META_DIR / "index.md"
    created = existing_created_date(index_path) or today()

    lines = [
        "---",
        'title: "Index"',
        "type: meta",
        "status: active",
        f"created: {created}",
        f"updated: {today()}",
        "---",
        "",
        "# Index",
        "",
        "This file is rebuilt by `python scripts/llm_wiki.py reindex`.",
        "",
    ]

    ordered_sections = ["_meta"] + VALID_PAGE_DIRS
    for section in ordered_sections:
        entries = sorted(pages_by_section.get(section, []), key=lambda item: item[1].lower())
        if not entries:
            continue
        heading = "Meta" if section == "_meta" else section.replace("-", " ").title()
        lines.extend([f"## {heading}", ""])
        for stem, title, summary in entries:
            lines.append(f"- [[{stem}]] - {summary}")
        lines.append("")

    out = META_DIR / "index.md"
    write_text(out, "\n".join(lines).rstrip() + "\n")
    return out


def append_log(kind: str, title: str, bullets: list[str]) -> Path:
    path = META_DIR / "log.md"
    existing = read_text(path) if path.exists() else "---\ntitle: Log\ntype: meta\nstatus: active\ncreated: {}\nupdated: {}\n---\n\n# Log\n".format(today(), today())
    existing = refresh_frontmatter_updated(existing)
    entry_lines = [
        "",
        f"## [{today()}] {kind} | {title}",
        "",
    ]
    for bullet in bullets:
        entry_lines.append(f"- {bullet}")
    entry_lines.append("")
    write_text(path, existing.rstrip() + "\n" + "\n".join(entry_lines))
    return path


def ingest_source(raw_path_str: str, title: str | None) -> int:
    raw_path = (ROOT / raw_path_str).resolve() if not Path(raw_path_str).is_absolute() else Path(raw_path_str).resolve()
    if not raw_path.exists():
        print(f"Source not found: {raw_path}", file=sys.stderr)
        return 1

    if ROOT not in raw_path.parents and raw_path != ROOT:
        print("Source path must live inside this project.", file=sys.stderr)
        return 1

    if not is_recommended_raw_source(raw_path):
        allowed = ", ".join(path.relative_to(ROOT).as_posix() + "/" for path in RECOMMENDED_RAW_SOURCE_DIRS)
        print(
            f"Warning: source is outside recommended raw source folders ({allowed}). "
            "Registration will continue because the path is inside this project.",
            file=sys.stderr,
        )

    source_title = title or raw_path.stem.replace("-", " ").replace("_", " ").title()
    filename = f"source-{today()}-{slugify(source_title)}.md"
    source_page = WIKI_DIR / "sources" / filename
    relative_raw_path = raw_path.relative_to(ROOT).as_posix()

    template = read_text(TEMPLATE_PATH)
    content = (
        template.replace("{{title}}", source_title)
        .replace("{{date}}", today())
        .replace("{{raw_path}}", relative_raw_path)
    )

    if source_page.exists():
        print(f"Source page already exists: {source_page.relative_to(ROOT)}")
    else:
        write_text(source_page, content)
        print(f"Created source page: {source_page.relative_to(ROOT)}")

    append_log(
        "ingest",
        source_title,
        [
            f"Registered source at `{relative_raw_path}`",
            f"Created or reused `[[{source_page.stem}]]`",
            "Pending LLM synthesis or ontology-backed ingest into the broader wiki",
        ],
    )
    rebuild_index()
    print("Source registration complete.")
    print("Full LLM synthesis or ontology-backed ingest is still pending.")
    print("Next: use agent-guided work or the llm-wiki-loop skill to complete the gated wiki growth loop.")
    return 0


def available_analysis_path(title: str) -> Path:
    base = WIKI_DIR / "analyses" / f"answer-{today()}-{slugify(title)}.md"
    if not base.exists():
        return base
    for index in range(2, 1000):
        candidate = WIKI_DIR / "analyses" / f"answer-{today()}-{slugify(title)}-{index}.md"
        if not candidate.exists():
            return candidate
    raise RuntimeError("Could not allocate answer receipt path")


def create_answer_receipt(
    question: str,
    title: str | None,
    answer_summary: str | None,
    used_wiki_pages: list[str],
    used_source_pages: list[str],
    used_raw_files: list[str],
    used_jsonl_hints: list[str],
    wiki_updates: list[str],
    uncertainties: list[str],
    follow_up: list[str],
) -> int:
    receipt_title = title or question
    path = available_analysis_path(receipt_title)
    template = read_text(ANSWER_RECEIPT_TEMPLATE_PATH)
    content = (
        template.replace("{{title}}", receipt_title)
        .replace("{{date}}", today())
        .replace("{{question}}", question)
        .replace("{{answer_summary}}", answer_summary or "TBD.")
        .replace("{{used_wiki_pages}}", bullet_list(used_wiki_pages))
        .replace("{{used_source_pages}}", bullet_list(used_source_pages))
        .replace("{{used_raw_files}}", bullet_list(used_raw_files))
        .replace("{{used_jsonl_hints}}", bullet_list(used_jsonl_hints))
        .replace("{{wiki_updates}}", bullet_list(wiki_updates))
        .replace("{{uncertainties}}", bullet_list(uncertainties))
        .replace("{{follow_up}}", bullet_list(follow_up))
    )

    write_text(path, content)
    append_log(
        "query",
        receipt_title,
        [
            f"Created answer receipt at `{path.relative_to(ROOT).as_posix()}`",
            "Receipt records context actually read and wiki updates made; it is not a heuristic answer generator.",
        ],
    )
    rebuild_index()
    print(f"Created answer receipt: {path.relative_to(ROOT)}")
    print("Answer receipt records context and follow-up only; it does not perform semantic routing or answer generation.")
    return 0


def lint_wiki() -> int:
    lookup = page_lookup()
    broken: list[tuple[Path, str]] = []
    orphan_source_pages: list[Path] = []
    orphan_synthesis_pages: list[Path] = []
    no_frontmatter: list[Path] = []
    unindexed: list[Path] = []
    oversized: list[tuple[Path, int]] = []
    duplicate_titles: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    inbound: dict[str, int] = defaultdict(int)
    indexed_stems = indexed_page_stems()

    for path in iter_markdown_pages():
        rel = path.relative_to(WIKI_DIR)
        content = read_text(path)
        title = page_title_from_content(path, content)
        line_count = len(content.splitlines())
        is_meta_page = rel.parts[0] == "_meta"

        if rel != Path("_meta/index.md") and path.stem not in indexed_stems:
            unindexed.append(path)

        if rel.parts[0] != "_meta" and line_count > MAX_PAGE_LINES:
            oversized.append((path, line_count))

        duplicate_titles[title.casefold()].append((title, path))

        if not has_frontmatter(content):
            no_frontmatter.append(path)
        for link in wikilinks(content):
            if link in lookup:
                if not is_meta_page:
                    inbound[link] += 1
            else:
                broken.append((path, link))

    for stem, path in lookup.items():
        rel = path.relative_to(WIKI_DIR)
        if rel.parts[0] == "_meta":
            continue
        if inbound.get(stem, 0) == 0:
            if rel.parts[0] == "sources":
                orphan_source_pages.append(path)
            else:
                orphan_synthesis_pages.append(path)

    duplicate_title_hits = [
        entries for entries in duplicate_titles.values() if len(entries) > 1
    ]

    log_path = META_DIR / "log.md"
    log_entries = 0
    log_rotation_warning = False
    if log_path.exists():
        log_entries = len(re.findall(r"^##\s+\[", read_text(log_path), re.MULTILINE))
        log_rotation_warning = log_entries > LOG_ROTATION_THRESHOLD

    print("Lint results")
    print("Hard failures")
    print(f"- Broken wikilinks: {len(broken)}")
    print(f"- Missing frontmatter: {len(no_frontmatter)}")
    print("")
    print("Advisory warnings")
    print(f"- Orphan source pages: {len(orphan_source_pages)}")
    print(f"- Orphan synthesis pages: {len(orphan_synthesis_pages)}")
    print(f"- Unindexed pages: {len(unindexed)}")
    print(f"- Oversized pages (>{MAX_PAGE_LINES} lines): {len(oversized)}")
    print(f"- Duplicate titles: {len(duplicate_title_hits)}")
    print(f"- Log rotation warnings: {1 if log_rotation_warning else 0}")
    print("")

    if broken:
        print("Broken wikilinks:")
        for path, link in broken:
            print(f"- {path.relative_to(ROOT)} -> [[{link}]]")
        print("")

    if orphan_source_pages:
        print("Orphan source pages:")
        for path in orphan_source_pages:
            print(f"- {path.relative_to(ROOT)}")
        print("")

    if orphan_synthesis_pages:
        print("Orphan synthesis pages:")
        for path in orphan_synthesis_pages:
            print(f"- {path.relative_to(ROOT)}")
        print("")

    if unindexed:
        print("Pages missing from wiki/_meta/index.md:")
        for path in unindexed:
            print(f"- {path.relative_to(ROOT)}")
        print("")

    if oversized:
        print(f"Oversized pages (>{MAX_PAGE_LINES} lines):")
        for path, line_count in oversized:
            print(f"- {path.relative_to(ROOT)} ({line_count} lines)")
        print("")

    if duplicate_title_hits:
        print("Duplicate page titles:")
        for entries in duplicate_title_hits:
            title = entries[0][0]
            print(f"- {title}")
            for _, path in entries:
                print(f"  - {path.relative_to(ROOT)}")
        print("")

    if log_rotation_warning:
        print("Log rotation warning:")
        print(
            f"- wiki/_meta/log.md has {log_entries} entries; rotate it after {LOG_ROTATION_THRESHOLD} entries."
        )
        print("")

    if no_frontmatter:
        print("Pages missing frontmatter:")
        for path in no_frontmatter:
            print(f"- {path.relative_to(ROOT)}")
        print("")

    return 1 if broken or no_frontmatter else 0


def status() -> int:
    markdown_pages = iter_markdown_pages()
    raw_files = [path for path in RAW_DIR.rglob("*") if path.is_file()]
    log_path = META_DIR / "log.md"
    index_path = META_DIR / "index.md"
    log_entries = 0
    index_entries = 0

    if log_path.exists():
        log_entries = len(re.findall(r"^##\s+\[", read_text(log_path), re.MULTILINE))
    if index_path.exists():
        index_entries = len(re.findall(r"^- \[\[", read_text(index_path), re.MULTILINE))

    print("LLM Wiki status")
    print(f"- Root: {ROOT}")
    print(f"- Raw files: {len(raw_files)}")
    print(f"- Wiki pages: {len(markdown_pages)}")
    print(f"- Log entries: {log_entries}")
    print(f"- Index entries: {index_entries}")
    return 0


def log_command(kind: str, title: str, bullets: list[str]) -> int:
    append_log(kind, title, bullets or ["No details recorded."])
    print(f"Appended {kind} entry to wiki/_meta/log.md")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local tooling for an Obsidian-first LLM Wiki. `ingest` is source registration only."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser(
        "ingest",
        help="Register a raw source and create a source page stub. This is not ontology-backed ingest.",
    )
    ingest.add_argument("path", help="Path to the raw source, absolute or relative to project root.")
    ingest.add_argument("--title", help="Human-readable title for the source page.")

    receipt = sub.add_parser(
        "answer-receipt",
        help="Create a structural answer receipt under wiki/analyses/. This records context; it does not answer.",
    )
    receipt.add_argument("question", help="Question that was answered or investigated.")
    receipt.add_argument("--title", help="Receipt title. Defaults to the question.")
    receipt.add_argument("--answer-summary", help="Optional short answer summary. Defaults to TBD.")
    receipt.add_argument("--used-wiki", action="append", default=[], help="Wiki page actually read. Repeatable.")
    receipt.add_argument("--used-source", action="append", default=[], help="Source page actually read. Repeatable.")
    receipt.add_argument("--used-raw", action="append", default=[], help="Raw file revisited because wiki context was insufficient. Repeatable.")
    receipt.add_argument("--used-jsonl", action="append", default=[], help="JSONL or ontology hint consulted. Repeatable.")
    receipt.add_argument("--wiki-update", action="append", default=[], help="Wiki page created or updated after the answer. Repeatable.")
    receipt.add_argument("--uncertainty", action="append", default=[], help="Uncertainty or limitation to preserve. Repeatable.")
    receipt.add_argument("--follow-up", action="append", default=[], help="Follow-up action or open question. Repeatable.")

    sub.add_parser("reindex", help="Rebuild wiki/_meta/index.md")
    sub.add_parser("lint", help="Check for broken links, source/synthesis orphans, and missing frontmatter.")
    sub.add_parser("status", help="Show counts and basic wiki health metrics.")

    log_parser = sub.add_parser("log", help="Append a structured log entry.")
    log_parser.add_argument("kind", help="Entry type such as ingest, query, lint, or refactor.")
    log_parser.add_argument("title", help="Short title for the log entry.")
    log_parser.add_argument(
        "details",
        nargs="*",
        help="Optional bullet items for the log entry.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ingest":
        return ingest_source(args.path, args.title)
    if args.command == "answer-receipt":
        return create_answer_receipt(
            args.question,
            args.title,
            args.answer_summary,
            args.used_wiki,
            args.used_source,
            args.used_raw,
            args.used_jsonl,
            args.wiki_update,
            args.uncertainty,
            args.follow_up,
        )
    if args.command == "reindex":
        out = rebuild_index()
        print(f"Rebuilt {out.relative_to(ROOT)}")
        return 0
    if args.command == "lint":
        return lint_wiki()
    if args.command == "status":
        return status()
    if args.command == "log":
        return log_command(args.kind, args.title, args.details)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
