# Monitoring → checkpoint → statistical diagnosis → Muse investigation

The three pages remain **HOME | DEMO | TECHNOLOGY**. The Console now has an
explicit replay-driven presentation state machine; it is not an alarm detector.
The existing live/captured event model and all experiment records remain unchanged.

## Trigger decision and evidence boundary

We inspected `data.read_incident`, `incident_replay.resolve_window`/`raw_payload`,
`baselines.GaussianEvidence`, `measurements.summarize`, the captured packets, and
the available knowledge package. The local raw `../3W/dataset` remains unavailable.
No historical operational alarm stream or verified time-local alarm criterion is
supplied for these two examples. The trusted loader's transient-window selection
uses private evaluation metadata; it is **not** a time-local detection event.

The classifier uses full-window **median, standard deviation, and change** (the
latter compares median values in the two halves). Neither its evaluation nor the
captured prediction establishes an online early-warning detector. The classifier
is not rerun or refitted by the viewer, and its uncalibrated score is not displayed
as a calibrated likelihood.

We therefore use an explicitly labeled **Demo investigation checkpoint**, not
“Diagnostic alert triggered” or a claimed historical operational alarm.

- **Raw mode:** checkpoint index is `len(recorded_timestamps) - 1`, at the actual
  final timestamp. For the current frozen windows this is sample 600 / index 599,
  599 seconds after the first observation. It is not a chosen pressure threshold.
- **Endpoint mode:** checkpoint is the second supplied captured endpoint. No
  timestamps or intermediate samples are fabricated. The UI says “Captured
  endpoint 1 of 2,” then “Captured endpoint 2 of 2,” and “Timestamps unavailable.”
  The classifier still used the original full-window summaries, **not two values**.
- Counts and elapsed time derive from the loaded data. The Python presentation
  helper computes timestamp differences; the frontend reads those values. A
  seven-position irregular-time software fixture tests that no 600/599/1 Hz
  assumption exists in the UI. Production raw eligibility remains the original
  frozen 600-observation, 1 Hz protocol; that scientific boundary is not relaxed.
- The triangular upcoming marker and vertical line sit at the final position. They
  activate when reached. Relevant pressure indicators gain a restrained outline;
  their measurement-trend colors still mean relative change, not danger or safety.
- Reaching the checkpoint does not establish cause or sufficient physical evidence.
  It only makes the retrospective prediction eligible to be shown.

This rule uses public replay shape/time only, never hidden class labels, wells,
filenames, future observations beyond the diagnostic window or an invented
engineering threshold. Jumping to the last sample is navigation, not a claim that
the operator reviewed all preceding measurements. The counter says **Sample X of N**.

## Presentation state machine

| State | Visible information | Transition |
| --- | --- | --- |
| Monitoring | Well, 12 indicators, 27-channel inventory, counter, elapsed time, upcoming checkpoint | Play or scrub to final position |
| Checkpoint reached | Marker activates; checkpoint notice and relevant sensor outlines appear | Immediately reveal the saved statistical diagnosis |
| Statistical diagnosis | Suspected fault, plain-English mechanism, measured observations, model basis/limitations and the selected execution mode | Explicit **Investigate with Muse Spark** click |
| Muse investigation | Actual received evidence, source lookups, optional v3 sensor queries, historical analogues and evidence assessment | Captured record advancement or actual live stream events |

The checkpoint event and diagnosis reveal are synchronous presentation transitions:
there is no staged inference spinner or fabricated model-processing interval. The
checkpoint notice remains visible when diagnosis and investigation are available.
`data-workflow-stage`/`data-ui-transitions` describe **UI state only**, not model
reasoning or extra audit entries. Before the checkpoint, the result drawer, live
execution controls and all evidence graph nodes are concealed as well as the
primary action. Switching to Inside Muse shows an instruction, not a future result.

