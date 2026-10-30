# Instrument landscape and explicit Muse result

The guided experience still has three scenes and two main-action clicks to the
verdict. This refinement adds instrument context and a concrete investigation
result, without changing model instructions or any frozen experiment.

## Three tiers

**12 indicators are displayed in the illustration.** The layout is explanatory;
functional grouping and coordinates are not verified individual-well topology.

| Tier | Sensors | Presentation |
|---|---|---|
| 1: claim evidence (2) | P-PDG, P-TPT | Large friendly names, selected value, signed change, colored well marker |
| 2: gas lift (2) | ABER-CKGL, QGL | Small opening/flow indicators |
| 2: production equipment (4) | ABER-CKP, P-MON-CKP, P-JUS-CKP, ESTADO-SDV-P | Small opening, pressure and reported-state indicators |
| 2: other well instruments (4) | T-TPT, T-PDG, ESTADO-DHSV, P-ANULAR | Small temperature, reported-state and pressure indicators |
| 3: inventory (27) | Entire existing documented sensor catalog | Optional All sensors drawer, grouped by type |

The inventory groups are **10 pressure, 4 temperature, 9 valve/equipment state,
and 4 flow/opening/other channels**. Each row shows a friendly name, raw ID,
incident-column presence, whether Muse received a summary, window availability
and the selected reading/status. Category shortcuts and optional Inspect buttons
keep this detail out of the hero composition.

## Actual data versus audit evidence

When the existing private mapping/fingerprint/window checks succeed, the viewer
may inspect all 27 allowlisted measurement/control channels in that same real
600-sample diagnostic window. The original three captured channels stay in
`series`. Other channels are explicitly separate in `viewer_series`, and never
enter the immutable capture packet, live Muse input or query accounting.

All displayed nodes read the selected real sample. Orange ↑ means higher than
the first valid observation, blue ↓ lower, gray → unchanged; missing, absent and
unobserved states remain distinct. Colors are not safety thresholds. Reported
valve codes are numeric sensor readings, not independently confirmed actuator
positions. No interpolation, filling or unrecorded time-series behavior is added.

Presence and availability are separate: a present all-missing column is not an
absent column. Without raw data, column presence remains **unknown** unless a
valid captured observation establishes presence. A channel not supplied to Muse
is not automatically missing from the incident. Unknown/unobserved indicators do
not animate or acquire guessed values.

**Raw data is unavailable in this workspace for both captured incidents.** The
screenshots therefore contain genuine first/last-valid summary values for the
three original channels and unobserved placeholders elsewhere. Play is disabled.
The complete inventory reports unknown presence for the other channels. Synthetic
fixtures validate raw-channel behavior in tests and never appear in demo images.

## What Muse contributes

Scene 3 now presents four concrete sections:

1. **What the model suggested:** the original statistical hypothesis, without a
   calibrated-likelihood claim.
2. **What Muse checked:** measurements, retrieved engineering sources and whether
   the causal conclusion follows. This is an editorial work map, not an invented
   tool chronology or private reasoning transcript.
3. **What Muse concluded:** supported observations beside the unestablished causal
   claim, plus an exact excerpt of the unchanged captured justification.
4. **What would be needed next:** applicable well documents, validated criteria and
   an explicit statement when no discriminating rule/test has been supplied.

The second case still supports the narrow published-example comparison. Missing
premises for a stronger causal conclusion do not invalidate that comparison.
Full model outputs, provenance, retrieved analogues and scope annotations remain
in Explore evidence. Independent engineering review remains pending.

## Verification

365 pytest tests passed, including new checks for the 27-channel allowlist,
unknown/absent/all-missing distinctions, real viewer-sample projection, valid zero
codes, unchanged captured evidence and no viewer fields in mocked live requests.
Browser checks cover 12 indicators, inventory grouping, extra viewer-channel
updates, both captured cases, desktop/mobile layout, original-output equality,
fixed verdicts and no paid requests. Mobile stacks the result vertically with an
easy-to-reach action; desktop fits at 1440×900. See [screenshots](screenshots/).

Run with the existing demo command; no new dependencies or infrastructure are
needed. Captured protocols/results remain unchanged. Any separately authorized
live execution continues to require a fresh code-matching protocol.
