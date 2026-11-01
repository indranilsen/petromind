# Atomic findings and composite assessments (v5)

The successful live006 run is preserved unchanged: six requests, 27.4 seconds and
$0.06248955 estimated usage cost. Its recorded overall and causal-finding labels
remain PARTIALLY_SUPPORTED. It is not retrospectively passed through v5, edited,
or republished as a corrected model result.

## Correctness change

New live runs use `claim-auditor-v5-active-atomic` or
`claim-auditor-v5-scope-atomic`. The three-field submission shape remains
`verdict`, `findings`, `numeric_observations`. No new required fields are added.
Each finding must describe one independently assessed proposition within its
existing scope:

- `measured_observation`: what supplied measurements establish.
- `documented_comparison`: the narrow comparison an actually retrieved source establishes.
- `diagnostic_conclusion`: the inference to a cause or fault-discriminating conclusion.

Atomic verdicts are SUPPORTED, NOT_ESTABLISHED and CONTRADICTED. A composite
finding must be split rather than marked PARTIALLY_SUPPORTED. The overall verdict
summarizes the **conjunction of the submitted propositions**, not fault probability:

| Atomic findings | Required overall verdict |
| --- | --- |
| All SUPPORTED | SUPPORTED |
| All NOT_ESTABLISHED | NOT_ESTABLISHED |
| SUPPORTED and NOT_ESTABLISHED | PARTIALLY_SUPPORTED |
| Any CONTRADICTED | CONTRADICTED |

An incorrect aggregate is rejected with the expected aggregate; neither Python
nor the UI rewrites submitted findings. Contradiction still requires actual
cited contrary evidence. The schema does not represent disjunctions or a
probabilistic root-cause claim.

The current registry supplies no verified fault-discriminating causal rules.
Consequently v5 rejects SUPPORTED findings declared as diagnostic_conclusion.
A source-backed mechanism description is a documented fact, not proof that the
mechanism caused this incident. A fault-8 production-line hydrate example cannot
substantiate fault-9 service-line hydrate. The model is explicitly instructed to
separate necessity from sufficiency and compare only actually observed features.
A supported comparison can match two reported directions without establishing
the entire published signature (including unobserved downstream measurements).

Provenance, returned-citation membership, numeric equality, source/scope checks,
missing-premise requirements, six turns, eight tools, two repairs at most, repeated
invalid-submission stopping and the shared five-sensor budget remain enforced.
A small overridable aggregation hook retains the original membership rule for
v1–v4; their session behavior and model-facing contracts remain unchanged.

## Presentation and scientific limits

The final panel separates sensors, source comparisons and causal gaps. Every
proposition is labeled **Claim assessed**, with its recorded verdict, explanation
and missing premise. Older causal PARTIALLY_SUPPORTED labels get an explicit
presentation warning: they are unchanged and do not mean partial proof of cause.
Findings without a declared scope are grouped by recorded measurement/documented
basis where available; otherwise they remain Other recorded findings, not inferred
causal findings. The UI does not compute a replacement verdict for any recording.

Mechanical checks cannot establish that prose is atomic, correctly scoped,
physically entailed, or an adequate discriminating test. A model could mislabel
causal prose as an observation/comparison. Such a semantic error still requires
source-based human review; Python does not certify it. The old live006 causal
label and its necessity/sufficiency ambiguity remain in the original artifact,
with presentation qualification. No new model efficacy claim follows from v5.

## Regression and browser verification

`tests/fixtures/live006-public-assessment.json` contains the successful run's
unchanged public assessment, originally supplied summaries and returned source
facts, with the uploaded archive SHA-256. No hidden target labels, original paths
or well identities are included. Tests build separate in-memory proposed v5
inputs; these are not new model outputs and are never written back to the run.

```bash
python -m pip install -e '.[test,agent,audit]'
python -m pytest -q
```

With Playwright and Chromium installed, run the offline final-layout check:

```bash
python scripts/verify_atomic_assessment.py \
  --capture .petromind/claim-audit-v1 \
  --screenshots .petromind/atomic-assessment-screenshots-v1
```

Use a fresh screenshot directory. If using a separately installed Chromium binary,
add `--browser /path/to/chromium`. Screenshots prominently label the unchanged
recorded-v4 input versus constructed-v5 expected-contract input. The latter is
an offline UI fixture, never a successful new Muse run. No tool chronology is
invented by this layout check, and no model calls are made.

## Run the demo after merging (no paid calls)

Stop the old server, then:

```bash
git pull --ff-only
python -m pip install -e '.[test,agent,audit]'
python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --monitoring .petromind/monitoring-demo-v1
```

Open http://127.0.0.1:8765/demo and hard-refresh. Captured playback remains
unchanged; only its final presentation is grouped. Do not pass an old
`--enable-live` directory after this source change.

No paid calls are part of this PR. For a separately authorized future investigation,
prepare a fresh directory, for example `readiness-live-007`, using the existing
prepare-live procedure with a $2 conservative reservation cap. Verify that it
reports v5. Do not reuse, edit or overwrite live004, live005 or successful live006.
