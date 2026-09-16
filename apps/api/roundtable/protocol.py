"""The Chair as a LangGraph state machine with a checkpointer.

Each round is a node. The graph pauses after every node (so a serverless request runs exactly one round),
persists its state in Postgres, and pauses on `interrupt()` when the human seat is needed. The meeting
resumes with the next request, on any server instance. Model settings travel in a context variable set
per request; they are never written to the checkpoint.
"""

from __future__ import annotations

import asyncio
import contextvars
import re
import uuid
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from . import schemas as S
from .gateway import Gateway, Settings
from .prompts import ROLES, render
from .store import Store

ROUNDS = ["brief", "research", "scope", "estimate", "price", "draft", "critique", "reconcile", "human_seat", "finalise"]
SECTIONS = ["Understanding and approach", "Response to requirements", "Team and experience", "Delivery plan and timeline", "Commercials", "Risks and assumptions"]
OWNER_OF = {"section": "writer", "pricing": "pricer", "estimate": "estimator", "risk": "risk"}
LIMITS = {"objections_per_meeting": 5, "arbitrations": 3}

current_settings: contextvars.ContextVar[Settings] = contextvars.ContextVar("current_settings")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


class MeetingState(TypedDict, total=False):
    meeting_id: str
    answers: dict[str, dict[str, str]]


class Meeting:
    """One meeting's runtime for one request: the store, the gateway, the RFP and the knowledge base."""

    def __init__(self, mid: str, store: Store, gw: Gateway, rfp: dict[str, Any], kb: list[dict[str, Any]]):
        self.id = mid
        self.store = store
        self.gw = gw
        self.rfp = rfp
        self.kb = kb
        self.kb_by_id = {c["id"]: c for c in kb}
        self.round = (store.meeting(mid) or {}).get("round") or "brief"

    # ------------------------------------------------------------ bus helpers
    def say(self, kind: str, frm: str, to: str, text: str, refs: list[str] | None = None) -> None:
        self.store.say(self.id, self.round, kind, frm, to, text, refs)

    async def turn(self, agent: str, task: str, schema: type[S.BaseModel], evidence: dict[str, Any], role: str | None = None, ctx: dict[str, Any] | None = None):
        tid = f"turn-{uuid.uuid4().hex[:8]}"
        self.store.start_turn(tid, self.id, self.round, agent)
        gw = Gateway(self.store, self.gw.settings)  # per-turn gateway so parallel turns record against their own turn id
        gw.current = {"meeting": self.id, "turn": tid}
        self.say("assign", "chair", agent, task)
        try:
            out = await gw.complete(role=role or agent, schema=schema, system=ROLES[role or agent], user=render(evidence, task), case_id=self.id, context=ctx or {})
            self.store.end_turn(tid, "done")
            return out
        except Exception as e:  # noqa: BLE001
            self.store.end_turn(tid, "failed")
            self.say("error", agent, "chair", f"{type(e).__name__}: {str(e)[:200]}")
            raise

    def put(self, entry_id: str, kind: str, owner: str, payload: dict[str, Any], evidence: list[dict[str, Any]] | None = None, status: str = "open") -> str:
        return self.store.put(self.id, entry_id, kind, owner, payload, evidence, status)

    def entries(self, kind: str) -> list[dict[str, Any]]:
        return self.store.entries(self.id, kind)

    def set_round(self, r: str) -> None:
        self.round = r
        self.store.set_meeting(self.id, round=r)
        self.say("round", "chair", "all", f"Round: {r.replace('_', ' ')}")

    def rfp_text(self) -> str:
        return "\n\n".join(f"[page {p['page']}]\n{p['text']}" for p in self.rfp["pages"])

    def quote_ok(self, quote: str, page: int) -> bool:
        pg = next((p for p in self.rfp["pages"] if p["page"] == page), None)
        return bool(pg) and _norm(quote) in _norm(pg["text"])

    def known_ids(self) -> set[str]:
        ids = set(self.kb_by_id)
        ids |= {f"rfp:p{p['page']}" for p in self.rfp["pages"]}
        ids |= {e["id"] for e in self.store.entries(self.id)}
        ids |= {e["payload"].get("id") for e in self.entries("requirement")}
        ids |= {e["payload"].get("id") for e in self.entries("work_package")}
        ids |= {i["id"] for i in self.kb_by_id.get("playbook", {}).get("data", [])}
        return {i for i in ids if i}

    def ask_later(self, kind: str, ref: str, text: str, options: list[str]) -> None:
        """Queue a decision for the human seat; the human_seat node raises them all at once."""
        n = len(self.entries("decision")) + 1
        self.put(f"decision:{n}", "decision", "chair", {"kind": kind, "ref": ref, "text": text, "options": options}, [{"type": "entry", "ref": ref}], status="open")


