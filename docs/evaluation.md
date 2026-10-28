# Milestone 3: paired evaluation

This runner evaluates graph/retrieval access without assuming it helps. It
requires the **existing** `.petromind/split.json` from the local demos and checks
that it still yields **33 held-out incidents**. It never selects a new split or
silently filters difficult test cases. The original experimental scripts remain
unchanged; their historical scores do not become results of this protocol.

## 1. Freeze the protocol offline

Use the same Python 3.10+ environment, real 3W dataset and split used for the live
demonstration. Install/update the project and test it first:

```bash
python -m pip install -e '.[test,agent,experiments]'
python -m pytest -q
python scripts/evaluate.py prepare \
  --dataset ../3W/dataset \
  --split .petromind/split.json \
  --out .petromind/eval-m3-v1 \
  --budgets 5 --pilot-cases 2
```

`prepare` makes **zero API requests** and refuses to overwrite a protocol. It
freezes train/test well assignments, hashes of all eligible incident files and
their locators, random opaque case IDs, pilot selection, budgets, method order
seed, source-code digest, runtime versions, prompt/configuration and price rates.
No target labels are used to choose pilot cases or method order. The serialized
manifest contains evaluator-only well assignments; it must never be given to
the model. Public case IDs are random UUIDs, not event-coded filenames.

Every later run verifies the eligible cohort and file bytes, code and runtime.
Changed data/code/configuration requires a new output directory and protocol;
do not edit the manifest to bypass checks. The initial freeze cannot retroactively
verify that data files were unchanged before this milestone.

The default `--budgets 5` uses an identical maximum of five unique sensor queries
for every method. Early model stopping is allowed and measured. Conventional
policies use their full cap (or exhaust the public candidate list). Missing and
rejected readings cost one; repeated requests are cached. To pre-register a
budget curve, pass `--budgets 1 2 3 4 5` **before** any pilot, recognizing that it
multiplies paid work by five. `--expected-test-incidents` is an explicit override
for alternate/synthetic datasets; do not use it to shrink the real cohort.

## 2. Execute only the small live pilot

With `MODEL_API_KEY` exported in this same terminal:

```bash
python scripts/evaluate.py pilot \
  --dataset ../3W/dataset --out .petromind/eval-m3-v1
```

At the default single budget, this runs **two identical incidents across five
methods**: six paid Muse investigations and four local conventional runs. No
full-cohort evaluation starts automatically. Across the entire output directory,
the pilot defaults to 120 HTTP attempts. Its total output reservation is derived
from the number of planned Muse runs and the frozen per-run reservation; at the
default 2,048-token cap and 20 turns this is 245,760 tokens, including retries.
Adjust using `--max-requests-total` and
`--max-output-tokens-total`; reservations persist before each request so restarting
the command cannot reset spending counters. Per-investigation transport limits
are the same for all Muse variants. These are request/output bounds, not an
invoice-level dollar cap. Input tokens also cost money.

Review `report.md`, `report.json`, `results.csv`, `results.jsonl`, and `traces/`.
Check failures, quality flags, sensor budgets, tool calls, reported token usage
and estimated costs. `pilot_ready: true` means every pilot task completed its
tool workflow; it does **not** require correct diagnoses. Wrong predictions never
disqualify an incident or block advancement. Do not tune prompts/sensor policies
against pilot labels from this held-out cohort. Any subsequent tuning needs a
separate development cohort and a clearly new protocol.

## 3. Resume the same protocol for all 33 only after pilot review

```bash
python scripts/evaluate.py full \
  --dataset ../3W/dataset --out .petromind/eval-m3-v1
```

`full` refuses to run without a successful complete pilot, preserves pilot
results and runs only pending tasks. At one budget the total is **165 paired
investigations: 99 Muse and 66 conventional**, including the pilot. Full-stage
default global caps are 2,000 requests and the number of planned Muse runs times
their frozen output reservation (4,055,040 tokens at the default 2,048-token cap
and 20 turns), including previous pilot reservations. Each request checks these caps in Python.
If a limit stops work, the incomplete report must not be described as accuracy
over all 33 cases.

