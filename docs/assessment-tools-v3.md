# Decision-specific assessment tools v3

This change addresses the v3 pilot's submission failure, without changing the
statistical policy or diagnostic strategy. The reviewed archive
`467106c59a977f23ce742fa89f3d3c0c7debf58732eed629b2ac5b686c737a43`
contained 16 rejected attempts: 13 `alternative_not_allowed_for_decision` and
three repeat rejections with that underlying code. All had a non-CHALLENGE
decision and a non-null alternative. Fourteen alternatives were strings and two
were integers; exact rejected string contents were not retained. Those attempts
failed before evidence validation, so they cannot establish diagnostic quality.

## Submission paths

| Tool | Required top-level arguments | Canonical result |
| --- | --- | --- |
| `submit_support` | `confidence`, `claims`, `relationships`, `uncertainty` | SUPPORT, alternative null |
| `submit_insufficient_evidence` | Same four | INSUFFICIENT_EVIDENCE, alternative null |
| `submit_challenge_without_alternative` | Same four | CHALLENGE, alternative null |
| `submit_challenge_with_alternative` | Same four plus `alternative_fault_type` | CHALLENGE, separately recorded alternative |

The first three tools have **no alternative argument**. All tools have no
`decision` argument: the chosen tool supplies the decision. Extra fields,
including irrelevant alternatives even when null, are rejected before
normalization. Unknown fields are never silently discarded. The old universal
`submit_assessment` is absent from the tool list and rejected by dispatch.
Its private canonical validation method remains for internal normalization and
regression tests; it is not a model capability.

Each claim retains all nine provenance/interpretation fields: `source_id`,
`hypothesis_fault_type`, `category`, `sensor_name`, `field`, `value`,
`interpretation`, `expected_if_hypothesis_true`. Source binding, exact values,
quality checks, expectations and returned-graph checks are unchanged.
`uncertainty` explicitly describes missing/inconclusive information and limitations.
`relationships` may be empty; illustrative associations cannot become proof.

The alternative-bearing challenge tool requires a non-null public fault ID and
at least two claims. Python requires a baseline contradiction and a separate
supporting claim targeting the alternative, with no submitted contradiction of
that alternative. A cross-field physical assertion cannot be established by JSON
Schema. Splitting the tools removes optional-alternative ambiguity while retaining
the existing deterministic consistency checks. Unsupported strings are not
coerced into fault IDs. Existing integral JSON numbers remain accepted as before.

Accepted calls normalize to the existing `assessment-contract-v2.1` result:
`decision`, `alternative_fault_type`, unchanged baseline, claims with derived
relationships, and evidence provenance. Additive `submission_tool` and
`tool_contract_version: assessment-tools-v3` fields identify the new interface.
No tool overwrites the statistical diagnosis. Existing reporting still scores
SUPPORT / CHALLENGE / INSUFFICIENT_EVIDENCE and alternatives separately.

## Repair and preservation

There is one investigation-wide limit: initial submission plus at most two
repairs, shared across all four tools. An identical still-invalid call to the
same tool fails on its second occurrence; changing JSON key order does not evade
this check. Choosing another tool does not reset the counter. Successful or
terminally failed investigations remain sealed. No invalid assessment becomes a
successful abstention. A valid abstention must itself be explicitly submitted
with observed citations and uncertainty.

Errors and audit records retain only allowlisted validation metadata for rejected
submissions, including the tool and contract versions. Rejected prose, values,
unknown keys and private reasoning are not saved. The evaluator collects rejected
attempts from every new tool. The shared five-sensor cap, two initial statistical
queries, training-only retrieval, hidden-label isolation and generic equipment
graph are unchanged. No M3/M4 data, original protocol, results or trace was edited.

## Fresh protocols

The model-facing contract is `assessment-tools-v3`; the instruction version is
`petromind-challenger-v2-tools`. The historical diagnostic policy constant remains
byte-identical. Actual model instructions replace only its obsolete submission
sentence with the new tool names and their argument rules. New protocols freeze:

- `prompt_digest`: the original diagnostic policy, retained for cohort continuity.
- `model_instructions_digest`: the complete instructions actually sent now.
- `tool_contract_version` and `tool_schema_digest`: all variant tool definitions.
- Existing code/runtime/data hashes, assessment result contract and repair limit.

Protocols lacking or differing in these new interface fields are rejected before
execution. `prepare --cohort-from OLD/protocol.json --out NEW_DIRECTORY` creates a
new protocol linked to its parent, preserving cohort IDs, initial hypotheses and
evidence, pilot/method order, fit/retrieval split, configuration and scientific
gate. It neither edits the parent nor copies previous results. Use the parent's
case and pilot counts. Preparation is local and makes zero API requests.

After code review, a separate decision is required about a tightly bounded live
development pilot. This PR does not run or authorize the full cohort.

## Offline validation and limits

The complete suite passes **264 tests**. Four dedicated HTTP-mocked agent
interactions submit each decision tool successfully in one request each, normalize
the result, preserve provenance/budget, and seal the session. These use synthetic
fixtures and `httpx.MockTransport`, not Meta or real incident evidence. Additional
regressions cover missing citations on every path, absent/unsupported/conflicting
alternatives, exact repetition, malformed arguments, shared repair exhaustion,
valid missing-measurement abstention, explicit abstention repair, removed-tool
rejection, label isolation, fresh protocols and sanitized evaluator diagnostics.

The interface is substantially simpler **per submission**: four required fields
for the first three paths versus six previously, and five for a proposed
alternative; there is no redundant decision or nullable alternative choice.
The nine-field evidence claim remains deliberately detailed. Four tool definitions
increase the combined submission-schema size from 3,531 to 11,178 compact JSON
bytes in the sensor-only variant. This is a reliability tradeoff, not a claim of
reduced prompt tokens or API cost. No live compliance improvement is established.

Structural checks cannot prove physical expectations, the validity of a claimed
support/contradiction, calibrated confidence, causal attribution, or useful fault
investigation. Those still require expert interpretation. There are no newly
verified topology edges or physical rules. Successful mocked submissions justify
reviewing the interface, not a GO decision for the scientific hypothesis.