# ------------------------------------------------------------------ rounds

async def r_brief(m: Meeting) -> None:
    m.set_round("brief")
    out = await m.turn("scoper", "Build the requirements matrix from the RFP and list questions for the client.", S.RequirementsMatrix, {"rfp": m.rfp}, ctx={"rfp": m.rfp})
    bad = [r.id for r in out.requirements if not m.quote_ok(r.quote, r.page)]
    for r in out.requirements:
        m.put(f"req:{r.id}", "requirement", "scoper", r.model_dump(), [{"type": "rfp_page", "ref": r.page, "quote": r.quote}], status="open" if r.id not in bad else "unverified")
    for i, q in enumerate(out.questions, 1):
        m.put(f"q:{i}", "question", "scoper", q.model_dump(), [], status="open")
    musts = sum(1 for r in out.requirements if r.priority == "must")
    m.say("deliver", "scoper", "chair", f"{len(out.requirements)} requirements ({musts} must-have), {len(out.questions)} questions for the client" + (f"; {len(bad)} quotes could not be verified" if bad else "; every quote verified on its page"), [f"req:{r.id}" for r in out.requirements])


async def r_research(m: Meeting) -> None:
    m.set_round("research")
    kb = [c for c in m.kb if c["kind"] in ("case_study", "past_proposal", "policy")]
    out = await m.turn("researcher", "Produce findings the team should know, each with its source id.", S.Findings, {"knowledge_base": kb, "rfp_summary": m.rfp_text()[:3000], "criteria": m.rfp["evaluation_criteria"]}, ctx={})
    ok = m.known_ids()
    kept = 0
    for f in out.findings:
        if f.source_id not in ok:
            m.say("reject", "chair", "researcher", f"Finding dropped: source '{f.source_id}' is not in the evidence")
            continue
        kept += 1
        m.put(f"finding:{kept}", "finding", "researcher", f.model_dump(), [{"type": "source", "ref": f.source_id}])
    m.say("deliver", "researcher", "chair", f"{kept} findings, every one with a source", [f"finding:{i}" for i in range(1, kept + 1)])


async def r_scope(m: Meeting) -> None:
    m.set_round("scope")
    reqs = [e["payload"] for e in m.entries("requirement")]
    past = m.kb_by_id["past-packages"]["data"]
    out = await m.turn("scoper", "Group the requirements into work packages with assumptions; every must-have must be covered.", S.WorkPackages, {"requirements": reqs, "past_package_keys": list(past.keys())}, ctx={})
    covered = {rid for p in out.packages for rid in p.requirement_ids}
    missing = [r["id"] for r in reqs if r["priority"] == "must" and r["id"] not in covered]
    for p in out.packages:
        m.put(f"wp:{p.id}", "work_package", "scoper", p.model_dump(), [{"type": "entry", "ref": f"req:{rid}"} for rid in p.requirement_ids])
    if missing:
        m.say("warning", "chair", "scoper", f"Must-have requirements not covered by any package: {missing}. They will be answered as constraints in the draft.")
    m.say("deliver", "scoper", "chair", f"{len(out.packages)} work packages ({sum(1 for p in out.packages if p.optional)} optional)", [f"wp:{p.id}" for p in out.packages])


