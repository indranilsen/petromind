# PetroMind: a guided physical investigation

The defining sequence is: **the readings changed → a diagnosis sounds plausible
→ Muse identifies the premise that the evidence does not establish**. Five
clickable scenes explain the well, show the change, present the diagnosis, inspect
the actual captured audit, and state the bounded verdict. No new model experiment
or claim of physical certification is introduced.

## Run

```bash
python -m pip install -e '.[test,agent]'
python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json
```

Open http://127.0.0.1:8765. `--dataset` and `--science-protocol` use the paths shown
by default. Replay remains usable without either: it explicitly falls back to
captured first/last valid values, with Play disabled. An existing but mismatched
source protocol or changed raw file fails closed rather than showing a guessed
replay. The source capture is required and is not redistributed with the repo.

The physical schematic is our own explanatory SVG. Original source descriptions
were checked against the [3W author manuscript](https://arxiv.org/html/2507.01048v1),
particularly Table 2 sensor definitions, Table 3 units/valve encodings and Figure 3.
The existing registry also pins dataset.ini blob
`4c4799e80e04a9cf8b10cb3f9a23f1c487797cc9`. Generic associations are documented;
individual-well tag correctness, geometry, depth, pipe routing and the exact
configuration are not verified. Section 2.5 explicitly notes unverified original
tag contextualization and pre-conversion units. No new fault-propagation path is
asserted by the drawing.

## Sensor and relationship inventory

| Identifier | Friendly name / quantity | Documented unit | Generic documented association | Exposure |
|---|---|---|---|---|
| P-PDG | Downhole pressure | Pa | Pressure at permanent downhole gauge | Captured summary; raw viewer stream only when verified |
| P-TPT | Tree pressure | Pa | Pressure at subsea-tree transducer | Captured summary; raw viewer stream only when verified |
| ABER-CKGL | Gas-lift choke opening | % | Opening of gas-lift choke | Captured summary; raw viewer stream only when verified |
| T-PDG | Downhole temperature | °C (`degC`) | Temperature at permanent downhole gauge | Definition only; not queried in these audits |
| T-TPT | Tree temperature | °C (`degC`) | Temperature at subsea-tree transducer | Definition only; not queried |
| QGL | Gas-lift flow | m³/s | Gas-lift flow | Definition only; not queried |
| ESTADO-DHSV | Safety-valve state | Dimensionless | Encoded DHSV state | Definition only; actual valve position unknown |

Each definition carries the exact location/unit fact, locator, source/version and
scope. Pressure cards/charts display MPa for readability, explicitly computed as
Pa ÷ 1,000,000; the selected sensor panel also shows its canonical Pa value. Unknown
units are labeled unknown rather than guessed. Valve encoding is 0 closed, 1 open,
0.5 other, per Table 3. It does not establish an actual actuator position, and
hidden operational `state`/`class` labels are never substituted for readings.

**Illustrative only:** sea/seabed placement, depth, equipment silhouettes, component
coordinates, wellbore shape and dashed pipe connections. Solid sensor callouts
represent generic documented equipment associations, not surveyed coordinates or
verified hydraulic paths. Sensors outside the charged set have definition buttons
marked “not in audit”; no value is inferred for them.

## Raw-data mapping and timing

`incident_replay.py` is a trusted server-side adapter, never an agent tool. It:

1. Checks the private M5 protocol and parent protocol hashes against the captured
   claim protocol's source identifier.
2. Resolves the captured opaque case ID to its frozen development record, requiring
   development membership and exclusion from fitting/original test wells.
3. Resolves that record's opaque relative-path hash. It does not guess an event
   from a class-bearing filename or choose a file by its fault directory.
4. Verifies the well-group hash, file fingerprint and existing loader's diagnostic
   window. The trusted retrospective loader uses the original transient onset;
   labels remain private and are used neither for display nor new model fitting.
5. Verifies that each charged sensor's full-window summary equals the captured
   evidence. Only those sensor series and actual timestamps are exported.

A raw window is exactly **600 ordered observations at 1 Hz**, with **599 seconds
between first and last**, using original timestamps with their encoded timezone
(or explicitly unspecified timezone). No downsampling, resampling, missing-value
filling or generated measurements occurs. Chart segments connect adjacent valid
samples and break at missing/invalid positions. Playback at 10× or 30× advances
that many recorded samples per wall second; all 600 remain in the slider/chart.
Display-frame skipping is not dataset downsampling.

Colors and symbols describe change from each sensor's first valid window sample:
blue ↑ rising, purple ↓ falling, teal → numerically unchanged, gray — missing,
amber ! invalid. They are not normality, risk or danger classifications. The
existing magnitude guardrail is numerical, not an engineering safety threshold.
Zero values are valid. An earlier reference is not certified normal operation.

Without raw data, the slider has only two discrete positions. First/last **valid**
summary values can occur at different unknown instants for different sensors;
they are not presented as synchronized timestamps. The chart has separate endpoint
dots and no connecting trace. Play/speed controls are disabled.

## Availability and agent boundaries in this implementation

| Captured example | Workspace raw availability | What is actually displayed here |
|---|---|---|
| Fault-9 causal-claim audit | `../3W/dataset` absent | Actual captured endpoint comparison; no continuous replay |
| Fault-2 published-example comparison | `../3W/dataset` absent | Actual captured endpoint comparison; no continuous replay |

Raw loading is tested using explicitly synthetic Parquet fixtures. This is adapter
validation, not evidence that the real raw windows were loaded in this workspace.
On the user's machine, each case is independently verified at startup; the badge
states “Real samples · viewer only” only after successful verification.

Muse actually received P-PDG, P-TPT and ABER-CKGL **summaries** and the constructed
claim, plus the logged document/history tool responses in the grounded condition.
For fault 9, retrieved facts describe service-line hydrate obstruction; they do
not provide a necessary/specific joint-pressure rule. For fault 2, the retrieved
published example supports the two-direction comparison. Historical overlap is
shown explicitly (3,3,1 versus 2,2,2); distances are not fault probabilities.

The explanatory schematic/definitions are viewer context, not retroactively
claimed as consulted by Muse. A raw series, if available, is **post-hoc viewer-only
visualization** of already charged sensors. It is never attached to `case.packet`
or live agent input. No extra sensor channels are exposed by the adapter. Moving
the slider changes neither the original five-query accounting (three charged here)
nor the immutable captured audit verdict. No ground-truth reveal is implemented.

“Editorial guide” and the final large summary are labeled as such. Exact original
model outputs, actual tool order (including repairs), citations and protocols are
inspectable. We do not simulate private reasoning, live typing, or invented calls.
The live v2 integration and loopback/Origin/Host/CSRF/CSP protections are retained;
it remains disabled by default and needs a new versioned protocol after code
changes. No paid API calls were run for this redesign.

## Verification and screenshots

```bash
python -m pytest -q
# Optional real-browser check against a running replay server:
python scripts/check_claim_demo_browser.py \
  --url http://127.0.0.1:8765 --screenshots .petromind/guided-screenshots
```

363 offline tests passed. Chromium checks cover both actual captured examples at
1440×900 and 390×844, all five scenes, endpoint controls, sensor selection, original
output equality, actual tool order, and verdict immutability under cursor changes.
A separate `--test-synthetic-raw-controls` option exercises Play/Pause, missing and
invalid states and broken chart segments using an explicitly synthetic routed
fixture. It is never saved as a real-data screenshot or shipped as replay data.

Screenshots in [screenshots/](screenshots/) show **actual endpoint-mode evidence**,
not synthetic raw telemetry. No raw dataset, private protocol or credentials are
committed. The 30-second understanding target is an interaction/design acceptance
check, not a measured user-study result.
