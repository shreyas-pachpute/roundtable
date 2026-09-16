"""The API the meeting room talks to. Stateless per request: the database and the LangGraph checkpointer hold
the meeting, the UI advances it with `step` calls and polls `messages`. Model settings arrive as headers."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import connect
from .gateway import ANTHROPIC_MODELS, Gateway, Settings
from .protocol import ROUNDS, Engine
from .store import Store

ROOT = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("ROUNDTABLE_DATA", ROOT / "data" / "harbor"))

store = Store(connect(ROOT / "data" / "runtime" / "roundtable.sqlite", "roundtable"))
RFP = json.loads((DATA / "rfp.json").read_text(encoding="utf8"))
KB = json.loads((DATA / "knowledge.json").read_text(encoding="utf8"))
engine = Engine(store, RFP, KB)

app = FastAPI(title="Roundtable API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class HumanIn(BaseModel):
    answers: dict[str, dict[str, str]]  # decision id -> {decision, note}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "db": store.db.label, "checkpointer": type(engine.saver).__name__}


@app.get("/api/settings")
def get_settings(request: Request) -> dict[str, Any]:
    s = Settings.from_headers(request.headers)
    return {"provider": s.provider, "model": s.model, "base_url": s.base_url, "has_key": bool(s.api_key), "label": s.label, "anthropic_models": ANTHROPIC_MODELS, "server_default": Settings.from_env().label}


@app.post("/api/settings/check")
async def check_settings(request: Request) -> dict[str, Any]:
    gw = Gateway(store, Settings.from_headers(request.headers))
    gw.current = {"meeting": "settings", "turn": ""}
    return await gw.check()


@app.get("/api/rfp")
def rfp() -> dict[str, Any]:
    return {"rfp": RFP, "knowledge": [{"id": c["id"], "kind": c["kind"], "title": c["title"]} for c in KB]}


@app.post("/api/demo/reset")
def reset() -> dict[str, Any]:
    store.reset()
    return {"ok": True}


@app.post("/api/meetings")
async def start(request: Request) -> dict[str, Any]:
    settings = Settings.from_headers(request.headers)
    running = store.one("SELECT id FROM meetings WHERE status IN ('running','waiting_for_human') ORDER BY created_at DESC LIMIT 1")
    if running:
        return {"ok": True, "id": running["id"], "already": True}
    mid = f"mtg-{uuid.uuid4().hex[:6]}"
    store.new_meeting(mid, RFP["title"], settings.label)
    store.say(mid, "brief", "open", "chair", "all", f"Meeting opened on “{RFP['title']}” for {RFP['client']} · model: {settings.label}")
    out = await engine.step(mid, settings, first=True)
    return {"ok": True, "id": mid, **out}


@app.post("/api/meetings/{mid}/step")
async def step(mid: str, request: Request) -> dict[str, Any]:
    """Run the next round. Returns what comes next; the UI keeps calling until finished or waiting."""
    m = store.meeting(mid)
    if not m:
        raise HTTPException(404)
    if m["status"] == "waiting_for_human":
        return {"ok": True, "waiting": True, "finished": False, "next": ["human_seat"]}
    if m["status"] in ("finished", "failed"):
        return {"ok": True, "waiting": False, "finished": True, "next": []}
    out = await engine.step(mid, Settings.from_headers(request.headers))
    return {"ok": True, **out}


@app.post("/api/meetings/{mid}/human")
async def human(mid: str, h: HumanIn, request: Request) -> dict[str, Any]:
    m = store.meeting(mid)
    if not m:
        raise HTTPException(404)
    if m["status"] != "waiting_for_human":
        raise HTTPException(409, "nothing is waiting for you")
    out = await engine.step(mid, Settings.from_headers(request.headers), resume=h.answers)
    return {"ok": True, **out}


@app.get("/api/meetings")
def list_meetings() -> dict[str, Any]:
    return {"meetings": store.q("SELECT id, title, status, round, created_at, model FROM meetings ORDER BY created_at DESC LIMIT 20")}


@app.get("/api/meetings/{mid}")
def get_meeting(mid: str) -> dict[str, Any]:
    mt = store.meeting(mid)
    if not mt:
        raise HTTPException(404)
    entries = store.entries(mid, include_history=True)
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        by_kind.setdefault(e["kind"], []).append(e)
    calls = store.q("SELECT SUM(tokens_in) AS tin, SUM(tokens_out) AS tout, SUM(cost_usd) AS cost, COUNT(*) AS n FROM calls WHERE meeting_id=%s", (mid,))[0]
    return {
        "meeting": mt,
        "rounds": ROUNDS,
        "blackboard": by_kind,
        "turns": store.turns(mid),
        "cost": {"tokens": int(calls["tin"] or 0) + int(calls["tout"] or 0), "usd": round(float(calls["cost"] or 0), 4), "calls": int(calls["n"] or 0)},
        "db": store.db.label,
    }


@app.get("/api/meetings/{mid}/messages")
def messages(mid: str, after: int = 0) -> dict[str, Any]:
    rows = store.messages(mid, after)
    return {"messages": rows, "last_id": rows[-1]["id"] if rows else after}


def run() -> None:
    import uvicorn

    uvicorn.run("roundtable.main:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8788")), reload=False)


if __name__ == "__main__":
    run()
