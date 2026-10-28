# Decision-specific assessment tools v3

The active model-facing contract is `assessment-tools-v3`, documented in
[the schema simplification review](assessment-tools-v3.md). It offers four
decision-specific tools and normalizes their accepted calls into the existing
`assessment-contract-v2.1` result schema. The universal `submit_assessment` tool
is no longer registered or accepted by the agent dispatcher.

The remainder describes the retained canonical evidence validator and its
historical v2.1 introduction. Its provenance, physical-evidence checks and
repair ceiling still apply. The new interface requires a fresh protocol; the
original pilot artifacts remain unchanged.

## Canonical assessment reliability contract v2.1

See the [v2 run review and v2.1 correction](milestone4-v2-review.md). Tool descriptions
now disclose alternative-support rules before submission; alternative errors carry
specific safe type/predicate diagnostics. Integral JSON fault IDs are accepted and
normalized, while strings, booleans and fractional IDs remain invalid.

This is a contract/repair correction, not a new diagnostic strategy. The original
M4 prompt text and scientific gate are unchanged. Tools now specify the required
provenance, evaluated hypothesis, expectation and consistency fields. No paid
post-fix evaluation has run. Review this PR before further paid experiments.

The original v1 protocol, results and traces remain unchanged. The uploaded
archive SHA-256 is `2a20717175e43ac262c785e295bde08ea73542d40d1565382e81d24def8f343a`.
Its full [offline review](milestone4-pilot-review.md) explains both the operational
failure and weak accepted claims. Do not replace or rescore its submissions under
v2 and then present them as original outcomes.

## Actionable errors and sanitized diagnostics

An invalid submission returns, for example:

```json
{
  "error": "invalid_assessment",
  "validation_code": "citation_value_mismatch",
  "field": "claims[0].value",
  "correction": "Quote the exact value from the queried summary without rounding or replacing it.",
  "submission_attempt": 1,
  "repairs_remaining": 2,
  "remaining_budget": 0,
  "contract_version": "assessment-contract-v2.1"
}
```

Codes are stable categorical names. Field paths use schema-controlled names and
bounded claim indices, never unknown model-supplied keys. Correction instructions
are static validator text; they never echo rejected names, values, labels, paths,
prose or unknown fields. They do not reveal the expected value of an unqueried
measurement. Audit entries preserve codes, fields, counters and contract version;
traces and result rows retain these sanitized diagnostics. Report histograms show
error codes and fields. Raw rejected arguments and private model reasoning are
not exported. Accepted evidence interpretations are explicit public submissions,
not private reasoning transcripts.

Malformed JSON, duplicate keys, nonfinite JSON constants, non-object arguments and
arguments over the 8192-character bound get distinct actionable error categories.
The exact rejected payload is not retained. Consequently v1's historical generic
errors cannot be diagnosed retrospectively; the fix improves future observability.

## At most two repairs

The initial assessment may be followed by at most **two corrected submissions**:
three submissions total. This is a Python-enforced cap, independent of turn count.
After the third invalid submission, the run ends with `assessment_repair_limit`.
No fallback assessment or diagnosis is invented. Failed runs remain scored and
are never selectively retried.

A submission that is identical to a previously rejected payload and remains
invalid ends the run immediately with `assessment_repeated_invalid_submission`.
The second occurrence is detected during its tool call; there is no third paid
turn. Canonical JSON detects key-order/whitespace changes in parsed objects.
Malformed arguments use exact-text fingerprints. Fingerprints stay in memory and
are not exported. If new authorized evidence has actually made the same payload
valid, it is no longer an invalid repeat and may be accepted within the repair
budget. Terminal failure seals all tools and cannot be reopened with a later
valid submission. Cached sensor calls do not reset the repair counters.

The three-submission ceiling bounds repairs; the existing run/HTTP/output/turn
budgets also remain in force. The model may consume other turns before submitting,
so this is not a promise of three total HTTP requests per investigation.

## Explicit evidence provenance

Every claim requires:

