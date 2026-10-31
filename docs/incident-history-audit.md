# Full-history data audit: first-stage handoff

The requested implementation is explicitly staged. **The actual 3W dataset is
absent in the Work workspace.** The earlier user-run verification established
that the two local 600-sample windows match their frozen protocols; it did not
measure how much history exists outside those windows.

This PR therefore implements the executable first-stage audit and local fixture
projection, not a detector chosen from unavailable measurements. No alert,
threshold, pre-fault duration, detector delay or success rate is invented. The
existing website and final-position demo checkpoint stay unchanged for now.

## Documentation verified

- [3W Dataset 2.0.0 authors, Section 2.4, Table 4](https://arxiv.org/html/2507.01048v1):
  normal operation is distinct from transient and steady undesirable conditions.
  The documented transient codes cover events 1, 2, 5, 6, 7, 8 and 9; events 3/4
  have no corresponding transient code in that table. Unknown annotations are
  distinct from normality. The report emits generic categories, never raw fault codes.
- The same paper's Table 5 and Figure 7 distinguish operational state from class:
  a nominal-normal class does not guarantee steady open production or a stationary
  signal. State labels are not measurement columns such as ESTADO-DHSV.
- [Official dataset README](https://github.com/petrobras/3W/blob/main/dataset/README.md)
  declares **CC BY 4.0** for dataset files. Its release notes say some normal
  periods were extended with a one-hour minimum as a goal; that does **not**
  establish the duration in our two selected files.
- [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) requires applicable
  attribution, license linkage and disclosure of changes; it is not a guarantee
  of anonymity or clearance of every privacy right. Exported manifests and
  ATTRIBUTION.json carry source links, attribution and transformation notices.

These documentation facts do not establish a physically precise event onset,
validated normal reference, installed sensor calibration, or an alert threshold.

## Run the first-stage audit

Before merge:

```bash
git fetch origin
git switch feat/incident-history-audit
python -m pip install -e '.[test,agent,audit]'
python scripts/audit_incident_history.py \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --out .petromind/history-audit-v1
```

After merge use `git switch main` and `git pull`. Use a fresh output directory
for each run; nothing overwrites previous experiments. No API key or Meta call is
used. The optional `audit` dependency adds Matplotlib for standalone SVG plots.

The command resolves **only the two selected development files** with the existing
trusted private locator, file hashes and well-isolation checks. It verifies the
original 600-sample cadence/labels and summary equality before analyzing the full
record. It does not read other wells to search for a more favorable example.
Labels/state stay inside this trusted offline process; nothing new is registered
as an agent tool or served by the web app.

Outputs:

- **report.json — attach this file here first.** Generic stage/operational categories,
  full/pre/initial-transient/post counts, total transient count, timestamp quality,
  observed cadence, example discontinuities, and all 27 channels' presence/quality.
  It includes earlier median/MAD and longest valid row runs as descriptive values,
  not fitted normal distributions or passed/failed baseline criteria.
- **summary.md** — small count/duration and grouped sensor-availability tables.
- **case-1-trajectories.svg / case-2-trajectories.svg** — Matplotlib plots of the
  predeclared P-PDG, P-TPT, T-TPT and QGL channels around the annotation. Actual
  samples only; missing/invalid readings and timestamp gaps break lines, and isolated
  readings remain visible. Annotation is explicitly marked **not a detector alert**.
- **ATTRIBUTION.json** — source/license references and transformations.

The report excludes raw class/state codes, fault ground truth, well identifiers,
original filenames/paths, source locator/file hashes and calendar timestamps.
It DOES contain offline annotation timing and diagnosis-readiness row offsets.
It is an **offline review artifact, never a browser or Muse evidence packet**.
Waveform statistics can still be identifying: “sanitized” does not mean anonymous.

The full-record cadence report does not sort, fill or resample. A non-monotonic,
duplicate or missing timestamp is reported; unusable timing is not replaced with
an assumed 1 Hz grid. A sensor absent from the file is distinguished from an
all-missing channel and from a legitimate constant zero.

## Optional small telemetry package

Do not upload or commit the 1.8 GB dataset. The report is the first useful handoff.
If actual recorded samples are needed for offline development, run into another
fresh directory:

```bash
python scripts/audit_incident_history.py \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --out .petromind/history-audit-fixture-v1 \
  --export-local-fixture
```

Default plot/export context is up to 1800 actual seconds before and 1200 after
first transient annotation (end-inclusive, no interpolation). These are presentation
bounds, **not detector parameters**. `--before-seconds` accepts 1–7200;
`--after-seconds` accepts 600–7200 so the original diagnostic window remains covered.
The full-record audit statistics always use the whole file, independent of clip size.

`local-fixture/` contains a manifest and two small Parquet projections:

| Field | Meaning |
| --- | --- |
| `elapsed_seconds` | Original relative offsets from the clip's first recorded timestamp; gaps retained |
| `<sensor ID>` | Unmodified usable numeric reading; invalid/missing projected to null, never imputed |
| `<sensor ID>__quality` | valid / missing / invalid |
| `<sensor ID>__reason` | Existing numeric guardrail/missingness explanation; guardrail is not a physical safety limit |
| Manifest `present_sensor_ids` | Distinguishes absent channels from present all-missing channels |

No class/state annotations, annotated-onset marker, absolute date, well ID,
private locator or baseline ground truth is included in the telemetry projection.
Checksums verify artifact bytes, **not authenticity, anonymity or license compliance**.
The manifest retains attribution, original source and license links, units,
transformation notices and the fact that this clip was selected using offline
annotation bounds. Such selection can indirectly reveal timing: this package is
**not a prospectively blinded or product-ready packet**, and must never be fed to
Muse or directly served as a new replay without a separate reviewed boundary.
Keep the manifest with its measurements. The tool publishes nothing automatically.

If you choose to provide the package for offline review after checking that your
local files are the covered public data and considering applicable privacy constraints:

```bash
tar -czf .petromind/history-telemetry-v1.tar.gz \
  -C .petromind/history-audit-fixture-v1 local-fixture ATTRIBUTION.json
```

The generated artifacts remain under ignored `.petromind/`; no real telemetry or
plots are committed by this PR. Only clearly constructed software fixtures live
in the tests. No independent dataset download is added because we require these
exact frozen files, not a possibly changed current snapshot.

## Detector design gate after the real report

No method or numeric threshold is selected yet. The initial design comparison is:

| Candidate | Data prerequisite / failure case |
| --- | --- |
| Robust median/MAD with persistence | Requires a defensible label-blind warm-up/reference; zero MAD needs an independently justified resolution/noise floor, not an arbitrary epsilon |
| CUSUM | Requires reference centering and scale/drift assumptions, plus reset behavior across missing data or operating changes |
| Multi-sensor deviation | Requires sufficient concurrent usable channels and a frozen aggregation rule; a missing sensor cannot silently supply normal evidence |

Use **Option A**: separate anomaly monitoring from the original classifier. A
future detector must consume only a prefix at time t, with no annotation input,
full-future statistics or demo-optimized timestamp. Freeze parameters before scoring
these two examples; any learned scales or thresholds need separate fitting/reference
wells and an appropriate broader development check. Report cold-start, unavailable
reference, pre-annotation alerts, late alerts and no alert with honest denominators.
Annotated “normal” is offline evaluation context, not permission to calibrate to
its known endpoint. Tests must compare prefix decisions under changed suffix data.

The existing diagnosis remains the original fixed 600-sample summary prediction,
not a new sliding 600-sample window started at a detected alert. Its earliest complete
row is reported offline. Its window was annotation-selected: a causal monitoring
rule alone does not make that diagnostic-window selection an independently validated
online model. The later UI must explicitly distinguish anomaly alert, accumulating
diagnostic evidence, statistical prediction and root cause. An annotation marker
must remain off the prospective operator view; readiness metadata also needs review
for indirect timing disclosure.

Keep all monitoring/reference/broader viewer data out of the existing Muse packet.
The original three summaries and at most two new live-v3 queries still refer only
to the original 600-sample window. Giving Muse a detector-derived reading or reference
would be a separate evidence/protocol change, even if the sensor name is the same.
No detector efficacy, early-warning, anomaly timestamp or new UI integration is
claimed before the actual report establishes feasibility.

## Verification

```bash
python -m pytest -q
```

Tests use explicitly constructed histories: normal/transient/steady/unknown categories,
operational shifts under nominal normality, unknown codes, no pre-history, zero/constant/
missing/invalid readings, timestamp gaps, duplicates/NaT, export privacy, Matplotlib
plots, original evidence equality, frozen-file tampering, held-out-file exclusion and
no overwrite. No actual-data findings are fabricated and no paid requests occur.

No website changes or new alert screenshots are delivered at this first stage:
showing a successful detector scene now would imply evidence we do not have.
The next input is the actual **report.json**, not another paid evaluation.
