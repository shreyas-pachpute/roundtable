"""Deterministic stand-ins for the model, derived from the same evidence the model would see. Labelled 'mock' in the UI."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from . import schemas as S

SECTION_TEXT = {
    "Understanding and approach": (
        "Harbor Logistics is replacing its legacy warehouse management system with Cortex WMS in Q1 2027 and needs the new system connected to NetSuite, "
        "three carriers and the customer portal before 31 March 2027 (R1, R2, R4). We have done this shape of work before: at Brightwater Distribution we "
        "integrated Cortex WMS with NetSuite and two carriers with synchronisation under three minutes (cs-brightwater). Our approach is integration-first: "
        "the ERP and carrier links go live behind feature flags on the existing system, so migration (R3) and cut-over carry no big-bang risk."
    ),
    "Response to requirements": (
        "R1. NetSuite integration for purchase orders, sales orders, inventory and goods receipts with synchronisation under 5 minutes; our reference "
        "implementation ran under 3 minutes (cs-brightwater). WP1.\n"
        "R2. Coastal Express, Meridian Freight and Northgate Parcel for labels, tracking and proof of delivery (WP2).\n"
        "R3. Migration of five years of inventory and order data with reconciliation reports; our toolkit reconciled to zero unreconciled SKUs at Brightwater (cs-brightwater). WP3.\n"
        "R4. Customer portal integration with real-time order status and tracking, as delivered for Cedar Foods (cs-cedar). WP4.\n"
        "R5. Monitoring dashboard with alerting (WP5). R6. Training for 16 people (WP6). R7. 90 days of hypercare (WP7).\n"
        "R8 and R9 are offered as priced options (WP8, WP9).\n"
        "R11. All user-facing components use your existing SSO (WP4)."
    ),
    "Team and experience": (
        "The team is the one that delivered Brightwater Distribution's WMS integration in 22 weeks (cs-brightwater): an engagement lead, a solution "
        "architect, three integration engineers, a data engineer and a QA engineer, plus the portal specialist from Cedar Foods (cs-cedar)."
    ),
    "Delivery plan and timeline": (
        "Weeks 1-3 discovery and environment access; weeks 4-14 ERP and carrier integration (WP1, WP2) in parallel with migration tooling (WP3); "
        "weeks 10-16 portal (WP4) and monitoring (WP5); week 17 migration dry run; weeks 18-20 training and rehearsal; go-live in week 21, two weeks before "
        "31 March 2027 with data migration complete two weeks before go-live as required."
    ),
    "Commercials": (
        "A fixed price for WP1 to WP7, built from our rate card and the package estimates, with a 10 percent reduction on data migration (WP3) because "
        "our migration toolkit is reused, as on P-2025-07 (pp-2025-07). Options WP8 and WP9 are priced separately. Change requests at a blended "
        "time-and-materials rate of USD 1,150 per day (rate-card)."
    ),
    "Risks and assumptions": (
        "Carrier API access and documentation are assumed available in week 1 (R2, WP2). We propose the playbook positions on liability, payment terms, "
        "termination notice, intellectual property in pre-existing tools and service credits (playbook). Assumptions per package are listed in the appendix."
    ),
}


def respond(role: str, schema: type[BaseModel], ctx: dict[str, Any]) -> Any:
    if schema is S.RequirementsMatrix:
        reqs = []
        for page in ctx["rfp"]["pages"]:
            for m in re.finditer(r"^(R\d+)\. (.+)$", page["text"], re.M):
                text = m.group(2)
                prio = "must" if " must " in text else "should" if " should " in text else "may"
                reqs.append(S.Requirement(id=m.group(1), text=text, priority=prio, page=page["page"], quote=m.group(0)))
        return S.RequirementsMatrix(
            requirements=reqs,
            questions=[
                S.ClientQuestion(text="Do the three carrier APIs include a returns flow, or is returns handling confined to the optional R8 workflow?", why="R2 and R8 overlap; it changes the carrier integration estimate."),
                S.ClientQuestion(text="Does the 5-minute synchronisation target in R1 apply to goods receipts as well as orders?", why="Goods receipts are batch in most NetSuite setups."),
            ],
            timeline="Live before 31 March 2027; migration complete two weeks before go-live.",
            evaluation_criteria_note="Approach 30, team 20, price 30, risk 20.",
        )

    if schema is S.Findings:
        return S.Findings(findings=[
            S.Finding(text="Brightwater Distribution (2025) is a direct comparable: Cortex WMS to NetSuite with two carriers and a 4-year migration, delivered in 22 weeks.", source_id="cs-brightwater", confidence=0.95),
            S.Finding(text="P-2025-07 (Brightwater) was won at USD 412,000 with a 12% discount on data migration justified by the migration toolkit.", source_id="pp-2025-07", confidence=0.95),
            S.Finding(text="P-2025-11 (Kestrel Retail, four carriers and portal) was lost on price at USD 540,000; the winner was roughly 15% lower.", source_id="pp-2025-11", confidence=0.9),
            S.Finding(text="Price and approach carry 60% of the evaluation weight between them.", source_id="rfp:p3", confidence=1.0),
            S.Finding(text="The draft contract has an unlimited liability clause and 90-day payment terms.", source_id="rfp:p4", confidence=1.0),
        ])

    if schema is S.WorkPackages:
        P = S.WorkPackage
        return S.WorkPackages(packages=[
            P(id="WP1", name="NetSuite integration", requirement_ids=["R1"], assumptions=["NetSuite sandbox available in week 1"], past_package_key="erp"),
            P(id="WP2", name="Carrier integrations", requirement_ids=["R2"], assumptions=["Three carrier APIs with documentation"], past_package_key="carrier_per", multiplier=3),
            P(id="WP3", name="Data migration", requirement_ids=["R3"], assumptions=["Legacy data exportable as CSV"], past_package_key="migration"),
            P(id="WP4", name="Customer portal integration", requirement_ids=["R4", "R11"], assumptions=["Portal team available for SSO wiring"], past_package_key="portal"),
            P(id="WP5", name="Monitoring dashboard", requirement_ids=["R5"], assumptions=[], past_package_key="monitoring"),
            P(id="WP6", name="Training", requirement_ids=["R6"], assumptions=["16 trainees in two groups"], past_package_key="training_per8", multiplier=2),
            P(id="WP7", name="Hypercare", requirement_ids=["R7"], assumptions=["Business-hours support"], past_package_key="hypercare"),
            P(id="WP8", name="Returns workflow (option)", requirement_ids=["R8"], assumptions=[], past_package_key="returns", optional=True),
            P(id="WP9", name="Analytics layer (option)", requirement_ids=["R9"], assumptions=[], past_package_key="analytics", optional=True),
        ])

    if schema is S.PackageEstimate:
        wp = ctx["package"]
        base = ctx["past"][wp["past_package_key"]]
        mult = float(wp.get("multiplier") or 1)
        variant = ctx.get("variant", 1)
        factor = mult * (1.4 if variant == 2 and wp["id"] == "WP2" else 1.0)
        assumptions = list(wp.get("assumptions") or [])
        if variant == 2 and wp["id"] == "WP2":
            assumptions.append("Assumed a fourth carrier endpoint for returns, as R8 implies")
        return S.PackageEstimate(package_id=wp["id"], days_by_role=[S.RoleDays(role=r, days=round(d * factor, 1)) for r, d in base.items()], assumptions=assumptions, confidence=0.8 if variant == 1 else 0.6, rationale=f"Based on past package '{wp['past_package_key']}' × {factor:g}.")

    if schema is S.Reconciliation:
        flags = [S.ReconciliationFlag(package_id=f["package_id"], note=f["note"]) for f in ctx.get("flags", [])]
        return S.Reconciliation(total_days=ctx["total_days"], flags=flags, note="Totals exclude the optional packages WP8 and WP9. Engagement lead time is added at 10% of engineering days." + (" One package disagrees by more than 25% and is flagged." if flags else ""))

    if schema is S.PricingDecision:
        return S.PricingDecision(
            deviations=[S.Deviation(package_id="WP3", percent=-10.0, reason="Migration toolkit reused; the same discount won P-2025-07 and is within the 10% limit.", comparable_id="pp-2025-07")],
            summary="The price is rate card times the reconciled estimates for WP1 to WP7, with a 10 percent reduction on data migration because our toolkit is reused, as on the won Brightwater proposal. Margin stays above the 32 percent floor.",
        )

    if schema is S.RiskRegister:
        page4 = next(p for p in ctx["rfp"]["pages"] if p["page"] == 4)
        risks = []
        for item in ctx["playbook"]:
            line = next((ln for ln in page4["text"].split("\n") if item["trigger"] in ln), None)
            if line:
                sev = "high" if item["stance"] == "decline" else "medium"
                risks.append(S.Risk(kind="contract", quote=line.strip(), page=4, severity=sev, stance=item["stance"], playbook_id=item["id"], position=item["position"]))
        risks.append(S.Risk(kind="delivery", quote="R2. The vendor must integrate Cortex WMS with our three carrier APIs (Coastal Express, Meridian Freight, Northgate Parcel) for label generation, tracking and proof of delivery.", page=1, severity="medium", stance="accept", playbook_id=None, position="Carrier API access and sandbox credentials are needed in week 1; each week of delay moves go-live by a week (WP2)."))
        return S.RiskRegister(risks=risks)

    if schema is S.Section:
        title = ctx["title"]
        body = SECTION_TEXT[title]
        cites = sorted(set(re.findall(r"\b(cs-[a-z]+|pp-\d{4}-\d{2}|R\d+|WP\d+|rate-card|playbook)\b", body)))
        return S.Section(title=title, body=body, citations=cites)

    if schema is S.Critique:
        sections = ctx["sections"]
        resp = next((s for s in sections if s["payload"]["title"] == "Response to requirements"), None)
        objections = []
        if resp and "R10" not in resp["payload"]["body"]:
            objections.append(S.Objection(target_kind="section", target_id=resp["id"], claim="R10 (data residency) and R12 (safety certification for on-site staff) are must-have constraints and the response does not address them; the committee scores compliance line by line.", evidence_ids=["R10", "R12", "rfp:p3"], proposed_resolution="Add explicit responses to R10 and R12 to the requirements section."))
        objections.append(S.Objection(target_kind="pricing", target_id="price:summary", claim="The total sits close to the level at which P-2025-11 was lost on price to a bid roughly 15% lower; price carries 30% of the score.", evidence_ids=["pp-2025-11", "rfp:p3"], proposed_resolution="Consider a further 5% on WP2 or present a phased option."))
        return S.Critique(
            scores=[S.CriterionScore(criterion="approach", score=8, reason="Integration-first plan and a direct comparable."), S.CriterionScore(criterion="team", score=8, reason="Same team as the comparable delivery."), S.CriterionScore(criterion="price", score=6, reason="Defensible but exposed against P-2025-11."), S.CriterionScore(criterion="risk", score=7, reason="Playbook positions stated; carrier access risk named.")],
            objections=objections,
            unsupported_claims=[],
            summary="Strong on approach and team; the price exposure and two unanswered constraints are the gaps.",
        )

    if schema is S.Defence:
        obj = ctx["objection"]
        if obj["target_kind"] == "section":
            body = ctx["target"]["payload"]["body"] + "\nR10. All processing runs in your region; no data leaves it (WP1, WP3).\nR12. All on-site staff hold current warehouse safety certification; certificates are supplied before the first site visit (WP6, WP7)."
            return S.Defence(accept=True, response="Agreed. R10 and R12 were missing; added explicit responses.", evidence_ids=["R10", "R12"], revised_text=body)
        return S.Defence(accept=False, response="P-2025-11 had four carriers and a larger portal scope at a 41% margin; this bid is already priced at rate card with a discount on migration that won P-2025-07, and a further 5% would take WP2 below the margin floor.", evidence_ids=["pp-2025-07", "margin-policy", "pp-2025-11"])

    if schema is S.Ruling:
        return S.Ruling(decision="overrule_objection", reason="The comparable that was lost had a larger scope and higher margin; the current price already carries a won-deal discount and sits above the floor. No further discount without the managing partner.")

    raise ValueError(f"mock has no handler for {schema.__name__}")
