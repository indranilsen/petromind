# Replay and explanation refinement — PR #15 snapshot

This records the earlier five-indicator implementation. The current 12-indicator,
27-channel viewer extension is documented in [instrument-landscape.md](instrument-landscape.md).

The three scenes, two-click path, visual style, backend and frozen captures remain
unchanged in scope. This pass adds instructive context rather than a new layout.

| Change | Why it helps |
|---|---|
| Always-visible pressure values and signed differences | Scrubbing has an immediately readable numerical effect. |
| Warm/orange higher, cool/blue lower, gray unchanged; muted/dashed unavailable | Both label and well marker visibly change; arrows/text prevent reliance on color. The legend says these are changes, not danger states. |
| Five indicators with two levels of prominence | Two pressures lead. Choke opening is a real third measured channel; two temperature indicators add context while explicitly disclosing that no readings were supplied. |
| Diagnosis shows observed changes, definition and conditional plausibility | A first-time viewer can understand the proposed restriction without treating it as an established fault-specific pressure rule. |
| Three-check Muse guide before the large verdict | The viewer sees the job: read measurements, consult engineering sources, check the causal leap. It is an editorial guide, not a fabricated tool chronology. |
| Plain missing-premise statement and exact captured excerpt | The model's contribution is the unsupported leap, not arithmetic or a new fault diagnosis. Full original output remains inspectable. |

## Evidence boundaries

The server still exports raw samples only for the three already charged channels
and only after private mapping and full-window verification. No new channels,
labels, paths or measurements were added to agent input. Raw data is absent in
this workspace: screenshots therefore use genuine captured first/last-valid
values and disabled Play, never generated intermediate points.

- Fault-9 claim: P-PDG 24.103160 → 24.394920 MPa; P-TPT 10.272620 →
  10.604840 MPa; choke opening 53% → 53%.
- Published-example case: P-PDG 35.200490 → 35.625110 MPa; P-TPT 19.954790 →
  13.033210 MPa; choke opening unavailable.
- T-PDG and T-TPT have no measurements in either captured audit. They remain
  dashed/unobserved at every slider position, even if other raw channels exist in
  a local source file. No free observations are introduced.

Primary color encodes comparison with each sensor's first valid observation,
not a derivative between adjacent samples, a normal reference or a danger limit.
The radius is a capped visual encoding of relative change, not calibrated risk.
Endpoint comparisons may use different first/last valid instants per sensor;
timing details remain inspectable. Raw mode retains actual one-second timestamps,
no interpolation, all 600 samples and the existing 10× playback rate.

The restriction explanation is explicitly a conditional hypothesis. It supplies
no verified well-specific pressure rule. Muse's displayed quotation is an exact
first-sentence excerpt of its captured justification; complete findings, source
scope, repairs and original outputs remain unchanged in the evidence drawer.

## Validation

363 offline tests passed. Chromium checks cover both genuine captured cases at
1440×900 and 390×844, all three scenes, start/end differences, marker classes,
optional charts, percent units, unobserved channels, two-click verdict access,
modal focus, original-output equality and verdict immutability. A separate
synthetic widget fixture checks raw Play/Pause, actual selected-sample formatting,
zero values, increasing/decreasing colors, constant measurements and gap handling;
it is not used for product screenshots or scientific claims.

Screenshots were reviewed for hierarchy and readable mobile labels; see
[screenshots](screenshots/). All desktop scenes fit without scrolling and main
mobile actions remain visible. No paid calls or frozen-result changes were made.
This is not a measured comprehension study or independent engineering review.
