"""Local, source-addressable project and NASA/JPL metadata search."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import zipfile
from pathlib import Path

from app.services.lunarsight.point import repository_root


def _id(path: str, offset: int, content: str, source_hash: str) -> str:
    return hashlib.sha256((path + "\0" + str(offset) + "\0" + source_hash + "\0" + content).encode("utf-8")).hexdigest()[:20]


def _plain(path: str, text: str):
    # Split long docs into addressable overlapping passages without losing provenance.
    cleaned = text.replace("\x00", " ")
    size, overlap = 1800, 180
    source_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    version_match = re.search(r"v\d+\.\d+\.\d+", path)
    source_version = version_match.group(0) if version_match else "working-tree"
    lowered = path.lower().replace("\\", "/")
    historical_paths = ("/history/", "archive", "docs/submission/", "docs/decisions/llm-backend-openrouter.md",
                        "docs/validation/lunarsight/v0.2.0/")
    source_status = "historical" if any(part in lowered for part in historical_paths) else "current"
    for offset in range(0, max(1, len(cleaned)), size - overlap):
        body = cleaned[offset:offset + size].strip()
        if body:
            yield path, offset, body, source_hash, source_version, source_status


def _read_text(path: Path) -> str:
    text=path.read_text(encoding="utf-8",errors="replace")
    if path.suffix.lower()!=".json":
        return text
    try:
        parsed=json.loads(text,parse_constant=lambda value:value)
        return json.dumps(parsed,ensure_ascii=False,indent=2,allow_nan=False)
    except (ValueError,TypeError):
        return text


class ProjectKnowledge:
    def __init__(self, db_path: str | Path | None = None, project_root: Path | None = None,
                 raw_root: Path | None = None):
        self.root = Path(project_root or repository_root())
        default_db = self.root / "data/cache/assistant/knowledge.sqlite3"
        self.db_path = Path(db_path or os.getenv("ASSISTANT_DATABASE_PATH") or default_db)
        configured_raw=os.getenv("LUNARSIGHT_RAW_DATASET_PATH")
        self.raw_root = Path(raw_root or configured_raw or self.root/"data/source-delivery")

    def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_path, timeout=30)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=30000")
        return con

    def _documents(self):
        allowed = {".md", ".txt", ".json", ".py", ".toml", ".csv"}
        for folder in ("docs", "backend/app/assistant", "backend/app/mission", "backend/app/planning",
                       "backend/app/point_analysis", "manifests", "data/raw/nasa", "data/processed/lunarsight",
                       "data/cache/lunarsight"):
            base = self.root / folder
            if not base.is_dir():
                continue
            for path in base.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in allowed or any(
                    item in {"node_modules", ".git", "__pycache__"} for item in path.parts):
                    continue
                try:
                    if path.stat().st_size > 2_000_000:
                        continue
                    text = _read_text(path)
                    yield from _plain(path.relative_to(self.root).as_posix(), text)
                except OSError:
                    continue
        for name in ("README.md",):
            path = self.root / name
            if path.is_file():
                yield from _plain(name, path.read_text(encoding="utf-8", errors="replace"))
        if self.raw_root.is_dir():
            for name in ("README_RAW_DATASET.txt", "REGION_INVENTORY.json", "SOURCE_MANIFEST.json", "DOWNLOAD_CHECKSUMS.json"):
                path = self.raw_root / name
                if path.is_file() and path.stat().st_size <= 2_000_000:
                    text = _read_text(path)
                    yield from _plain(f"dataset/{name}", text)
            # Index receipts and original NASA README from archives; never extract assets to disk.
            for archive in sorted(self.raw_root.glob("*.zip")):
                try:
                    with zipfile.ZipFile(archive) as zf:
                        for member in zf.infolist():
                            if member.is_dir() or member.file_size > 256_000:
                                continue
                            is_receipt=member.filename.startswith("receipts/") and member.filename.endswith(".json")
                            is_readme=member.filename.endswith("/README")
                            if not (is_receipt or is_readme):
                                continue
                            if Path(member.filename).name == "Site06_ROIs.tgz":
                                continue
                            try:
                                raw = zf.read(member)
                                text = raw.decode("utf-8", errors="replace")
                                yield from _plain(f"dataset/{archive.name}!/{member.filename}", text)
                            except (OSError, KeyError, RuntimeError, zipfile.BadZipFile):
                                continue
                except (OSError, zipfile.BadZipFile):
                    continue

    def source_fingerprint(self) -> str:
        digest = hashlib.sha256()
        allowed = {".md", ".txt", ".json", ".py", ".toml", ".csv"}
        for folder in ("docs", "backend/app/assistant", "backend/app/mission", "backend/app/planning",
                       "backend/app/point_analysis", "manifests", "data/raw/nasa", "data/processed/lunarsight",
                       "data/cache/lunarsight"):
            base = self.root / folder
            if base.is_dir():
                for path in sorted(base.rglob("*")):
                    if path.is_file() and path.suffix.lower() in allowed and path.stat().st_size <= 2_000_000:
                        stat = path.stat()
                        digest.update(f"{path.relative_to(self.root).as_posix()}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
        for name in ("README.md",):
            path = self.root / name
            if path.is_file():
                stat = path.stat()
                digest.update(f"{name}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
        if self.raw_root.is_dir():
            for path in sorted(self.raw_root.glob("*.zip")):
                stat = path.stat()
                digest.update(f"zip\0{path.name}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
            for name in ("README_RAW_DATASET.txt", "REGION_INVENTORY.json", "SOURCE_MANIFEST.json", "DOWNLOAD_CHECKSUMS.json"):
                path = self.raw_root / name
                if path.is_file():
                    stat = path.stat()
                    digest.update(f"dataset/{name}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
        return digest.hexdigest()

    def rebuild(self) -> dict:
        fingerprint = self.source_fingerprint()
        con = self._connect()
        try:
            existing = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='passages'").fetchone()
            if existing and "source_hash" not in (existing[0] or ""):
                # Passage indexes are derived and can be rebuilt; old schema IDs are not portable.
                con.execute("DROP TABLE passages")
            con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS passages USING fts5(source_id UNINDEXED,path UNINDEXED,offset UNINDEXED,source_hash UNINDEXED,source_version UNINDEXED,source_status UNINDEXED,body,tokenize='unicode61 remove_diacritics 2')")
            con.execute("CREATE TABLE IF NOT EXISTS index_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            con.execute("DELETE FROM passages")
            count = 0
            for path, offset, body, source_hash, source_version, source_status in self._documents():
                con.execute("INSERT INTO passages(source_id,path,offset,source_hash,source_version,source_status,body) VALUES(?,?,?,?,?,?,?)",
                            (_id(path, offset, body, source_hash), path, offset, source_hash, source_version, source_status, body))
                count += 1
            con.execute("INSERT OR REPLACE INTO index_meta VALUES('passage_count',?)", (str(count),))
            con.execute("INSERT OR REPLACE INTO index_meta VALUES('project_root',?)", (str(self.root),))
            con.execute("INSERT OR REPLACE INTO index_meta VALUES('source_fingerprint',?)", (fingerprint,))
            con.commit()
            return {"passages": count, "database": str(self.db_path)}
        finally:
            con.close()

    @staticmethod
    def _query(text: str) -> str:
        tokens = re.findall(r"[\wÀ-ỹ]+", text, flags=re.UNICODE)
        return " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens[:24])

    def search(self, query: str, limit: int = 8) -> list[dict]:
        expression = self._query(query)
        if not expression:
            return []
        con = self._connect()
        try:
            try:
                rows = con.execute("SELECT source_id,path,offset,source_hash,source_version,source_status,body,bm25(passages) AS score FROM passages "
                    "WHERE passages MATCH ? ORDER BY CASE source_status WHEN 'current' THEN 0 ELSE 1 END, score LIMIT ?",
                    (expression, max(1, min(limit, 20)))).fetchall()
            except sqlite3.OperationalError:
                return []
            return [{"source_id": row[0], "path": row[1], "offset": row[2], "source_hash": row[3],
                     "source_version": row[4], "source_status": row[5], "excerpt": row[6],
                     "score": float(row[7])} for row in rows]
        finally:
            con.close()

    def source(self, source_id: str) -> dict | None:
        con = self._connect()
        try:
            row = con.execute("SELECT source_id,path,offset,source_hash,source_version,source_status,body FROM passages WHERE source_id=? LIMIT 1", (source_id,)).fetchone()
            return {"source_id": row[0], "path": row[1], "offset": row[2], "source_hash": row[3],
                    "source_version": row[4], "source_status": row[5], "excerpt": row[6]} if row else None
        finally:
            con.close()

    def context_sources(self) -> list[dict]:
        """Current project orientation, with the same addressable citations as search."""
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT source_id,path,offset,source_hash,source_version,source_status,body FROM passages "
                "WHERE path IN (?,?) AND source_status='current' ORDER BY path,offset LIMIT 8",
                ("docs/assistant/lunarsight-current-context.md", "docs/assistant/decision-support-guide.md"),
            ).fetchall()
            return [{"source_id": row[0], "path": row[1], "offset": row[2], "source_hash": row[3],
                     "source_version": row[4], "source_status": row[5], "excerpt": row[6]} for row in rows]
        finally:
            con.close()
