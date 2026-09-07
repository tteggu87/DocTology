"""Derived native read/citation projection; Pi's active transcript stays authoritative."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


CITATION_INSTRUCTION = """When your answer relies on local wiki or raw documents, cite the documents you actually used with Markdown links using their exact workspace-relative paths, for example [Document title](wiki/concepts/example.md). Place links near the supported statements. Sources read earlier in this session can be cited without rereading them. Do not invent sources or cite a document merely because you found its filename. Keep your normal tools and workflow; no extra reporting tool is required. This is a display convention, not a request to change the user's task."""


class NativeCitations:
    MAX_ENTRIES = 4096
    MAX_READS = 128
    MAX_FILE_BYTES = 2_000_000

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.entries = {}
        self.cursor = None
        self.leaf = None

    def request_arguments(self):
        return {"since": self.cursor} if self.cursor else {}

    def update(self, data):
        if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
            raise ValueError("Pi 읽기 기록을 확인하지 못했습니다.")
        # Keep only parent identity and bounded read payloads, never reasoning text.
        for entry in data["entries"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or len(entry["id"]) > 200:
                continue
            key = entry["id"]
            if key not in self.entries and len(self.entries) >= self.MAX_ENTRIES:
                self.entries.clear()
                self.cursor = None
                raise ValueError("읽기 기록 표시 한도를 넘었습니다. 인용을 자동 연결하지 않았습니다.")
            row = {"parent": entry.get("parentId")}
            message = entry.get("message") or {}
            if isinstance(message, dict):
                content = message.get("content")
                if message.get("role") == "assistant" and isinstance(content, list):
                    row["calls"] = {part["id"]: part.get("arguments", {}).get("path")
                                    for part in content[:128] if isinstance(part, dict) and part.get("type") == "toolCall"
                                    and part.get("name") == "read" and isinstance(part.get("id"), str)
                                    and len(part["id"]) <= 200 and isinstance(part.get("arguments"), dict)
                                    and isinstance(part["arguments"].get("path"), str) and len(part["arguments"]["path"]) <= 2000}
                elif message.get("role") == "toolResult" and message.get("toolName") == "read" and not message.get("isError"):
                    text = "\n".join(part["text"] for part in content or []
                                     if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str))
                    row["read"] = (message.get("toolCallId"), text[:4096])
            self.entries[key] = row
            self.cursor = key
        self.leaf = data.get("leafId")

    def _path(self, value):
        if not isinstance(value, str) or len(value) > 2000 or "\x00" in value:
            return None
        try:
            value = value.replace("\\", "/")
            path = Path(value)
            path = path if path.is_absolute() else self.root / path
            relative = path.relative_to(self.root)
            if not relative.parts or relative.parts[0] not in {"wiki", "raw"} or path.suffix.lower() != ".md":
                return None
            if any(part in {"..", "."} or part.startswith(".") for part in relative.parts):
                return None
            parent = self.root
            for part in relative.parts:
                parent = parent / part
                if parent.is_symlink():
                    return None
            if path.resolve().is_relative_to(self.root) and path.is_file():
                return relative.as_posix()
        except (OSError, ValueError):
            pass
        return None

    def _reads(self):
        branch, seen, key = [], set(), self.leaf
        while key:
            if key in seen or key not in self.entries:
                raise ValueError("현재 Pi 대화 가지의 읽기 기록을 확인하지 못했습니다.")
            seen.add(key)
            row = self.entries[key]
            branch.append(row)
            key = row["parent"]
        calls, reads = {}, {}
        for row in reversed(branch):
            calls.update(row.get("calls", {}))
            if "read" not in row:
                continue
            tool_id, text = row["read"]
            path = self._path(calls.get(tool_id))
            if path and text.strip():
                # Pi's truncation footer is not source content.
                snippet = re.split(r"\n\[(?:Showing |Use offset=|Output truncated)", text)[0].strip()[:2048]
                if len(snippet) >= 8:
                    reads.pop(path, None)
                    reads[path] = snippet
                    while len(reads) > self.MAX_READS:
                        reads.pop(next(iter(reads)))
        return reads

    def _targets(self, answer, reads):
        lines, fence = [], None
        for line in answer.splitlines():
            marker = re.match(r"^\s*(`{3,}|~{3,})", line)
            if marker:
                run = marker.group(1)
                if fence is None:
                    fence = run
                elif run[0] == fence[0] and len(run) >= len(fence):
                    fence = None
                continue
            if fence is None:
                lines.append(line)
        clean = re.sub(r"(`+).*?\1", "", "\n".join(lines))
        matches = []
        for match in re.finditer(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)|\[\[([^\]\n]+)\]\]", clean):
            target = match.group(1) or match.group(2).split("|", 1)[0]
            target = target.strip().strip("<>")
            try:
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or parsed.query:
                    continue
                target = unquote(parsed.path)
                if target.startswith("./"):
                    target = target[2:]
            except ValueError:
                continue
            # Full paths are preferred; basename wikilinks need a unique read match.
            candidates = [path for path in reads if target in {path, path[:-3]}]
            if not candidates and match.group(2) and "/" not in target:
                candidates = [path for path in reads if Path(path).stem == target.removesuffix(".md")]
                # Check unseen namesakes too: an ambiguous wiki link is not a citation.
                if len(candidates) == 1:
                    namesakes = list((self.root / "wiki").rglob(Path(candidates[0]).name))
                    if len(namesakes) != 1:
                        candidates = []
            if len(candidates) == 1 and candidates[0] not in matches:
                matches.append(candidates[0])
        return matches[:20]

    def project(self, answer):
        reads = self._reads()
        references = []
        for path in self._targets(answer, reads):
            if self._path(path) != path:
                continue
            try:
                file = self.root / path
                with file.open("rb") as handle:
                    raw = handle.read(self.MAX_FILE_BYTES + 1)
                if len(raw) > self.MAX_FILE_BYTES:
                    continue
                text = raw.decode("utf-8")
                snippet = reads[path]
                if snippet not in text:
                    continue  # A changed/missing read excerpt cannot support this link.
                heading = re.search(r"(?m)^#\s+(.+)$", text)
                title = heading.group(1).strip() if heading else Path(path).stem
                references.append({"id": path, "title": title[:500], "number": len(references) + 1,
                                   "excerpt": snippet[:1000], "rawSources": [],
                                   "contentHash": hashlib.sha256(raw).hexdigest(), "provenance": "native-read-link"})
            except (OSError, UnicodeError):
                continue
        return references, [{"id": path, "title": Path(path).stem} for path in list(reads)[-64:]]
