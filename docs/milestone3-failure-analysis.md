# Milestone 3 offline failure analysis

Analyzed the user-supplied frozen results on October 27, 2026, with zero API calls.
No original result or protocol file was modified. Reproduce locally:

```bash
python scripts/evaluate_challenger.py offline-m3 \
  --results .petromind/eval-m3-v2/results.jsonl \
  --out .petromind/m3-offline-analysis.json
```

Source results SHA-256:
`81a0cace4fb1eb4c792fa327205eefe916bb9af2508b58e4d3fbf6895fd028e2`.
Protocol ID:
`5e56257bc1ee4383ace4e500375a47a5f0824737a11de76c4d3edd5c549fb23a`.
The supplied protocol, split, report and per-case results agree on 33 cases,
eight test wells, 72 training incidents, five methods and a five-sensor budget.
All 165 unique cells completed; all recorded audits and usage completeness flags
are true. Returned historical IDs are in the training partition, and each
match's sensor names are a subset of that retrieval call's observed names.
These checks use exported records; full audit chains cannot be independently
reconstructed from their final digest/validity flags alone.

| Method | Correct | Unavailable unique queries / 165 | Graph calls | Retrieval calls |
|---|---:|---:|---:|---:|
| sensor_only | 4/33 | 50 | 0 | 0 |
| topology | 1/33 | 50 | 46 | 0 |
| graphrag | 5/33 | 48 | 43 | 41 |
| fixed | 13/33 | 42 | 0 | 0 |
| adaptive | 20/33 | 48 | 0 | 0 |

Reported API cost: $3.68794575; 823 requests. GraphRAG minus sensor-only accuracy
is +3.0 percentage points, with the existing well-bootstrap interval -8.3 to
+31.3 points. It fixed four errors and introduced three. This does not establish
a GraphRAG classification improvement. There are 21 fault-7 cases; fault 6 has
five cases but is absent from training. All methods miss those five cases.

## 1. Repeated P-PDG selection

Observed: every Muse variant queried P-PDG in all 33 cases. The sensor was
constant zero in 26, missing in four and variable in three. This is repeated
selection across investigations, not evidence of repeatedly spending budget on
a cached request within one investigation. Legitimate zeros remained available.
Constant measurements can still be discriminative; these exports do not prove
P-PDG was useless relative to the fitted training distribution.

Unknown: whether Muse selected it from a domain prior, prompt salience, familiar
sensor naming or some other reason. No model-intent transcript is available.
Do not infer a reason simply from the selection frequency.

## 2. Unavailable-query spending

Observed: 29–30% of Muse's unique sensor queries returned unavailable evidence.
Sensor-only requested ESTADO-DHSV unavailable 17 times and P-JUS-CKP unavailable
13 times; GraphRAG's corresponding counts were 22 and eight. The adaptive
baseline also spent 48/165 queries on unavailable evidence.

Mechanism established by code: names are visible, target availability is not.
Every new sensor is charged, including missing readings, with repeated requests
cached. The model cannot know a target's unqueried availability for free. These
records do not establish how many missing queries were avoidable prospectively.
Changing this accounting after seeing outcomes would change the experiment.

## 3. Fault-2 predictions for fault-7 cases

Observed: GraphRAG predicted fault 2 in 15/21 actual fault-7 cases; only two were
correctly called fault 7. For all 15 fault-2 predictions, at least one preceding
retrieval returned a fault-2 incident as its nearest match. Such a nearest match
occurred in 17/21 fault-7 cases overall. The 26 nonempty retrieval calls across
these cases had nearest labels 2 on 21 calls, 8 on four and 7 on one.

This is consistent with retrieval-label anchoring as a hypothesis, but does not
prove it. There is no same-evidence, same-generation counterfactual, and the
agent selected different sensors across conditions. It is equally necessary to
inspect retrieval quality and measurement ambiguity before attributing intent.

## 4. Retrieval evidence quality

Code-level observation: the existing distance is the mean relative difference
of medians over shared available sensors. It ignores temporal shape, variability,
physical constraints and overlap weighting. Equal constant channels contribute
zero distance; matches can differ in how many sensors they share. Returned
training labels are allowed but are not target-label evidence or probabilities.

The exported events establish label association and observed-sensor restriction.
They do not provide unqueried historical waveforms or enough information to
verify physical equivalence. A small distance is not evidence of the same fault.
No retrieval parameters are changed as part of this analysis.

## 5. Contradictory evidence

Not established from these exports. They contain sensor summaries and graph /
retrieval events but no structured supporting-versus-contradictory claims. The
complete per-call traces and original data are not present in this execution
workspace. Even complete tool traces would not establish fault-specific physical
contradictions without domain-grounded interpretation. An incorrect prediction
alone is not proof that the model ignored an observable contradiction.

## Consequences for the new study

Preserve these findings as descriptive failure analysis. No sensor-specific
exclusions, fault-specific instructions, engineered thresholds or retrieval
parameter changes are fitted to these held-out labels. M4 uses generic evidence
quotation/provenance checks and a distinct training-well development split. It
tests whether Muse can substantively challenge a hypothesis, not whether this
same test cohort can be made to look better with a new prompt.

Actual M4 results: **not run**. Dataset and secure Meta credentials are absent
from this execution workspace. Synthetic transport tests validate accounting,
isolation and scoring behavior, not scientific feasibility.
