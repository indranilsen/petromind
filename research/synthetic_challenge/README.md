# PetroMind independent synthetic industrial challenge

A 40-minute producing-well outlet incident and seven controlled evidence tasks.
This is a synthetic-model reasoning benchmark, not industrially certified physics
or a new Petrobras dataset. All files are synthetic except attributed source
paraphrases. The constructed classifier score and historical similarity score are
not calibrated probabilities or measured model results.

The investigator must separate measured channel behavior, document comparisons,
conditional hydraulic conclusions and material identification. Public case IDs
carry no cause, variant letter or reference verdict. All cases share one incident;
the different tasks and evidence conditions are correlated by construction.

## Start here

`public/index.json` lists case IDs. Open `public/cases/{case_id}.json` for the
initial packet, exact atomic statements, synchronized samples, units, simultaneous
error bounds, quality flags, model premises and sensor catalog. The 5-sensor
budget counts initial channels, unavailable requests and frozen requests. Repeated
queries are cached. It is not a five-tool-call budget. A case with withdrawn
calibration assurance must be interpreted using its case-local model, not the
common `model.json` default. Calibration-unverified channel numbers remain channel
observations; their error bounds do not certify the true physical pressures.

`public/documents.json` contains attributed paraphrases and source locators.
`public/graph.json` supplies typed nodes and connected relationships, each with
provenance, epistemic status, assumptions and scope. Observed-measurement graph
nodes contain references only; a graph lookup cannot reveal unqueried values.
`public/history.json` is a permitted, explicitly constructed historical analogue.
`RUBRIC.md` freezes scoring before any model evaluation.

The separate PRIVATE evaluator package contains the generator, numerical checks,
answer key, hidden sensor vault, scorer and deterministic algebraic baseline.
It must never be checked into Git, given to an investigator, mounted in its
runtime, embedded in prompts, or used as a retrieval corpus. Reproducibility code
is intentionally private because its cause parameters reveal the generating
process. The owner has a separate durable copy. Public inputs and the private
package have independent SHA-256 commitments in `FREEZE.json`.

## Trusted adapter contract

Load `adapter.py` by path; it has no third-party dependencies. Construct
`ChallengeSession(public_root, case_id, read_sensor)` in a trusted host.
`read_sensor(sensor_id)` must return ONLY the selected measurement payload from
a case-specific vault, never reference answers. It must have no network access.
Only serialize `packet()` and `call(name, arguments)` responses to the agent.
Never expose Python objects, callbacks, source files or filesystem access.

| Tool | Arguments | Result |
|---|---|---|
| query_sensor | sensor: catalog ID | id, sensor, unit, absolute_error_bound, samples |
| read_document | id: document ID | scoped public source paraphrase |
| lookup_graph | node: exact node ID, hops: 1 or 2 | <=40 connected public edges |
| search_history | empty object | constructed public analogue |
| submit_audit | verdict, findings, numeric_observations | accepted assessment or bounded validation error |

Findings use the current v5 field names: `statement`, `scope`, `premises`, `basis`,
`verdict`, `citations`, `missing_premise`, `next_evidence`, `justification`.
Use each supplied atomic statement exactly once to match it to its private
reference; no new required `claim_id` field. Atomic verdicts are SUPPORTED,
NOT_ESTABLISHED, CONTRADICTED. Overall aggregation follows v5 conjunction semantics.
`next_evidence` retains kind/target/purpose. Numeric observations retain
sensor/metric/value: use `metric="t_s:<integer>"` and an exact observed raw value.
Derived interval calculations belong in the justification, with measurement IDs.

This preserves the assessment shape, not the legacy domain policy. Existing v5
rejects every supported diagnostic conclusion because its original registry has
no verified discriminating rules. This standalone adapter permits conditional M1
conclusions. Do not pass this benchmark through that legacy validator or alter
its rules; record `synthetic-physics-v1.1` as the separate contract version. Existing
scoring and presentation code need not be changed to import the serialized shape;
benchmark scores must use the frozen rubric and isolated evaluator, never the
33-incident classifier score.

A host must run tools sequentially. Maximum 24 calls, three submission attempts
(initial plus <=2 repairs), then closure. Hash-linked audit events include the
initial packet, arguments, exact results and accepted assessment. Keep the log in
the trusted host and commit its final digest externally; hashes detect changes
relative to that commitment, not a forged full transcript by an untrusted host.

## Verification and baseline

Run `python -m pytest -q research/synthetic_challenge/tests` from the repository.
Owner-only reproduction instructions are in the private package. Baseline rules
are fixed: use endpoint simultaneous error intervals and M1 algebra; retrieve the
scoped documents and analogue; request independently calibrated flow when testing
a drift-only explanation; refuse material identification without material evidence.
Its parser recognizes the benchmark's explicit proposition templates; it is a
transparent arithmetic/interface baseline, not a general-language competitor.

Do not run any model until both package hashes and the rubric are frozen. No
model calls, credentials or payment paths are included. Never tune this version
against model results. Correct a genuine benchmark defect with a new version and
an explicit changelog; retain the original frozen artifacts.