async def r_estimate(m: Meeting) -> None:
    m.set_round("estimate")
    packages = [e["payload"] for e in m.entries("work_package")]
    past = m.kb_by_id["past-packages"]["data"]

    async def sub(wp: dict[str, Any], variant: int) -> S.PackageEstimate:
        base = past.get(wp["past_package_key"], {})
        nudge = " Independently, assume the broader reading of the requirement." if variant == 2 else ""
        return await m.turn("estimator", f"Estimate {wp['id']} {wp['name']} (variant {variant}).{nudge}", S.PackageEstimate, {"package": wp, "past_package": {wp["past_package_key"]: base}, "requirements": [e["payload"] for e in m.entries("requirement") if e["payload"]["id"] in wp["requirement_ids"]]}, role="sub_estimator", ctx={"package": wp, "past": past, "variant": variant})

    def base_days(wp: dict[str, Any]) -> float:
        return sum(past.get(wp["past_package_key"], {}).values()) * float(wp.get("multiplier") or 1)

    m.say("fanout", "estimator", "sub-estimators", f"Spawning one sub-estimator per package ({len(packages)}), two for packages over 30 days")
    jobs = []
    for wp in packages:
        jobs.append(sub(wp, 1))
        if base_days(wp) >= 30:
            jobs.append(sub(wp, 2))
    results = await asyncio.gather(*jobs)
    by_pkg: dict[str, list[S.PackageEstimate]] = {}
    for r in results:
        by_pkg.setdefault(r.package_id, []).append(r)

    flags = []
    total = 0.0
    for wp in packages:
        ests = by_pkg.get(wp["id"], [])
        if not ests:
            continue
        days = [sum(rd.days for rd in e.days_by_role) for e in ests]
        chosen = ests[0]
        if len(ests) == 2 and max(days) > 0 and abs(days[0] - days[1]) / max(days) > 0.25:
            note = ests[1].assumptions[-1] if ests[1].assumptions else "different assumptions"
            flags.append({"package_id": wp["id"], "note": f"Two estimates disagree by {abs(days[0]-days[1])/max(days):.0%} ({days[0]:g} vs {days[1]:g} days): {note}. Using the lower estimate and raising a client question."})
            m.put(f"q:{len(m.entries('question'))+1}", "question", "estimator", {"text": f"Please confirm the assumption behind {wp['id']} ({wp['name']}): {note}.", "why": "Two independent estimates disagree by more than 25%."}, [], status="open")
        payload = chosen.model_dump()
        payload["alternatives"] = [e.model_dump() for e in ests[1:]]
        m.put(f"est:{wp['id']}", "estimate", "estimator", payload, [{"type": "source", "ref": "past-packages"}, {"type": "entry", "ref": f"wp:{wp['id']}"}])
        if not wp.get("optional"):
            total += days[0]
    lead = round(total * 0.10, 1)
    rec = await m.turn("estimator", "Reconcile the sub-estimates: totals, flags, one-sentence notes.", S.Reconciliation, {"estimates": [e["payload"] for e in m.entries("estimate")], "flags": flags, "total_days": total + lead}, ctx={"flags": flags, "total_days": total + lead})
    m.put("est:reconciliation", "estimate", "estimator", {**rec.model_dump(), "engineering_days": total, "lead_days": lead}, [{"type": "entry", "ref": f"est:{wp['id']}"} for wp in packages])
    m.say("deliver", "estimator", "chair", f"{len(packages)} packages estimated, {total + lead:g} days including engagement lead; {len(flags)} flagged", ["est:reconciliation"])


