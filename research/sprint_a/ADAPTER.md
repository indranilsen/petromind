# Independent frozen-case adapter v1

The exchange is an explicit trust boundary, not a way to ingest an unreleased
answer key. Session B authors and freezes its scenario independently. Session A
imports the released file **without modifying the judgments**. Author/review
attestations are recorded, not treated as software proof of independence or
physical correctness. The importer runs no remote code and fetches no URLs.

Invoke:

```bash
python scripts/research_sprint_a.py prepare \
  --benchmark /path/to/released-frozen-exchange.json \
  --out .petromind/research-a-independent-v1 \
  --max-cost-usd 5
python scripts/research_sprint_a.py offline \
  --out .petromind/research-a-independent-v1
```

This shares the original Session-A $5 ledger, not a new allowance. Do not invoke
the paid pilot until the released benchmark/protocol has been inspected. It will
choose at most two hash-selected tasks if the original named pilot tasks are
absent; this choice is frozen before model output. There is no automatic expansion.

## Top-level exchange

`validate_exchange` in [benchmark.py](benchmark.py) is executable documentation:
unknown public fields fail closed. Required keys:

| Key | Contract |
|---|---|
| `exchange_version` | `sprint-a-exchange-v1` |
| `author` | Reference-author/protocol provenance, never model-generated authority |
| `frozen` | Boolean true; content digest pins the exact released file |
| `isolation` | Hashed `fit_groups`, `development_groups`, `excluded_test_groups`: nonempty, pairwise disjoint; plus `history_provenance` explaining the training-only constructor or independent index evidence |
| `facts` | At most 200 source records with the same provenance/status/scope shape as `PhysicalKnowledge.Fact.public()` |
| `cases` | 1–20 case records, each separating `public`, `reference`, `source`, `history`, `optional_summaries` |

A `public` case has exactly:

- `task_id`: unique opaque 32-character lowercase hex ID.
- `constructed_evaluation_claim`: true. Synthetic claims/data must also be
  explicitly identified as such in their statement/scope; never label them real
  expert diagnoses or actual 3W recordings.
- `observations`: 1–5 **already charged** 3W sensor-name → `SensorSummary.to_dict()` records.
- `baseline`: only the public proposed `prediction` (integer 1–9), never the true cause.
- `candidate_faults`: 1–3 public proposed fault IDs, not private ground truth.
- `claims`: 1–6 atomic `{claim_id, statement, predicate}` objects.
- `scope`: window, timing, measurement/synthetic status and applicability.

No filename, class-bearing path, raw frame, future sample, well identity, target
label, reference verdict or unqueried availability field is permitted here.
Semantic leakage inside author-supplied natural language still requires human
review; a schema cannot prove that text is label-safe.

A `reference` has exactly `name`, `judgments` (claim ID → verdict), `review_status`
and `reference_basis`. Allowed review statuses: `mechanical_source_scope`,
`independent_review_pending`, `external_review_attested`. Verdicts are SUPPORTED,
NOT_ESTABLISHED, CONTRADICTED or UNASSESSED. These fields **never enter the model
context**. Do not falsely attest to external engineering review.

A `source` has `group` (hash in development groups), `partition`=`development`,
and `evidence_digest`. It is private. Held-out test membership is refused.

A `history` row has only opaque `case_id`, permitted `training_event`, finite
`distance`, `shared_sensors`, `matched_sensors`. Matches must be subsets of the
initially observed names. Source/index provenance must establish training-only
membership; the importer cannot independently authenticate arbitrary external
opaque IDs or dataset files from an attestation string. C strips labels; D
retains original training labels explicitly. Raw target metadata is never returned.

`optional_summaries` is either empty (no new measurement tool) or a **complete
backend catalog** for all 27 existing 3W tags, with unavailable channels genuinely
represented as unavailable. It never enters the initial model input. A query
returns one summary and costs one shared budget unit, including missing data;
repeats are free. A partial provider catalog is rejected to avoid a free
availability oracle. The budget is five across initial and new evidence.

## Facts

Each has `id`, `subject`, `relation`, `object`, `source`, `locator`, `status`,
`scope`, `provenance`. Status is documented / engineering_hypothesis /
empirical_correlation. Provenance requires a public HTTPS `url` and `version`,
with optional immutable URL, git blob, authors and license. Do not provide
credential-bearing URLs. The importer does not fetch arbitrary endpoints.

Synthetic scenario assumptions must be identified as assumptions, with their
actual source/author/version and declared applicability; they are not verified
industrial laws. Generic measurement locations are not installed-well topology.
Published examples are not universal fault signatures. An encoded declaration
cannot certify that a synthetic model matches a real well.

## Public formal predicates

These are supplied equally to Muse and the deterministic baseline. They are not
private answer labels and are not automatically extracted from prose:

| Kind | Additional fields | Mechanically assessed scope |
|---|---|---|
| `metric_equal` | sensor, metric, value | Exact received numeric metric; missing ≠ opposite |
| `direction_equal` | sensor, value (-1/0/1) | First-to-last-valid change direction |
| `cross_sensor_constraint` | left_sensor, right_sensor, metric, operator (lt/le/eq/ge/gt) | Measured ordering with compatible documented units, not a fault law |
| `fact` | subject, relation, object, scope | Literal generic definition; stronger well-specific inference not established |
| `example_comparison` | fault_type, sensors | Only named observed directions versus documented example directions |
| `causal_inference` | fault_type, quantifier (necessity/sufficiency), sensors | Current real-data registry lacks a verified discriminating rule; absence here is not universal falsity |
| `history_implication` | sensors | Median analogue alone cannot establish a unique cause |
| `expert_claim` | none | Deterministic baseline UNASSESSED; independent reference agreement and engineering review required |

Use `expert_claim` for a synthetic causal rule or complex reasoning proposition
that this small mechanical language does not implement. Do not misencode it as
one of the easy forms to manufacture a deterministic failure or model success.
Private references are not generated by the tested Muse model. Public prose and
formal predicate must express the same proposition; an independent reviewer must
check that consistency. This harness does not pretend to be a universal physics
solver or broad natural-language entailment checker.

## Model result and evaluation

All Muse variants use the same `submit_findings` schema: atomic IDs/verdicts,
received citation IDs, missing premise, concrete next evidence and concise public
justification, plus exact structured numeric observations if quoting values.
Citations/quotes and unique five-sensor accounting are enforced in Python; semantic
mistakes are recorded for research scoring, never silently repaired into success.
Identical invalid submissions stop immediately; at most two repairs follow the
initial invalid attempt. Rejected bodies and private model reasoning are not saved.

Fixed-reference, evidence-conditioned and source-retrieval metrics are separate.
Missing a source is not automatically bad reasoning, and a source ID is not proof
of entailment. Field presence does not grade premise quality or realistic next
tests. Export reviewer verdicts separately; do not silently rewrite frozen
references or historical outputs after inspection. All conclusions remain
exploratory until independent review and a genuinely unseen comparison exist.
