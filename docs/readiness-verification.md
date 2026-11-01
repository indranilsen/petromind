# Readiness verification receipt

Run on the merged PR #23 application, followed by the focused readiness fixes.
This is a software/demo receipt, not engineering certification. No Meta API call
was made. All frozen experiment files and captured model outputs are unchanged.

## What was actually executed

| Check | Result | Scope |
| --- | --- | --- |
| Python offline suite | **449 passed** | Budget, cache, missing/invalid/constant/zero data, provenance, label isolation, source split checks, schema/repair contracts and new startup regressions |
| Recorded monitoring UI | **Passed** | Two supplied clips, 3,001 positions each; 36 selected positions × 12 displayed sensors; 27-channel inventory; synchronized charts/values, alerts, diagnostic readiness, rewind and no-alert software fixture |
| Automatic complete Muse journey | **Passed** | Both cases at 1440×900 and 390×844; actual events revealed in order through completion without Skip; Skip tested separately, pause/resume/restart, no future graph facts/assessment, source inspection, visible final heading, reduced motion |
| Home / Demo / Technology and mock live | **Passed** | Three pages, both viewports, zero JavaScript errors; seven mocked Meta HTTP responses cover incremental v2/v3 events, additional sensor query and failure states |
| Real paid Meta connectivity | **Not run** | Credential and full original dataset unavailable here; no paid-authorization flag invoked. Mock results do not establish API functionality |
| Full original dataset replay | **Not run here** | Actual recorded projections were supplied; original files were previously audited on the user's machine. This run does not independently authenticate those originals |
| Frozen-artifact integrity | **Passed** | Original claim protocol, claim results and private source protocol byte hashes match their pre-verification values; capture loader also verifies its fixed protocol/row digests |
| Historical event-label visibility | **Fixed for new live; exception in frozen replay** | All six original training analogue records contain `training_event`; no held-out target field. Original records stay unchanged. New live responses/audits suppress event labels under a fresh pinned projection version |
| Source/provenance and physical claims | **Scoped review** | Graph uses actual returned facts and citations, not installed-well topology. Numerical/source integrity is checked; physical interpretation remains independently unreviewed |
| Public tracked-tree scan | **No real credentials/private source paths found by the scoped patterns** | Matches were explicit fake credentials/well names in software tests. This is not a comprehensive secret scan of all remote Git history |
| Ruff / JavaScript syntax / diff checks | **Passed** | Changed code and local tested commit |

## Real recorded inputs and unchanged timing

Two user-supplied development projections contain 3,001 original positions each,
0–3,000 relative seconds at 1 Hz. No interpolation, imputation or sample generation
was introduced. All 27 catalog channels are present. Across each entire clip:

- Case 1: 57,019 valid scalar readings; 24,008 missing.
- Case 2: 41,849 valid scalar readings; 39,178 missing.

No invalid numeric readings occur in these particular clips. Invalid/extreme
handling is verified with **software fixtures**, not claimed as a naturally
occurring invalid-data event in this replay. Constant zero gas flow remains valid.

Checksum validation and exact equality with original captured sensor summaries
passed. The detector consumes only the current pair of pressure samples and a
past measured prefix; altered future suffixes cannot change prefix decisions.
The original rule and classifier window are untouched:

| Clip | First computed anomaly | Original classifier readiness |
| --- | --- | --- |
| 1 | 14:32 / position 873 | 39:59 / position 2,400 |
| 2 | 31:02 / position 1,863 | 39:59 / position 2,400 |

These clips were selected around private annotation boundaries, not prospectively
sampled. The first alert substantially predates the annotation. No false-alarm,
sensitivity, early fault-detection or industrial alarm efficacy claim is justified.
Annotation-relative scoring and private source metadata remain offline, not in
agent or browser packets. Readiness time is the original retrospective evidence
boundary, not a new online classifier timestamp.

## Issues found and fixed

1. **Generic startup error hid a missing monitoring bundle and port conflict.**
   Added zero-API `check` and safe actionable codes for missing capture/bundle and
   occupied port. No incident paths, labels, secret values or raw exceptions are
   printed by the new structured errors. Invalid inputs still fail closed.
2. **Automatic replay could finish with the assessment below the viewport.**
   The actual submitted verdict is now brought into view, with no invented model
   message. Full automatic completion and visible heading are regression-checked.
3. **Replay controls could scroll away during the investigation.**
   Kept pause/resume/restart controls reachable; the classifier's existing primary
   action remains reachable while reading its result. No pre-readiness action is
   exposed. Graph labels wrap at word boundaries rather than splitting words.
4. **Historical training labels were present in agent-facing analogue metadata.**
   Frozen captures are retained and explicitly disclosed as not label-free.
   Newly prepared live runs suppress the event-label field in responses/audits,
   pin `training-history-label-free-v1` and require a fresh protocol. Existing
   experiment defaults remain unchanged; held-out target isolation is preserved.
5. **Submission and startup docs lagged live v3 and the monitoring requirements.**
   Corrected supported tools, consolidated canonical commands and the three-minute
   script, added local-deployment limits, and separated the CLI versus UI single-
   investigation smoke routes. No prompts, tool-argument schemas or scientific methods changed. The new live
   historical-result privacy projection is separately versioned.

## Browser review and screenshots

Actual Chromium interaction plus screenshot inspection covered monitoring, both
computed alerts, classifier attribution, genuine retrieved graph facts, missing
premises and the final assessment. Desktop and mobile were reviewed. Tool/record
headings are interface labels; no new Muse commentary is attributed to the model.
The second case retains the narrow scope of matching a documented example.

Real-telemetry screenshots are delivered privately and are not committed to the
public repository. Reproduce them using the two browser commands in the
[runbook](hackathon-readiness.md). Home/Technology screenshots in the separate
platform suite show application pages; the platform's constructed telemetry and
mock Meta tests must not be described as actual full-dataset or paid verification.

Attribution: Petrobras and the 3W Dataset contributors; Vaz Vargas et al., *3W
Dataset 2.0.0*, arXiv:2507.01048v1. Dataset declaration:
https://github.com/petrobras/3W/blob/main/dataset/README.md ; CC BY 4.0:
https://creativecommons.org/licenses/by/4.0/ . Derived screenshots use bounded
relative-time projections and documented display-unit conversions. Stripping
labels/paths does not certify anonymization or instrument calibration.

## Submission recommendation and remaining limits

**Ready to record the scoped captured demonstration**, with an explicit replay
badge and the timed script. Frozen history is not retroactively label-free: its training-event metadata is
an explicit remaining exception. New interactive live history suppresses those
fields. Real API readiness remains pending one deliberately
authorized, cost-capped local smoke. Public cloud deployment and a self-contained
public incident package are not delivered. The application is supported on a
trusted local machine with the required authorized artifacts.

Do not claim Muse classification superiority, GraphRAG accuracy benefit, proven
root cause, verified installed topology, validated industrial alarm performance,
or independently certified physical reasoning. The strongest defensible demo
moment is still: **the measured change is real; the causal inference is not
established by the supplied evidence.** For the second example, a documented
comparison can be supported without proving cause. No new experiment, fine-tuning,
infra component or expanded cohort was introduced.
