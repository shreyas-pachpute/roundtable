# Evaluation

A team is evaluated on the quality of what it ships and on how it got there. Both are measured; a change that lowers either does not merge.

## Suites

| Suite        | What it measures                                                                 | Grader                                   | Gate (v1 target)         |
| ------------ | -------------------------------------------------------------------------------- | ---------------------------------------- | ------------------------ |
| `brief`      | Requirement recall and precision; must-have coverage; citation presence         | Deterministic                            | ≥ 0.92 / ≥ 0.90 / 100% / 100% |
| `research`   | Source presence; relevance; contradiction with source                            | Deterministic + judge                    | 100% / judged / 0        |
| `numbers`    | Estimate tolerance vs baselines; arithmetic; policy violations; double counting | Deterministic                            | tolerance / 100% / 0 / 0 |
| `risk`       | Catch rate on seeded clauses; false positives; playbook agreement               | Deterministic                            | ≥ 0.95 / ≤ 10% / ≥ 0.9   |
| `proposal`   | Rubric score vs human-written baseline per criterion; claim citation presence    | Rubric judge (calibrated) + deterministic | ≥ baseline − 5% / 100%   |
| `critic`     | Catch rate on seeded unsupported claims; objection validity                     | Deterministic + judge                    | 100% / ≥ 0.9             |
| `dispute`    | Resolution correctness on seeded disputes; Arbiter agreement with adjudicators  | Deterministic + human-labelled           | ≥ 0.9                    |
| `protocol`   | Illegal transitions; limit violations; meeting length and cost within budget     | Deterministic                            | 0 / 0 / 100%             |
| `humanloop`  | Correct resumption after answer, override, veto, settle                          | Deterministic                            | 100%                     |
| `cost`       | Tokens and dollars per meeting and per agent; cache hit rate                    | Measured                                 | Reported, alerted on +20% |

## Datasets

Five synthetic RFPs of different sizes and industries, each with a labelled requirements matrix, baseline estimates, a human-written baseline proposal, seeded risky clauses and seeded disputes. The Meridian Systems knowledge base (past proposals with outcomes, rate card, policies, case studies, style guide). All in the repo, versioned, with notes on tricky cases.

## Graders

Deterministic wherever the answer is a value, a set or a boolean. Rubric judges only for proposal quality and relevance, with a fixed judge model and version and a calibration set of human-graded examples the judge must agree with at ≥ 0.9 before its scores count. The judge never runs on the same model version as the agent under test in the same run.

## Recorded meetings

Whole meetings are recorded (packs, deliveries, messages) and replayed in CI with a recorded-response cache keyed on the exact request. A pull request that does not change prompts, packs or protocol costs nothing to evaluate. Changed requests hit the model; the cache is refreshed by a maintainer.

## Running

```
make eval              # all suites, scorecard, evals/reports/<commit>.json
make eval-meeting      # protocol + dispute + humanloop on recorded meetings
make eval-diff BASE=main
```

## What gets an eval before it gets a feature

Labelled cases, a failing test, the behaviour, a passing test, the pull request. In that order.
