# Build plan

Five phases. Each ends with something a stranger can verify by running one command. Sequential, evenings and weekends, one person. One GitHub issue per phase carries the checklist.

## Phase 0 · Foundations

**Goal:** a meeting that runs with stub agents, fully recorded.

- [ ] Monorepo: `apps/api` (FastAPI), `apps/worker` (LangGraph), `apps/meeting-room` (Next.js), `packages/core` (entries, messages, protocol), `packages/mcp-knowledge`, `evals/`
- [ ] Blackboard: Postgres schema for versioned, owned, cited entries; optimistic versioning; history view
- [ ] Message bus: typed messages (Pydantic) over a Postgres outbox; transcript table; replay
- [ ] Protocol state machine with rounds, turn budgets, round limits, re-entry tracking; unit-tested with stub agents
- [ ] Model gateway: Anthropic SDK with adaptive thinking, structured outputs, prompt caching on stable prefixes, cost accounting; OpenAI-compatible adapter for vLLM
- [ ] Meeting room shell: transcript stream, blackboard browser, open objections
- [ ] OpenTelemetry to Langfuse; a trace per turn
- [ ] CI: lint, type-check, unit tests, compose smoke test
- [ ] `make meeting` runs the protocol end to end with stub agents on the Harbor Logistics RFP

**Done when:** a fresh clone runs `docker compose up && make meeting` and the meeting room shows ten rounds, every turn traced, with stub content.

## Phase 1 · Brief and research

**Goal:** the RFP becomes a matrix and the team knows the client.

- [ ] RFP ingestion: PDF (text and OCR), DOCX, email; page-level provenance
- [ ] Scoper: requirements matrix with citations and priorities; work packages; assumptions; client questions
- [ ] Researcher: firm knowledge base via MCP (past proposals, case studies, rate card, policy); web search through the model's server-side tool with a domain allow-list; sources on every finding
- [ ] Evals: requirement recall ≥ 0.92 and precision ≥ 0.9 on 5 labelled RFPs; must-have coverage 100%; finding source presence 100%

**Done when:** `make eval-brief` passes and the meeting room shows a cited matrix for the demo RFP.

## Phase 2 · Estimate and price

**Goal:** numbers the firm can defend.

- [ ] Estimator with fan-out sub-estimators, dual estimates above a value threshold, reconciliation entry with variance explanations
- [ ] Pricer with rate card, margin policy and past-deal memory (pgvector over won and lost proposals with outcomes); deviation reasons; below-margin escalation
- [ ] Consistency checks: arithmetic, double counting, package coverage
- [ ] Evals: estimates within tolerance of baselines on 5 RFPs; policy violations 0; arithmetic 100%

**Done when:** `make eval-numbers` passes and every price line in the demo traces to a source.

## Phase 3 · Write, critique, reconcile

**Goal:** the argument.

- [ ] Writer with per-section fan-out, style guide, citation per claim
- [ ] Risk with the legal playbook; register with stance
- [ ] Critic: criteria scoring, objections with evidence, final unsupported-claim pass
- [ ] Objection protocol end to end: defence, revision, arbitration, limits
- [ ] Arbiter with written rulings and escalation
- [ ] Human join-in: answer, override, veto, settle; resumption from the affected round
- [ ] Evals: proposal rubric score against human-written baselines; objection validity and resolution correctness on seeded disputes; Critic catch rate on seeded unsupported claims 100%; protocol conformance on recorded meetings

**Done when:** the Harbor Logistics meeting runs unattended to either finalisation or a well-formed escalation, and `make eval-meeting` passes.

## Phase 4 · Deliverables and hardening

**Goal:** something a sales lead would send.

- [ ] Exports: proposal DOCX and PDF, pricing sheet CSV, risk register, client Q&A, minutes in Markdown
- [ ] Meeting room complete: live transcript, blackboard diff view, objection threads, cost meter, join-in controls
- [ ] Evals as a CI gate with thresholds; scorecards per commit
- [ ] Cost budgets per meeting and per agent; model routing by role; cache hit-rate monitoring
- [ ] vLLM path validated with an open-weight model; accuracy delta documented
- [ ] Quick-quote protocol variant for short requests
- [ ] Demo recording and written walkthrough

**Done when:** a stranger can run the demo meeting from the README and open the resulting proposal.

## Out of scope for v1

- Sending anything to a client automatically; Roundtable produces documents, people send them
- CRM integration beyond reading past deals
- Multi-firm tenancy

## Principles that outrank the plan

1. An objection without evidence is noise and is rejected before it costs a turn.
2. A number without a source does not reach the final proposal.
3. When the evidence is even, a person decides, and the minutes say so.
