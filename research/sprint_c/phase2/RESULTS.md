# Sprint C Phase 2: verified primary and repeat results

Status: all 70 declared cells attempted; 64 completed, five reached the frozen
output-token limit, and one was interrupted. No complete seven-case matched cohort
was obtained. This is a bounded research result, not production authorization.

Source implementation: `143928d0e4ea789f82ec3bdf091c66e06a2784a2`.
The frozen scientific protocol, prompts, cases, reference answers, model/reasoning,
tools, five-sensor policy and scorer were unchanged. No further paid requests were
made during independent export verification. Preserve the owner checkout at this
source commit; this report does not authorize migrating an active journal.

## Independent integrity verification

The latest private export matched SHA-256
`b8270115ff9edb87d3e10cf310a3435608b11c382ced46e391f39d105ad21909`.
All 2,400 internal file commitments, the exact file set, SQLite integrity, all
1,912 event hashes/anchors, funding/activation/registry identity, allowed cell order,
request counts, capture commitments and host chains verified. The earlier 1,149
events remain an exact prefix, and all 1,522 earlier artifacts other than the
expected growing database/report/top-level manifest are byte-identical.
All 12 current frozen scorer outputs and derived metrics reproduced exactly.
The earlier archived source, original monetary history and prior score snapshot
remain preserved. Seventy blinded packets and a separate unblinding map are private.
No reference answers, raw provider envelopes, credentials or private captures are
included in this public report.

Accounting contains 442 new-phase reservations, 441 validated settlements and one
full retained hold. Every local transport has a closure record. Settled phase usage
estimate: $4.34267095; unresolved phase hold: $0.119768; remaining phase capacity:
$25.53756105 under the existing $30 approval. The prior $5.35707335 liability is
unchanged, making current Sprint C accounted liability $9.81951230. PR #33 remains
separate. These are conservative local estimates/holds, not provider invoices.
No authorization was reset or increased during the repeat.

## Completion and failure mechanisms

| Execution group | Attempted | Completed | Matched cases |
|---|---:|---:|---:|
| Primary `confirmatory-v1` | 28 | 26 | 5/7 |
| Secondary `remaining-v1` | 14 | 13 | 2 internally matched groups |
| Separate `confirmatory-repeat-v2` | 28 | 25 | 4/7 |

The secondary batch is not pooled with the confirmation cohorts. The original
exploratory reports and failures are retained unchanged.

| Group | Cell | Outcome |
|---|---|---|
| Primary | c-42e8 / V1 | Incomplete at 4,096 output tokens |
| Primary | c-80b2 / V0 | Process interruption; full request hold retained |
| Secondary | c-9bc4 / V3 | Incomplete at 4,096 output tokens |
| Repeat | c-42e8 / V1 | Incomplete at 4,096 output tokens |
| Repeat | c-80b2 / V1 | Incomplete at 4,096 output tokens |
| Repeat | c-9bc4 / V3 | Incomplete at 4,096 output tokens |

All five token-limited envelopes were HTTP 200, model-matching terminal
`incomplete` responses with valid bounded usage; they settled correctly and never
executed partial output as a successful assessment. Their reported reasoning-token
counts were 3,494, 4,094, 3,428, 3,664 and 4,094 respectively. The fixed output
budget was consumed before an acceptable final assessment, including repeated
V1/c-42e8 and V3/c-9bc4 failures. These are observable model-completion constraints,
not accounting corruption or new receipt-validation failures. The exact earlier
pre-Phase-2 rejected receipt remains unrecoverable and is not retrospectively explained.

The sole unresolved new-phase request belongs to the interrupted primary
c-80b2/V0 cell. Its $0.119768 full hold remains despite local transport closure.
Restart preserved it, marked the cell interrupted and continued untouched cells.
Neither failed nor interrupted cells were silently replayed in their original group.

## Primary complete-case analysis

Five matched cases: c-7a91, c-6f03, c-a57c, c-13df and c-9bc4; 17 atomic findings.
These paired metrics use the same completed cases for all four conditions.

| Variant | Qualified correct | Raw verdict matches | Citation failures among raw matches | Incorrect contradictions |
|---|---:|---:|---:|---:|
| V0 | 11/17 | 15/17 | 4 | 2 |
| V1 | 16/17 | 16/17 | 0 | 1 |
| V2 | 13/17 | 17/17 | 4 | 0 |
| V3 | 17/17 | 17/17 | 0 | 0 |

All conditions matched the eight reference SUPPORTED and two CONTRADICTED verdicts
on this subset. Evidence qualification, which additionally requires the frozen
citation/evidence contract, is different: qualified SUPPORTED recall is 5/8 for
V0/V2 and 8/8 for V1/V3; qualified CONTRADICTED recall is 1/2 for V0/V2 and 2/2 for
V1/V3. No reference-disagreeing excess abstention or unsupported causal support was
scored on this matched subset. Neither absence proves safety outside this sample.

