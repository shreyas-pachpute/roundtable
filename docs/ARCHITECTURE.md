# Architecture

One deployment per firm. A supervisor graph runs the protocol; each agent is a subgraph; the blackboard and the message bus live in Postgres; the meeting room reads both live.

## Components

| Service         | Runtime           | Responsibility                                                                   |
| --------------- | ----------------- | -------------------------------------------------------------------------------- |
| `api`           | FastAPI           | Start meetings, upload RFPs, human join-in actions, meeting-room API, exports    |
| `worker`        | Python, LangGraph | Runs the Chair's supervisor graph and agent subgraphs; sub-agents as spawned graph runs |
| `meeting-room`  | Next.js           | Live transcript, blackboard, objections, cost meter, join-in                     |
| `mcp-knowledge` | Python MCP server | Firm knowledge base: past proposals, case studies, rate card, policies, style guide |
| `postgres`      | Postgres 16 + pgvector | Blackboard, bus, transcript, memory, evals                                   |
| `langfuse`      | Langfuse          | Traces                                                                           |
| `vllm` (optional) | vLLM            | Self-hosted models behind an OpenAI-compatible endpoint                          |

## The supervisor graph

The Chair is a LangGraph graph whose state is the meeting: current round, turn schedule, budgets, re-entry counts, open objections. Each node either runs an agent subgraph as a turn, closes a round, or escalates. Agent subgraphs receive a context pack (see below), run to a structured delivery, and return. Sub-agents (sub-estimators, section writers) are spawned graph runs with narrow packs and their own budgets, joined by the parent before it delivers.

Round transitions are explicit edges. There is no free-form "next speaker" choice by a model; the Chair's model decides *within* the protocol (which package to re-open, whether to grant another turn), not *about* it.

## Blackboard

```
entries        id, kind, owner_agent, version, status, payload (jsonb), evidence (jsonb[]), created_by_turn, superseded_by
```

Kinds: `requirement`, `finding`, `work_package`, `assumption`, `question`, `estimate`, `reconciliation`, `price_line`, `risk`, `section`, `score`, `objection`, `ruling`. Evidence items are `{type: rfp_page | kb_document | entry | human, ref, quote}`; quotes are validated against the source on write. Writes by a non-owner are rejected at the API, not by convention.

## Message bus and transcript

```
messages       id, meeting_id, turn_id, kind, from_agent, to_agent, refs (entry ids), payload, created_at
turns          id, meeting_id, round, agent, budget_tokens, used_tokens, budget_seconds, used_seconds, status, trace_id
```

The transcript is the ordered message list joined to turns. The minutes are rendered from it, not written separately, so they cannot drift from what happened.

## Context packs

Per agent, per turn: role and rules (stable), the protocol state that matters to this turn, the blackboard entries the turn needs (by kind and package, budgeted), evidence documents, and, for Pricer and Estimator, past-deal memory. Stable parts first for prompt caching; the pack is stored on the turn for replay.

## Memory

Past proposals with outcomes (won, lost, price, margin, client segment) embedded in pgvector. Written only when a human records an outcome, never from a meeting's own conclusions.

## Meeting room

Server-sent events stream turns, messages and entry versions. Views: transcript, blackboard by kind with version diffs, objection threads, cost meter, and the join-in panel (answer, override, veto, settle). Human actions are messages on the bus like any other, marked `from: human`.

## Exports

Proposal from `section` entries in the client's requested order (DOCX via python-docx, PDF via a headless renderer), pricing sheet from `price_line`, risk register from `risk`, client Q&A from `question`, minutes from the transcript.

## Security posture

- No shell, no browser agent. Web research goes through the model's server-side search tool with a domain allow-list.
- The RFP and retrieved documents are wrapped as untrusted data; the Critic's final pass checks for instructions that originated in documents.
- Nothing is sent to a client by the system.
- Every turn is budgeted; every meeting has a hard cap on total turns and cost.
