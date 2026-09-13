# Demo scenario: Harbor Logistics × Meridian Systems

Both companies are fictional and every document is synthetic.

## The client: Harbor Logistics

A 3PL with four warehouses issuing a 34-page RFP for integrating a new warehouse-management system with its ERP, carrier APIs and a customer portal. The RFP has 61 requirements (28 must, 21 should, 12 may), stated evaluation criteria with weights (approach 30, team 20, price 30, risk 20), a 14-day response window, and a draft contract with an unlimited-liability clause and a 90-day payment term.

## The firm: Meridian Systems

A 25-person consultancy. Knowledge base:

| Set                | Count | Notes                                                                         |
| ------------------ | ----- | ----------------------------------------------------------------------------- |
| Past proposals     | 12    | 7 won, 5 lost, with price, margin, segment and a short outcome note            |
| Case studies       | 6     | Two directly comparable (WMS integrations), four adjacent                       |
| Rate card          | 1     | Roles and day rates, two currencies                                             |
| Margin policy      | 1     | Floor margin, discount rules, approval thresholds                               |
| Legal playbook     | 1     | Clauses to accept, negotiate or decline, with standard positions                |
| Style guide        | 1     | Voice, structure, banned phrases, how to cite case studies                      |
| Past packages      | 40    | Package-level estimates from past work, for the sub-estimators                  |

## The meeting

1. `make meeting` ingests the RFP and opens the meeting room.
2. Brief: the requirements matrix appears with page citations. Two requirements are ambiguous and become client questions.
3. Research: three findings about the client, two comparable past proposals (one won at a 12% discount, one lost on price), one competitor signal from an allow-listed source.
4. Scope: nine work packages; four assumptions; the two questions.
5. Estimate: nine sub-estimators run in parallel; package 6 (carrier integrations) gets two estimates that disagree by 40%; the reconciliation entry explains it (one assumed four carriers, one assumed nine) and raises a question.
6. Price: rate card × estimates; a discount on package 3 citing the won comparable; total margin above floor.
7. Risk: the liability clause is must-negotiate per the playbook; the payment term is negotiate; two delivery risks reference package 6.
8. Draft: sections in parallel; every claim cites a case study or the matrix.
9. Critique: scored against the four weighted criteria; two sections sent back for missing must-haves; one objection to the price ("comparable P-2023-11 was lost at this level").
10. Reconcile: Pricer defends with the won comparable and the margin policy; the Critic does not accept; the Arbiter rules for the Pricer with a written reason. The liability clause is escalated to the human with the playbook position and the RFP quote side by side.
11. You settle the clause from the meeting room; the Chair resumes and finalises.
12. Outputs: the proposal, the pricing sheet, the risk register, the client Q&A and the minutes showing all of the above.

## A second scenario: the quick quote

A two-page email asking for a price on a small data migration. The Chair picks the quick-quote variant: Brief, Estimate, Price, Draft, Critique, Finalise. Ten minutes, one page, still cited.

## What the demo is for

It is the evaluation dataset, the onboarding tutorial and the regression suite at once.
