"""The blackboard, the bus and the turns, in one database (see db.py). Entries are keyed per meeting."""

from __future__ import annotations

import json
import time
from typing import Any

from .db import DB

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (id TEXT PRIMARY KEY, title TEXT, status TEXT, round TEXT, created_at REAL, finished_at REAL, waiting TEXT, arbitrations INTEGER DEFAULT 0, objections_raised INTEGER DEFAULT 0, model TEXT);
CREATE TABLE IF NOT EXISTS entries (meeting_id TEXT, id TEXT, kind TEXT, owner TEXT, version INTEGER, status TEXT, payload TEXT, evidence TEXT, created_at REAL, superseded_by TEXT, PRIMARY KEY (meeting_id, id));
CREATE TABLE IF NOT EXISTS messages (id {SERIAL}, meeting_id TEXT, round TEXT, kind TEXT, from_agent TEXT, to_agent TEXT, refs TEXT, text TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS turns (id TEXT PRIMARY KEY, meeting_id TEXT, round TEXT, agent TEXT, status TEXT, tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0, cost_usd REAL DEFAULT 0, ms INTEGER DEFAULT 0, started_at REAL, ended_at REAL);
CREATE TABLE IF NOT EXISTS calls (id {SERIAL}, meeting_id TEXT, turn_id TEXT, agent TEXT, model TEXT, tokens_in INTEGER, tokens_out INTEGER, cached INTEGER, cost_usd REAL, ms INTEGER, ts REAL);
"""


def _j(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


class Store:
    def __init__(self, db: DB):
        self.db = db
        db.script(SCHEMA)

    def q(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        return self.db.q(sql, args)

    def one(self, sql: str, args: tuple = ()) -> dict[str, Any] | None:
        return self.db.one(sql, args)

    def x(self, sql: str, args: tuple = ()) -> None:
        self.db.x(sql, args)

    def reset(self) -> None:
        for t in ("meetings", "entries", "messages", "turns", "calls"):
            self.x(f"DELETE FROM {t}")
        if self.db.pg:
            for t in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
                try:
                    self.x(f"DELETE FROM {t}")
                except Exception:  # noqa: BLE001
                    pass

    # ---- meetings
    def new_meeting(self, mid: str, title: str, model: str) -> None:
        self.x("INSERT INTO meetings (id, title, status, round, created_at, model) VALUES (%s,%s,'running','brief',%s,%s)", (mid, title, time.time(), model))

    def meeting(self, mid: str) -> dict[str, Any] | None:
        m = self.one("SELECT * FROM meetings WHERE id=%s", (mid,))
        if m and m.get("waiting"):
            try:
                m["waiting"] = json.loads(m["waiting"])
            except (TypeError, ValueError):
                pass
        return m

    def set_meeting(self, mid: str, **f: Any) -> None:
        sets = ", ".join(f"{k}=%s" for k in f)
        vals = [_j(v) if isinstance(v, (dict, list)) else v for v in f.values()]
        self.x(f"UPDATE meetings SET {sets} WHERE id=%s", (*vals, mid))

    def bump(self, mid: str, column: str, by: int = 1) -> int:
        self.x(f"UPDATE meetings SET {column} = COALESCE({column},0) + %s WHERE id=%s", (by, mid))
        return int((self.one(f"SELECT {column} AS v FROM meetings WHERE id=%s", (mid,)) or {}).get("v") or 0)

    # ---- blackboard: only the owner writes; every write is a new version
    def put(self, mid: str, entry_id: str, kind: str, owner: str, payload: dict[str, Any], evidence: list[dict[str, Any]] | None = None, status: str = "open") -> str:
        prev = self.one("SELECT * FROM entries WHERE meeting_id=%s AND id=%s", (mid, entry_id))
        if prev and prev["owner"] != owner and owner != "human":
            raise PermissionError(f"{owner} may not write {entry_id}, owned by {prev['owner']}")
        version = (prev["version"] + 1) if prev else 1
        if prev:
            hist_id = f"{entry_id}@v{prev['version']}"
            self.x(
                "INSERT INTO entries (meeting_id, id, kind, owner, version, status, payload, evidence, created_at, superseded_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (meeting_id, id) DO UPDATE SET payload=excluded.payload, status=excluded.status",
                (mid, hist_id, prev["kind"], prev["owner"], prev["version"], "superseded", prev["payload"], prev["evidence"], prev["created_at"], entry_id),
            )
        self.x(
            "INSERT INTO entries (meeting_id, id, kind, owner, version, status, payload, evidence, created_at, superseded_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL) "
            "ON CONFLICT (meeting_id, id) DO UPDATE SET kind=excluded.kind, version=excluded.version, status=excluded.status, payload=excluded.payload, evidence=excluded.evidence, created_at=excluded.created_at, superseded_by=NULL",
            (mid, entry_id, kind, owner if not prev else prev["owner"], version, status, _j(payload), _j(evidence or []), time.time()),
        )
        return entry_id

    def get(self, mid: str, entry_id: str) -> dict[str, Any] | None:
        e = self.one("SELECT * FROM entries WHERE meeting_id=%s AND id=%s", (mid, entry_id))
        return self._parse(e) if e else None

    def entries(self, mid: str, kind: str | None = None, include_history: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM entries WHERE meeting_id=%s" + (" AND kind=%s" if kind else "") + ("" if include_history else " AND status!='superseded'") + " ORDER BY created_at"
        rows = self.q(sql, (mid, kind) if kind else (mid,))
        return [self._parse(r) for r in rows]

    def set_status(self, mid: str, entry_id: str, status: str) -> None:
        self.x("UPDATE entries SET status=%s WHERE meeting_id=%s AND id=%s", (status, mid, entry_id))

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
        self.x("INSERT INTO messages (meeting_id, round, kind, from_agent, to_agent, refs, text, ts) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (mid, round_, kind, from_agent, to_agent, _j(refs or []), text, time.time()))

    def messages(self, mid: str, after: int = 0) -> list[dict[str, Any]]:
        rows = self.q("SELECT * FROM messages WHERE meeting_id=%s AND id>%s ORDER BY id", (mid, after))
        for r in rows:
            r["refs"] = json.loads(r["refs"]) if r.get("refs") else []
        return rows

    # ---- turns and cost
    def start_turn(self, tid: str, mid: str, round_: str, agent: str) -> None:
        self.x("INSERT INTO turns (id, meeting_id, round, agent, status, started_at) VALUES (%s,%s,%s,%s,'running',%s) ON CONFLICT (id) DO NOTHING", (tid, mid, round_, agent, time.time()))

    def end_turn(self, tid: str, status: str = "done") -> None:
        self.x("UPDATE turns SET status=%s, ended_at=%s WHERE id=%s", (status, time.time(), tid))

    def record_call(self, mid: str, tid: str, agent: str, model: str, tin: int, tout: int, cached: int, cost: float, ms: int) -> None:
        self.x("INSERT INTO calls (meeting_id, turn_id, agent, model, tokens_in, tokens_out, cached, cost_usd, ms, ts) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (mid, tid, agent, model, tin, tout, cached, cost, ms, time.time()))
        self.x("UPDATE turns SET tokens_in=tokens_in+%s, tokens_out=tokens_out+%s, cost_usd=cost_usd+%s, ms=ms+%s WHERE id=%s", (tin, tout, cost, ms, tid))

    def turns(self, mid: str) -> list[dict[str, Any]]:
        return self.q("SELECT * FROM turns WHERE meeting_id=%s ORDER BY started_at", (mid,))
