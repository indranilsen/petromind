# Milestone 4: hypothesis challenger feasibility

Status: implementation and synthetic transport tests complete; **real development
cohort, live pilot, expert review and GO decision pending**. This execution
workspace has neither the 3W Parquet dataset nor `MODEL_API_KEY`. No real Muse M4
requests have been made. Synthetic tests are not evidence of diagnostic ability.
The November 4 submission should use the observed gate outcome, not a presumed
improvement. No UI or new infrastructure is included.

## Preserve Milestone 3

Keep `.petromind/eval-m3-v2` unchanged. Its protocol is
`5e56257bc1ee4383ace4e500375a47a5f0824737a11de76c4d3edd5c549fb23a`.
See [the offline analysis](milestone3-failure-analysis.md). M3 found no established
GraphRAG advantage over sensor-only. M4 tests a different capability; it must not
be presented as a repaired M3 accuracy result. M3 protocols pin source/runtime;
use their original checkout if resuming them, not this branch.

## Freeze before spending

Install in the existing Python 3.12 environment and use a NEW output directory:

```bash
python -m pip install -e '.[test,agent]'
python -m pytest -q
python scripts/evaluate_challenger.py prepare \
  --dataset ../3W/dataset \
  --split .petromind/split.json \
  --out .petromind/challenge-m4-v1 \
  --cases 16 --pilot-cases 2
```

This makes zero API requests. It requires the original frozen M3 split, never
creates a replacement, and excludes every original test well from fitting,
retrieval, selection, and development cases. Inventory hashing includes excluded
files to detect drift; their values/labels do not influence model fitting or
cohort selection. Keep protocol and outputs private: they contain scoring labels
and split metadata. They are never serialized into an agent prompt.

A fixed seed of 104 hashes original training wells into approximately one-third
development wells and two-thirds fitting wells. All incidents from a development
well are excluded from fitting and retrieval. No split retry is performed to
improve class coverage. The same fitting incidents feed GaussianEvidence and the
historical index; neither contains development or original test wells.

Within the development pool, the two-query adaptive hypothesis is scored offline.
Selection alternates initial-hypothesis wrong/correct strata, subdividing by
five-query baseline correctness and class, with hash order within each bucket. This deliberately enriches errors and class coverage. It does
not promise exactly 50/50 or representation of every class. The protocol records
pool/selected error counts at both two and five queries, private labels, opaque case IDs, hashed well groups,
roles, class counts, fitting classes, initial sensor sequences/probabilities,
source/runtime/data hashes, prompt/configuration, prices and gate thresholds.
It requests 12–20 cases; if the isolated pool is smaller, freezes all available
cases and reports the shortfall. Do not try alternate seeds to obtain better
results. Too few correct/wrong cases prevents the gate from making a claim.

The pilot uses one baseline error and one correct hypothesis if available, then
fills deterministically. Freeze happens before any Muse call. Ground truth is
used only for this offline selection and subsequent scoring.

## What is compared

All four conditions use the same fitted Gaussian model, public 1–9 taxonomy,
initial two sensor queries, and initial hypothesis/probabilities:

| Condition | Initial evidence | Remaining evidence | Tools |
|---|---|---|---|
| A: baseline | Two adaptive queries | Three further adaptive queries | Statistical policy only |
| B: challenger | Same two queries | Up to three Muse-selected queries | Sensor tools + assessment |
| C: challenger_graph | Same two queries | Up to three Muse-selected queries | B + illustrative graph |
| D: challenger_graphrag | Same two queries | Up to three Muse-selected queries | C + fitting-well retrieval |

The primary challenge target is the **two-query hypothesis**, identical across
conditions. A records that hypothesis AND its final five-query prediction;
it is not silently replaced by a Muse alternative. A is a five-query comparator,
not a CHALLENGE classifier, so challenge precision/recall are not defined for A.
This differs from M3's five-query baseline trained on all original training wells.
Do not compare the new enriched-sample percentages directly to M3 population
accuracy. No calibrated probabilities are claimed.

Both model and Muse query the same DiagnosticSession instance. Every unique
request, including unavailable evidence, consumes the shared five-sensor budget.
Repeats are free, and Muse may stop early. Model fitting cannot read target
measurements. The model's inference accesses only charged observations. There is
no free availability scan or unqueried feature preview. A baseline-only run uses
a separate identical session so its extra observations cannot enter B/C/D.

Muse may SUPPORT, CHALLENGE, or report INSUFFICIENT_EVIDENCE. CHALLENGE requires a
contradictory measurement citation; an optional alternative is stored separately.
SUPPORT requires a supporting citation. Missing evidence cannot be cited as a
supporting/contradictory reading. Every decision includes uncertainty. A valid
schema does not establish a meaningful contradiction: that is a scored human
review question. Invalid submissions stay in the audit and may be corrected
within the same bounded run. A failed run is retained, never selectively retried.

## Small live pilot first

With `MODEL_API_KEY` exported securely in the same terminal (not in files):

```bash
python scripts/evaluate_challenger.py pilot \
  --dataset ../3W/dataset --out .petromind/challenge-m4-v1
```