Completed and failed tasks are never automatically rerun. A task intent is
persisted before execution. If the process dies mid-task, its trace/ledger remain
and the next command refuses an automatic paid retry. Inspect and retain these
artifacts; do not delete failure rows to cherry-pick results. If a protocol has
an operational failure requiring code/config changes, retain it and start a new
protocol rather than silently replacing failed outcomes. Advisory file locking
prevents concurrent evaluation processes (Mac/Linux).

Offline report regeneration:

```bash
python scripts/evaluate.py analyze --out .petromind/eval-m3-v1 --cohort pilot
python scripts/evaluate.py analyze --out .petromind/eval-m3-v1 --cohort full
```

`analyze` never reads a key or calls Meta. It analyzes the saved records; it does
not establish data integrity beyond the original run-time checks. Use the same
analysis code version for the final report.

## Operational token-limit revision

`model_output_token_limit` means one response exhausted its generation cap,
including reasoning, before a complete tool call/submission. It is distinct from
the sensor-query budget. `stage_complete: true` means all planned tasks were
attempted; `pilot_ready: false` means at least one workflow did not complete.
Keep those failures in the original results. Do not retry only failed variants,
edit their rows, pool protocols, or bypass the full-stage gate.

For a uniform larger cap, create a new protocol and repeat the entire pilot:

```bash
python scripts/evaluate.py prepare \
  --dataset ../3W/dataset --split .petromind/split.json \
  --out .petromind/eval-m3-v2 --budgets 5 --pilot-cases 2 \
  --max-output-tokens 4096 \
  --cohort-from .petromind/eval-m3-v1/protocol.json
python scripts/evaluate.py pilot \
  --dataset ../3W/dataset --out .petromind/eval-m3-v2
```

`--cohort-from` verifies the parent protocol's integrity, file hashes, split,
sensor budgets, prompts and other model settings, and preserves every opaque
case ID, pilot ID and method order. Among model settings only the generation-token cap may change;
the source/runtime are freshly recorded and the parent protocol ID is linked.
No prior results are imported or overwritten. The default remains 2,048 until
the larger value is explicitly requested. Increasing the cap does not guarantee
completion, a correct diagnosis or a graph benefit.

Per-run output reservations now scale as `max_turns * max_output_tokens`.
For 4,096 tokens and 20 turns, that is 81,920 per run and 491,520 total for the
six-run Muse pilot. This is reserved capacity, not actual output usage or a
dollar charge. Explicit lower global caps remain available. All three Muse
conditions receive the same revised cap; model draws remain stochastic. This
is an operational reliability revision, not permission to tune on test labels.

## Compared configurations

| Method | Measurements | Generic graph | Train-only analogues | Predictor |
|---|---|---|---|---|
| `sensor_only` | Charged queries | Disabled in Python | Disabled in Python | Muse Spark 1.3 |
| `topology` | Charged queries | Enabled | Disabled in Python | Muse Spark 1.3 |
| `graphrag` | Charged queries | Enabled | Enabled | Muse Spark 1.3 |
| `fixed` | Charged queries | Disabled | Disabled | Existing Gaussian evidence policy, train-ranked sensors |
| `adaptive` | Charged queries | Disabled | Disabled | Existing Gaussian evidence policy, posterior-weighted sensor separation |

Muse variants share the same public prior information, prompt text, model,
reasoning effort, turn/output limits and window. Only capabilities/tool schemas
change. Tool removal is enforced by the session, including direct calls to
disabled graph/retrieval methods. Public sensor meanings can themselves contain
equipment information in all three variants; this tests the incremental tools,
not a model with no prior knowledge of physical systems. The illustrative graph
is still not verified per-well topology.

The conventional implementation preserves `active_sensors.py`'s three features
(median, population standard deviation, half-window median change), train-only
robust scaling, diagonal Gaussian likelihoods, variance floor, Laplace priors,
fixed ranking and adaptive separation rule. It handles all-missing training
columns explicitly rather than emitting NaN warnings. Regression tests load the
unchanged original definitions and compare parameters, ranking and both query
policies. In this runner, target features arrive only through charged session
queries. Quality flags are recorded but not added as new baseline features.
The same evidence-submission validation applies to every method: an all-unavailable
investigation fails rather than accepting the prototype's prior-only prediction.

