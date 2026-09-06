#!/usr/bin/env python3
"""Bounded source-preparation tools for one Wiki Studio batch worker.

Canonical documents remain read-only.  A worker may only write proposed Wiki
Markdown below its backend-owned attempt directory, then submit one immutable
proposal after completely reading the assigned source and the two governing
context documents.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
import sys


try:
    from wiki_dashboard_chat_tools import WikiChatTools, WikiChatToolError
except ImportError:  # Stable sibling loading for direct file-based test/import use.
    _SIBLING_NAME = "wiki_dashboard_chat_tools"
    _SIBLING_PATH = Path(__file__).with_name(f"{_SIBLING_NAME}.py")
    _spec = importlib.util.spec_from_file_location(_SIBLING_NAME, _SIBLING_PATH)
    if _spec is None or _spec.loader is None:
        raise
    _module = importlib.util.module_from_spec(_spec)
    sys.modules.setdefault(_SIBLING_NAME, _module)
    _spec.loader.exec_module(_module)
    WikiChatTools = _module.WikiChatTools
    WikiChatToolError = _module.WikiChatToolError


__all__ = ["SourceDraftTools", "WikiChatToolError"]


class SourceDraftTools(WikiChatTools):
    """Read canonical context and prepare one source-bound draft proposal."""

    MAX_BODY_BYTES = 2_000_000
    MAX_TOOL_CALLS = 256
    MAX_READ_DOCUMENTS = 64
    MAX_RETURNED_CHARACTERS = 4_000_000
    MAX_READ_LIMIT = 10_000
    MAX_FILE_BYTES = 2_000_000

    MAX_DRAFT_FILES = 32
    MAX_DRAFT_FILE_BYTES = 256 * 1024
    MAX_DRAFT_TOTAL_BYTES = 4 * 1024 * 1024
    MAX_SUMMARY_CHARACTERS = 8_000
    MAX_PLAN_CHARACTERS = 32_000

    REQUIRED_CONTEXT = ("AGENTS.md", "wiki/_meta/index.md")
    _TOOLS = WikiChatTools._TOOLS | {"draft_write", "draft_submit"}

    def __init__(self, root, source, draft_root, helpers, on_change=None):
        super().__init__(root, "wiki", helpers)
        self.source = self._source_path(source)
        self.draft_root = self._draft_root_path(draft_root)
        self._draft_root_pathname = self.root / PurePosixPath(self.draft_root)
        self._files_root = self._draft_root_pathname / "files"
        self._proposal_path = self._draft_root_pathname / "proposal.json"
        if on_change is not None and not callable(on_change):
            raise ValueError("on_change must be callable.")
        self._on_change = on_change
        self._read_evidence: dict[str, dict] = {}
        self._submitted_result = None

        self._check_existing_components(self._draft_root_pathname)
        inventory = self._inventory()
        if self.source not in inventory:
            raise WikiChatToolError("Assigned source is not in the current inventory.")
        source_bytes = self._bytes_for(self.source, inventory)
        self._source_hash = self._digest(source_bytes)

    # ----- public state and dispatch -----

    def call(self, tool, arguments=None) -> dict:
        if tool not in {"draft_write", "draft_submit"}:
            return super().call(tool, arguments)
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise WikiChatToolError("Tool arguments must be an object.")

        changed = False
        with self._state_lock:
            if self._stopped or self._cancelled.is_set():
                raise WikiChatToolError("This chat tool bridge is not active.", status=410)
            if self._calls >= self.MAX_TOOL_CALLS:
                self._exhausted = True
                self._event(tool, arguments, 0, "exhausted")
                raise WikiChatToolError(
                    "Wiki preparation call budget is exhausted.", status=429, exhausted=True)
            self._calls += 1
        try:
            with self._operation_lock:
                self._check_cancelled()
                if tool == "draft_write":
                    result, count, truncated, next_offset, changed = self._draft_write(arguments)
                else:
                    result, count, truncated, next_offset, changed = self._draft_submit(arguments)
        except WikiChatToolError as exc:
            with self._state_lock:
                if exc.exhausted:
                    self._exhausted = True
                self._event(tool, arguments, 0, "exhausted" if exc.exhausted else "error")
            raise
        except (OSError, UnicodeError, ValueError, TypeError):
            with self._state_lock:
                self._event(tool, arguments, 0, "error")
            raise WikiChatToolError("The draft operation failed safely.") from None
        with self._state_lock:
            self._event(tool, arguments, count, "ok")
        response = self._result(result, truncated=truncated, next_offset=next_offset)
        if changed:
            self._notify_change()
        return response

    def draft_result(self):
        with self._state_lock:
            return copy.deepcopy(self._submitted_result)

    def snapshot(self, validate: bool = False) -> dict:
        base = super().snapshot(validate=validate)
        try:
            files = self._draft_files()
        except WikiChatToolError:
            files = []
        with self._state_lock:
            if self._submitted_result is not None:
                status_value = "submitted"
            elif self._stopped or self._cancelled.is_set():
                status_value = "cancelled"
            elif files:
                status_value = "drafting"
            else:
                status_value = "empty"
        base["draft"] = {
            "status": status_value,
            "count": len(files),
            "files": [dict(item) for item in files],
        }
        return base

    # ----- source-owned read boundary and evidence -----

    def _inventory(self):
        """Expose Wiki context, the exact contract, and only this worker's raw source."""
        inventory = super()._inventory()
        assigned = getattr(self, "source", None)
        return {
            relative: path for relative, path in inventory.items()
            if relative.startswith("wiki/") or relative == "AGENTS.md" or relative == assigned
        }

    def _wiki_read(self, arguments):
        result, count, truncated, next_offset = super()._wiki_read(arguments)
        document = result["document"]
        relative = document["path"]
        content_hash = document["contentHash"]
        offset = result["offset"]
        end = offset + result["returnedCharacters"]
        total = result["totalCharacters"]
        with self._state_lock:
            previous = self._read_evidence.get(relative)
            ranges = [] if previous is None or previous["contentHash"] != content_hash \
                else previous["readRanges"]
            ranges = self._merge_ranges(ranges + [{"offset": offset, "end": end}])
            self._read_evidence[relative] = {
                "path": relative,
                "contentHash": content_hash,
                "totalCharacters": total,
                "readRanges": ranges,
            }
        return result, count, truncated, next_offset

    def _validated_read_evidence(self):
        with self._state_lock:
            evidence = copy.deepcopy(self._read_evidence)
        required = (self.source, *self.REQUIRED_CONTEXT)
        missing = [relative for relative in required if relative not in evidence]
        if missing:
            raise WikiChatToolError(
                "Complete wiki_read evidence is required for the assigned source, AGENTS.md, "
                "and wiki/_meta/index.md before submission.", status=409)

        inventory = self._inventory()
        rows = []
        for relative in sorted(evidence):
            item = evidence[relative]
            if relative not in inventory:
                raise WikiChatToolError(
                    "A document used for preparation left the current inventory.", status=409)
            data = self._bytes_for(relative, inventory)
            digest = hashlib.sha256(data).hexdigest()
            if digest != item["contentHash"]:
                raise WikiChatToolError(
                    "A document used for preparation changed after it was read.", status=409)
            text = data.decode("utf-8")
            if len(text) != item["totalCharacters"]:
                raise WikiChatToolError(
                    "A document used for preparation changed after it was read.", status=409)
            ranges = self._merge_ranges(item["readRanges"])
            complete = (len(ranges) == 1 and ranges[0]["offset"] == 0
                        and ranges[0]["end"] == len(text))
            if relative in required and not complete:
                raise WikiChatToolError(
                    "The assigned source and governing context documents must be read completely.",
                    status=409)
            rows.append({
                "path": relative,
                "sha256": self._digest(data),
                "bytes": len(data),
                "characters": len(text),
                "readRanges": ranges,
                "complete": complete,
            })

        source_row = next(row for row in rows if row["path"] == self.source)
        if source_row["sha256"] != self._source_hash:
            raise WikiChatToolError(
                "Assigned source changed after this preparation attempt began.", status=409)
        return rows

    # ----- draft operations -----

    def _draft_write(self, arguments):
        self._strict_keys(arguments, {"path", "content"})
        relative = self._draft_target(arguments.get("path"))
        content = self._text(
            arguments.get("content"), "content", maximum=self.MAX_DRAFT_FILE_BYTES)
        data = content.encode("utf-8")
        if len(data) > self.MAX_DRAFT_FILE_BYTES:
            raise WikiChatToolError("Draft content exceeds the 256 KiB file limit.")
        with self._state_lock:
            if self._submitted_result is not None:
                raise WikiChatToolError("A submitted draft proposal is immutable.", status=409)

        target = self._files_root / PurePosixPath(relative)
        self._ensure_safe_directory(target.parent)
        current = self._draft_files()
        temporary = self._atomic_temporary(target.parent, target.name, data)
        try:
            with self._state_lock:
                if self._stopped or self._cancelled.is_set():
                    raise WikiChatToolError("This chat tool bridge is not active.", status=410)
                if self._submitted_result is not None:
                    raise WikiChatToolError("A submitted draft proposal is immutable.", status=409)
                by_path = {item["path"]: item for item in current}
                if relative not in by_path and len(current) >= self.MAX_DRAFT_FILES:
                    raise WikiChatToolError("Draft file count limit is exhausted.", status=429,
                                            exhausted=True)
                old_size = by_path.get(relative, {}).get("bytes", 0)
                total = sum(item["bytes"] for item in current) - old_size + len(data)
                if total > self.MAX_DRAFT_TOTAL_BYTES:
                    raise WikiChatToolError("Draft total byte limit is exhausted.", status=429,
                                            exhausted=True)
                self._reject_symlink_or_nonfile(target)
                self._check_existing_components(target.parent)
                os.replace(temporary, target)
                temporary = None
                self._fsync_directory(target.parent)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except OSError:
                    pass
        row = {"path": relative, "sha256": self._digest(data), "bytes": len(data)}
        return ({"written": True, "file": row, "count": len(self._draft_files())},
                len(data), False, None, True)

    def _draft_submit(self, arguments):
        self._strict_keys(arguments, {"summary", "plan"})
        summary = self._text(
            arguments.get("summary"), "summary", maximum=self.MAX_SUMMARY_CHARACTERS).strip()
        plan = self._text(
            arguments.get("plan"), "plan", maximum=self.MAX_PLAN_CHARACTERS).strip()
        if not summary or not plan:
            raise WikiChatToolError("Submission summary and plan must not be empty.")

        with self._state_lock:
            existing = self._submitted_result
            if existing is not None:
                if existing["summary"] == summary and existing["plan"] == plan:
                    return copy.deepcopy(existing), len(existing["files"]), False, None, False
                raise WikiChatToolError("A submitted draft proposal is immutable.", status=409)

        files = self._draft_files()
        if not files:
            raise WikiChatToolError("At least one draft file is required before submission.",
                                    status=409)
        read_evidence = self._validated_read_evidence()
        result = {
            "submitted": True,
            "source": self.source,
            "sourceHash": self._source_hash,
            "draftDir": f"{self.draft_root}/files",
            "files": files,
            "summary": summary,
            "plan": plan,
            "readEvidence": read_evidence,
        }
        proposal = json.dumps(result, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":")).encode("utf-8") + b"\n"
        self._ensure_safe_directory(self._draft_root_pathname)
        temporary = self._atomic_temporary(
            self._draft_root_pathname, self._proposal_path.name, proposal)
        try:
            with self._state_lock:
                if self._stopped or self._cancelled.is_set():
                    raise WikiChatToolError("This chat tool bridge is not active.", status=410)
                if self._submitted_result is not None:
                    existing = self._submitted_result
                    if existing["summary"] == summary and existing["plan"] == plan:
                        return copy.deepcopy(existing), len(existing["files"]), False, None, False
                    raise WikiChatToolError("A submitted draft proposal is immutable.", status=409)
                self._reject_symlink_or_nonfile(self._proposal_path)
                self._check_existing_components(self._draft_root_pathname)
                os.replace(temporary, self._proposal_path)
                temporary = None
                self._fsync_directory(self._draft_root_pathname)
                self._submitted_result = copy.deepcopy(result)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except OSError:
                    pass
        return copy.deepcopy(result), len(files), False, None, True

    # ----- path and filesystem safety -----

    def _source_path(self, value):
        relative = self._relative(value)
        if not relative.startswith("raw/") or not relative.endswith(".md"):
            raise WikiChatToolError("Assigned source must be a raw Markdown path.")
        return relative

    def _draft_root_path(self, value):
        relative = self._relative(value)
        parts = PurePosixPath(relative).parts
        valid = (len(parts) == 6
                 and parts[0:2] == ("state", "wiki_batches")
                 and parts[3] == "workers"
                 and bool(parts[2]) and bool(parts[4])
                 and parts[5].startswith("attempt-")
                 and parts[5][8:].isdigit() and int(parts[5][8:]) > 0)
        if not valid:
            raise WikiChatToolError("Draft root is not a backend-owned batch attempt path.")
        return relative

    def _draft_target(self, value):
        relative = self._relative(value)
        parts = PurePosixPath(relative).parts
        if len(parts) < 2 or parts[0] != "wiki" or not relative.endswith(".md"):
            raise WikiChatToolError("Draft target must be a wiki Markdown path.")
        return relative

    def _draft_files(self):
        if not self._files_root.exists():
            self._check_existing_components(self._files_root)
            return []
        self._check_existing_components(self._files_root)
        rows = []
        try:
            paths = sorted(self._files_root.rglob("*"))
        except OSError:
            raise WikiChatToolError("Draft files are unavailable.") from None
        for path in paths:
            try:
                mode = path.lstat().st_mode
            except OSError:
                raise WikiChatToolError("Draft files are unavailable.") from None
            if stat.S_ISLNK(mode):
                raise WikiChatToolError("Draft paths may not contain symbolic links.")
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode):
                raise WikiChatToolError("Draft paths may contain only regular files.")
            relative = path.relative_to(self._files_root).as_posix()
            self._draft_target(relative)
            try:
                data = path.read_bytes()
            except OSError:
                raise WikiChatToolError("Draft files are unavailable.") from None
            if len(data) > self.MAX_DRAFT_FILE_BYTES:
                raise WikiChatToolError("A draft file exceeds the 256 KiB file limit.")
            rows.append({"path": relative, "sha256": self._digest(data), "bytes": len(data)})
        if len(rows) > self.MAX_DRAFT_FILES:
            raise WikiChatToolError("Draft file count limit is exhausted.", status=429,
                                    exhausted=True)
        if sum(item["bytes"] for item in rows) > self.MAX_DRAFT_TOTAL_BYTES:
            raise WikiChatToolError("Draft total byte limit is exhausted.", status=429,
                                    exhausted=True)
        return rows

    def _check_existing_components(self, path: Path):
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            raise WikiChatToolError("Draft path is outside the connected root.") from None
        current = self.root
        for part in relative.parts:
            current = current / part
            try:
                mode = current.lstat().st_mode
            except FileNotFoundError:
                return
            except OSError:
                raise WikiChatToolError("Draft path is unavailable.") from None
            if stat.S_ISLNK(mode):
                raise WikiChatToolError("Draft paths may not contain symbolic links.")
            if current != path and not stat.S_ISDIR(mode):
                raise WikiChatToolError("Draft path has a non-directory component.")

    def _ensure_safe_directory(self, directory: Path):
        try:
            relative = directory.relative_to(self.root)
        except ValueError:
            raise WikiChatToolError("Draft path is outside the connected root.") from None
        current = self.root
        for part in relative.parts:
            current = current / part
            try:
                mode = current.lstat().st_mode
            except FileNotFoundError:
                try:
                    current.mkdir(mode=0o700)
                except FileExistsError:
                    mode = current.lstat().st_mode
                except OSError:
                    raise WikiChatToolError("Draft directory could not be created.") from None
                else:
                    mode = current.lstat().st_mode
            except OSError:
                raise WikiChatToolError("Draft directory is unavailable.") from None
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise WikiChatToolError("Draft paths may contain only real directories.")

    @staticmethod
    def _reject_symlink_or_nonfile(path: Path):
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            return
        except OSError:
            raise WikiChatToolError("Draft target is unavailable.") from None
        if stat.S_ISLNK(mode):
            raise WikiChatToolError("Draft targets may not be symbolic links.")
        if not stat.S_ISREG(mode):
            raise WikiChatToolError("Draft targets may only be regular files.")

    @staticmethod
    def _atomic_temporary(parent: Path, name: str, data: bytes) -> Path:
        temporary = parent / f".{name}.tmp-{secrets.token_hex(12)}"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(temporary, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise
        return temporary

    @staticmethod
    def _fsync_directory(directory: Path):
        flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        try:
            descriptor = os.open(directory, flags)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            os.close(descriptor)

    @staticmethod
    def _digest(data: bytes) -> str:
        return "sha256:" + hashlib.sha256(data).hexdigest()

    def _notify_change(self):
        callback = self._on_change
        if callback is None:
            return
        try:
            callback()
        except Exception:
            return
