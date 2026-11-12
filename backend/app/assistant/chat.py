"""Persistent local sessions and chat runs with replayable progress events."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from .config import AssistantSettings


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ChatStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as con:
            con.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, created_utc TEXT NOT NULL, updated_utc TEXT NOT NULL,
              working_state TEXT NOT NULL DEFAULT '{}', applied_state TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL,
              content TEXT NOT NULL, created_utc TEXT NOT NULL, run_id TEXT,
              FOREIGN KEY(session_id) REFERENCES sessions(id));
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
              status TEXT NOT NULL, stage TEXT NOT NULL, result TEXT, error_code TEXT, created_utc TEXT NOT NULL,
              updated_utc TEXT NOT NULL, UNIQUE(session_id,idempotency_key));
            CREATE TABLE IF NOT EXISTS events(run_id TEXT NOT NULL, seq INTEGER NOT NULL, event TEXT NOT NULL,
              created_utc TEXT NOT NULL, PRIMARY KEY(run_id,seq));
            """)
            columns = {row[1] for row in con.execute("PRAGMA table_info(messages)")}
            if "run_id" not in columns:
                con.execute("ALTER TABLE messages ADD COLUMN run_id TEXT")
            con.execute("CREATE INDEX IF NOT EXISTS messages_session_order ON messages(session_id,created_utc,id)")
            con.execute("CREATE INDEX IF NOT EXISTS messages_run ON messages(run_id)")

    def _connect(self):
        con = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=30000")
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @contextmanager
    def _connection(self):
        con=self._connect()
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def create_session(self) -> dict:
        identifier, now = uuid4().hex, utc_now()
        with self.lock, self._connection() as con:
            con.execute("INSERT INTO sessions(id,created_utc,updated_utc) VALUES(?,?,?)", (identifier, now, now))
        return self.session(identifier)

    def session(self, identifier: str) -> dict | None:
        with self._connection() as con:
            row = con.execute("SELECT * FROM sessions WHERE id=?", (identifier,)).fetchone()
            if not row:
                return None
            messages = con.execute("SELECT id,role,content,created_utc,run_id FROM messages WHERE session_id=? ORDER BY created_utc,id", (identifier,)).fetchall()
            runs = con.execute("SELECT * FROM runs WHERE session_id=? ORDER BY created_utc,id", (identifier,)).fetchall()
        return {"id": row["id"], "created_utc": row["created_utc"], "updated_utc": row["updated_utc"],
                "working_state": json.loads(row["working_state"]), "applied_state": json.loads(row["applied_state"]),
                "messages": [dict(item) for item in messages], "runs": [self._run_row(item) for item in runs]}

    def begin_run(self, session_id: str, idempotency_key: str, text: str) -> tuple[dict, bool]:
        now, run_id = utc_now(), uuid4().hex
        with self.lock, self._connection() as con:
            if not con.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone():
                raise KeyError("SESSION_NOT_FOUND")
            prior = con.execute("SELECT * FROM runs WHERE session_id=? AND idempotency_key=?", (session_id,idempotency_key)).fetchone()
            if prior:
                return self._run_row(prior), False
            con.execute("INSERT INTO runs(id,session_id,idempotency_key,status,stage,created_utc,updated_utc) VALUES(?,?,?,?,?,?,?)",
                        (run_id,session_id,idempotency_key,"queued","queued",now,now))
            con.execute("INSERT INTO messages(id,session_id,role,content,created_utc,run_id) VALUES(?,?,?,?,?,?)",
                        (uuid4().hex,session_id,"user",text,now,run_id))
            con.execute("UPDATE sessions SET updated_utc=? WHERE id=?", (now,session_id))
            self._append(con,run_id,{"status":"queued","stage":"queued"})
            return {"id":run_id,"session_id":session_id,"status":"queued","stage":"queued","result":None,
                    "error_code":None,"created_utc":now,"updated_utc":now}, True

    @staticmethod
    def _run_row(row):
        return {"id":row["id"],"session_id":row["session_id"],"status":row["status"],"stage":row["stage"],
                "result":json.loads(row["result"]) if row["result"] else None,"error_code":row["error_code"],
                "created_utc":row["created_utc"],"updated_utc":row["updated_utc"]}

    def run(self, identifier: str) -> dict | None:
        with self._connection() as con:
            row=con.execute("SELECT * FROM runs WHERE id=?",(identifier,)).fetchone()
        return self._run_row(row) if row else None

    def set_stage(self, run_id: str, status: str, stage: str):
        with self.lock, self._connection() as con:
            now=utc_now(); cursor=con.execute("UPDATE runs SET status=?,stage=?,updated_utc=? WHERE id=? AND status IN ('queued','running')",(status,stage,now,run_id))
            if cursor.rowcount:
                self._append(con,run_id,{"status":status,"stage":stage})

    def finish(self, run_id: str, status: str, result: dict | None = None, error_code: str | None = None):
        with self.lock, self._connection() as con:
            session = con.execute("SELECT session_id FROM runs WHERE id=?",(run_id,)).fetchone()
            if not session:
                return
            now=utc_now(); cursor=con.execute("UPDATE runs SET status=?,stage=?,result=?,error_code=?,updated_utc=? WHERE id=? AND status IN ('queued','running')",
                (status,"complete" if status=="completed" else status,json.dumps(result,ensure_ascii=False,allow_nan=False) if result is not None else None,error_code,now,run_id))
            if not cursor.rowcount:
                return
            self._append(con,run_id,{"status":status,"result":result,"error_code":error_code})
            if result and status in {"completed","partial","needs_input"}:
                con.execute("INSERT INTO messages(id,session_id,role,content,created_utc,run_id) VALUES(?,?,?,?,?,?)",
                    (uuid4().hex,session["session_id"],"assistant",result.get("answer", ""),now,run_id))

    def cancel(self, run_id: str):
        with self.lock, self._connection() as con:
            now=utc_now(); cursor=con.execute("UPDATE runs SET status='cancelled',stage='cancelled',updated_utc=? WHERE id=? AND status IN ('queued','running')",(now,run_id))
            if cursor.rowcount:
                self._append(con,run_id,{"status":"cancelled","stage":"cancelled"})

    def update_working(self, session_id: str, state: dict):
        with self.lock, self._connection() as con:
            con.execute("UPDATE sessions SET working_state=?,updated_utc=? WHERE id=?",(json.dumps(state,ensure_ascii=False),utc_now(),session_id))

    def apply(self, session_id: str, state: dict):
        with self.lock, self._connection() as con:
            con.execute("UPDATE sessions SET applied_state=?,updated_utc=? WHERE id=?",(json.dumps(state,ensure_ascii=False),utc_now(),session_id))

    def events_after(self, run_id: str, cursor: int):
        with self._connection() as con:
            rows=con.execute("SELECT seq,event,created_utc FROM events WHERE run_id=? AND seq>? ORDER BY seq",(run_id,cursor)).fetchall()
        return [{"id":row["seq"],"data":json.loads(row["event"]),"created_utc":row["created_utc"]} for row in rows]

    @staticmethod
    def _append(con,run_id,data):
        row=con.execute("SELECT COALESCE(MAX(seq),0)+1 AS seq FROM events WHERE run_id=?",(run_id,)).fetchone()
        con.execute("INSERT INTO events VALUES(?,?,?,?)",(run_id,row["seq"],json.dumps(data,ensure_ascii=False,allow_nan=False),utc_now()))

    def interrupt_active(self):
        with self.lock, self._connection() as con:
            rows=con.execute("SELECT id FROM runs WHERE status IN ('queued','running')").fetchall()
            for row in rows:
                con.execute("UPDATE runs SET status='interrupted',stage='interrupted',error_code='PROCESS_RESTARTED',updated_utc=? WHERE id=?",(utc_now(),row["id"]))
                self._append(con,row["id"],{"status":"interrupted","error_code":"PROCESS_RESTARTED"})


def default_database(settings: AssistantSettings):
    if settings.assistant_database_path:
        return Path(settings.assistant_database_path)
    from app.services.lunarsight.point import repository_root
    return repository_root() / "data/cache/assistant/chat.sqlite3"
