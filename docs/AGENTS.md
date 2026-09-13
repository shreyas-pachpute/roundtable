# The agents

Nine agents, one supervisor graph, one subgraph each. Every agent has a fixed tool set, a context pack contract, a turn budget and its own evaluation cases. Agents communicate only through typed messages routed by the Chair and through blackboard entries they own. See [`COLLABORATION.md`](COLLABORATION.md) for the protocol.

Model defaults (configurable): Chair, Critic and Arbiter run on Claude Opus 5 with adaptive thinking at high effort, because judgment is their whole job. Researcher, Scoper, Estimator sub-agents and Writer sections run on Claude Sonnet 5 at medium effort. The vLLM path substitutes an open-weight model behind the same gateway; the evals report the accuracy delta.

---

## Chair

**Purpose.** Run the protocol. Decide which round is next, who takes the turn, what budget they get, when a round is done, when to re-enter one, and when the meeting is over.
**Owns.** The agenda, the turn schedule, the meeting status, the minutes.
**Tools.** `read_blackboard`, `schedule_turn`, `close_round`, `escalate_to_human`, `finalise`.
**Rules.** Never writes proposal content. Rejects objections without evidence before they cost a turn. Enforces every limit in the protocol. Ends with a summary that a sales lead can read in two minutes.
**Evals.** Protocol conformance on recorded meetings (no illegal transitions, limits respected); meeting length within budget; escalation precision.

## Researcher

**Purpose.** Everything the team should know about the client, the market and what the firm has done before.
**Owns.** `finding` entries.
**Tools.** `search_knowledge_base` (MCP), web search (server-side tool, domain-restricted), `read_document`.
**Rules.** Every finding has a source. Findings are facts, not recommendations. Marks confidence; low-confidence findings are questions for the client, not assumptions.
**Evals.** Source presence (100%); relevance judged against a labelled set; no findings contradicted by the source.

## Scoper

**Purpose.** Turn the RFP into a requirements matrix and work packages the rest of the team can estimate and answer.
**Owns.** `requirement`, `work_package`, `assumption`, `question` entries.
**Tools.** `read_document`, `search_knowledge_base`.
**Rules.** Every requirement cites a page. Priorities come from the RFP's own language (must, should, may) or are marked inferred. A must-have requirement not covered by any package blocks the Scope round.
**Evals.** Requirement recall and precision against labelled RFPs; coverage (must-haves mapped to packages); assumption plausibility judged.

## Estimator

**Purpose.** Effort, schedule and staffing per work package, reconciled across packages.
**Owns.** `estimate` entries and the reconciliation entry.
**Tools.** `spawn_sub_estimator`, `search_past_estimates`, `read_blackboard`.
**Rules.** Fans out one sub-estimator per package with a narrow pack. Requests two independent sub-estimates for packages above a value threshold and explains disagreement above 25%. Never estimates a package without reading its requirements.
**Sub-estimator.** A short-lived agent with one package, comparable past packages and a small budget; returns a structured estimate with assumptions and a confidence.
**Evals.** Estimate within tolerance of labelled baselines; variance explanation present when required; no package double-counted in reconciliation.

## Pricer

**Purpose.** Turn estimates into a price the firm can defend.
**Owns.** `price_line` entries and the pricing summary.
**Tools.** `read_rate_card`, `read_margin_policy`, `search_past_deals` (pgvector memory of won and lost proposals with outcomes), `read_blackboard`.
**Rules.** Every line traces to rate card × estimate, or to a documented deviation with a reason and a policy check. Discounts cite a comparable past deal. Below-margin pricing is escalated, never silent.
**Evals.** Arithmetic consistency (100%); policy compliance (0 violations); deviation reasons judged.

## Risk

**Purpose.** What could hurt the firm if it wins.
**Owns.** `risk` entries with severity, likelihood, recommended stance (accept, negotiate, decline).
**Tools.** `read_document`, `search_knowledge_base` (past contracts, legal playbook), `read_blackboard`.
**Rules.** Flags contract terms by quoting them. Marks anything the playbook calls must-negotiate. Delivery risks reference the estimate they threaten.
**Evals.** Catch rate on seeded risky clauses; false-positive rate; stance agreement with the playbook.

## Writer

**Purpose.** The proposal, in the firm's voice, section by section.
**Owns.** `section` entries.
**Tools.** `read_blackboard`, `search_knowledge_base` (style guide, case studies), `render_section`.
**Rules.** Fans out per section. Every claim cites a case study, a finding or a matrix entry. Answers requirements in the client's own order and words where the RFP asks for it. Never invents a client reference.
**Evals.** Citation presence per claim (judge, 100% target); style-guide adherence (judge); coverage of must-have requirements in the text.

## Critic

**Purpose.** Read the draft the way the client's evaluation committee will.
**Owns.** `score` entries and its `objection` entries.
**Tools.** `read_document` (the RFP's evaluation criteria), `read_blackboard`.
**Rules.** Scores each criterion with a reason. Raises objections only with evidence. Runs a final pass that rejects any number or claim without a source; the Chair cannot finalise until it passes.
**Evals.** Score correlation with human graders on labelled drafts; objection validity rate; catch rate on seeded unsupported claims.

## Arbiter

**Purpose.** Settle what the owner and the objector cannot.
**Owns.** `ruling` entries.
**Tools.** `read_blackboard`, `search_knowledge_base`.
**Rules.** Reads both sides and the evidence, rules with a written reason, or escalates when the evidence is even or the stakes are above a threshold. Never introduces new content of its own.
**Evals.** Ruling agreement with human adjudicators on labelled disputes; escalation precision.

---

## Cross-cutting

- Structured outputs everywhere; free text lives in designated fields.
- Every agent can say "I cannot" with a reason, and that is a valid delivery.
- No agent has a shell, a browser or write access outside its owned entries and its tools.
- Every turn is a trace with tokens, cost and duration; the meeting room shows the running total.
