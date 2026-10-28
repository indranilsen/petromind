# M4 v1 pilot: trace review and operational correction

The supplied pilot archive was reviewed offline; no further API requests were
made. Original protocol/results are preserved. Protocol ID:
`feff763deb7d41592e7742641339aac8068dc1c2a6e367edf333545599275558`.
All eight exported audit snapshots independently pass hash-chain verification.
This is not an independent verification of the original raw sensor measurements.

## Actual execution

Two cases, four conditions: five of six paid investigations completed, plus both
local baselines. Every accepted Muse assessment was CHALLENGE. Total known-usage
cost was $0.79728865 across 89 HTTP requests. There were **55 assessment attempts,
50 rejected**, including 13 rejected attempts in the GraphRAG run that exhausted
its 20 turns. Turns containing rejected assessments account for $0.4786182 of
reported response usage; this is descriptive accounting, not a prediction of
savings from a fix.

The original dispatcher returns only `invalid_assessment` and records `{}` for
rejected arguments, so the agent gets no reason to guide a repair. The invalid
arguments cannot be recovered from these traces. Their exact failure causes,
such as field shape, quote rounding or category mismatch, are therefore unknown.
Do not infer that every rejection was caused by one particular validation rule.
The run demonstrates repeated rejected submissions, not a need for a higher
output-token cap or more turns.

## Assessment quality

The first case's two-query baseline was fault 9 and its actual event was fault 2.
The five-query adaptive comparator predicted fault 1, also incorrect. Sensor-only
and graph challengers proposed fault 2, but correct alternatives do not establish
faithful evidence:

- Sensor-only cited a temperature standard deviation of 16.285553844137194,
  saying variability contradicted an expectation of a constant reading. The
  supplied evidence contains no established constant-temperature requirement for
  the baseline diagnosis. A correct quotation is not proof of that requirement.
- Graph cited DHSV `constant_value = 1.0`, describing it as constant open that
  "contradicts spurious closure alternative", yet proposed that same alternative
  (fault 2). This is an internal inconsistency in the submitted argument,
  independent of the event label. It does not explain a contradiction of fault 9.
- GraphRAG produced no accepted assessment. Its only retrieval returned three
  fault-9 analogues matched on P-TPT alone, consistent with the baseline label.
  The record does not establish an effect on a final diagnosis because none was
  submitted.

The second case's initial and five-query baselines were fault 1, matching its
actual event. All three variants falsely challenged it:

- Sensor-only cited P-TPT median 18,301,285 with the interpretation "expert review
  needed for this contradictory observation", proposed fault 8 and reported
  confidence 1.0. The text supplies no substantive explanation of a contradiction.
- Graph and GraphRAG cited T-TPT median 116.9109 and asserted an expected cooling
  disturbance for the baseline diagnosis. No such necessary condition is
  established by the supplied context. A median alone also cannot establish
  temporal stability; additional queried summaries show small variation but do
  not establish the fault-specific physical expectation.
- Proposed alternatives were fault 8 (sensor-only/graph) and fault 7 (GraphRAG),
  all incorrect for this case.

These are logical/provenance observations, not a qualified petroleum-engineering
review or an assertion that a particular temperature response is impossible.
Expert review remains necessary. No review judgments were fabricated or entered
into the scoring system.

## Graph, retrieval and query efficiency

Every graph traversal happened after all five unique queries were already spent.
The graph therefore could not have caused a subsequent NEW sensor selection in
these runs. Sensor choices differed across variants, but those differences
preceded graph traversal. One stochastic draw still cannot identify a causal
condition effect. The only retrieval call was also after budget exhaustion and
occurred in the failed run; the completed GraphRAG run never used retrieval.

For the incorrect-baseline case, all challenger variants spent two of Muse's
three additional queries on unavailable service measurements (QBS and P-JUS-BS).
No free availability preview existed. For the correct-baseline case, downhole
constant zeros were retained as available with quality flags, as intended.

## Context limitation

Muse receives the initial candidate probabilities, two queried sensor summaries,
quality metadata, public fault names, sensor descriptions/units, shared budget,
and graph/retrieval capabilities. It does not receive verified fault-specific
physical expectations, a pre-incident normal reference window, full raw time
series, per-class feature expectations from the fitted Gaussian model, or exact
well topology. The graph explicitly remains illustrative. Fault names and nearby
training labels do not supply a validated physical falsification rule.

The cooling and constant-temperature expectations in the accepted claims are not
established by the supplied context. This limits what this pilot tests: it shows
poorly supported challenges in the current workflow, not inability of Muse to
investigate under appropriately grounded conditions. A domain-context revision
must be sourced, documented and evaluated separately, not constructed to fit the
known pilot labels. This engineering correction does not change the prompt or add
those missing expectations.

The selection is deliberately outcome-stratified; the existing `enriched` flag
must not be read as a measured increase in error fraction. The initial-baseline
error fraction is 25/29 in the pool and 12/16 in the selected cohort (it decreases).
Five-query error counts are 23/29 and 10/16. Selection remains biased and these
figures are not population accuracy estimates.

## Decision

Keep the full cohort paused. The predeclared scientific gate remains **PENDING**:
the pilot has only one correct and one incorrect baseline, one operational
failure, and no completed expert review. This is not a GO or PARTIAL GO. Neither
better schema compliance nor a correct alternative by itself establishes useful
physical investigation. The present pilot does not justify building the full
challenger product or claiming diagnosis improvement.

## Narrow engineering fix

The follow-up versions the assessment contract, diagnostics and repair control;
diagnostic instructions and statistical policy remain unchanged:

- Preserve exact quotation, prompt text, statistical policy and scientific gate.
  Version the submission contract to add explicit evidence provenance, evaluated
  hypotheses and structural consistency checks; see [the v2 contract](assessment-contract.md).
- Emit categorical validation codes, schema-controlled field paths and static
  correction instructions without reflecting rejected text, sensor names, paths,
  values or unknown keys.
- Allow an initial submission plus at most two repairs, stopping with
  `assessment_repair_limit`, or immediately terminate an identical still-invalid
  repeat with `assessment_repeated_invalid_submission`. This is a scored execution failure, never an
  invented INSUFFICIENT_EVIDENCE decision or fallback diagnosis.
- Freeze the versioned submission contract and two-repair limit in NEW protocols.
- A `prepare --cohort-from ORIGINAL/protocol.json` validation revision preserves
  original IDs, cases, pilot, method order, evidence, split, prompts, model,
  runtime, prices and scientific gate. It links the parent protocol and copies
  no results. A new protocol and full disclosure are required; never edit v1 or
  rerun only its failed condition.

This correction is supported by synthetic transport tests; no real post-fix pilot
has run. It addresses opaque repair loops and structural inconsistencies, not
scientific faithfulness. Inspect
and review the claims before authorizing further live spending. A validation
revision, if undertaken, is development iteration rather than independent
confirmation of the original pilot.