Two cases mean six paid investigations plus two local baselines. Default Muse
settings: medium reasoning, 4,096 output tokens/request including reasoning,
20 turns, 40 tool calls, 300-second run deadline. Global pilot cap: 120 HTTP
attempts; reserved output cap: 6 × 20 × 4,096 tokens. `--max-requests-total` and
`--max-output-tokens-total` may lower spending bounds. Reservations persist BEFORE
every attempt including retries. These limits are not an invoice-level dollar
cap; inputs also cost money and prices may need a new protocol snapshot.

Inspect `report.md`, `report.json`, `results.jsonl`, and `traces/`. The report
records completion, labels/predictions after terminal runs, decisions, alternatives,
confidence, quotations/interpretations, sensor sequences/quality, graph/retrieval
events, audit validity, latency, reported token usage and estimated cost. API
errors and unknown usage are not represented as free successful investigations.
No full run starts automatically. `pilot_ready` means workflows completed,
not that the hypothesis succeeded. Review actual pilot claims and cost before
spending on the remaining development cases:

```bash
python scripts/evaluate_challenger.py full \
  --dataset ../3W/dataset --out .petromind/challenge-m4-v1 --reviewed-pilot
```

This reuses pilot rows; it does not rerun them. Default full cap is 1,000 attempts.
An interrupted task blocks automatic paid retry. Source/runtime/data drift blocks
execution. Never delete failed rows, revise prompts mid-protocol or reuse an old
output directory. A configuration revision requires a new frozen study and must
be disclosed; no automatic best-of retries or favorable condition selection.

## Evidence checks and expert review

Python mechanically verifies exact observed sensor names, summary fields and
values (including numeric-vs-boolean distinctions), available-vs-unavailable
categories, and graph relationships actually returned in this session. Graph
verification cannot be upgraded from illustrative to verified. Unknown sensors,
uncalled relationships, changed values and hidden-metadata fields are rejected.

These checks verify quotations and provenance. They do NOT verify that a reading
supports/contradicts a fault, prove a causal relationship, establish a threshold,
or detect every unsupported assertion in prose. The accepted quotation rate is
therefore reported explicitly alongside rejected submission attempts, not named
"physical faithfulness accuracy".

`review-packets.json` includes hypotheses, assessments, queried readings and tool
evidence, without ground truth or correctness. Have a qualified reviewer judge
these before consulting labeled result rows. Copy `review-template.json` to
`reviews.json` and complete:

- A named reviewer and substantive rationale.
- Every claim: `supported`, `unsupported`, or `requires_domain_expertise`.
- Whether the investigation is useful and any contradiction is meaningful.
- Count unsupported physical claims anywhere in the assessment, including
  uncertainty text, implicit topology assumptions and proposed alternative.

Every review binds to the exact assessment hash. Do not auto-fill review judgments
from case correctness. `requires_domain_expertise` remains unresolved, even when
a different fault prediction happens to be correct. Assessment duplication,
stale hashes and incomplete review schemas are rejected.

```bash
python scripts/evaluate_challenger.py analyze \
  --out .petromind/challenge-m4-v1 --cohort full \
  --reviews .petromind/challenge-m4-v1/reviews.json
```

Reports include incorrect-hypothesis recall, false-challenge rate, CHALLENGE
precision, counts of correct/proposed alternatives, insufficient decisions,
unavailable queries, tool calls, pairwise sensor/decision changes, cost and
latency. Alternative count uses all challenges as context, not only successful
alternatives. Failures remain in recall denominators and reduce completion.
One stochastic run does not identify a causal graph effect. Few wells, enrichment
and incomplete class coverage limit inference; no significance claims are made.

## Predeclared decision gate

The frozen `gate` is an engineering feasibility screen, not an industrial safety
standard or a statistically validated reliability threshold. No M4 real outcomes
were available when it was chosen. Each condition is reported separately; do not
select the best condition after the fact and call it confirmatory evidence.

A full gate needs at least four incorrect and four correct initial hypotheses,
>=95% successful runs, and expert resolution of every accepted claim and every
successful case. With missing review, small strata or an incomplete cohort the
recommendation is PENDING; this is not a fourth product direction or a GO claim.
With adequate strata, poor execution completion yields NO GO.

- **GO:** recall >=60%, false-challenge rate <=20%, CHALLENGE precision >=75%,
  >=80% of all CHALLENGEs judged meaningful by expert review, accepted mechanical
  citation rate >=95%, and zero unsupported claims/physical assertions.
- **PARTIAL GO:** GO detection criteria fail, but mechanical criterion and zero
  unsupported claims hold, and >=80% of cases have expert-reviewed useful
  investigations with every claim supported. Build an evidence audit/uncertainty
  assistant, without claiming diagnosis accuracy improvement.
- **NO GO:** sufficient evaluated/reviewed cases do not meet either criterion.
  Stop the challenger product build and consider a different Meta capability.

Do not tune these thresholds after seeing outcomes. If the pilot exposes a
protocol flaw, preserve its results and document a new study. Subsequent feature
or prompt development uses these development wells only. Original M3 held-out
labels never enter fitting, prompt selection or parameter optimization.
