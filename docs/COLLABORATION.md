# The collaboration protocol

How nine agents work on one proposal without talking over each other, looping forever, or agreeing too easily. This is the core of the project; everything else serves it.

## Three primitives

**Blackboard.** A versioned store of typed entries. Every entry has `kind` (requirement, assumption, work_package, estimate, price_line, risk, section, question, objection), `owner` (the agent that may edit it), `evidence` (citations), `version` and `status`. Agents read anything, but only the owner writes, and every write is a new version. Two agents cannot edit the same entry at once because only one owns it.

**Message bus.** Typed messages between agents, always through the Chair's turn schedule, never ad hoc. Kinds: `assign`, `deliver`, `question`, `answer`, `objection`, `defence`, `revision`, `ruling`, `escalate`, `done`. Each message names the blackboard entries it refers to. The full sequence is the transcript, and the transcript is the minutes.

**Protocol.** A state machine the Chair runs. Rounds in order, with the option to skip rounds the RFP does not need (a two-page quote request skips Research and most of Risk).

## Rounds

| Round      | Who works           | Parallel? | Exit condition                                                                 |
| ---------- | ------------------- | --------- | ------------------------------------------------------------------------------ |
| Brief      | Scoper              | No        | Requirements matrix complete: every requirement cited, prioritised, owned       |
| Research   | Researcher          | No        | Findings delivered with sources; open questions raised                          |
| Scope      | Scoper              | No        | Work packages cover every must-have requirement; assumptions listed             |
| Estimate   | Estimator + sub-agents | Yes    | Every package estimated; variances above threshold explained or escalated       |
| Price      | Pricer              | No        | Every price line traces to rate card, policy or a past deal; deviations explained |
| Risk       | Risk                | Yes (with Price) | Register complete; must-negotiate items marked                            |
| Draft      | Writer              | Yes (sections) | Every section drafted; every claim cited                                   |
| Critique   | Critic              | No        | Score per criterion; objections raised                                          |
| Reconcile  | Owners, Arbiter     | No        | No open objections, or all remaining ones escalated to a human                  |
| Finalise   | Chair               | No        | Deliverables rendered; minutes written                                          |

Rounds can be re-entered: an objection to an estimate re-opens Estimate for that package only. The Chair tracks re-entries and stops after a limit (default 3 per round) by escalating.

## Turns and budgets

Each turn has a token budget and a wall-clock budget set per agent. An agent that runs out delivers what it has with a `partial` flag, and the Chair decides whether to grant another turn. Budgets are visible in the meeting room, so a stalled meeting is diagnosable.

## Objections

An objection is an entry, not a chat message. It requires:

- the target entry and version
- a claim ("this estimate is 40% below the comparable in proposal P-2024-07")
- at least one citation (blackboard entry, knowledge base document, or RFP page)
- a proposed resolution

The owner replies with a `defence` (with citations) or a `revision` (new version of the entry). If the objector accepts, the objection closes. If not, the Arbiter rules with a written reason, or escalates when the evidence is genuinely even. An objection without a citation is rejected by the Chair before anyone spends a turn on it.

Limits: one open objection per entry at a time; three rounds of defence and revision, then arbitration; five arbitrations per meeting, then the human is asked to settle the rest. The limits are what make the argument productive instead of endless.

## Fan-out and fan-in

The Estimator does not estimate nine packages in one context. It spawns one sub-estimator per package with a narrow pack (the package, its requirements, comparable past packages) and a small budget. It then reconciles: totals, dependencies, double counting, and any package whose sub-estimates disagree by more than a threshold when two are requested for high-value packages. Reconciliation is itself a cited entry, so the Critic can object to it.

The Writer fans out per section the same way, and the Critic scores sections independently before scoring the whole.

## The human

The meeting room shows the transcript, the blackboard and open objections live. A person can, at any time:

- answer an open `question` (the answer becomes an assumption with `evidence: human`)
- `override` an entry (new version, owner unchanged, flagged as human)
- `veto` an entry (it is removed from the proposal and the minutes say why)
- settle an escalated objection

The Chair treats a human message as the highest-priority turn and resumes the protocol from the affected round.

## What cannot happen

- Two agents editing one entry: ownership.
- An agent citing itself: evidence must be a document, a blackboard entry owned by someone else, or a human.
- An unbounded loop: budgets, round limits, objection limits, and a hard cap on total turns per meeting.
- A quiet failure: every partial delivery, timeout and rejected objection is in the transcript.
- A number without a source in the final proposal: the Critic's last pass rejects it, and the Chair will not finalise.

## Why not free-form chat between agents

Because it is not debuggable and does not converge. Real meetings work when someone runs them. The protocol is the Chair's agenda, the blackboard is the whiteboard, and the transcript is the minutes. Every one of those is a thing a human can read after the fact and say "that is where it went wrong".
