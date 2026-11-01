# Run the recorded-history monitoring demo

Use Python 3.12 and the unchanged local claim capture/private science protocol.
Run all commands from the repository root. Preparation, replay and browser checks
make **zero paid calls**. This is the existing Home / Demo / Technology product,
with an optional prefix-only monitor, not a new application.

## 1. Install and export your real data

```bash
python -m pip install --upgrade pip
python -m pip install -e '.[test,agent,audit]'
python scripts/audit_incident_history.py \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --out .petromind/history-monitoring-export-v1 \
  --export-local-fixture
```

Use a fresh output directory. If you already exported `history-audit-fixture-v1`,
reuse its `local-fixture` and `report.json` instead; do not overwrite old artifacts.
The private report is offline-only. Do not put it in a web directory or commit it.
The fixture contains real potentially identifying telemetry, not synthetic data.

## 2. Prepare the bounded viewer replay and offline detector report

```bash
python scripts/prepare_monitoring_replay.py \
  --capture .petromind/claim-audit-v1 \
  --fixture .petromind/history-monitoring-export-v1/local-fixture \
  --history-report .petromind/history-monitoring-export-v1/report.json \
  --out .petromind/monitoring-demo-v1
```

If reusing your earlier export, substitute its two paths. For the supplied two
clips, first alerts occur at 14:32 and 31:02, with the original diagnosis becoming
eligible at 39:59. These are actual results of the fixed rule, **not** chosen
historical alarms. Read `offline-report.json` locally for annotation-relative
comparison and limitations. `viewer.json` contains only the allowlisted projection;
its trace is recomputed when loaded. Never send either file wholesale to an agent.

## 3. Start the demo

```bash
python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --monitoring .petromind/monitoring-demo-v1
```

Open **http://127.0.0.1:8765/demo**. No `--enable-live` is supplied.

1. Replay starts at sample 1 (index 0). Play advances through actual samples at
   10× recorded time, without interpolation. You may scrub for a shorter demo.
2. Watch all 12 displayed sensor indicators; all 27 channels remain in All sensors.
   Missing readings stay missing, constant zero flow stays valid. Optional sensor
   charts share the selected replay position. Trend colors mean relative change.
3. Before the first alert, no alert marker, fault prediction or investigation
   controls are visible. At the actual detector decision the marker appears and
   both pressure indicators gain an amber outline. This is an **anomaly**, not a
   historically logged alarm or fault identification.
4. The Console shows accumulation of the **original** 600 diagnostic observations.
   The saved statistical diagnosis is revealed only after their completion and an
   alert. If this detector never alerts, no diagnosis is triggered.
5. Click **Investigate with Muse Spark** to replay the unchanged captured audit.
   Inside Muse shows its genuine recorded tool calls. Broader replay is viewer-only;
   Muse still received its original summary packet, not the monitoring prefix.
6. Rewind: controls and marker hide. Advance again: the same saved investigation
   returns; no model is called. Switch cases: replay starts at the beginning.

The original diagnosis window was selected by the evaluation protocol, not by
this detector. Completion time is a retrospective evidence boundary, not a
validated online classifier. A recorded alert does not change the frozen verdict.

Without `--monitoring`, the previous 600-sample/endpoint checkpoint flow remains.
An invalid explicitly supplied monitoring bundle fails; it does not silently fall
back to endpoints. Data is served only on loopback with the existing protections.

## 4. Verify locally

```bash
python -m pytest -q
python -m pip install playwright
python -m playwright install chromium
python scripts/verify_monitoring_browser.py \
  --capture .petromind/claim-audit-v1 \
  --monitoring .petromind/monitoring-demo-v1 \
  --screenshots .petromind/monitoring-browser-v1
```

The browser check starts/stops its own loopback server. Use a fresh screenshots
folder; optionally add `--browser /absolute/path/to/chromium` for an existing
executable. It checks both cases at 1440×900 and 390×844, 12 nodes per sampled
position, 27-channel inventory, chart synchronization, alert/diagnosis/rewind gates,
unchanged agent packets/audits, no JavaScript errors and no live endpoint requests.
This verifies the supplied bounded recordings, not full-dataset authenticity or
prospective detection performance. Screenshots are real derived telemetry and
remain local by default.

The full suite additionally tests causal prefix invariance, missing/invalid/gapped
samples, constant/zero references, bad mappings/checksums/schema, hidden metadata
stripping, and unchanged existing investigation accounting. Existing v2/v3 HTTP
mock smoke tests remain in `scripts/check_claim_demo_browser.py` and are explicitly
separate from actual recorded-data verification.

## Live integration remains separate

Supported live tools are `lookup_knowledge`, training-only `search_history`, and
`submit_audit`; opt-in active v3 also offers bounded `request_sensor`. See
[existing opt-in instructions](../live-investigation-verification.md). A fresh
matching live protocol is required after source/runtime changes. The new monitor
adds no agent tool and sends no new measurements, references or alert scores to
Muse. Active v3 still resolves only the original verified 600-sample dataset
window and shares the same five-sensor budget. The monitoring projection alone
cannot authorize active queries. No paid call was run for this change.
