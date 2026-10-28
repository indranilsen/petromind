# Milestone 5: one-test scientific investigation

Status: implementation and offline/mock verification complete; real-data and live
pilot execution blocked by unavailable dataset and Meta credentials in this
workspace. No paid Meta calls were made. This is a feasibility screen, not a
production diagnostic system. No UI, fine-tuning or new infrastructure is added.
All previous experiments remain unchanged.

## Question and knowledge audit

Does Muse choose useful, physically defensible tests that distinguish a fixed
pair of candidate faults better than conventional statistical selection?
Selecting a plausible test, obtaining a reading, and quoting it faithfully are
separate from establishing diagnostic discrimination.

The registry reuses the source audit in [physical-evidence-coverage.md](physical-evidence-coverage.md):
Petrobras dataset.ini blob `4c4799e80e04a9cf8b10cb3f9a23f1c487797cc9`
and [the authors' versioned manuscript](https://arxiv.org/html/2507.01048v1),
Tables 2–3 and Figures 3–6. This independently documents generic measurement
positions, units and valve encodings, plus example fault signatures. It does not
validate individual well tags or establish universal fault thresholds. Previous
M3/M4 findings and the latest offline archive are retained: availability weighting
introduced two errors without correcting any; stronger shared-sensor retrieval
lost a correct match at five queries. Neither heuristic is promoted here.

| Test ID | Sensors | Mathematical output / primary metric | Defensible scope |
| --- | --- | --- | --- |
| `tree_trend` | P-TPT | Last valid minus first valid pressure, Pa | Window direction; example signatures only |
| `paired_pressure_trends` | P-PDG, P-TPT | Both deltas and their product, Pa² | Same/opposite direction at documented positions; source examples, not a causal rule |
| `choke_pressure_difference` | P-MON-CKP, P-JUS-CKP | Median pointwise difference on jointly valid samples, Pa | Generic named upstream/downstream positions; no inferred hydraulic coefficient or fault threshold |
| `tree_oscillation` | P-TPT | Detrended FFT peak-power fraction, peak period, amplitude | Signal structure only; no calibrated slugging threshold |
| `tree_reference_change` | P-TPT | Diagnostic median minus pre-window median, Pa | Measured reference, never assumed normal operation |

Each template declares sensors, mathematical computation, measurement meaning,
source fact IDs with provenance/status/scope, and permitted/unsupported
interpretations. Eligibility uses public sensor catalog, remaining budget,
reference configuration, and already-charged evidence; it never peeks at an
unqueried measurement. A configured test can still return unavailable results.
Trend tests need two valid samples. Oscillation uses the longest contiguous valid
segment, minimum 32 samples at the loader-validated 1 Hz cadence, no interpolation.
A machine-precision residual floor suppresses numerical detrending residue; it is
not a physical detection threshold. Constant/zero readings remain valid.

A scalar already supplied in initial summaries is not an unseen prospective
outcome. A cached trend, or a fully cached pair whose deltas are already supplied,
is therefore marked ineligible. Cached sensors remain free when used for genuinely
new calculations such as spectra or pre-window reference comparisons. The paired
product derives algebraically from documented example directions; its sign is
not independently established physics.

Historical retrieval is deliberately absent: it would confound this first test
of physical experiment design, and its relevance was weak in the previous study.
Training and development wells remain disjoint; no retrieval index exposes any
evaluation incident. M3 test-well files are excluded before measurement reads.

## Small agent contract

`ExperimentSession` reuses DiagnosticSession/ChallengeSession's isolation, source
binding, immutable audit chain and shared five-sensor cap. It registers only:

1. `list_tests()` — definitions and structural executability.
2. `propose_test(test_id, required_sensors, baseline_expected, alternative_expected,
   knowledge_ids, uncertainty)` — commit a single test. Each expectation has
   only `relation: gt|lt|unknown` and a finite numeric `threshold`. Unknown uses 0.
3. `execute_test()` — execute that committed test through Python.
4. `assess_test(result_id, baseline_relation, alternative_relation, uncertainty)` —
   explicitly choose supports, contradicts or inconclusive for each prediction.

The initial baseline diagnosis and highest-scoring different represented class
are fixed before the model sees the case. No alternative-fault submission field
or unrestricted tool execution is introduced. Predictions cannot be revised once
accepted. No sensor queries outside the planned test are available to the agent.

Python preflights the entire required-sensor set atomically. Two unseen sensors
cost two queries, already observed sensors cost zero, missing/extreme readings
still cost their sensor identities. A test cannot partially consume budget when
its full cost exceeds the cap. Results contain measured statistics, complete
sensor-summary quality, audited measurement source IDs and, in the physical
variant, documented provenance. Execution returns no target label, well identity,
file metadata, prediction match or physical conclusion.

Assessments bind to the returned result ID and exact Python value. Numeric
supports/contradicts must agree with the precommitted inequality. Unknown
expectations or unavailable values permit only an explicit inconclusive result.
This verifies mathematical interpretation, not physical truth or fault causality.
Invalid assessments never become successful abstentions. At most two repairs
follow an initial invalid submission; identical still-invalid calls stop on the
second occurrence. Rejected text/reasoning is not exported; only safe error
codes/fields are retained. Accepted uncertainty is a bounded public scientific
statement, not a private reasoning transcript. Existing M4 assessment rules and
tools are untouched.

References use the prior 300 seconds, strictly before the already-known
retrospective onset, with at least 30 valid observations. Class/state labels are
not used to declare the reference normal or fit its statistics. No future values
reach the calculation. Reference quality and normality limitations are returned
only after the sensor is charged.

## Frozen paired study

`prepare` creates a fresh protocol linked to the unmodified M4 development parent.
It requests six incidents (configurable 5–8), alternating correct/incorrect initial
diagnoses while preferring new classes and wells, with hash tie-breaking. Selection
uses offline development labels/correctness only. This is deliberate outcome
stratification, not a population sample. Selected IDs, class counts, well count,
initial correctness, code/runtime, registry/knowledge/prompt/tool hashes, all model
settings, scoring rubric, reference settings and spending limits are frozen before
new outcomes. Fewer than five cases or a single correctness stratum is rejected.

Every policy receives the same two charged initial statistical observations and
candidate pair. Each selects one test from the same numerical menu, under a
five-sensor cap. Unused budget is not silently spent. Record actual sensor costs.

- **A: information_gain.** Seeded Monte Carlo expected posterior entropy reduction
  per new sensor, 64 draws under the existing fitted diagonal-Gaussian model.
  This is an explicit generative-model approximation, not the old separation
  score renamed. It assumes conditionally independent available summary features
  across sensors and does not model spectral/reference features or missingness.
- **B: muse_no_graph.** Same test computations/sensors, initial evidence and public
  fault descriptions, without the sourced graph facts/example signatures.
- **C: muse_physical.** Adds documented generic physical context, source provenance
  and example limitations before planning. This treatment adds source knowledge,
  not merely a visual graph layout. One stochastic draw cannot establish a causal
  effect of topology.

The original statistical engine updates its posterior using every acquired
sensor's ordinary features in all three policies. These matched-data posterior
updates are reported separately from Muse's test interpretation, preventing extra
measurements from being presented as uniquely LLM reasoning. The conventional
policy makes no physical directional claim; its unknown expectations are recorded.

## Metrics and predeclared gate

Reports include accepted executable test selections, wrong sensor declarations,
tests returning measurements, numeric-interpretation rejection counts, exact
registered example matches (not physical proof), numeric prediction separation,
matched-data classifier correctness before/after, abstentions, sensor sequences,
latency, token/cache counts, estimated cost and complete audit snapshots. Evaluation
also discloses whether the true class lies within the fixed candidate pair; this
label-based coverage check is never sent to the agent. Neither candidate is
guaranteed correct, and a test may appropriately leave both unresolved.

Review packets omit truth/correctness and source filenames. All three methods
receive the same source reference pack for independent review. Human judgments
must bind to a digest of the complete plan, result, assessment and candidate pair.
Review every public claim, not just source IDs. Numeric inequality agreement is
not sufficient to mark a test physically discriminative. The reviewer must judge
physical justification, documented expectations, meaningful discrimination,
interpretation faithfulness, appropriate abstention and unsupported claims.

The frozen gate requires at least six cases, including three initially correct
and three incorrect; at least 80% completion; and independent reviews of every
completed investigation plus all conventional cases. Five-case runs are
exploratory and cannot earn a GO under this gate.

- Planning: at least 80% have both defensible plans and documented expectations;
  at least 50% provide meaningful discrimination; no unsupported planning claims.
- Faithfulness: at least 80% faithful interpretation, no unsupported interpretation
  claims. Mechanical quotation/inequality checks alone cannot satisfy this.
- Comparative value: at least one additional correct matched-data classifier
  diagnosis **or** one additional independently judged discriminating test versus
  information gain. Failed agent investigations receive no comparative credit.
- **GO:** planning, faithfulness and comparative value pass.
- **PARTIAL GO:** planning and comparative value pass, interpretation fails; keep
  interpretation deterministic and use Muse for planning/communication.
- **NO GO:** adequate reviewed evaluation fails these criteria; retain the evidence
  auditor direction. Inadequate sample/review remains **PENDING**.

This is an engineering feasibility screen with small-sample uncertainty, not
statistical confirmation, a production safety claim or population accuracy.
No parameters or criteria may be selected after seeing these outcomes.
The real default six-case metadata-only lock is committed in
[m5-cohort-lock-v1.json](m5-cohort-lock-v1.json): one incident per available class,
three initial successes and three errors across five development wells. Its first
two IDs form the pilot. Runtime/file validation and the final execution protocol
remain local prepare requirements; the lock does not represent a completed run.

## Execution and spending

Preparation is local and free:

```bash
python scripts/evaluate_scientist.py prepare \
  --dataset ../3W/dataset \
  --cohort-from .petromind/challenge-m4-v4/protocol.json \
  --out .petromind/science-m5-v1 --cases 6 --pilot-max-cost-usd 5
```

The paid pilot uses two frozen incidents, one from each correctness stratum:
two conventional runs and four Muse runs. With MODEL_API_KEY exported locally:

```bash
python scripts/evaluate_scientist.py pilot \
  --dataset ../3W/dataset --out .petromind/science-m5-v1
```

Each Muse investigation has eight turns, twelve tool calls, 4096 output tokens per
response, ten HTTP attempts including retries, and the existing run deadline.
The pilot additionally caps the whole study at 40 HTTP attempts, 163840 reserved
output tokens and $5 in conservative estimated-cost reservations by default.
Input reservations use twice UTF-8 payload bytes plus 8192 framing tokens, at
frozen uncached-input prices; output uses the full response cap. Every attempt,
including retries, reserves durably before HTTP. This bounds estimated spending
under the frozen pricing snapshot, **not the provider's eventual invoice**.
Actual usage/cost estimates and unknown attempts are reported separately.

Inspect `report.json`, `review-packets.json`, `review-template.json` and traces.
Completed or failed tasks are not rerun; interrupted task intents block automatic
retry. No paid larger cohort follows a pilot automatically. Only after reviewing
pilot validity, cost and evidence, explicitly request:

```bash
python scripts/evaluate_scientist.py development --reviewed-pilot \
  --dataset ../3W/dataset --out .petromind/science-m5-v1
```

This resumes the same frozen cohort, preserving pilot rows. The separate,
predeclared total-development caps are 120 requests, 491520 output tokens and
three times the pilot dollar reservation cap, counting prior pilot reservations.
A failed pilot blocks expansion. Resume never resets spending limits.

After completing independent judgments in a separate review JSON:

```bash
python scripts/evaluate_scientist.py analyze \
  --out .petromind/science-m5-v1 --cohort pilot --reviews reviews.json
```

Use `--cohort development` for the whole six-case study. Do not edit original
protocols, results or review packets. Any revised instructions need a new protocol.
