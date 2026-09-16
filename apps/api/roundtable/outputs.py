"""Deliverables, rendered from the blackboard and the transcript. The minutes cannot drift from what happened because they are the transcript."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .protocol import Meeting


def assemble(m: "Meeting") -> dict[str, str]:
    sections = m.entries("section")
    pricing = m.store.get(m.id, "price:summary")["payload"]
    lines = [e["payload"] for e in m.entries("price_line")]
    packages = [e["payload"] for e in m.entries("work_package")]
    risks = [e["payload"] for e in m.entries("risk")]
    questions = [e["payload"] for e in m.entries("question")]
    reqs = [e["payload"] for e in m.entries("requirement")]

    # ---- proposal
    p = [f"# Proposal: {m.rfp['title']}", f"*Prepared for {m.rfp['client']} by Meridian Systems*", ""]
    for s in sections:
        p.append(f"## {s['payload']['title']}")
        p.append(s["payload"]["body"])
        p.append(f"\n*Sources: {', '.join(s['payload']['citations'])}*\n")
    p.append("## Assumptions")
    for wp in packages:
        for a in wp.get("assumptions") or []:
            p.append(f"- {wp['id']} {wp['name']}: {a}")
    p.append("\n## Questions we would like to confirm")
    for q in questions:
        p.append(f"- {q['text']}")
    proposal = "\n".join(p)

    # ---- pricing sheet
    ps = ["package,role,days,rate,amount,optional"]
    for l in lines:
        ps.append(f"{l['package_id']},{l['role']},{l['days']},{l['rate']},{l['amount']},{'yes' if l['optional'] else 'no'}")
    ps.append(f"SUBTOTAL,,,,{pricing['subtotal']},")
    for d in pricing["deviations"]:
        ps.append(f"DEVIATION {d['package_id']},{d['percent']}%,,,{d['reason']} ({d['comparable_id']}),")
    ps.append(f"TOTAL,,,,{pricing['total']},")
    ps.append(f"MARGIN,,,,{pricing['margin']},floor {pricing['floor_margin']}")
    pricing_sheet = "\n".join(ps)

    # ---- risk register
    rr = ["| # | Kind | Severity | Stance | Clause | Our position | Decision |", "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(risks, 1):
        rr.append(f"| {i} | {r['kind']} | {r['severity']} | {r['stance']} | {r['quote'][:80]}… | {r['position']} | {r.get('decision', '')} |")
    risk_register = "\n".join(rr)

    # ---- client Q&A
    qa = [f"- **{q['text']}** — {q['why']}" for q in questions]
    client_qa = "\n".join(qa) or "(no open questions)"

    # ---- minutes: the transcript
    msgs = m.store.messages(m.id)
    turns = None
    mins = [f"# Minutes · {m.rfp['title']}", f"*{time.strftime('%Y-%m-%d %H:%M')}*", ""]
    current = None
    for x in msgs:
        if x["round"] != current:
            current = x["round"]
            mins.append(f"\n## {current}")
        who = f"**{x['from_agent']} → {x['to_agent']}**" if x["to_agent"] not in ("all", "chair") or x["from_agent"] == "chair" else f"**{x['from_agent']}**"
        mins.append(f"- {who} ({x['kind']}): {x['text']}")
    if turns:
        mins.append("\n## Turns\n" + turns)
    minutes = "\n".join(mins)

    return {"proposal": proposal, "pricing_sheet": pricing_sheet, "risk_register": risk_register, "client_qa": client_qa, "minutes": minutes}