async def r_price(m: Meeting) -> None:
    rates = m.kb_by_id["rate-card"]["data"]
    policy = m.kb_by_id["margin-policy"]["data"]
    packages = {e["payload"]["id"]: e["payload"] for e in m.entries("work_package")}
    ests = {e["payload"]["package_id"]: e["payload"] for e in m.entries("estimate") if e["id"] != "est:reconciliation"}
    rec = m.store.get(m.id, "est:reconciliation")["payload"]
    lines = []
    for pid, est in ests.items():
        for rd in est["days_by_role"]:
            rate = rates.get(rd["role"], rates["blended_tm"])
            lines.append({"package_id": pid, "role": rd["role"], "days": rd["days"], "rate": rate, "amount": round(rd["days"] * rate, 2), "optional": bool(packages[pid].get("optional"))})
    lines.append({"package_id": "LEAD", "role": "Engagement lead", "days": rec["lead_days"], "rate": rates["Engagement lead"], "amount": round(rec["lead_days"] * rates["Engagement lead"], 2), "optional": False})
    subtotal = round(sum(l["amount"] for l in lines if not l["optional"]), 2)
    past = [c for c in m.kb if c["kind"] == "past_proposal"]
    out = await m.turn("pricer", "Decide any deviations from rate card (each must cite a WON comparable and respect the margin policy) and explain the price.", S.PricingDecision, {"lines": lines, "subtotal": subtotal, "margin_policy": policy, "past_proposals": past, "findings": [e["payload"] for e in m.entries("finding")]}, ctx={})
    devs = []
    for d in out.deviations:
        comp = m.kb_by_id.get(d.comparable_id, {})
        if comp.get("kind") != "past_proposal" or comp.get("data", {}).get("outcome") != "won":
            m.say("reject", "chair", "pricer", f"Deviation on {d.package_id} dropped: comparable '{d.comparable_id}' is not a won proposal")
            continue
        if abs(d.percent) / 100 > policy["max_discount_without_approval"] + 1e-9:
            m.say("reject", "chair", "pricer", f"Deviation on {d.package_id} dropped: {d.percent:+.0f}% exceeds the {policy['max_discount_without_approval']:.0%} limit")
            continue
        devs.append(d.model_dump())
    total = subtotal
    for d in devs:
        pkg_amount = sum(l["amount"] for l in lines if l["package_id"] == d["package_id"])
        total += pkg_amount * d["percent"] / 100
    total = round(total, 2)
    cost = subtotal * policy["cost_ratio"]
    margin = round(1 - cost / total, 3) if total else 0
    summary = {"subtotal": subtotal, "total": total, "margin": margin, "floor_margin": policy["floor_margin"], "deviations": devs, "summary": out.summary, "options_total": round(sum(l["amount"] for l in lines if l["optional"]), 2)}
    for l in lines:
        m.put(f"price:{l['package_id']}:{l['role']}", "price_line", "pricer", l, [{"type": "source", "ref": "rate-card"}, {"type": "entry", "ref": f"est:{l['package_id']}"}])
    m.put("price:summary", "pricing", "pricer", summary, [{"type": "source", "ref": "rate-card"}, {"type": "source", "ref": "margin-policy"}, *[{"type": "source", "ref": d["comparable_id"]} for d in devs]])
    if margin < policy["floor_margin"]:
        m.say("warning", "chair", "you", f"Margin {margin:.0%} is below the {policy['floor_margin']:.0%} floor; this needs the managing partner")
    m.say("deliver", "pricer", "chair", f"Fixed price USD {total:,.0f} (subtotal {subtotal:,.0f}, {len(devs)} deviation{'s' if len(devs)!=1 else ''}), margin {margin:.0%}; options USD {summary['options_total']:,.0f}", ["price:summary"])


async def r_risk(m: Meeting) -> None:
    playbook = m.kb_by_id["playbook"]["data"]
    out = await m.turn("risk", "Build the risk register from the contract terms and constraints against the playbook, plus delivery risks.", S.RiskRegister, {"rfp": m.rfp, "playbook": m.kb_by_id["playbook"], "packages": [e["payload"] for e in m.entries("work_package")]}, ctx={"rfp": m.rfp, "playbook": playbook})
    kept = 0
    for r in out.risks:
        if not m.quote_ok(r.quote, r.page):
            m.say("reject", "chair", "risk", f"Risk dropped: quote not found verbatim on page {r.page}")
            continue
        kept += 1
        m.put(f"risk:{kept}", "risk", "risk", r.model_dump(), [{"type": "rfp_page", "ref": r.page, "quote": r.quote}, *([{"type": "source", "ref": r.playbook_id}] if r.playbook_id else [])])
    declines = [e for e in m.entries("risk") if e["payload"]["stance"] == "decline"]
    m.say("deliver", "risk", "chair", f"{kept} risks; {len(declines)} must-negotiate clause{'s' if len(declines)!=1 else ''} flagged for you", [e["id"] for e in m.entries("risk")])


async def r_price_and_risk(m: Meeting) -> None:
    m.set_round("price")
    m.say("parallel", "chair", "pricer, risk", "Price and Risk run in parallel")
    await asyncio.gather(r_price(m), r_risk(m))