Play selects only existing samples based on their elapsed timestamps at 10× speed.
It does not interpolate. Gaps longer than a playback tick hold the last selected
sample until the next recorded timestamp. Scrubbing pauses playback and synchronizes
indicators, optional chart cursor and sample count. The clock is incident-relative;
raw timestamp timezone scope remains as encoded. Viewing a chart is retrospective
visualization and never grants telemetry to Muse.

At a forward crossing the Console brings the checkpoint notice into view where
needed. The operator can then read the diagnosis and choose captured replay or
explicitly authorized live mode. No API request occurs from playback, scrubbing,
case selection, view navigation or reaching the checkpoint.

Scrubbing backward returns to monitoring without clearing the selected incident's
investigation. Forward navigation restores that investigation, including failure
state, without another model call. “Review Muse investigation” opens existing
activity; it is not a paid rerun. “Restart replay” returns to index 0 and keeps the
investigation internally. Selecting a different incident always starts that
incident at index 0; returning to its checkpoint restores its own results. Ordinary
Home/Demo/Technology and Console/Inside Muse navigation preserves the current
incident position; leaving Demo pauses playback. Each page reload starts monitoring.

A real additional sensor request highlights that sensor if it is one of the 12
illustrated indicators; all 27 channels remain available through the inventory,
and the actual query/returned measurement/source link remains in the graph.
Exact well topology, fault propagation and private model reasoning are not invented.

## Run locally (no API key or paid call for replay)

Before merge:

```bash
git fetch origin
git switch feat/monitoring-investigation-progression
python -m pip install -e '.[test,agent]'
python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json
```

After merge, use `git switch main` and `git pull` instead of switching to the feature
branch. Stop any old server first, open http://127.0.0.1:8765/demo, and hard-refresh
(Cmd+Shift+R). Initial index must be zero; no diagnosis or Muse action is visible.
Play/scrub to the end. Check the marker, diagnosis and action. Run captured activity,
scrub back, then forward: the original activity must return without restarting.
Choose the second incident: it must begin at its first sample.

With no raw files you get two endpoints, disabled Play and no historical alarm
timestamp. Move the endpoint slider to the right to reach the comparison checkpoint.
No 600-sample replay is claimed.

## Verify the user's actual 3W files

```bash
python scripts/verify_claim_replay.py \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json
```

For the real browser check, install the development-only browser dependency and run:

```bash
python -m pip install playwright
python -m playwright install chromium
python scripts/verify_claim_replay.py \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --browser-check
```

That command checks the exact private frozen mapping and file hashes, every exposed
scalar/timestamp, all timeline positions, progress/diagnosis gating, chart cursor,
27 inventory entries and privacy separation. It fails on endpoint fallback rather
than counting it as verified raw data. No Meta calls occur.

## Offline verification and limits

```bash
python -m pytest -q
python scripts/check_claim_demo_browser.py \
  --url http://127.0.0.1:8765 \
  --mock-live-capture .petromind/claim-audit-v1 \
  --screenshots .petromind/workflow-browser-check
```

The second command needs the replay server, Playwright and Chromium. It checks
1440×900 and 390×844, both cases, initial zero, forward/backward crossings,
case resets, page/view preservation, immutable captured outputs, and explicit
mocked live success/failure paths. A seven-position timestamp fixture exercises
Play through the checkpoint; an explicitly constructed 600-position fixture tests
all 12 indicators and the chart at every position. Mocked Meta transport verifies
that rewind/forward/review and hidden button clicks do not cause extra requests.
Those fixtures are **not actual Petrobras replay or paid Meta verification**.

Screenshots show genuine captured values and audits in endpoint mode, before/after
the checkpoint, on desktop/mobile. No synthetic raw or mocked model response is
photographed as real telemetry. Actual raw files and paid Meta execution were not
available/executed here. All previous protocols, results and captures remain intact.

The live tools, five-query accounting, isolation and capped spending are unchanged.
Because source is pinned, live use after this update requires a **fresh** protocol;
see [live setup and explicit authorization](live-investigation-verification.md).
No paid call or additional scientific experiment was run for this UI refinement.
