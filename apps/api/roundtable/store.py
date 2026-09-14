"""The blackboard, the bus and the turns, in one SQLite file."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (id TEXT PRIMARY KEY, title TEXT, status TEXT, round TEXT, created_at REAL, finished_at REAL, waiting TEXT);
CREATE TABLE IF NOT EXISTS entries (id TEXT PRIMARY KEY, meeting_id TEXT, kind TEXT, owner TEXT, version INTEGER, status TEXT, payload TEXT, evidence TEXT, created_at REAL, superseded_by TEXT);
CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, meeting_id TEXT, round TEXT, kind TEXT, from_agent TEXT, to_agent TEXT, refs TEXT, text TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS turns (id TEXT PRIMARY KEY, meeting_id TEXT, round TEXT, agent TEXT, status TEXT, tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0, cost_usd REAL DEFAULT 0, ms INTEGER DEFAULT 0, started_at REAL, ended_at REAL);
CREATE TABLE IF NOT EXISTS calls (id INTEGER PRIMARY KEY AUTOINCREMENT, meeting_id TEXT, turn_id TEXT, agent TEXT, model TEXT, tokens_in INTEGER, tokens_out INTEGER, cached INTEGER, cost_usd REAL, ms INTEGER, ts REAL);
"""


def _j(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


class Store:
    def __init__(self, path: str | Path):
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def q(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def one(self, sql: str, args: tuple = ()) -> dict[str, Any] | None:
        rows = self.q(sql, args)
        return rows[0] if rows else None

    def x(self, sql: str, args: tuple = ()) -> None:
        with self._lock:
            self.conn.execute(sql, args)
            self.conn.commit()

    def reset(self) -> None:
        with self._lock:
            for t in ("meetings", "entries", "messages", "turns", "calls"):
                self.conn.execute(f"DELETE FROM {t}")
            self.conn.commit()

    # ---- meetings
    def new_meeting(self, mid: str, title: str) -> None:
        self.x("INSERT INTO meetings (id, title, status, round, created_at) VALUES (?,?,'running','brief',?)", (mid, title, time.time()))

    def set_meeting(self, mid: str, **f: Any) -> None:
        sets = ", ".join(f"{k}=?" for k in f)
        vals = [_j(v) if isinstance(v, (dict, list)) else v for v in f.values()]
        self.x(f"UPDATE meetings SET {sets} WHERE id=?", (*vals, mid))

    # ---- blackboard: only the owner writes; every write is a new version
    def put(self, mid: str, entry_id: str, kind: str, owner: str, payload: dict[str, Any], evidence: list[dict[str, Any]] | None = None, status: str = "open") -> str:
        prev = self.one("SELECT * FROM entries WHERE meeting_id=? AND id=?", (mid, entry_id))
        if prev and prev["owner"] != owner and owner != "human":
            raise PermissionError(f"{owner} may not write {entry_id}, owned by {prev['owner']}")
        version = (prev["version"] + 1) if prev else 1
        if prev:
            # keep history: archive the previous version under a suffixed id
            hist_id = f"{entry_id}@v{prev['version']}"
            self.x("INSERT OR REPLACE INTO entries (id, meeting_id, kind, owner, version, status, payload, evidence, created_at, superseded_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (hist_id, mid, prev["kind"], prev["owner"], prev["version"], "superseded", prev["payload"], prev["evidence"], prev["created_at"], entry_id))
        self.x("INSERT OR REPLACE INTO entries (id, meeting_id, kind, owner, version, status, payload, evidence, created_at, superseded_by) VALUES (?,?,?,?,?,?,?,?,?,NULL)",
               (entry_id, mid, kind, owner if not prev else prev["owner"], version, status, _j(payload), _j(evidence or []), time.time()))
        return entry_id

    def get(self, mid: str, entry_id: str) -> dict[str, Any] | None:
        e = self.one("SELECT * FROM entries WHERE meeting_id=? AND id=?", (mid, entry_id))
        return self._parse(e) if e else None

    def entries(self, mid: str, kind: str | None = None, include_history: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM entries WHERE meeting_id=?" + (" AND kind=?" if kind else "") + ("" if include_history else " AND status!='superseded'") + " ORDER BY created_at"
        rows = self.q(sql, (mid, kind) if kind else (mid,))
        return [self._parse(r) for r in rows]

    def set_status(self, mid: str, entry_id: str, status: str) -> None:
        self.x("UPDATE entries SET status=? WHERE meeting_id=? AND id=?", (status, mid, entry_id))

    @staticmethod
    def _parse(e: dict[str, Any]) -> dict[str, Any]:
        e = dict(e)
        for k in ("payload", "evidence"):
            try:
                e[k] = json.loads(e[k]) if e.get(k) else ([] if k == "evidence" else {})
            except (TypeError, ValueError):
                pass
        return e

    # ---- bus
    def say(self, mid: str, round_: str, kind: str, from_agent: str, to_agent: str, text: str, refs: list[str] | None = None) -> None:
        self.x("INSERT INTO messages (meeting_id, round, kind, from_agent, to_agent, refs, text, ts) VALUES (?,?,?,?,?,?,?,?)", (mid, round_, kind, from_agent, to_agent, _j(refs or []), text, time.time()))

    def messages(self, mid: str, after: int = 0) -> list[dict[str, Any]]:
        rows = self.q("SELECT * FROM messages WHERE meeting_id=? AND id>? ORDER BY id", (mid, after))
        for r in rows:
            r["refs"] = json.loads(r["refs"]) if r.get("refs") else []
        return rows

    def messages_since(self, after: int) -> list[dict[str, Any]]:
        rows = self.q("SELECT * FROM messages WHERE id>? ORDER BY id", (after,))
        for r in rows:
            r["refs"] = json.loads(r["refs"]) if r.get("refs") else []
        return rows

    # ---- turns and cost
    def start_turn(self, tid: str, mid: str, round_: str, agent: str) -> None:
        self.x("INSERT OR REPLACE INTO turns (id, meeting_id, round, agent, status, started_at) VALUES (?,?,?,?,'running',?)", (tid, mid, round_, agent, time.time()))

    def end_turn(self, tid: str, status: str = "done") -> None:
        self.x("UPDATE turns SET status=?, ended_at=? WHERE id=?", (status, time.time(), tid))

    def record_call(self, mid: str, tid: str, agent: str, model: str, tin: int, tout: int, cached: int, cost: float, ms: int) -> None:
        self.x("INSERT INTO calls (meeting_id, turn_id, agent, model, tokens_in, tokens_out, cached, cost_usd, ms, ts) VALUES (?,?,?,?,?,?,?,?,?,?)", (mid, tid, agent, model, tin, tout, cached, cost, ms, time.time()))
        self.x("UPDATE turns SET tokens_in=tokens_in+?, tokens_out=tokens_out+?, cost_usd=cost_usd+?, ms=ms+? WHERE id=?", (tin, tout, cost, ms, tid))

    def turns(self, mid: str) -> list[dict[str, Any]]:
        return self.q("SELECT * FROM turns WHERE meeting_id=? ORDER BY started_at", (mid,))
