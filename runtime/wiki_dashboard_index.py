"""Studio-owned incremental SQLite discovery. Markdown remains the read authority."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
import threading
import time
import unicodedata


class StudioIndex:
    VERSION = "studio-discovery-v2"
    MAX_FILE_BYTES = 2_000_000
    MAX_CANDIDATES = 120

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = self.root / "state" / "studio_search.sqlite"
        self.lock = threading.Lock()
        self.last_status = {"state": "missing", "pages": 0, "fts": False}

    def _safe_path(self):
        for path in (self.path.parent, self.path):
            if path.is_symlink() or not path.resolve().is_relative_to(self.root):
                raise ValueError("Studio 검색 인덱스가 위키 밖을 가리킵니다.")
        for suffix in ("-wal", "-shm", "-journal"):
            path = Path(str(self.path) + suffix)
            if path.is_symlink():
                raise ValueError("Studio 검색 인덱스 보조 파일이 링크입니다.")

    @staticmethod
    def _stamp(path):
        value = path.stat()
        return json.dumps([value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns])

    @staticmethod
    def normalize(value):
        return unicodedata.normalize("NFKC", value).casefold()

    def ensure(self, inventory, check=lambda: None, progress=None):
        while not self.lock.acquire(timeout=.1):
            check()
        connection = None
        try:
            check()
            self._safe_path()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=.2)
            connection.set_progress_handler(lambda: self._interrupt(check), 1000)
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
            version = connection.execute("SELECT value FROM metadata WHERE key='version'").fetchone()
            if version and version[0] not in {self.VERSION, "studio-discovery-v1"}:
                raise ValueError("Studio 검색 인덱스 버전이 다릅니다.")
            connection.execute("BEGIN IMMEDIATE")
            if not version or version[0] != self.VERSION:
                connection.execute("DROP TABLE IF EXISTS document_fts")
                connection.execute("DROP TABLE IF EXISTS documents")
            connection.execute("CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, stamp TEXT NOT NULL, title TEXT NOT NULL)")
            connection.execute("CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(path UNINDEXED, content, tokenize='trigram')")
            known = {path: (stamp, rowid) for path, stamp, rowid in connection.execute("SELECT path,stamp,id FROM documents")}
            live = set()
            for index, (relative, path) in enumerate(inventory.items()):
                check()
                if progress:
                    progress("sqlite", path=relative, current=index, total=len(inventory))
                # The injected inventory is not a substitute for current containment.
                path = Path(path).resolve(strict=True)
                if not path.is_relative_to(self.root) or not path.is_file() or path.stat().st_size > self.MAX_FILE_BYTES:
                    continue
                stamp = self._stamp(path)
                live.add(relative)
                if known.get(relative, (None, None))[0] == stamp:
                    continue
                with path.open("rb") as handle:
                    data = handle.read(self.MAX_FILE_BYTES + 1)
                check()
                if len(data) > self.MAX_FILE_BYTES:
                    live.discard(relative)
                    continue
                try:
                    body = data.decode("utf-8")
                except UnicodeError:
                    live.discard(relative)
                    continue
                if self._stamp(path) != stamp:
                    raise ValueError("색인 중 문서가 변경되었습니다. 다시 연결하거나 검색해 주세요.")
                match = re.search(r"^#\s+(.+)$", body, re.M)
                title = match.group(1).strip() if match else path.stem
                connection.execute("INSERT INTO documents(path,stamp,title) VALUES (?,?,?) ON CONFLICT(path) DO UPDATE SET stamp=excluded.stamp,title=excluded.title", (relative, stamp, title))
                rowid = connection.execute("SELECT id FROM documents WHERE path=?", (relative,)).fetchone()[0]
                if relative in known:
                    connection.execute("DELETE FROM document_fts WHERE rowid=?", (rowid,))
                connection.execute("INSERT INTO document_fts(rowid,path,content) VALUES (?,?,?)", (rowid, relative, self.normalize(relative + '\n' + body)))
            for relative in known.keys() - live:
                connection.execute("DELETE FROM document_fts WHERE rowid=?", (known[relative][1],))
                connection.execute("DELETE FROM documents WHERE path=?", (relative,))
            check()
            connection.execute("INSERT OR REPLACE INTO metadata VALUES ('version',?)", (self.VERSION,))
            connection.commit()
            self.last_status = {"state": "current", "pages": len(live), "fts": True, "checkedAt": time.time()}
            if progress:
                progress("sqlite", current=len(inventory), total=len(inventory))
            return dict(self.last_status)
        except Exception:
            self.last_status = {"state": "error", "pages": self.last_status.get("pages", 0), "fts": False}
            raise
        finally:
            if connection is not None:
                connection.close()
            self.lock.release()

    @staticmethod
    def _interrupt(check):
        try:
            check()
        except Exception:
            return 1
        return 0

    def search(self, terms, inventory, check, scope="all"):
        """Return unchecked candidate paths; caller reopens their current Markdown."""
        self.ensure(inventory, check)
        check()
        self._safe_path()
        connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=.2)
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.set_progress_handler(lambda: self._interrupt(check), 1000)
            # Trigram MATCH preserves literal Korean/English substrings >=3 chars.
            # Short terms use a bounded SQL content scan, still avoiding file opens.
            long = [term for term in terms if len(term) >= 3]
            short = [term for term in terms if len(term) < 3]
            paths = set()
            limited = False
            scope_sql = " AND path LIKE 'raw/%'" if scope == "raw" else " AND path NOT LIKE 'raw/%'" if scope == "wiki" else ""
            if long:
                query = " OR ".join('"' + term.replace('"', '""') + '"' for term in long)
                rows = list(connection.execute("SELECT path FROM document_fts WHERE document_fts MATCH ?" + scope_sql + " ORDER BY bm25(document_fts),path LIMIT ?", (query, self.MAX_CANDIDATES)))
                paths.update(row[0] for row in rows)
                limited = len(rows) == self.MAX_CANDIDATES
            if short:
                where = " OR ".join("instr(content,?) > 0" for _ in short)
                rows = list(connection.execute("SELECT path FROM document_fts WHERE (" + where + ")" + scope_sql + " ORDER BY path LIMIT ?", [*short, self.MAX_CANDIDATES]))
                paths.update(row[0] for row in rows)
                limited = limited or len(rows) == self.MAX_CANDIDATES
            check()
            return {"paths": sorted(paths & inventory.keys()), "limited": limited}
        finally:
            connection.close()