- `source_id`: an audited measurement source or actually returned verified graph
  relationship source. IDs are supplied in the initial `evidence_sources` context
  and sensor/graph tool results. Source lookup contains only evidence already
  returned to the agent.
- `hypothesis_fault_type`: the public fault hypothesis evaluated by THIS claim.
- `category`: supporting, contradictory, unavailable or uncertainty. The accepted
  result explicitly derives `relationship`: supports, contradicts or inconclusive
  (the last two categories are inconclusive).
- For measurements, the exact `sensor_name`, summary `field` and scalar `value`.
  A source cannot be reassigned to another sensor, even if its value happens to
  match. Missing observations remain charged evidence with unavailable metadata.
- `interpretation`, distinct from the quoted fact. Contradictions also require a
  substantive `expected_if_hypothesis_true` statement. This identifies the claimed
  premise; it does NOT verify that the physical expectation is true.

Measurement source IDs bind to the first charged query's audit sequence; cached
requests return the same ID. A graph source binds to its graph query and exact
returned relationship/provenance. Only edges marked `verified_generic` by the
trusted graph can be graph evidence sources. That marker still does not establish
per-well topology or independently validate its engineering source.

The current equipment graph has **no verified edges**. Its illustrative edges
remain available as navigation/context, and may be listed in the top-level
`relationships` context array when actually returned. They cannot be promoted to
graph evidence sources. No topology or verification flags were invented for this
patch. Synthetic verified-edge fixtures exist only in unit tests.

Accepted results include the cited `evidence_provenance` map, contract version,
`physical_correctness_verified: false`, and required expert-review status.

## Structural consistency

The validator enforces the following submission rules:

- CHALLENGE requires an observed contradiction of the baseline itself. A
  contradiction of another fault does not meet that condition.
- A proposed alternative is separate from the baseline, requires its own
  supporting claim, and cannot be contradicted by another submitted claim.
- SUPPORT requires baseline support and cannot retain an unresolved contradictory
  baseline claim; INSUFFICIENT_EVIDENCE is available for unresolved evidence.
- The same cited fact cannot both support and contradict the same hypothesis.
- Missing readings cannot serve as diagnostic supporting/contradictory readings.
- Generic recommendations such as the pilot's "expert review needed for this
  contradictory observation" are rejected as supporting/contradictory evidence.
  A narrow English lexical guard detects stock generic text; uncertainty claims can
  legitimately request review. Review recommendations are not measurements.

These rules would reject a structurally encoded proposal of fault 2 whose only
claim contradicts fault 2. They cannot detect every case where prose says
something different from its declared hypothesis ID.

## Semantic limits that remain

Exact quotations, source binding and declared direction are mechanically checked.
Physical implication, necessary fault signatures, expectations such as cooling,
causal links, reported certainty and the usefulness of a proposed sensor
query still need domain review. The generic-text guard has limited lexical
coverage and may reject concise useful wording or miss polished generic prose;
it is not semantic understanding. A plausible but unsourced physical expectation
can satisfy the structural schema, so accepted claims remain unverified.

This patch does not supply verified fault-specific rules, normal-operation
reference windows, full raw time series, exact well topology or statistical feature
attributions. Adding any of those would be a separately documented experiment,
not a reliability fix fitted to known pilot labels. Confidence remains subjective
and uncalibrated. No GO or PARTIAL GO follows from improved validator compliance.

## Protocol preservation

New protocols freeze `assessment_contract_version` and `assessment_repair_limit=2`.
Old protocols cannot resume against changed code. The existing
`prepare --cohort-from OLD/protocol.json` path can create a fresh reliability
revision, preserving original cases, IDs, pilot and method order, initial
hypotheses/evidence, model, original diagnostic policy, runtime, prices and scientific gate.
The new tool-selection sentence and full tool schemas are separately versioned
and hashed; see the v3 review. It links
the parent and copies no outcomes. This option does not authorize a paid run;
review the validator/repair changes first. Never edit v1 or retry only its failure.