V3 completed all seven cases with 23/23 qualified atomic findings. That descriptive
full-variant result is not a seven-case paired comparison because V0/V1 did not
complete all seven. V3's separate full-plan weighted mechanical score is 27.93/29:
three cases required correction of a rejected submission. Atomic correctness does
not imply flawless first-pass structural submission or semantic entailment.

## Repeat complete-case analysis

Four matched cases: c-7a91, c-6f03, c-a57c and c-13df; 14 atomic findings.

| Variant | Qualified correct | Raw verdict matches | Citation failures among raw matches | Incorrect contradictions |
|---|---:|---:|---:|---:|
| V0 | 10/14 | 13/14 | 3 | 1 |
| V1 | 13/14 | 13/14 | 0 | 1 |
| V2 | 11/14 | 14/14 | 3 | 0 |
| V3 | 13/14 | 13/14 | 0 | 1 |

All conditions matched the seven reference SUPPORTED and one CONTRADICTED verdicts
on this subset. Qualified SUPPORTED recall is 4/7 for V0/V2 and 7/7 for V1/V3;
qualified CONTRADICTED recall is 1/1 for every condition. No scored excess abstention
or unsupported causal support occurred on this matched subset. V3 did not repeat
its primary perfect raw-verdict result and did not outperform V1 in this cohort.

## Sensitivity to different matched subsets and noncompletion

The five-case and four-case totals above are not directly comparable samples.
For a transparent sensitivity check, restrict both cohorts to their four common
complete cases (14 atoms), without pooling repeated attempts:

| Variant | Primary, common four cases | Repeat, same four cases |
|---|---:|---:|
| V0 | 9/14 | 10/14 |
| V1 | 13/14 | 13/14 |
| V2 | 11/14 | 11/14 |
| V3 | 14/14 | 13/14 |

This post-execution intersection check does not replace either cohort's primary
complete-case report. It conditions on completion in both and still has selection
bias. It shows that the apparent change is not solely a denominator change.

For an explicitly completion-aware descriptive measure, counting every unsubmitted
atom as zero across the 23 planned atoms gives:

| Variant | Primary planned atoms | Repeat planned atoms | Cells completed, primary / repeat |
|---|---:|---:|---|
| V0 | 13/23 | 17/23 | 6/7 / 7/7 |
| V1 | 18/23 | 16/23 | 6/7 / 5/7 |
| V2 | 18/23 | 18/23 | 7/7 / 7/7 |
| V3 | 23/23 | 18/23 | 7/7 / 6/7 |

These are not paired complete-case effect estimates. In particular the interrupted
V0 primary cell is an infrastructure/operator interruption, not a model verdict
error. The table makes missingness visible: improved citation compliance among
completed assessments did not guarantee better end-to-end completion at this budget.

## Findings, limits and next action

- Citation grounding has a consistent descriptive mechanical benefit in both
  cohorts: V1/V3 eliminate the citation-contract failures present in V0/V2 on the
  matched subsets. V1 improves all five matched primary cases relative to V0;
  on the common four cases it improves three in the repeat and ties one.
- Verdict discipline alone reduces incorrect contradiction decisions to zero on
  both matched subsets and retains their correct CONTRADICTED judgments and raw
  SUPPORTED recall. There are only two true CONTRADICTED atoms in the primary
  subset and one in the repeat, so preservation evidence is very limited.
- V3 combines both benefits in the primary cohort, but its additional verdict gain
  over V1 does not replicate in the repeat. Do not claim uniform superiority,
  robust synergy, population accuracy, or a statistically established effect.
- All seven cases are correlated, previously inspected synthetic development tasks
  that informed the interventions. Single stochastic executions and failure-related
  complete-case selection limit causal/generalization claims. Repeated cases are
  not independent new samples; cohorts and earlier protocol versions stay separate.
- Actual entailment, scientifically justified abstention, premise quality and
  next-evidence usefulness remain ungraded. Prepared blinded packets require
  qualified independent human review; the tested model is not its own evaluator.

Overall: promising mechanical grounding and verdict-discipline signals, with an
inconclusive claim of generally improved industrial evidence reasoning. Complete
seven-case matched coverage and independent semantic validation were not achieved.

All currently declared cells/cohorts are exhausted. Stop identical reruns. The next
priority is blinded semantic review and final reporting. A prospective higher-token-
budget study across all four conditions could test completion sensitivity, but it
would materially change the frozen execution configuration and needs an explicit,
separately versioned protocol/owner decision before new calls. Existing remaining
funds alone do not authorize arbitrary new cohorts or changes to the current study.
No prompt tuning, reference changes, selective replacement of failed cells, hidden
retries, automatic budget increase, merge or production integration is authorized.
