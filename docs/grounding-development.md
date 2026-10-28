# Bounded grounding development experiment

This adds optional capabilities and a zero-API comparison. It does not enable a
new paid cohort, replace prior experimental policies, or change assessment tools.

## Sources and graph

`petromind/knowledge.py` contains paraphrased facts from Petrobras' 3W 2.0.0
configuration and the authors' immutable [preprint v1](https://arxiv.org/html/2507.01048v1).
The corresponding published work is [Scientific Data, DOI
10.1038/s41597-026-07225-z](https://doi.org/10.1038/s41597-026-07225-z).
The publisher's full text could not be fetched directly in this session; factual
extraction uses the accessible primary author manuscript, with exact table/figure
locators. The repository's structure documentation was also checked for metadata
leakage risks. A second paper, [Vargas et al. 2019](https://doi.org/10.1016/j.petrol.2019.106223),
was checked through its publisher record for historical context; no additional
physical rule was extracted from inaccessible full text.

The graph exports typed nodes and immutable fact records with IDs, provenance,
status and scope. Units, observation locations and valve encodings are documented
metadata. Example signatures remain scoped to the published figures. Generic
sensor placement does not establish a complete well configuration. No undocumented
engineering hypothesis or fitted correlation is represented as verified physics.
The original `equipment.py` graph stays intact.

Inspect the graph without any dataset or model calls:

```bash
python scripts/evaluate_grounding.py knowledge
```

## Training-derived availability policy

The new optional policy multiplies the existing statistical separation score by
the fitting-only availability fraction. Rates are averaged within each well, then
across wells, so wells with more incidents do not dominate. Ties prefer higher
training availability, then the existing deterministic sensor order. No labels
are consulted in fitting these rates, and constant/zero readings remain available.
This is an empirical query-yield heuristic, not a probability of sensor reliability
or a physical expectation. The conventional Gaussian model remains unchanged.

No target quality is inspected before a charged query. Missing requests cost one;
repeats remain cached. Each policy gets its own identical five-sensor cap. The
benchmark records initial two-query and final five-query predictions, missingness,
query sequences and audit checks. It does not give either policy a free target
availability mask. The fitted availability profile can also be supplied to Muse
as an explicitly historical prior, never a target availability assertion.

## Offline benchmark with the existing independent development cohort

Run this on the machine with the dataset. It makes **zero API calls**:

```bash
python scripts/evaluate_grounding.py benchmark \
  --dataset ../3W/dataset \
  --cohort-from .petromind/challenge-m4-v4/protocol.json \
  --out .petromind/grounding-offline-v1
```

Use a new output directory. This is a new offline study linked to the original
unmodified cohort; it is not a resume or reinterpretation of original outcomes.
The parent digest, fitting/development memberships and file hashes are checked.
Original M3 test-well files are excluded **before measurement reads**, including
availability inspection. All fitting and retrieval use fitting wells only;
selected development wells remain excluded from both. No held-out class is used
to choose parameters or thresholds.

Before scoring, the new manifest freezes code/runtime, knowledge digest, parent
ID, selected IDs and the following predeclared comparison:

- Original versus availability-weighted adaptive selection, two/five queries.
- Original median-distance retrieval; at least two shared observations; and at
  least two shared observations whose medians vary across fitting incidents.
- Same original charged sensor prefixes 1 through 5 for every retrieval condition.
  A constant target value, including zero, is not itself grounds for exclusion.

The informative-sensor criterion is only variation in the feature used by the
current **median-only retriever**. It does not establish physical informativeness
or class discrimination. Retrieval tests share identical observations at each
prefix. No unrequested historical measurements or identifying metadata are added
to returned matches. Empty retrieval is possible and does not refute a fault.

Outputs are `protocol.json`, `results.jsonl` and `report.json`. Read match coverage,
conditional same-class agreement and unconditional agreement together; same-class
matching is an evaluation proxy, not physical confirmation. The cohort was
outcome-stratified under the original policy, so results are not population
accuracy. Do not choose a winner or revise thresholds using these development
scores and then call the same scores independent confirmation.

The actual v4 archive can also be checked locally:

```bash
python scripts/evaluate_grounding.py trace-audit \
  --archive petromind-m4-v4-review.tar.gz
```

## Optional pre-window reference

`PreWindowReference(frame, diagnostic_start, sensor_names)` selects only rows
strictly before the supplied diagnostic start, within the previous 300 seconds.
It returns count, median and quartiles when at least 30 finite, non-extreme samples
exist. Those numerical limits are predeclared engineering experiment settings,
not physical cutoffs. The existing magnitude filter is only a numerical heuristic.

The start must be supplied by the trusted experiment/operator. In the existing
retrospective protocol, known onset is already part of window selection; no online
onset-detection claim is made. Labels and arbitrary metadata are never used to
fit reference distributions. Changing diagnostic/future samples or their labels
cannot change the reference. A preceding period is always marked
`normality: unverified_pre_window`, even if its class column says normal. Calling
it genuinely normal requires independent operational confirmation unavailable here.

A `GroundedChallengeSession` can receive this reference object. Only a queried
sensor's reference is returned with its charged observation; cached queries remain
free. Unqueried reference distributions are absent from model context. Sensors
without a reference entry return null rather than breaking the investigation.
The baseline and Muse still share five sensor identities across diagnostic and
reference evidence. References are context for review, not new automatic decision
rules. The unchanged assessment contract still quotes diagnostic-window fields;
interpretations involving reference distributions require review, and are not
advertised as mechanically validated reference citations. Reference efficacy is
not included in the baseline/retrieval comparison or claimed from unit tests.

## Context before sensor selection

The optional `GroundedChallengeSession` shares the original session boundary,
assessment schema, repair ceiling and audit chain. After the same two initial
queries and hypothesis binding, `run_challenger` invokes its trusted preparation
hook before the first model request. In graph-enabled variants the hook traverses
the two initial sensors, records those graph calls while three sensor queries
remain, and supplies their results as initial context. Priming is rejected if
additional sensors have already been queried. Sensor-only variants receive no
graph traversals. All variants receive the same public semantics and example
limitations. No extra target measurements are provided with graph context.

The standard session hook is empty, so existing experiments keep their behavior.
The paid evaluation CLI does not yet select this opt-in session. Before any future
paid adapter is enabled, freeze a **fresh live protocol** recording the grounding
version/digest, policy, reference setting and graph-priming treatment. Keep model,
initial evidence and budgets paired; do not reuse v4's protocol. One stochastic
run cannot establish that topology caused different choices.

## Verification and decision

The complete offline suite passes **292 tests**. Tests cover provenance, encoding, unknown facts, scoped example patterns,
source-bound graph citations, label-blind availability fitting, well balancing,
zero/missing/extreme readings, pre-window exclusion, reference access accounting,
training-only retrieval, stricter shared evidence, M3-test file-read exclusion and
graph-before-query timing. HTTP-mocked Muse interactions exercise all three
capability variants. They do not establish useful industrial reasoning.

See the short [evidence-coverage report](physical-evidence-coverage.md) for actual
trace findings, execution limits and the recommendation to focus on evidence
auditing while withholding further paid evaluation.
