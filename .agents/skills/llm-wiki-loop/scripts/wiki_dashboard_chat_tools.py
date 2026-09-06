#!/usr/bin/env python3
"""Ephemeral read-only document tools for one Wiki Studio chat.

The bridge deliberately exposes four bounded discovery/read operations instead
of general filesystem or process tools.  The dashboard supplies the canonical
inventory and document-payload helpers; this module rechecks that inventory for
every operation that can touch document bytes.
"""
from __future__ import annotations

import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path, PurePosixPath
import re
import secrets
import threading
import unicodedata
from urllib.parse import urlsplit


__all__ = ["WikiChatTools", "WikiChatToolError"]


class WikiChatToolError(ValueError):
    """A bounded, client-safe tool error."""

    def __init__(self, message: str, *, status: int = 400, exhausted: bool = False):
        super().__init__(message)
        self.status = status
        self.exhausted = exhausted


class _ToolServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False


class WikiChatTools:
    """Per-chat localhost capability bridge over helper-approved Markdown."""

    MAX_BODY_BYTES = 64 * 1024
    HTTP_READ_TIMEOUT_SECONDS = 5
    MAX_FILE_BYTES = 2_000_000
    MAX_TOOL_CALLS = 64
    MAX_READ_DOCUMENTS = 24
    MAX_RETURNED_CHARACTERS = 160_000
    MAX_EVENTS = 64
    MAX_LIST_LIMIT = 40
    MAX_SEARCH_LIMIT = 12
    MAX_READ_LIMIT = 10_000
    MAX_CANDIDATE_EXCERPT = 6_000
    MAX_LINKS = 200

    _TOOLS = {"ready", "wiki_list", "wiki_search", "wiki_read", "wiki_links"}
    _SCOPES = {"wiki", "raw", "all"}

    def __init__(self, root, mode: str, helpers):
        try:
            self.root = Path(root).resolve(strict=True)
        except (OSError, TypeError, ValueError):
            raise ValueError("Wiki root is unavailable.") from None
        if not self.root.is_dir():
            raise ValueError("Wiki root must be a directory.")
        if mode not in ("wiki", "project"):
            raise ValueError("Unsupported Wiki Studio mode.")
        self.mode = mode
        if isinstance(helpers, dict):
            inventory = helpers.get("document_inventory")
            payload = helpers.get("document_payload")
        else:
            inventory = getattr(helpers, "document_inventory", None)
            payload = getattr(helpers, "document_payload", None)
        if not callable(inventory) or not callable(payload):
            raise ValueError("Document inventory and payload helpers are required.")
        self.document_inventory = inventory
        self.document_payload = payload

        self._state_lock = threading.RLock()
        self._operation_lock = threading.Lock()
        self._cancelled = threading.Event()
        self._token = secrets.token_urlsafe(32)
        self._server = None
        self._thread = None
        self._url = None
        self._started = False
        self._stopped = False
        self._ready = False
        self._calls = 0
        self._returned_characters = 0
        self._read_documents: set[str] = set()
        self._events: list[dict] = []
        # This receipt is durable for the life of the chat. It intentionally is
        # not reconstructed from the bounded activity-event tail.
        self._retrieval_usage = {
            "version": 1,
            "basis": "successful_discovery_calls",
            "counts": {"grep": 0, "fts": 0, "wikilinks": 0, "vector": 0},
            "results": {"grep": 0, "fts": 0, "wikilinks": 0, "vector": 0},
            "listCalls": 0,
            "readCalls": 0,
            "unsupported": ["fts", "vector"],
        }
        self._candidates: dict[str, dict] = {}
        self._candidate_fragments: dict[str, list[str]] = {}
        self._numbers: dict[str, int] = {}
        self._exhausted = False
        self._invalidated_read_count = 0

    # ----- lifecycle and public state -----

    def start(self) -> dict[str, str]:
        """Start a one-chat loopback server and return its capability environment."""
        with self._state_lock:
            if self._stopped:
                raise WikiChatToolError("This chat tool bridge has expired.", status=410)
            if self._server is not None:
                return {
                    "WIKI_STUDIO_TOOL_URL": self._url,
                    "WIKI_STUDIO_TOOL_TOKEN": self._token,
                }
            server = _ToolServer(("127.0.0.1", 0), _ToolHandler)
            server.bridge = self
            port = server.server_address[1]
            self._url = f"http://127.0.0.1:{port}/"
            self._server = server
            self._started = True
            thread = threading.Thread(
                target=server.serve_forever,
                name=f"wiki-chat-tools-{port}",
                daemon=True,
            )
            self._thread = thread
            thread.start()
            return {
                "WIKI_STUDIO_TOOL_URL": self._url,
                "WIKI_STUDIO_TOOL_TOKEN": self._token,
            }

    @staticmethod
    def _shutdown_server(server, thread):
        server.shutdown()
        server.server_close()
        if thread is not threading.current_thread():
            thread.join(timeout=2)

    def stop(self):
        """Revoke immediately; finish server shutdown without blocking the caller."""
        with self._state_lock:
            if self._stopped:
                return
            self._cancelled.set()
            self._stopped = True
            self._token = None
            server = self._server
            thread = self._thread
            self._server = None
            self._thread = None
            self._url = None
        if server is not None:
            threading.Thread(
                target=self._shutdown_server,
                args=(server, thread),
                name="wiki-chat-tools-shutdown",
                daemon=True,
            ).start()

    def snapshot(self, validate: bool = False) -> dict:
        if validate:
            self._validate_candidates()
        with self._state_lock:
            return {
                "ready": self._ready,
                "candidates": [self._public_candidate(item)
                               for item in sorted(self._candidates.values(),
                                                  key=lambda row: row["number"])],
                "exploration": {
                    "calls": self._calls,
                    "readCount": len(self._read_documents),
                    "invalidatedReadCount": self._invalidated_read_count,
                    "staleEvidence": self._invalidated_read_count > 0,
                    "retrievalUsage": copy.deepcopy(self._retrieval_usage),
                    "events": [dict(event) for event in self._events],
                    "limits": self._limits(),
                    "exhausted": self._is_exhausted(),
                },
            }

    def _validate_candidates(self):
        with self._state_lock:
            # Cancelled jobs must not wait on optional freshness I/O to become stopped.
            if self._cancelled.is_set():
                for relative in list(self._candidates):
                    self._invalidate_locked(relative)
                return
            expected = [(relative, candidate["contentHash"])
                        for relative, candidate in self._candidates.items()]
        if not expected:
            return
        try:
            inventory = self._inventory()
        except WikiChatToolError:
            inventory = {}
        stale = []
        for relative, expected_hash in expected:
            if self._cancelled.is_set():
                with self._state_lock:
                    for candidate_id in list(self._candidates):
                        self._invalidate_locked(candidate_id)
                return
            path = inventory.get(relative)
            if path is None:
                stale.append((relative, expected_hash))
                continue
            try:
                current_hash = hashlib.sha256(self._bytes_for(relative, inventory)).hexdigest()
            except WikiChatToolError:
                current_hash = None
            if current_hash != expected_hash:
                stale.append((relative, expected_hash))
        with self._state_lock:
            for relative, expected_hash in stale:
                current = self._candidates.get(relative)
                if current is not None and current["contentHash"] == expected_hash:
                    self._invalidate_locked(relative)

    def _check_cancelled(self):
        if self._cancelled.is_set():
            raise WikiChatToolError("This chat tool bridge is not active.", status=410)

    def call(self, tool, arguments=None) -> dict:
        """Invoke one model tool directly under the same lifecycle and budgets."""
        if not isinstance(tool, str) or tool not in self._TOOLS:
            raise WikiChatToolError("Unknown wiki tool.")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise WikiChatToolError("Tool arguments must be an object.")

        if tool == "ready":
            self._strict_keys(arguments, set())
            with self._state_lock:
                if self._stopped or self._cancelled.is_set():
                    raise WikiChatToolError("This chat tool bridge is not active.", status=410)
                self._ready = True
            return self._result({"ready": True}, truncated=False, next_offset=None)

        with self._state_lock:
            if self._stopped or self._cancelled.is_set():
                raise WikiChatToolError("This chat tool bridge is not active.", status=410)
            if self._calls >= self.MAX_TOOL_CALLS:
                self._exhausted = True
                self._event(tool, arguments, 0, "exhausted")
                raise WikiChatToolError("Wiki exploration call budget is exhausted.",
                                        status=429, exhausted=True)
            self._calls += 1

        try:
            with self._operation_lock:
                self._check_cancelled()
                method = getattr(self, f"_{tool}")
                result, count, truncated, next_offset = method(arguments)
                self._check_cancelled()
        except WikiChatToolError as exc:
            with self._state_lock:
                if exc.exhausted:
                    self._exhausted = True
                self._event(tool, arguments, 0, "exhausted" if exc.exhausted else "error")
            raise
        except (OSError, UnicodeError, ValueError, TypeError):
            with self._state_lock:
                self._event(tool, arguments, 0, "error")
            raise WikiChatToolError("The requested wiki document could not be read.") from None
        with self._state_lock:
            self._event(tool, arguments, count, "ok")
        return self._result(result, truncated=truncated, next_offset=next_offset)

    # ----- tools -----

    def _wiki_list(self, arguments):
        self._strict_keys(arguments, {"offset", "limit", "scope", "filter"})
        offset = self._integer(arguments.get("offset", 0), "offset", minimum=0)
        limit = self._integer(arguments.get("limit", self.MAX_LIST_LIMIT), "limit",
                              minimum=1, maximum=self.MAX_LIST_LIMIT)
        scope = self._scope(arguments.get("scope", "wiki"))
        raw_filter = arguments.get("filter")
        if raw_filter is not None:
            raw_filter = self._text(raw_filter, "filter", maximum=500).strip()
        needle = self._normalize(raw_filter or "")
        inventory = self._inventory()
        rows = []
        eligible = 0
        skipped = 0
        for relative in sorted(inventory):
            self._check_cancelled()
            if not self._in_scope(relative, scope):
                continue
            eligible += 1
            title, readable = self._title_for(relative, inventory)
            if not readable:
                skipped += 1
            if needle and needle not in self._normalize(relative) and needle not in self._normalize(title):
                continue
            rows.append({"id": relative, "path": relative, "title": title,
                         "scope": self._document_scope(relative), "readable": readable})
        page = rows[offset:offset + limit]
        next_offset = offset + len(page) if offset + len(page) < len(rows) else None
        effective_scope = "all" if self.mode == "project" and scope == "wiki" else scope
        return ({"documents": page, "count": len(page), "total": len(rows),
                 "offset": offset, "scope": scope, "effectiveScope": effective_scope,
                 "inventoryCount": eligible, "readableCount": eligible - skipped,
                 "skippedCount": skipped}, len(page), next_offset is not None,
                next_offset)

    def _wiki_search(self, arguments):
        self._strict_keys(arguments, {"query", "limit", "scope"})
        query = self._text(arguments.get("query"), "query", maximum=1_000).strip()
        if not query:
            raise WikiChatToolError("Search query must not be empty.")
        limit = self._integer(arguments.get("limit", self.MAX_SEARCH_LIMIT), "limit",
                              minimum=1, maximum=self.MAX_SEARCH_LIMIT)
        scope = self._scope(arguments.get("scope", "all"))
        terms = self._terms(query)
        inventory = self._inventory()
        matches = []
        eligible = 0
        scanned = 0
        skipped = 0
        for relative in sorted(inventory):
            self._check_cancelled()
            if not self._in_scope(relative, scope):
                continue
            eligible += 1
            try:
                text = self._text_for(relative, inventory)
            except WikiChatToolError:
                skipped += 1
                continue
            scanned += 1
            heading = self._heading(text, Path(relative).stem)
            normalized_text = self._normalize(text)
            normalized_path = self._normalize(relative)
            normalized_title = self._normalize(heading)
            hit_terms = [term for term in terms
                         if term in normalized_text or term in normalized_path or term in normalized_title]
            if not hit_terms:
                continue
            score = (sum(normalized_title.count(term) * 8 for term in hit_terms)
                     + sum(normalized_path.count(term) * 3 for term in hit_terms)
                     + sum(min(normalized_text.count(term), 20) for term in hit_terms)
                     + len(hit_terms) * 20)
            matches.append((score, relative, heading))
        matches.sort(key=lambda row: (-row[0], row[1]))
        rows = [{"id": relative, "path": relative, "title": heading,
                 "scope": self._document_scope(relative)}
                for _, relative, heading in matches[:limit]]
        truncated = len(matches) > limit
        return ({"results": rows, "count": len(rows), "total": len(matches),
                 "query": query, "scope": scope, "inventoryCount": eligible,
                 "scannedCount": scanned, "skippedCount": skipped},
                len(rows), truncated, None)

    def _wiki_read(self, arguments):
        self._strict_keys(arguments, {"path", "offset", "limit"})
        relative = self._relative(arguments.get("path"))
        offset = self._integer(arguments.get("offset", 0), "offset", minimum=0)
        limit = self._integer(arguments.get("limit", self.MAX_READ_LIMIT), "limit",
                              minimum=1, maximum=self.MAX_READ_LIMIT)
        inventory = self._inventory()
        self._check_cancelled()
        if relative not in inventory:
            raise WikiChatToolError("Document is not in the current inventory.")

        before = self._bytes_for(relative, inventory)
        self._check_cancelled()
        before_hash = hashlib.sha256(before).hexdigest()
        with self._state_lock:
            previous = self._candidates.get(relative)
            stale_previous = previous is not None and previous["contentHash"] != before_hash
            if stale_previous:
                self._invalidate_locked(relative)
        if stale_previous:
            raise WikiChatToolError("Document changed since the prior read; prior evidence was invalidated.",
                                    status=409)

        payload = self._payload(relative)
        self._check_cancelled()
        current = self._inventory()
        self._check_cancelled()
        if relative not in current:
            with self._state_lock:
                self._invalidate_locked(relative)
            raise WikiChatToolError("Document left the current inventory during the read.", status=409)
        after = self._bytes_for(relative, current)
        self._check_cancelled()
        if before != after:
            with self._state_lock:
                self._invalidate_locked(relative)
            raise WikiChatToolError("Document changed during the read; prior evidence was invalidated.",
                                    status=409)
        text = after.decode("utf-8")
        normalized_payload = payload.get("text", payload.get("content"))
        if not isinstance(normalized_payload, str):
            raise WikiChatToolError("Document payload is invalid.")
        if self._universal_newlines(text) != self._universal_newlines(normalized_payload):
            with self._state_lock:
                self._invalidate_locked(relative)
            raise WikiChatToolError("Document changed during the read; prior evidence was invalidated.",
                                    status=409)
        content_hash = hashlib.sha256(after).hexdigest()
        title = self._bounded_title(payload.get("title"), Path(relative).stem)
        raw_sources = self._raw_sources(payload.get("rawSources"), current)

        if offset > len(text):
            raise WikiChatToolError("Read offset is beyond the end of the document.")
        if offset == len(text):
            self._check_cancelled()
            result = {
                "document": {"id": relative, "path": relative, "title": title,
                             "content": "", "contentHash": content_hash,
                             "readRanges": [], "rawSources": raw_sources,
                             "contentRole": "untrusted_document_data",
                             "citationCandidate": False},
                "offset": offset,
                "returnedCharacters": 0,
                "totalCharacters": len(text),
                "citationCandidate": False,
            }
            return result, 0, False, None

        with self._state_lock:
            if self._stopped or self._cancelled.is_set():
                raise WikiChatToolError("This chat tool bridge is not active.", status=410)
            is_new = relative not in self._read_documents
            if is_new and len(self._read_documents) >= self.MAX_READ_DOCUMENTS:
                self._exhausted = True
                raise WikiChatToolError("Wiki read-document budget is exhausted.",
                                        status=429, exhausted=True)
            remaining = self.MAX_RETURNED_CHARACTERS - self._returned_characters
            if remaining <= 0:
                self._exhausted = True
                raise WikiChatToolError("Wiki returned-character budget is exhausted.",
                                        status=429, exhausted=True)

        actual_limit = min(limit, remaining)
        content = text[offset:offset + actual_limit]
        end = offset + len(content)
        truncated = end < len(text)
        next_offset = end if truncated else None

        with self._state_lock:
            if self._stopped or self._cancelled.is_set():
                raise WikiChatToolError("This chat tool bridge is not active.", status=410)
            self._returned_characters += len(content)
            self._read_documents.add(relative)
            if self._returned_characters >= self.MAX_RETURNED_CHARACTERS:
                self._exhausted = True
            number = self._numbers.setdefault(relative, len(self._numbers) + 1)
            previous = self._candidates.get(relative)
            prior_ranges = (previous["readRanges"] if previous is not None
                            and previous["contentHash"] == content_hash else [])
            ranges = self._merge_ranges(prior_ranges + [{"offset": offset, "end": end}])
            fragments = self._candidate_fragments.setdefault(relative, [])
            if previous is None or previous["contentHash"] != content_hash:
                fragments.clear()
            if content not in fragments:
                fragments.append(content)
            excerpt = "\n…\n".join(fragments)[:self.MAX_CANDIDATE_EXCERPT]
            candidate = {
                "number": number,
                "id": relative,
                "title": title,
                "excerpt": excerpt,
                "rawSources": raw_sources,
                "contentHash": content_hash,
                "readRanges": ranges,
            }
            self._candidates[relative] = candidate

        result = {
            "number": number,
            "document": {"id": relative, "path": relative, "title": title,
                         "content": content, "number": number,
                         "contentHash": content_hash, "candidateNumber": number,
                         "readRanges": ranges, "rawSources": raw_sources,
                         "contentRole": "untrusted_document_data",
                         "citationCandidate": True},
            "offset": offset,
            "returnedCharacters": len(content),
            "totalCharacters": len(text),
            "citationCandidate": True,
        }
        return result, len(content), truncated, next_offset

    def _wiki_links(self, arguments):
        self._strict_keys(arguments, {"path"})
        relative = self._relative(arguments.get("path"))
        inventory = self._inventory()
        self._check_cancelled()
        if relative not in inventory:
            raise WikiChatToolError("Document is not in the current inventory.")
        # Enforce the bridge's file cap before the helper scans links or linked titles.
        self._bytes_for(relative, inventory)
        self._check_cancelled()
        payload = self._payload(relative)
        self._check_cancelled()
        current = self._inventory()
        self._check_cancelled()
        if relative not in current:
            raise WikiChatToolError("Document left the current inventory during link discovery.", status=409)
        links = payload.get("links")
        if not isinstance(links, list):
            raise WikiChatToolError("Document links payload is invalid.")
        rows = []
        seen = set()
        for item in links:
            if not isinstance(item, dict):
                continue
            target = item.get("id")
            try:
                target = self._relative(target)
            except WikiChatToolError:
                continue
            if target in seen or target not in current:
                continue
            seen.add(target)
            rows.append({"id": target, "path": target,
                         "title": self._bounded_title(item.get("title"), Path(target).stem),
                         "scope": self._document_scope(target)})
        rows.sort(key=lambda row: row["path"])
        truncated = len(rows) > self.MAX_LINKS
        visible = rows[:self.MAX_LINKS]
        return ({"path": relative, "items": visible, "count": len(visible),
                 "total": len(rows)}, len(visible), truncated, None)

    # ----- helper boundary and validation -----

    def _inventory(self) -> dict[str, Path]:
        try:
            supplied = self.document_inventory(self.root, self.mode)
        except Exception:
            raise WikiChatToolError("Current document inventory is unavailable.") from None
        if not isinstance(supplied, dict):
            raise WikiChatToolError("Current document inventory is invalid.")
        approved = {}
        for raw_relative, raw_path in supplied.items():
            try:
                relative = self._relative(raw_relative)
                path = Path(raw_path)
                resolved = path.resolve(strict=True)
                expected = (self.root / PurePosixPath(relative)).resolve(strict=True)
            except (WikiChatToolError, OSError, ValueError, TypeError):
                continue
            if (resolved != expected or not resolved.is_relative_to(self.root)
                    or not resolved.is_file() or resolved.suffix.lower() != ".md"):
                continue
            approved[relative] = resolved
        return dict(sorted(approved.items()))

    def _payload(self, relative: str) -> dict:
        try:
            payload = self.document_payload(self.root, self.mode, relative)
        except Exception:
            raise WikiChatToolError("The requested wiki document could not be read.") from None
        if not isinstance(payload, dict) or payload.get("path") != relative:
            raise WikiChatToolError("Document payload is invalid.")
        return payload

    def _bytes_for(self, relative: str, inventory: dict[str, Path]) -> bytes:
        path = inventory.get(relative)
        if path is None:
            raise WikiChatToolError("Document is not in the current inventory.")
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(self.root) or not resolved.is_file():
                raise WikiChatToolError("Document is outside the current inventory.")
            size = resolved.stat().st_size
            if size > self.MAX_FILE_BYTES:
                raise WikiChatToolError("Document exceeds the 2 MB read limit.")
            data = resolved.read_bytes()
        except WikiChatToolError:
            raise
        except OSError:
            raise WikiChatToolError("The requested wiki document could not be read.") from None
        if len(data) > self.MAX_FILE_BYTES:
            raise WikiChatToolError("Document exceeds the 2 MB read limit.")
        try:
            data.decode("utf-8")
        except UnicodeError:
            raise WikiChatToolError("Document is not valid UTF-8 Markdown.") from None
        return data

    def _text_for(self, relative: str, inventory: dict[str, Path]) -> str:
        return self._bytes_for(relative, inventory).decode("utf-8")

    def _title_for(self, relative: str, inventory: dict[str, Path]) -> tuple[str, bool]:
        try:
            text = self._text_for(relative, inventory)
        except WikiChatToolError:
            return Path(relative).stem, False
        return self._heading(text, Path(relative).stem), True

    @staticmethod
    def _strict_keys(arguments: dict, allowed: set[str]):
        if any(not isinstance(key, str) for key in arguments):
            raise WikiChatToolError("Tool argument names must be strings.")
        if set(arguments) - allowed:
            raise WikiChatToolError("Unsupported tool arguments were supplied.")

    @staticmethod
    def _integer(value, label, *, minimum, maximum=None):
        if isinstance(value, bool) or not isinstance(value, int):
            raise WikiChatToolError(f"{label} must be an integer.")
        if value < minimum or (maximum is not None and value > maximum):
            raise WikiChatToolError(f"{label} is outside the allowed range.")
        return value

    @staticmethod
    def _text(value, label, *, maximum):
        if not isinstance(value, str) or "\x00" in value or len(value) > maximum:
            raise WikiChatToolError(f"{label} must be a bounded text value.")
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise WikiChatToolError(f"{label} must be valid UTF-8 text.") from None
        return value

    def _relative(self, value) -> str:
        value = self._text(value, "path", maximum=4_096)
        if not value or "\\" in value or value.startswith("/"):
            raise WikiChatToolError("Document path must be a canonical relative path.")
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise WikiChatToolError("Document path must be a canonical relative path.")
        pure = PurePosixPath(value)
        if any(part in ("", ".", "..") for part in pure.parts) or pure.as_posix() != value:
            raise WikiChatToolError("Document path must be a canonical relative path.")
        return value

    def _scope(self, value):
        if not isinstance(value, str) or value not in self._SCOPES:
            raise WikiChatToolError("scope must be wiki, raw, or all.")
        return value

    def _in_scope(self, relative: str, scope: str) -> bool:
        if self.mode == "project" and scope == "wiki":
            return not relative.startswith("raw/")
        return (scope == "all" or (scope == "wiki" and relative.startswith("wiki/"))
                or (scope == "raw" and relative.startswith("raw/")))

    @staticmethod
    def _document_scope(relative: str) -> str:
        if relative.startswith("wiki/"):
            return "wiki"
        if relative.startswith("raw/"):
            return "raw"
        return "project"

    @staticmethod
    def _normalize(value: str) -> str:
        return unicodedata.normalize("NFKC", value).casefold()

    def _terms(self, query: str) -> list[str]:
        return list(dict.fromkeys(re.findall(r"[^\W_]+", self._normalize(query), re.UNICODE)))[:24]

    @staticmethod
    def _heading(text: str, fallback: str) -> str:
        match = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
        return (match.group(1).strip() if match else fallback)[:500]

    @staticmethod
    def _universal_newlines(text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n")

    @staticmethod
    def _bounded_title(value, fallback):
        if not isinstance(value, str) or not value.strip():
            value = fallback
        return value.replace("\x00", "")[:500]

    def _raw_sources(self, value, inventory):
        if not isinstance(value, list):
            return []
        rows = []
        seen = set()
        for item in value[:self.MAX_READ_DOCUMENTS]:
            if not isinstance(item, dict):
                continue
            try:
                source = self._relative(item.get("id"))
            except WikiChatToolError:
                continue
            if source in seen or source not in inventory or not source.startswith("raw/"):
                continue
            seen.add(source)
            rows.append({"id": source,
                         "title": self._bounded_title(item.get("title"), Path(source).stem)})
        return rows

    @staticmethod
    def _merge_ranges(ranges):
        pairs = sorted((int(item["offset"]), int(item["end"])) for item in ranges
                       if isinstance(item, dict) and isinstance(item.get("offset"), int)
                       and isinstance(item.get("end"), int) and item["end"] >= item["offset"])
        merged = []
        for start, end in pairs:
            if merged and start <= merged[-1]["end"]:
                merged[-1]["end"] = max(merged[-1]["end"], end)
            else:
                merged.append({"offset": start, "end": end})
        return merged

    def _invalidate_locked(self, relative):
        if self._candidates.pop(relative, None) is not None:
            self._invalidated_read_count += 1
        self._candidate_fragments.pop(relative, None)

    # ----- bounded receipts and HTTP support -----

    def _limits(self):
        with self._state_lock:
            return {
                "calls": self.MAX_TOOL_CALLS,
                "reads": self.MAX_READ_DOCUMENTS,
                "maxToolCalls": self.MAX_TOOL_CALLS,
                "toolCalls": self._calls,
                "remainingToolCalls": max(0, self.MAX_TOOL_CALLS - self._calls),
                "maxReadDocuments": self.MAX_READ_DOCUMENTS,
                "readDocuments": len(self._read_documents),
                "remainingReadDocuments": max(0, self.MAX_READ_DOCUMENTS - len(self._read_documents)),
                "maxReturnedCharacters": self.MAX_RETURNED_CHARACTERS,
                "returnedCharacters": self._returned_characters,
                "remainingReturnedCharacters": max(
                    0, self.MAX_RETURNED_CHARACTERS - self._returned_characters),
                "maxFileBytes": self.MAX_FILE_BYTES,
                "maxListLimit": self.MAX_LIST_LIMIT,
                "maxSearchLimit": self.MAX_SEARCH_LIMIT,
                "maxReadLimit": self.MAX_READ_LIMIT,
            }

    def _is_exhausted(self):
        with self._state_lock:
            return (self._exhausted or self._calls >= self.MAX_TOOL_CALLS
                    or self._returned_characters >= self.MAX_RETURNED_CHARACTERS)

    def _result(self, payload, *, truncated, next_offset):
        return {**payload, "truncated": bool(truncated), "nextOffset": next_offset,
                "limits": self._limits(), "exhausted": self._is_exhausted()}

    def _event(self, tool, arguments, count, status):
        event = {"tool": tool, "path": None, "query": None,
                 "count": int(count), "status": status}
        if tool in ("wiki_read", "wiki_links"):
            try:
                event["path"] = self._relative(arguments.get("path"))
            except WikiChatToolError:
                pass
        elif tool == "wiki_search":
            raw = arguments.get("query")
            if isinstance(raw, str):
                event["query"] = self._activity_text(raw, 1_000)
        elif tool == "wiki_list":
            raw = arguments.get("filter")
            if isinstance(raw, str):
                event["query"] = self._activity_text(raw, 500)
        self._events.append(event)
        if len(self._events) > self.MAX_EVENTS:
            del self._events[:-self.MAX_EVENTS]
        if status != "ok":
            return
        if tool == "wiki_search":
            self._retrieval_usage["counts"]["grep"] += 1
            self._retrieval_usage["results"]["grep"] += int(count)
        elif tool == "wiki_links":
            self._retrieval_usage["counts"]["wikilinks"] += 1
            self._retrieval_usage["results"]["wikilinks"] += int(count)
        elif tool == "wiki_list":
            self._retrieval_usage["listCalls"] += 1
        elif tool == "wiki_read":
            self._retrieval_usage["readCalls"] += 1

    def _activity_text(self, value, maximum):
        """Keep useful activity text while removing obvious credential-shaped values."""
        value = value[:maximum]
        if self._token:
            value = value.replace(self._token, "[REDACTED]")
        return re.sub(
            r"(?i)\b(api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+",
            r"\1=[REDACTED]",
            value,
        )

    @staticmethod
    def _public_candidate(candidate):
        return {
            "number": candidate["number"],
            "id": candidate["id"],
            "title": candidate["title"],
            "excerpt": candidate["excerpt"][:WikiChatTools.MAX_CANDIDATE_EXCERPT],
            "rawSources": [dict(item) for item in candidate["rawSources"]],
            "contentHash": candidate["contentHash"],
            "readRanges": [dict(item) for item in candidate["readRanges"]],
        }

    def _authorized(self, handler) -> bool:
        with self._state_lock:
            if self._stopped or not self._started or self._token is None:
                return False
            supplied = handler.headers.get_all("Authorization", [])
            if len(supplied) != 1 or not supplied[0].startswith("Bearer "):
                return False
            return secrets.compare_digest(supplied[0][7:], self._token)

    def _valid_host(self, handler) -> bool:
        with self._state_lock:
            server = self._server
            if server is None:
                return False
            port = server.server_address[1]
        hosts = handler.headers.get_all("Host", [])
        return len(hosts) == 1 and hosts[0].lower() in {
            f"127.0.0.1:{port}", f"localhost:{port}"
        }


class _ToolHandler(BaseHTTPRequestHandler):
    """Strict JSON-only endpoint; no browsing, CORS, or general RPC surface."""

    server_version = "WikiChatTools"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(self.server.bridge.HTTP_READ_TIMEOUT_SECONDS)

    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        self._send(405, {"ok": False, "error": "POST is required.", "exhausted": False})

    def do_OPTIONS(self):
        self._send(405, {"ok": False, "error": "Browser wildcard access is not enabled.",
                         "exhausted": False})

    def do_POST(self):
        bridge = self.server.bridge
        if self.path != "/":
            self._send(404, {"ok": False, "error": "Unknown tool endpoint.", "exhausted": False})
            return
        if not bridge._valid_host(self):
            self._send(400, {"ok": False, "error": "Invalid loopback Host header.",
                             "exhausted": False})
            return
        if not bridge._authorized(self):
            self._send(401, {"ok": False, "error": "Invalid or expired capability.",
                             "exhausted": False})
            return
        if self.headers.get("Transfer-Encoding") is not None:
            self._send(400, {"ok": False, "error": "Chunked request bodies are not accepted.",
                             "exhausted": False})
            return
        lengths = self.headers.get_all("Content-Length", [])
        try:
            size = int(lengths[0]) if len(lengths) == 1 else -1
        except (TypeError, ValueError):
            size = -1
        if size < 0:
            self._send(411, {"ok": False, "error": "A valid Content-Length is required.",
                             "exhausted": False})
            return
        if size > bridge.MAX_BODY_BYTES:
            self._send(413, {"ok": False, "error": "Tool request body is too large.",
                             "exhausted": False})
            return
        try:
            raw = self.rfile.read(size)
        except TimeoutError:
            self.close_connection = True
            self._send(408, {"ok": False, "error": "Tool request body timed out.",
                             "exhausted": False})
            return
        try:
            if len(raw) != size:
                raise ValueError
            body = json.loads(raw.decode("utf-8"))
            if (not isinstance(body, dict) or set(body) != {"tool", "arguments"}
                    or not isinstance(body.get("arguments"), dict)):
                raise ValueError
        except (UnicodeError, json.JSONDecodeError, ValueError):
            self._send(400, {"ok": False, "error": "Malformed tool request.",
                             "exhausted": False})
            return
        try:
            result = bridge.call(body.get("tool"), body["arguments"])
        except WikiChatToolError as exc:
            self._send(exc.status, {"ok": False, "error": str(exc),
                                    "exhausted": exc.exhausted or bridge.snapshot()["exploration"]["exhausted"],
                                    "limits": bridge.snapshot()["exploration"]["limits"]})
            return
        except Exception:
            self._send(500, {"ok": False, "error": "Wiki tool request failed safely.",
                             "exhausted": False})
            return
        self._send(200, {"ok": True, "result": result})

    def _send(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
