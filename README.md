# Roundtable

**A multi-agent proposal team. Send it an RFP; get back a proposal, a price, the risks, and the minutes of how the agents argued their way there.**

Responding to a request for proposal is a team sport: someone researches the client, someone scopes the work, someone estimates, someone prices, someone checks the contract terms, someone writes, and someone tears the draft apart before it goes out. It takes a week and the best people in the company. Roundtable is that team as nine AI agents around one table: they work in parallel, hand work to each other through typed messages, object to each other with evidence, and a Chair keeps the meeting moving until the proposal is done or a human is needed.

> **Status: v0 runs.** The Harbor Logistics meeting runs end to end on your machine: all nine seats, fan-out estimation with a flagged disagreement, price and risk in parallel, six drafted sections, objections with evidence, a defence, an Arbiter's ruling, two clauses escalated to your seat, and the five deliverables. Bring your own key (Anthropic, or any OpenAI-compatible endpoint such as vLLM) from the settings panel, or run the keyless mock to see the mechanics. See [Running it](#running-it). What is still a plan is in [`docs/PLAN.md`](docs/PLAN.md) and the [issues](../../issues).

Built by [Shreyas Pachpute](https://shreyaspachpute.in). Sister project of [Dispatch](https://github.com/shreyas-pachpute/dispatch), which is about running a back office; Roundtable is about agents *deliberating*. MIT licensed.

---

## Why this exists

Single-agent systems are good at tasks. They are bad at *judgment calls that need more than one perspective*: is this scope realistic, is this price defensible, is this clause a risk, does this draft actually answer what the client asked. Real teams solve that with disagreement. Most multi-agent demos solve it with a supervisor that tells workers what to do and never lets them argue.

Roundtable is built around the argument:

- **A shared blackboard.** One versioned workspace every agent reads and writes: requirements, assumptions, work packages, estimates, prices, risks, draft sections. Every entry has an owner and evidence.
- **A meeting protocol.** The Chair runs rounds: brief, research, draft in parallel, critique, reconcile, finalise. Turns have budgets; rounds have limits; nothing loops forever.
- **Objections with evidence.** Any agent can object to any entry, but only with a citation. The owner revises or defends; an Arbiter decides; unresolved objections go to a human with both sides in one screen.
- **Fan-out and fan-in.** The Estimator spawns a sub-estimator per work package, then reconciles them and explains the variance. The Writer drafts sections in parallel and the Critic scores them against the client's own evaluation criteria.
- **A human at the table.** You can join at any point: answer an open question, override a price, veto a clause. The team continues from there and the minutes record it.
- **Minutes.** The output is not just a proposal. It is the proposal, a pricing sheet, a risk register, a client Q&A list, and a readable record of who said what, what changed and why.

## A meeting, start to finish

The demo client is *Harbor Logistics*, a fictional 3PL that has issued an RFP for a warehouse-management integration. The responding firm is *Meridian Systems*, a fictional 25-person consultancy with twelve past proposals, a rate card, case studies and a margin policy in its knowledge base. Everything is synthetic. See [`docs/DEMO.md`](docs/DEMO.md).

| Round        | What happens                                                                                                    | Who                                 |
| ------------ | --------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| Brief        | The 34-page RFP becomes a requirements matrix: 61 requirements, each with a page citation and a priority          | **Chair**, **Scoper**               |
| Research     | Client context, past comparable proposals, three relevant case studies, two competitor signals                    | **Researcher**                      |
| Scope        | Nine work packages with assumptions and open questions for the client                                             | **Scoper**                          |
| Estimate     | One sub-estimator per package, reconciled; package 6 flagged: two estimates disagree by 40%                       | **Estimator** and its sub-agents    |
| Price        | Rate card plus margin policy plus what won last time; a discount proposed on package 3 with a reason              | **Pricer**                          |
| Risk         | Four contract terms flagged, one unlimited-liability clause marked as a must-negotiate                              | **Risk**                            |
| Draft        | Sections written in parallel in the firm's voice, every claim linked to a case study or the matrix                | **Writer**                          |
| Critique     | Scored against the RFP's stated evaluation criteria; two sections sent back; one objection to the price           | **Critic**                          |
| Reconcile    | The price objection is argued with evidence and settled; the liability clause is escalated to a human             | **Arbiter**, then you               |
| Finalise     | Proposal, pricing sheet, risk register, client Q&A and the minutes                                                 | **Chair**                           |

Every row is a planned behaviour with an evaluation case behind it. When the phase that delivers it ships, the row links to the recorded run.

## The table

| Agent          | Job                                                                                          | Talks to                          |
| -------------- | -------------------------------------------------------------------------------------------- | --------------------------------- |
| **Chair**      | Runs the protocol, assigns turns, enforces budgets and round limits, decides when it is done | Everyone                          |
| **Researcher** | Client, market and past-proposal context, with sources                                       | Scoper, Writer, Pricer            |
| **Scoper**     | Turns the RFP into a requirements matrix, work packages, assumptions and open questions      | Estimator, Writer, Critic         |
| **Estimator**  | Effort and schedule per package, via fan-out sub-estimators and reconciliation               | Pricer, Critic                    |
| **Pricer**     | Price from the rate card, margin policy and memory of past deals; explains every deviation   | Critic, Arbiter                   |
| **Risk**       | Contract terms, compliance, delivery risks; a register with severity and a recommended stance | Writer, Arbiter                   |
| **Writer**     | Proposal sections in the firm's voice, every claim cited                                     | Critic                            |
| **Critic**     | Scores the draft against the client's evaluation criteria; raises objections with evidence   | Everyone, through the Chair       |
| **Arbiter**    | Settles objections the owner and objector cannot; escalates to a human when evidence is even | Chair, you                        |

Full specifications, tools and evaluation cases per agent: [`docs/AGENTS.md`](docs/AGENTS.md). The protocol itself, message types, objection rules and how deadlocks are prevented: [`docs/COLLABORATION.md`](docs/COLLABORATION.md).

## How it works

```mermaid
flowchart TB
  RFP[RFP · PDF, DOCX, email]:::src --> CH
  KB[(Firm knowledge base<br/>past proposals · rate card · case studies · policy)]:::src
  subgraph Table["The table"]
    CH[Chair]
    BB[(Blackboard<br/>versioned, cited entries)]
    BUS[[Message bus · typed messages · transcript]]
    R[Researcher]
    S[Scoper]
    E[Estimator]
    E1[sub-estimator ×n]
    P[Pricer]
    K[Risk]
    W[Writer]
    C[Critic]
    A[Arbiter]
  end
  H((You))
  OUT[Proposal · pricing sheet · risk register · client Q&A · minutes]
  CH <--> BUS
  BUS <--> R & S & E & P & K & W & C & A
  E --> E1 --> E
  R & S & E & P & K & W & C & A <--> BB
  KB --> R & P & W
  A <--> H
  H <--> CH
  CH --> OUT
  classDef src fill:#eef,stroke:#88a
```

## What makes it different

1. **Agents disagree, on the record.** Objections are first-class objects with evidence, an owner, a status and a resolution. The minutes show them.
2. **Structure prevents chaos.** A fixed protocol with turn budgets and round limits. No unbounded chatter, no two agents editing the same entry at once, no infinite objection loops.
3. **Everything cited.** A number in a proposal traces to the rate card, a past deal, or the matrix. A claim traces to a case study. The Critic rejects anything that does not.
4. **The human is a participant, not a rubber stamp.** Join mid-meeting, answer, override, veto. The team adapts and the record shows it.
5. **Evaluated like a team, not a chatbot.** Requirement recall, estimate consistency, policy compliance, proposal score against a rubric versus human-written baselines, objection resolution correctness. A change that lowers a score does not merge.
6. **Your models.** Claude Opus 5 for the Chair, Critic and Arbiter; Sonnet 5 for research and drafting volume; a vLLM path for firms that keep documents in-house.

## Stack

| Layer        | Choice                                                                | Why                                                                              |
| ------------ | --------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Agents       | Python, LangGraph (one supervisor graph, one subgraph per agent)      | Explicit state, replayable rounds, testable nodes                                |
| Models       | Claude via the Anthropic SDK; vLLM for self-hosted models             | Judgment where it matters, volume where it does not; a private path from day one |
| Blackboard   | Postgres with versioned entries and pgvector for past-deal memory     | One store, one history, one backup                                               |
| Research     | Firm knowledge base via MCP; web search through the model's server-side tool | Sources attached to every finding                                          |
| Bus          | Typed messages (Pydantic) over a Postgres outbox; full transcript     | Every hand-off inspectable and replayable                                        |
| Meeting room | Next.js: live transcript, blackboard, objections, join-in             | The owner watches the meeting and can step in                                    |
| Outputs      | DOCX and PDF export, CSV pricing sheet, Markdown minutes              | What a client and a sales lead actually use                                      |
| Evals        | pytest, deterministic checks plus rubric judges, CI gate              | Quality is a number that must not go down                                        |

## Roadmap

Detailed plan with definition of done per phase: [`docs/PLAN.md`](docs/PLAN.md).

- [x] **v0 · vertical slice** — every seat, the blackboard, the bus, fan-out estimation, objections, Arbiter, human seat, meeting room, bring-your-own-key; SQLite, JSON RFP, Markdown outputs
- [ ] **Phase 0 · Foundations** — Postgres, tracing to Langfuse, CI, recorded-meeting replay
- [ ] **Phase 1 · Brief and research** — PDF/DOCX ingestion with OCR, web research through the model's server-side tool, brief evals
- [ ] **Phase 2 · Estimate and price** — past-deal memory in pgvector, dual estimates by value threshold, numbers evals
- [ ] **Phase 3 · Write, critique, reconcile** — re-entry into earlier rounds, override and veto from the seat, meeting evals
- [ ] **Phase 4 · Deliverables and hardening** — DOCX and PDF exports, evals as a CI gate, cost budgets, quick-quote variant, demo recording

## Running it

Python 3.11+ and Node 20+. No database server; v0 uses SQLite in `data/runtime/`.

```bash
git clone https://github.com/shreyas-pachpute/roundtable && cd roundtable
make install            # pip install -e apps/api · npm install in apps/meeting-room

# terminal 1
make api                # http://127.0.0.1:8788
# terminal 2
make ui                 # http://localhost:3101
```

Open the meeting room and press **Open the meeting**. The agenda advances round by round; the seats light up as agents take turns; the transcript shows every assignment, delivery, objection, defence and ruling; the blackboard tabs fill with the requirements matrix, findings, packages, estimates (with the second estimate where one was requested), the price with its margin, the risk register, the draft with version numbers, the Critic's scores and objections, and finally the outputs, which you can download. When a clause must be declined per the playbook, or the Arbiter escalates, the meeting pauses and **Your seat** appears with the options; the minutes record what you chose.

**Hosting it.** The UI is a static Next.js app and runs anywhere (Vercel works). The API needs an always-on server because it keeps a live queue and event stream; `render.yaml` deploys both API and UI on Render's free tier in one click: [Deploy to Render](https://render.com/deploy?repo=https://github.com/shreyas-pachpute/roundtable). A hosted UI can point at any API with `?api=https://your-api-host` in the address bar (remembered in the browser).

**Bring your own model.** Click the model button in the header: choose Anthropic (Opus 5 for the Chair, Critic and Arbiter and Sonnet 5 for the rest, or one model for everything), or any OpenAI-compatible endpoint with its base URL, paste your key, and press *Save and test*. The key stays in the API process's memory for the session; it is never written to disk. Without a key the demo runs on a deterministic mock so the mechanics are visible; the UI labels it as mock.

**What v0 is and is not.** It is the real protocol at small scale: an owned, versioned blackboard; a typed bus whose transcript is the minutes; rounds with limits; fan-out and fan-in; objections that are rejected before they cost a turn if they carry no evidence; a defence, an Arbiter, a human seat; prices computed in code from the rate card with the model deciding only cited deviations; verbatim quotes validated against the RFP. It is not yet Postgres, PDF ingestion and OCR, the DOCX/PDF exports, the eval suites in CI, or re-entry into earlier rounds; those are the open phases in the plan.

## License

MIT. See [`LICENSE`](LICENSE).