The retriever is fitted once from exactly the training partition. It rejects
unknown/test wells, uses persisted opaque training IDs, and matches only already
queried valid measurements. It returns no unqueried historical values. Each
condition has a fresh stateless session; evaluator labels/reports never feed
back into the model, train fitting or retrieval.

## Sensor quality metadata

Available summaries include `quality_status`, `missing_count`, `nonnumeric_count`,
`nonfinite_count`, `extreme_count`, `zero_count`, `is_constant`, `constant_value`,
`quality_flags`, and the original statistics. Missing samples are distinguished
from rejected nonnumeric/infinite/extreme values. `invalid_count` retains its old
aggregate unavailable-sample meaning for compatibility; consult the separate
counts for quality analysis. `change` is second-half minus first-half valid
median, preserving missing samples' positions; `delta` remains last minus first.

Zeros remain valid. A constant-zero pressure or valve reading is **not** silently
converted to missing or declared invalid. Constant values are flagged as needing
context; a single valid sample is flagged as insufficient to assess variation.
The magnitude cutoff `1e12` remains a numerical heuristic, not a sensor-specific
engineering range. Data-quality flags are not proven failure indicators.

## Recorded metrics and analysis

Each evaluator-only result includes opaque case/well-group IDs, method, cap,
prediction, true class, correctness, subjective uncalibrated confidence, latency,
charged sensor sequence and summaries/quality, graph/retrieval attempts and
successful-call counts, neighbor-following events, failure reason, audit digest,
API requests, output reservations, input/cached/output/reasoning tokens, and
estimated cost. Time excludes common data loading/model fitting but includes
per-case client setup, tool execution, retries and API latency. JSONL traces
contain sanitized tool activity, not model free text or encrypted reasoning.
Only the evaluator-only result records reveal test labels after a run terminates.

Primary accuracy counts failed attempts as incorrect. Unattempted tasks make
full primary accuracy null; attempted-only accuracy is explicitly labeled.
Supported-class macro F1, per-class accuracy, confusion counts, class coverage,
and per-error quality/selection details are provided. Paired comparisons use
matching case IDs at the same budget, report discordant wins/losses, and compute
a seeded 2,000-draw well-cluster bootstrap interval for the accuracy difference.
There is no interval with fewer than two wells and no automatic superiority
claim. Small groups/rare classes and multiple comparisons limit interpretation.

Selection comparisons record sequence/set changes, first divergence and Jaccard
overlap. Immediate graph-suggestion-following is recorded separately. Different
sensor choices or a graph query followed by a neighbor query do **not** prove
graph-caused accuracy gains: there is one stochastic model draw per condition,
no supported model-generation seed, and the bootstrap does not include sampling
variation across repeated LLM runs. The frozen seeded method order helps limit
systematic ordering/cache effects; it is not a deterministic model guarantee.

Cost uses Meta Standard Muse Spark rates verified October 27, 2026:
input $1.25, cached input $0.15, output $4.25 per million tokens, from
[Meta pricing](https://dev.meta.ai/docs/pricing-rate-limits). Cached tokens are
subtracted from normal input, and reasoning is already included in output, so
neither is billed twice. Missing cache counts use normal input prices. Attempts
without usage are explicitly counted and mark the estimate incomplete; their
unknown charges, account credits, taxes and discounts are not invented. Prices
are frozen in the protocol and estimates are not invoices.

## Current validation limits

Automated tests use fabricated Parquet incidents and mocked API responses; they
do not demonstrate a real-data improvement. This execution environment has no
Meta key, full 3W dataset or original split, so a new live pilot could not be run
here. The earlier successful live smoke investigation is not a paired evaluation
result. Run the two-case pilot locally before considering the remaining cohort.
Known transient onset, previously seen smoke/pilot labels, weak generic topology,
missingness/well shortcuts, limited class counts and stochastic inference remain
material limitations. No positive GraphRAG result is assumed.
