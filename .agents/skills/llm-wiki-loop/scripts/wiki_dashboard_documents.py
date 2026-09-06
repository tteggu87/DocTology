"""Document catalog helpers for the loop-owned Wiki Studio dashboard."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import unquote, urlparse


def inside(root: Path, relative: str, prefixes=("raw/", "wiki/", "state/")) -> Path:
    if not isinstance(relative, str) or not relative.startswith(prefixes):
        raise ValueError("허용된 위키 경로가 아닙니다.")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("위키 폴더 밖의 파일은 열 수 없습니다.")
    return path


def files(root: Path, pattern: str):
    return sorted(p for p in root.glob(pattern) if p.is_file() and p.resolve().is_relative_to(root))


def read_json(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("작업 기록 형식이 잘못되었습니다.")
    return value


def title(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.M)
    return match.group(1).strip() if match else fallback


class DocumentCatalog:
    """Read-only dashboard document views using the caller's authoritative gates."""

    def __init__(self, workflow, batch):
        self.workflow = workflow
        self.batch = batch

    def coverage(self, root: Path, source: str, reports: list[Path]):
        matches = []
        for report in reports:
            try:
                values = self.workflow.frontmatter_values(report)
                if values.get("raw_path") != source:
                    continue
                counts = {k: int(values[f"source_units_{k}"]) for k in ("total", "projected", "omitted", "deferred")}
                valid = (counts["total"] > 0 and min(counts.values()) >= 0
                         and counts["total"] == sum(counts[k] for k in ("projected", "omitted", "deferred"))
                         and values.get("status") == "applied" and values.get("coverage_mode") == "full"
                         and values.get("source_sha256") == self.workflow.file_digest(inside(root, source)))
                text = report.read_text(encoding="utf-8")
                matches.append({**counts, "valid": valid, "path": report.relative_to(root).as_posix(),
                                "targets": sorted(set(re.findall(r"wiki/[^\s`\]\)>#]+\.md", text)))})
            except (OSError, ValueError, KeyError, self.workflow.WorkflowError):
                continue
        if len(matches) != 1:
            return None  # Multiple receipts are ambiguous; never pick a convenient percentage.
        return matches[0]

    def graph(self, root: Path, pages: list[Path], include_meta=False):
        nodes, contents, lookup = [], {}, {}
        for path in pages:
            relative = path.relative_to(root).as_posix()
            if relative.startswith("wiki/_meta/") and not include_meta:
                continue
            body = path.read_text(encoding="utf-8")
            node = {"id": relative, "title": title(body, path.stem),
                    "kind": ("skill" if relative.startswith(".agents/") else "document" if relative.startswith("docs/")
                             else "source" if "/sources/" in relative else "concept"),
                    "modified": path.stat().st_mtime}
            nodes.append(node)
            contents[relative] = re.sub(r"```.*?```", "", body, flags=re.S)
            for alias in (path.stem, relative, relative.removesuffix(".md"), relative.removeprefix("wiki/").removesuffix(".md")):
                lookup.setdefault(alias, set()).add(relative)
        ids = {n["id"] for n in nodes}
        edges = set()
        for relative, body in contents.items():
            links = [m.split("|", 1)[0].split("#", 1)[0].strip() for m in re.findall(r"\[\[([^\]]+)\]\]", body)]
            for link in links:
                candidates = lookup.get(link, set())
                if len(candidates) == 1:
                    target = next(iter(candidates))
                    if target != relative:
                        edges.add((relative, target))
            for href in re.findall(r"\[[^\]]*\]\(([^)]+)\)", body):
                parsed = urlparse(href.strip("<>"))
                if parsed.scheme or not parsed.path:
                    continue
                target = (root / relative).parent / unquote(parsed.path)
                target = target.resolve()
                if target.is_relative_to(root):
                    key = target.relative_to(root).as_posix()
                    if key in ids and key != relative:
                        edges.add((relative, key))
        return {"nodes": nodes, "edges": [{"source": a, "target": b} for a, b in sorted(edges)]}

    def project_pages(self, root: Path):
        """Explicit documentation surfaces, never arbitrary files or skill fixtures."""
        pages = set()
        for pattern in ("wiki/**/*.md", "docs/**/*.md", "README.md", "AGENTS.md",
                        ".agents/skills/*/SKILL.md", ".agents/skills/*/references/**/*.md",
                        ".agents/skills/*/dashboard/README.md"):
            pages.update(files(root, pattern))
        return sorted(pages)

    def document_inventory(self, root: Path, mode: str) -> dict[str, Path]:
        """Return the only Markdown files the dashboard may read for this root."""
        root = root.resolve()
        pages = self.project_pages(root) if mode == "project" else files(root, "wiki/**/*.md") + files(root, "raw/**/*.md")
        inventory = {}
        for path in pages:
            try:
                resolved = path.resolve(strict=True)
            except OSError:
                continue
            if path.suffix.lower() == ".md" and resolved.is_file() and resolved.is_relative_to(root):
                inventory[path.relative_to(root).as_posix()] = path
        return dict(sorted(inventory.items()))

    def preparation_document_inventory(self, root: Path, mode: str) -> dict[str, Path]:
        """The preparation role additionally reads the exact vault contract, not arbitrary root files."""
        inventory = self.document_inventory(root, mode)
        contract = root.resolve() / "AGENTS.md"
        if mode == "wiki" and contract.is_file() and not contract.is_symlink():
            inventory["AGENTS.md"] = contract
        return dict(sorted(inventory.items()))

    def preparation_document_payload(self, root: Path, mode: str, relative: str) -> dict:
        if relative != "AGENTS.md" or mode != "wiki":
            return self.document_payload(root, mode, relative)
        inventory = self.preparation_document_inventory(root, mode)
        if relative not in inventory:
            raise ValueError("위키 운영 규칙 파일을 안전하게 읽을 수 없습니다.")
        with inventory[relative].open("rb") as handle:
            data = handle.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("표시 가능한 Markdown 파일이 아닙니다.")
        text = data.decode("utf-8")
        return {"root": str(root.resolve()), "path": relative, "text": text, "content": text,
                "contentHash": hashlib.sha256(data).hexdigest(), "title": title(text, "AGENTS"),
                "rawSources": [], "links": []}

    def document_kind(self, relative: str) -> str:
        if relative.startswith("raw/"):
            return "source"
        if relative.startswith("wiki/"):
            return "wiki"
        if relative.startswith("docs/"):
            return "document"
        if relative.startswith(".agents/"):
            return "skill"
        return "project"

    def _without_fenced_code(self, text: str) -> str:
        return re.sub(r"^```.*?^```\s*$", "", text, flags=re.M | re.S)

    def _link_lookup(self, inventory: dict[str, Path]) -> dict[str, set[str]]:
        lookup: dict[str, set[str]] = {}
        for relative, path in inventory.items():
            aliases = {relative, relative.removesuffix(".md"), path.stem}
            if relative.startswith("wiki/"):
                aliases.add(relative.removeprefix("wiki/").removesuffix(".md"))
            if relative.startswith("raw/"):
                aliases.add(relative.removeprefix("raw/").removesuffix(".md"))
            for alias in aliases:
                lookup.setdefault(alias, set()).add(relative)
        return lookup

    def document_links(self, root: Path, relative: str, text: str, inventory: dict[str, Path]) -> list[dict]:
        """Resolve only real, in-inventory Markdown links; ambiguous wikilinks stay unresolved."""
        if relative not in inventory:
            raise ValueError("문서 목록에 없는 파일입니다.")
        root = root.resolve()
        body = self._without_fenced_code(text)
        lookup = self._link_lookup(inventory)
        resolved_by_path = {path.resolve(): key for key, path in inventory.items()}
        targets = set()
        for raw in re.findall(r"\[\[([^\]]+)\]\]", body):
            target = raw.split("|", 1)[0].split("#", 1)[0].strip()
            candidates = lookup.get(target, set())
            if len(candidates) == 1:
                targets.add(next(iter(candidates)))
        for raw in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", body):
            parsed = urlparse(raw.strip().strip("<>"))
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            decoded = unquote(parsed.path)
            paths = [inventory[relative].parent / decoded]
            if decoded.startswith(("wiki/", "raw/", "docs/", ".agents/")):
                paths.append(root / decoded)
            for unresolved in paths:
                try:
                    candidate = unresolved.resolve(strict=True)
                except (OSError, ValueError):
                    continue
                if not candidate.is_relative_to(root):
                    continue
                target = resolved_by_path.get(candidate)
                if target:
                    targets.add(target)
                    break
        targets.discard(relative)
        return [{"id": item, "title": title(inventory[item].read_text(encoding="utf-8"), inventory[item].stem),
                 "kind": self.document_kind(item)} for item in sorted(targets)]

    def receipt_source_map(self, root: Path, inventory: dict[str, Path]) -> dict[str, set[str]]:
        """Map explicit coverage receipt targets to their real raw source, without title guessing."""
        mapping: dict[str, set[str]] = {}
        raw_ids = {item for item in inventory if item.startswith("raw/")}
        wiki_ids = {item for item in inventory if item.startswith("wiki/")}
        for report in files(root, "wiki/_meta/ingest_reports/ingest-*.md"):
            try:
                values = self.workflow.frontmatter_values(report)
                source = values.get("raw_path")
                if source not in raw_ids or values.get("status") != "applied":
                    continue
                if values.get("source_sha256") and values.get("source_sha256") != self.workflow.file_digest(inventory[source]):
                    continue
                body = self._without_fenced_code(report.read_text(encoding="utf-8"))
                for target in set(re.findall(r"wiki/[^\s`\]\)>#]+\.md", body)) & wiki_ids:
                    mapping.setdefault(target, set()).add(source)
            except (OSError, ValueError, KeyError, self.workflow.WorkflowError):
                continue
        return mapping

    def raw_sources_for(self, root: Path, relative: str, text: str, inventory: dict[str, Path],
                        source_map: dict[str, set[str]] | None = None) -> list[dict]:
        sources = {relative} if relative.startswith("raw/") else set()
        for link in self.document_links(root, relative, text, inventory):
            if link["id"].startswith("raw/"):
                sources.add(link["id"])
        if source_map is None:
            source_map = self.receipt_source_map(root, inventory)
        sources.update(source_map.get(relative, set()))
        return [{"id": item, "title": title(inventory[item].read_text(encoding="utf-8"), inventory[item].stem)}
                for item in sorted(sources) if item in inventory]

    def document_payload(self, root: Path, mode: str, relative: str) -> dict:
        inventory = self.document_inventory(root, mode)
        if relative not in inventory:
            raise ValueError("문서 목록에 없는 파일입니다.")
        path = inventory[relative]
        if path.stat().st_size > 2_000_000:
            raise ValueError("표시 가능한 Markdown 파일이 아닙니다.")
        document_bytes = path.read_bytes()
        if len(document_bytes) > 2_000_000:
            raise ValueError("표시 가능한 Markdown 파일이 아닙니다.")
        text = document_bytes.decode("utf-8")
        return {"root": str(root.resolve()), "path": relative, "text": text, "content": text,
                "contentHash": hashlib.sha256(document_bytes).hexdigest(),
                "title": title(text, path.stem), "rawSources": self.raw_sources_for(root, relative, text, inventory),
                "links": self.document_links(root, relative, text, inventory)}

    def _search_terms(self, query: str) -> list[str]:
        normalized = unicodedata.normalize("NFKC", query).casefold()
        return list(dict.fromkeys(re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)))[:24]

    def _excerpt(self, text: str, terms: list[str], limit=700) -> str:
        # Reference cards show source prose, not YAML administration fields.
        text = re.sub(r"\A---\r?\n[\s\S]*?\r?\n---\r?\n", "", text)
        normalized = unicodedata.normalize("NFKC", text).casefold()
        starts = [normalized.find(term) for term in terms if normalized.find(term) >= 0]
        center = min(starts) if starts else 0
        start = max(0, center - limit // 3)
        end = min(len(text), start + limit)
        if end - start < limit:
            start = max(0, end - limit)
        prefix = "…" if start else ""
        suffix = "…" if end < len(text) else ""
        return prefix + text[start:end].strip().replace("\x00", "") + suffix

    def lexical_candidates(self, root: Path, mode: str, query: str, limit=6) -> list[dict]:
        """Deterministic local candidate discovery. It does not validate answer citations."""
        terms = self._search_terms(query)
        if not terms:
            return []
        inventory = self.document_inventory(root, mode)
        source_map = self.receipt_source_map(root, inventory)
        ranked = []
        for relative, path in inventory.items():
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            heading = title(text, path.stem)
            normalized_text = unicodedata.normalize("NFKC", text).casefold()
            normalized_title = unicodedata.normalize("NFKC", heading).casefold()
            normalized_path = unicodedata.normalize("NFKC", relative).casefold()
            matched = [term for term in terms if term in normalized_text or term in normalized_path]
            if not matched:
                continue
            full = unicodedata.normalize("NFKC", query).casefold().strip()
            score = (len(matched) * 100 + (80 if full and full in normalized_text else 0)
                     + sum(25 for term in matched if term in normalized_title)
                     + min(40, sum(normalized_text.count(term) for term in matched)))
            lane = 0 if relative.startswith("wiki/") else 1 if relative.startswith("docs/") else 2 if not relative.startswith("raw/") else 3
            ranked.append((-score, lane, relative, text, heading))
        candidates = []
        for number, (_, _, relative, text, heading) in enumerate(sorted(ranked)[:max(0, min(limit, 6))], 1):
            candidates.append({"id": relative, "title": heading, "number": number,
                               "excerpt": self._excerpt(text, terms),
                               "rawSources": self.raw_sources_for(root, relative, text, inventory, source_map)})
        return candidates

    def snapshot(self, root: Path, mode="wiki"):
        root = root.resolve()
        if mode == "project":
            return {"demo": False, "mode": "project", "readOnly": True, "root": str(root), "name": root.name,
                    "sources": [], "graph": self.graph(root, self.project_pages(root), include_meta=True),
                    "batches": [], "warnings": [], "checkedAt": time.time()}
        warnings, runs = [], {}
        for path in files(root, "state/wiki_runs/*.json"):
            try:
                run = read_json(path)
                source = run["source"]
                inside(root, source, ("raw/",))
                if source not in runs or str(run.get("updated_at", "")) > str(runs[source].get("updated_at", "")):
                    runs[source] = run
            except (OSError, ValueError, KeyError, TypeError):
                warnings.append(f"읽을 수 없는 작업 기록: {path.name}")
        batches = []
        for path in files(root, "state/wiki_batches/*/manifest.json"):
            try:
                batches.append(self.batch.batch_status(root, path.parent.name))
            except (OSError, ValueError, KeyError, TypeError, AttributeError, self.batch.BatchError, self.workflow.WorkflowError):
                warnings.append(f"확인할 수 없는 배치: {path.parent.name}")
        reports = files(root, "wiki/_meta/ingest_reports/ingest-*.md")
        sources = []
        for path in files(root, "raw/**/*.md"):
            relative = path.relative_to(root).as_posix()
            run = runs.get(relative)
            status, stage, refs = None, "queued", set()
            cov = self.coverage(root, relative, reports)
            if run:
                try:
                    status = self.workflow.project_status(root, run)
                    completed = status["completed_stages"]
                    final_refs = run.get("stages", {}).get("final_review_completed", {}).get("references", [])
                    if status["wiki_complete"]:
                        self.workflow.validate_full_coverage_receipt(root, run, [r["path"] for r in final_refs], "ready")
                    stage = "review" if len(completed) >= 7 else "writing" if len(completed) >= 3 else "reading"
                    if status["wiki_complete"] and status["run_status"] == "completed":
                        stage = "done"
                    if status["stale_stages"] or any(b != "PROCEDURE_STAGE_MISSING" for b in status["blockers"]):
                        stage = "blocked"
                    for entry in run.get("stages", {}).values():
                        refs.update(r["path"] for r in entry.get("references", []) if r.get("path", "").startswith("wiki/"))
                except (OSError, ValueError, KeyError, TypeError, self.workflow.WorkflowError) as exc:
                    stage = "blocked"
                    status = {"blockers": [str(exc)], "completed_stages": [], "missing_stages": list(self.workflow.PROCEDURE_ORDER)}
            memberships = [b for b in batches if run and any(
                isinstance(r, dict) and r.get("path") == relative and r.get("run_id") == run["run_id"]
                and r.get("disposition") != "deferred_with_reason" for r in b["sources"])]
            if stage == "done" and any(b["status"] != "certified" or (b.get("certification") or {}).get("status") != "pass" for b in memberships):
                stage = "review"
            if cov and cov["valid"]:
                refs.update(cov["targets"])
            sources.append({"id": relative, "title": title(path.read_text(encoding="utf-8"), path.stem),
                            "stage": stage, "coverage": cov, "run": status,
                            "references": sorted(refs), "modified": path.stat().st_mtime})
        return {"demo": False, "mode": "wiki", "readOnly": False, "root": str(root), "name": root.name, "sources": sources,
                "graph": self.graph(root, files(root, "wiki/**/*.md")), "batches": batches,
                "warnings": warnings, "checkedAt": time.time()}