async def r_draft(m: Meeting) -> None:
    m.set_round("draft")
    evidence = {
        "requirements": [e["payload"] for e in m.entries("requirement")],
        "packages": [e["payload"] for e in m.entries("work_package")],
        "findings": [e["payload"] for e in m.entries("finding")],
        "pricing": m.store.get(m.id, "price:summary")["payload"],
        "risks": [e["payload"] for e in m.entries("risk")],
        "case_studies": [c for c in m.kb if c["kind"] == "case_study"],
        "style_guide": m.kb_by_id["style-guide"]["text"],
        "rate_card": m.kb_by_id["rate-card"]["text"],
    }
    m.say("fanout", "writer", "section writers", f"Drafting {len(SECTIONS)} sections in parallel")

    async def one(i: int, title: str) -> tuple[int, S.Section]:
        return i, await m.turn("writer", f"Write the section '{title}'.", S.Section, {**evidence, "section": title}, ctx={"title": title})

    results = await asyncio.gather(*(one(i, t) for i, t in enumerate(SECTIONS, 1)))
    ok = m.known_ids() | {"rate-card", "playbook", "style-guide"}
    for i, sec in results:
        dangling = [c for c in sec.citations if c not in ok]
        m.put(f"sec:{i}", "section", "writer", {**sec.model_dump(), "dangling": dangling}, [{"type": "entry", "ref": c} for c in sec.citations if c in ok])
    m.say("deliver", "writer", "chair", f"{len(results)} sections drafted, {sum(len(s.citations) for _, s in results)} citations", [f"sec:{i}" for i, _ in results])


async def r_critique(m: Meeting) -> None:
    m.set_round("critique")
    sections = m.entries("section")
    out = await m.turn("critic", "Score the draft against the evaluation criteria and raise objections with evidence.", S.Critique, {"criteria": m.rfp["evaluation_criteria"], "sections": [{"id": s["id"], **s["payload"]} for s in sections], "pricing": m.store.get(m.id, "price:summary")["payload"], "requirements": [e["payload"] for e in m.entries("requirement")], "findings": [e["payload"] for e in m.entries("finding")], "past_proposals": [c for c in m.kb if c["kind"] == "past_proposal"]}, ctx={"sections": sections})
    for sc in out.scores:
        m.put(f"score:{sc.criterion}", "score", "critic", sc.model_dump())
    ok = m.known_ids()
    raised = 0
    for i, o in enumerate(out.objections, 1):
        if int((m.store.meeting(m.id) or {}).get("objections_raised") or 0) >= LIMITS["objections_per_meeting"]:
            m.say("limit", "chair", "critic", "Objection limit for this meeting reached")
            break
        missing = [e for e in o.evidence_ids if e not in ok]
        if missing or not o.evidence_ids:
            m.say("reject", "chair", "critic", f"Objection on {o.target_id} rejected before it costs a turn: evidence {missing or 'missing'} is not on the blackboard")
            continue
        m.put(f"obj:{i}", "objection", "critic", o.model_dump(), [{"type": "entry", "ref": e} for e in o.evidence_ids], status="open")
        m.store.bump(m.id, "objections_raised")
        raised += 1
        m.say("objection", "critic", OWNER_OF[o.target_kind], f"On {o.target_id}: {o.claim}", [f"obj:{i}", o.target_id])
    weights = {c["id"]: c["weight"] for c in m.rfp["evaluation_criteria"]}
    weighted = sum(sc.score * weights.get(sc.criterion, 0) for sc in out.scores) / 10
    m.put("score:weighted", "score", "critic", {"criterion": "weighted", "score": round(weighted), "reason": out.summary})
    m.say("deliver", "critic", "chair", f"Weighted score {weighted:.0f}/100; {raised} objection{'s' if raised!=1 else ''} raised, {len(out.unsupported_claims)} unsupported claims", ["score:weighted"])


