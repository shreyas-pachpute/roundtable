"""The API the meeting room talks to: start a meeting, watch it, sit at the table."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .gateway import Gateway
from .protocol import ROUNDS, Meeting, run_meeting
from .store import Store

ROOT = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("ROUNDTABLE_DATA", ROOT / "data" / "harbor"))
DB = Path(os.environ.get("ROUNDTABLE_DB", ROOT / "data" / "runtime" / "roundtable.sqlite"))
DB.parent.mkdir(parents=True, exist_ok=True)

store = Store(DB)
gateway = Gateway(store)
RFP = json.loads((DATA / "rfp.json").read_text(encoding="utf8"))
KB = json.loads((DATA / "knowledge.json").read_text(encoding="utf8"))

app = FastAPI(title="Roundtable API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

meetings: dict[str, Meeting] = {}
tasks: dict[str, asyncio.Task] = {}


class SettingsIn(BaseModel):
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None


class HumanIn(BaseModel):
    decision: str
    note: str = ""


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "model": gateway.settings.label, "meetings": len(meetings)}


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return gateway.settings.public()


@app.post("/api/settings")
def set_settings(s: SettingsIn) -> dict[str, Any]:
    gateway.configure(**{k: v for k, v in s.model_dump().items() if v is not None})
    return gateway.settings.public()


@app.post("/api/settings/check")
async def check_settings() -> dict[str, Any]:
    gateway.current = {"meeting": "settings", "turn": "check"}
    return await gateway.check()


@app.get("/api/rfp")
def rfp() -> dict[str, Any]:
    return {"rfp": RFP, "knowledge": [{"id": c["id"], "kind": c["kind"], "title": c["title"]} for c in KB]}


@app.post("/api/demo/reset")
def reset() -> dict[str, Any]:
    for t in tasks.values():
        t.cancel()
    tasks.clear()
    meetings.clear()
    store.reset()
    return {"ok": True}


@app.post("/api/meetings")
async def start() -> dict[str, Any]:
    running = [m for m in meetings.values() if (store.one("SELECT status FROM meetings WHERE id=?", (m.id,)) or {}).get("status") in ("running", "waiting_for_human")]
    if running:
        return {"ok": True, "id": running[0].id, "already": True}
    mid = f"mtg-{uuid.uuid4().hex[:6]}"
    store.new_meeting(mid, RFP["title"])
    m = Meeting(mid, store, gateway, RFP, KB)
    meetings[mid] = m
    m.say("open", "chair", "all", f"Meeting opened on “{RFP['title']}” for {RFP['client']} · model: {gateway.settings.label}")
    tasks[mid] = asyncio.create_task(run_meeting(m))
    return {"ok": True, "id": mid}


@app.get("/api/meetings")
def list_meetings() -> dict[str, Any]:
    return {"meetings": store.q("SELECT * FROM meetings ORDER BY created_at DESC")}


@app.get("/api/meetings/{mid}")
def get_meeting(mid: str) -> dict[str, Any]:
    mt = store.one("SELECT * FROM meetings WHERE id=?", (mid,))
    if not mt:
        raise HTTPException(404)
    if mt.get("waiting"):
        try:
            mt["waiting"] = json.loads(mt["waiting"])
        except (TypeError, ValueError):
            pass
    entries = store.entries(mid, include_history=True)
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        by_kind.setdefault(e["kind"], []).append(e)
    turns = store.turns(mid)
    calls = store.q("SELECT SUM(tokens_in) tin, SUM(tokens_out) tout, SUM(cost_usd) cost, COUNT(*) n FROM calls WHERE meeting_id=?", (mid,))[0]
    return {
        "meeting": mt,
        "rounds": ROUNDS,
        "blackboard": by_kind,
        "messages": store.messages(mid),
        "turns": turns,
        "cost": {"tokens": (calls["tin"] or 0) + (calls["tout"] or 0), "usd": round(calls["cost"] or 0, 4), "calls": calls["n"] or 0},
        "model": gateway.settings.label,
    }


@app.post("/api/meetings/{mid}/human")
def human(mid: str, h: HumanIn) -> dict[str, Any]:
    m = meetings.get(mid)
    if not m:
        raise HTTPException(404)
    if not m.pending:
        raise HTTPException(409, "nothing is waiting for you")
    m.resolve_human(h.decision, h.note)
    return {"ok": True}


@app.get("/api/events")
async def events(after: int = 0):
    async def gen():
        last = after
        while True:
            for x in store.messages_since(last):
                last = x["id"]
                yield {"event": "msg", "id": str(x["id"]), "data": json.dumps(x, default=str)}
            await asyncio.sleep(0.4)

    return EventSourceResponse(gen())


def run() -> None:
    import uvicorn

    uvicorn.run("roundtable.main:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8788")), reload=False)


if __name__ == "__main__":
    run()
