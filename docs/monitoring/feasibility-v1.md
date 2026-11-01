# Causal monitoring feasibility: two supplied recorded clips

This is an offline implementation check, **not validated fault detection**. No
Meta API requests were made. Frozen M3/M4/M5 predictions, claim protocols and
captured Muse outputs are unchanged. The monitoring rule was committed before
reading/scoring ordered values (`aeb843e`, `rule-v1.json`); no thresholds were
changed after seeing the two outcomes. Aggregate history reports had already
been inspected. This is not a preregistered independent trial.

## Data and provenance

The user supplied `history-telemetry-v1.tar.gz`, exported by the merged history
audit. Both Parquet clips have 3,001 actual recorded positions from 0 to 3,000
relative seconds at 1 Hz, 27 sensor channels plus explicit quality/reason flags.
Each spans 1,800 seconds before the private annotation reference and 1,200 after,
inclusive. **Selection is annotation-centered and retrospective**; clip timing
can indirectly disclose selection information. It is not prospectively blinded,
agent-visible history, or independently anonymized data.

The exporter reports checking the original source-file hashes against the frozen
private protocol on the user's machine. Here, the uploaded Parquet checksums and
all three captured original 600-sample summaries match exactly. The full original
3W dataset is unavailable here. We did **not** independently verify its authenticity,
run against all full records, validate a detector on held-out wells, or run paid
Meta integration. This distinction remains in the verification output and UI.

Checksums (offline integrity checks, never evidence of physical correctness):

- Case 1: `b6d4f660df0562ae42251cd125ad43875aadca8b7869c60c6a6750777810bf6a`
- Case 2: `3b67ca9fec54e1966eeca96209957888a803f604929fbd8a9d1d541ac1fff455`

Attribution: Petrobras and 3W Dataset contributors; Vaz Vargas et al., *3W
Dataset 2.0.0*, arXiv:2507.01048v1. Upstream dataset declaration:
[dataset README](https://github.com/petrobras/3W/blob/main/dataset/README.md),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Changes: bounded slicing, relative time, stripped evaluator columns/paths/wells,
invalid values represented as null with explicit quality flags, no imputation or
resampling. Screenshots are derived local visualizations. No telemetry files are
committed. Source stripping does not certify anonymization.

## Fixed rule

Both `P-PDG` and `P-TPT` must deviate from their own frozen reference median by at
least six robust scales (`1.4826 × MAD`) for 30 consecutive observed seconds.
The reference uses only observations in the first 300 recorded seconds, with at
least 240 valid samples per pressure. These are **earlier measurements**, not
certified normal operation. Zero/constant measurements are valid; zero MAD disables
that reference rather than substituting an epsilon. Missing/invalid readings or
an interval over 1.5 seconds reset pending persistence. The alert latches at the
first qualifying decision. It cannot identify a failure type or confirm cause.

The 300/240/6/30/1.5 choices are fixed **software-feasibility heuristics**; they
are not documented industrial alarm settings, safety limits, trained operating
thresholds or optimized fault criteria. The sensor measurement semantics are
source-backed; this alert threshold is an empirical monitoring hypothesis.
The detector receives only one relative time and two quality-tagged samples at
a time. It receives no class/state labels, onset, well identity, filenames,
annotation boundary, future samples, or classifier predictions.

## Actual offline findings

Annotation comparison below is **offline review only**; no annotation marker or
relative-to-annotation score is served to the browser or Muse.

| Recorded clip | First alert elapsed | Relative to annotation reference | Original diagnosis ready |
| --- | --- | --- | --- |
| Case 1 | 872 s / 14:32 (position 873) | 928 s before | 2,399 s / 39:59 (position 2,400) |
| Case 2 | 1,862 s / 31:02 (position 1,863) | 62 s after | 2,399 s / 39:59 (position 2,400) |

The first alert predates the annotated transient substantially. Treat it as a
**pre-annotation deviation** and a specificity warning, not proof of early
failure detection. The earlier report includes operating-state/unknown segments;
it cannot certify stationary normality. The second timing is compatible with a
post-annotation deviation, not independent fault-onset validation. With two
selected clips, no false-alarm rate, sensitivity, detection accuracy or general
predictive claim is justified. There was no successful-outcome retuning.

## Product recommendation

Use the feature as an explicitly labeled **prefix-only anomaly demonstration**,
followed by evidence accumulation and retrospective diagnosis. Do not market it
as industrial early warning. Keep the captured claim audit as the scientific
centerpiece: a genuine measured change and a statistical diagnosis still do not
establish root cause. No additional paid investigation is needed to demonstrate
this separation. Detector validation on independently selected long normal and
fault records would be a different future experiment.

The default 600-sample/endpoint demo remains a **complete-evidence checkpoint**;
only explicit `--monitoring` enables the new empirical alert rule. It fails
closed if evidence does not match or the rule does not fire. There is no forced
alert, annotation-triggered alert, shifted classifier window, or silently
substituted assessment.

## Browser review captures

Actual supplied recorded clips were inspected at 1440×900 and 390×844. These
are viewer telemetry screenshots and captured Muse replay, not new model
executions. The real-measurement images remain local rather than being published
in the repository. Regenerate PNGs with `scripts/verify_monitoring_browser.py`
using the exact command in [run.md](run.md). The requested screenshots include
monitoring, actual alert, diagnosis and captured Muse assessment for both cases
and both viewports. No interpolation or fictitious model events appear.

The browser run checked 36 positions, 12 displayed sensor nodes per position,
all 27 inventory channels, chart cursor alignment, alert/diagnosis gating,
rewind, unchanged agent packets and captured audits, and zero live requests.
A separate unscreenshoted constant-zero software fixture verified that an
unusable reference cannot force an alert, diagnosis or investigation action.
These checks do not certify the detector or any physical diagnosis.