async def r_reconcile(m: Meeting) -> None:
    m.set_round("reconcile")
    for obj in [e for e in m.entries("objection") if e["status"] == "open"]:
        o = obj["payload"]
        owner = OWNER_OF[o["target_kind"]]
        target = m.store.get(m.id, o["target_id"])
        if not target:
            m.store.set_status(m.id, obj["id"], "dropped")
            continue
        d = await m.turn(owner, f"Respond to the objection on {o['target_id']}: accept and revise, or defend with evidence.", S.Defence, {"objection": o, "target": target, "evidence": {k: m.kb_by_id[k] for k in o["evidence_ids"] if k in m.kb_by_id}, "context": [e["payload"] for e in m.entries("finding")]}, role="defence", ctx={"objection": o, "target": target})
        if d.accept:
            payload = dict(target["payload"])
            if o["target_kind"] == "section" and d.revised_text:
                payload["body"] = d.revised_text
            elif d.revised_text:
                payload["note"] = d.revised_text
            m.store.put(m.id, o["target_id"], target["kind"], target["owner"], payload, target["evidence"])
            m.store.set_status(m.id, obj["id"], "accepted")
            m.say("revision", owner, "critic", f"Accepted; {o['target_id']} revised (v{target['version']+1}). {d.response}", [o["target_id"], obj["id"]])
            continue
        m.say("defence", owner, "critic", d.response, d.evidence_ids)
        if int((m.store.meeting(m.id) or {}).get("arbitrations") or 0) >= LIMITS["arbitrations"]:
            m.ask_later("objection", obj["id"], f"Arbitration limit reached. Settle the objection on {o['target_id']}: {o['claim']}", ["uphold objection", "overrule objection"])
            continue
        m.store.bump(m.id, "arbitrations")
        r = await m.turn("arbiter", f"Rule on the objection to {o['target_id']}.", S.Ruling, {"objection": o, "target": target, "defence": d.model_dump(), "margin_policy": m.kb_by_id.get("margin-policy"), "past_proposals": [c for c in m.kb if c["kind"] == "past_proposal"]}, ctx={"objection": o})
        m.say("ruling", "arbiter", "all", f"{r.decision.replace('_', ' ')}: {r.reason}", [obj["id"]])
        if r.decision == "escalate":
            m.ask_later("objection", obj["id"], f"The Arbiter escalated the objection on {o['target_id']}: {o['claim']}", ["uphold objection", "overrule objection"])
        elif r.decision == "uphold_objection":
            await _revise_after_uphold(m, obj, target)
        else:
            m.store.set_status(m.id, obj["id"], "overruled")
    # must-negotiate clauses always go to the human seat before finalising
    for risk in [e for e in m.entries("risk") if e["payload"]["stance"] == "decline" and e["status"] == "open"]:
        p = risk["payload"]
        m.ask_later("risk", risk["id"], f"Clause to decline per playbook {p.get('playbook_id')}: “{p['quote']}”. Propose our position: {p['position']}?", ["propose our position", "accept the client's clause", "leave open for negotiation"])
    pending = [e for e in m.entries("decision") if e["status"] == "open"]
    m.say("deliver", "chair", "you" if pending else "all", f"{len(pending)} decision{'s' if len(pending)!=1 else ''} for your seat" if pending else "Nothing needs your seat; finalising", [e["id"] for e in pending])


async def _revise_after_uphold(m: Meeting, obj: dict[str, Any], target: dict[str, Any]) -> None:
    o = obj["payload"]
    owner = OWNER_OF[o["target_kind"]]
    d = await m.turn(owner, f"The objection on {o['target_id']} was upheld. Revise accordingly.", S.Defence, {"objection": o, "target": target, "instruction": "accept and revise"}, role="defence", ctx={"objection": o, "target": target, "force_accept": True})
    payload = dict(target["payload"])
    if d.revised_text:
        payload["body" if o["target_kind"] == "section" else "note"] = d.revised_text
    m.store.put(m.id, o["target_id"], target["kind"], target["owner"], payload, target["evidence"])
    m.store.set_status(m.id, obj["id"], "upheld")


def human_seat(m: Meeting) -> dict[str, dict[str, str]]:
    """Raise every open decision at once. On resume, `interrupt` returns the answers and the node completes."""
    # a resumed node replays from its start, so only announce the seat the first time through
    already = (m.store.meeting(m.id) or {}).get("status") == "waiting_for_human"
    if not already:
        m.set_round("human_seat")
    else:
        m.round = "human_seat"
    pending = [e for e in m.entries("decision") if e["status"] == "open"]
    if not pending:
        return {}
    payload = [{"id": e["id"], **e["payload"]} for e in pending]
    if not already:
        m.store.set_meeting(m.id, status="waiting_for_human", waiting=payload)
        m.say("escalate", "chair", "you", f"Waiting for your seat: {len(payload)} decision{'s' if len(payload)!=1 else ''}", [e["id"] for e in pending])
    answers = interrupt(payload)
    m.store.set_meeting(m.id, status="running", waiting=None)
    return answers or {}


async def apply_human(m: Meeting, answers: dict[str, dict[str, str]]) -> None:
    for e in [e for e in m.entries("decision") if e["status"] == "open"]:
        a = answers.get(e["id"]) or {}
        decision = a.get("decision") or e["payload"]["options"][0]
        note = a.get("note") or ""
        m.say("human", "you", "chair", decision + (f": {note}" if note else ""), [e["payload"]["ref"]])
        ref = e["payload"]["ref"]
        if e["payload"]["kind"] == "risk":
            risk = m.store.get(m.id, ref)
            if risk:
                m.store.put(m.id, ref, "risk", "human", {**risk["payload"], "decision": decision, "note": note}, risk["evidence"], status="settled")
        else:
            obj = m.store.get(m.id, ref)
            if obj:
                target = m.store.get(m.id, obj["payload"]["target_id"])
                if decision.startswith("uphold") and target:
                    await _revise_after_uphold(m, obj, target)
                else:
                    m.store.set_status(m.id, ref, "overruled")
        m.store.set_status(m.id, e["id"], "settled")


