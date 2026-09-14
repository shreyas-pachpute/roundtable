"""Structured outputs for every seat at the table. Validated by the model API and again on the blackboard."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Requirement(BaseModel):
    id: str = Field(description="The RFP's own id, e.g. R3")
    text: str
    priority: Literal["must", "should", "may"]
    page: int
    quote: str = Field(description="Verbatim text from the RFP page that contains the requirement")


class ClientQuestion(BaseModel):
    text: str
    why: str


class RequirementsMatrix(BaseModel):
    requirements: list[Requirement]
    questions: list[ClientQuestion] = Field(default_factory=list, description="Ambiguities to put to the client")
    timeline: str
    evaluation_criteria_note: str


class Finding(BaseModel):
    text: str
    source_id: str = Field(description="Knowledge chunk id or 'rfp:pN'")
    confidence: float = Field(ge=0, le=1)


class Findings(BaseModel):
    findings: list[Finding]


class WorkPackage(BaseModel):
    id: str = Field(description="WP1, WP2, ...")
    name: str
    requirement_ids: list[str]
    assumptions: list[str]
    past_package_key: str = Field(description="Key from past-packages data this resembles: erp, carrier_per, migration, portal, monitoring, training_per8, hypercare, returns, analytics")
    multiplier: float = Field(default=1.0, description="e.g. number of carriers, or groups of 8 trainees")
    optional: bool = False


class WorkPackages(BaseModel):
    packages: list[WorkPackage]


class RoleDays(BaseModel):
    role: str
    days: float


class PackageEstimate(BaseModel):
    package_id: str
    days_by_role: list[RoleDays]
    assumptions: list[str]
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(description="One sentence citing the past package it is based on")


class ReconciliationFlag(BaseModel):
    package_id: str
    note: str


class Reconciliation(BaseModel):
    total_days: float
    flags: list[ReconciliationFlag]
    note: str


class PriceLine(BaseModel):
    package_id: str
    role: str
    days: float
    rate: float
    amount: float


class Deviation(BaseModel):
    package_id: str
    percent: float = Field(description="Negative for a discount")
    reason: str
    comparable_id: str = Field(description="Past proposal id that justifies it")


class PricingDecision(BaseModel):
    """The model decides deviations and explains; the lines, totals and margin are computed in code from the rate card."""

    deviations: list[Deviation]
    summary: str = Field(description="Two sentences a sales lead can read: what the price is built from and why any deviation")


class Risk(BaseModel):
    kind: Literal["contract", "delivery"]
    quote: str = Field(description="Verbatim clause or requirement text")
    page: int
    severity: Literal["low", "medium", "high"]
    stance: Literal["accept", "negotiate", "decline"]
    playbook_id: str | None = None
    position: str


class RiskRegister(BaseModel):
    risks: list[Risk]


class Section(BaseModel):
    title: str
    body: str
    citations: list[str] = Field(description="Ids of case studies, findings, requirements or packages every claim relies on")


class CriterionScore(BaseModel):
    criterion: str
    score: int = Field(ge=0, le=10)
    reason: str


class Objection(BaseModel):
    target_kind: Literal["section", "pricing", "estimate", "risk"]
    target_id: str
    claim: str
    evidence_ids: list[str]
    proposed_resolution: str


class Critique(BaseModel):
    scores: list[CriterionScore]
    objections: list[Objection]
    unsupported_claims: list[str] = Field(default_factory=list)
    summary: str


class Defence(BaseModel):
    accept: bool = Field(description="True if the owner accepts the objection and revises")
    response: str
    evidence_ids: list[str]
    revised_text: str | None = Field(default=None, description="The revised section body or pricing note when accepting")


class Ruling(BaseModel):
    decision: Literal["uphold_objection", "overrule_objection", "escalate"]
    reason: str