async def r_finalise(m: Meeting) -> None:
    from .outputs import assemble

    m.set_round("finalise")
    outputs = assemble(m)
    for k, v in outputs.items():
        m.put(f"out:{k}", "output", "chair", {"name": k, "text": v})
    m.store.set_meeting(m.id, status="finished", round="finalise")
    m.say("done", "chair", "all", "Proposal, pricing sheet, risk register, client Q&A and minutes are ready", [f"out:{k}" for k in outputs])


# ------------------------------------------------------------------ the graph

class Engine:
    """Compiles the meeting graph once per process with a checkpointer; runs one round per `step`."""

    def __init__(self, store: Store, rfp: dict[str, Any], kb: list[dict[str, Any]]):
        self.store = store
        self.rfp = rfp
        self.kb = kb
        self.saver = self._make_saver()
        self.graph = self._build()

    def _make_saver(self):
        if self.store.db.pg:
            from langgraph.checkpoint.postgres import PostgresSaver

            saver = PostgresSaver(self.store.db.pool)  # type: ignore[arg-type]
            saver.setup()
            return saver
        return MemorySaver()

    def meeting(self, mid: str) -> Meeting:
        settings = current_settings.get(None) or Settings.from_env()
        return Meeting(mid, self.store, Gateway(self.store, settings), self.rfp, self.kb)

    def _build(self):
        async def wrap(fn):
            return fn

        steps = [("brief", r_brief), ("research", r_research), ("scope", r_scope), ("estimate", r_estimate), ("price", r_price_and_risk), ("draft", r_draft), ("critique", r_critique), ("reconcile", r_reconcile)]
        g = StateGraph(MeetingState)

        def make(fn):
            async def node(s: MeetingState) -> MeetingState:
                await fn(self.meeting(s["meeting_id"]))
                return {}

            return node

        for name, fn in steps:
            g.add_node(name, make(fn))

        def n_human(s: MeetingState) -> MeetingState:
            return {"answers": human_seat(self.meeting(s["meeting_id"]))}

        async def n_apply(s: MeetingState) -> MeetingState:
            await apply_human(self.meeting(s["meeting_id"]), s.get("answers") or {})
            return {}

        async def n_final(s: MeetingState) -> MeetingState:
            await r_finalise(self.meeting(s["meeting_id"]))
            return {}

        g.add_node("human_seat", n_human)
        g.add_node("apply_human", n_apply)
        g.add_node("finalise", n_final)
        order = [n for n, _ in steps] + ["human_seat", "apply_human", "finalise"]
        g.add_edge(START, order[0])
        for a, b in zip(order, order[1:]):
            g.add_edge(a, b)
        g.add_edge("finalise", END)
        # pause after every round so one HTTP request runs one round
        return g.compile(checkpointer=self.saver, interrupt_after=order[:-1])

    def config(self, mid: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": mid}}

    async def step(self, mid: str, settings: Settings, resume: dict[str, Any] | None = None, first: bool = False) -> dict[str, Any]:
        token = current_settings.set(settings)
        try:
            cfg = self.config(mid)
            if first:
                await self.graph.ainvoke({"meeting_id": mid}, cfg)
            elif resume is not None:
                await self.graph.ainvoke(Command(resume=resume), cfg)
            else:
                await self.graph.ainvoke(None, cfg)
        except Exception as e:  # noqa: BLE001
            self.store.say(mid, "chair", "error", "chair", "all", f"Round failed: {type(e).__name__}: {str(e)[:300]}")
            self.store.set_meeting(mid, status="failed")
            raise
        finally:
            current_settings.reset(token)
        st = await self.graph.aget_state(cfg)
        waiting = bool(getattr(st, "interrupts", None)) or (self.store.meeting(mid) or {}).get("status") == "waiting_for_human"
        finished = not st.next
        if finished:
            self.store.set_meeting(mid, status="finished")
        return {"next": list(st.next), "waiting": waiting, "finished": finished}
