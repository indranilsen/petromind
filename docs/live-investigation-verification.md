# Replay and bounded live investigation refinement

This change is stacked on PR #18. The offline suite passed **387 tests**; changed Python files passed Ruff. Keep **HOME | DEMO | TECHNOLOGY**; Demo keeps
Operator Console and Inside Muse. Synthetic Challenge remains explicitly deferred.
No frozen study, capture, label, classifier, historical index or result is changed.

## Verification status

| Behavior | Executed here | What that establishes |
| --- | --- | --- |
| Frozen captured outputs and source events | Yes | Original four audits load unchanged; both example cases remain inspectable |
| Python budget, cache, provenance, isolation and repair checks | Yes, offline suite | Software invariants on constructed fixtures, not diagnostic effectiveness |
| Actual local browser at 1440×900 and 390×844 | Yes | Replay UI, all-sensor inventory, captured events and operator explanation work without overflow |
| Every timeline position, 12 schematic sensors and chart cursor | Yes, **constructed 600-sample fixture** | Browser synchronization/checking logic, not actual Petrobras replay |
| Audit-only success, active sensor query and token-limit failure streaming | Yes, **7 mocked Meta responses** | Actual server/session/runner/UI paths and incremental tool-event delivery; no paid calls |
| Actual Petrobras files for these captured incidents | **Not executed** | `../3W/dataset` is absent in this workspace; endpoint fallback is honestly labeled |
| Paid Meta smoke test | **Not executed** | No server credential here, and no paid authorization flag was invoked |
| New useful sensor selection or physical correctness | **Not established** | No efficacy or causal graph-benefit claim; independent engineering review remains necessary |

Screenshots `refinement-*.webp` show genuine captured outputs and **endpoints**, not
mocked live results or fabricated continuous telemetry. Existing screenshots remain.

## Run replay (no key, no API spend)

After PR #18 and this follow-up merge, stop the old server (Ctrl+C):

```bash
git switch main
git pull
python -m pip install -e '.[test,agent]'
python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json
```

Open http://127.0.0.1:8765 and hard-refresh (Cmd+Shift+R). Server remains loopback-only.
Without matching raw files, the page shows **Captured endpoints · raw replay unavailable**
and disables Play. This is not a passing real-data verification.

## Verify your actual local replay, with zero API requests

Keep your original private M5 protocol; never publish its well identities/locators.
The verifier resolves exact protocol hashes, verifies file bytes, development-well
membership, held-out/retrieval exclusion, captured-summary equality and 1 Hz cadence.
It independently checks every scalar in the 27-channel projection and every timestamp.
It refuses to silently pass an endpoint fallback. It reads only the resolved incidents;
filename enumeration is used for hash resolution, not opening other test-well files.

```bash
python scripts/verify_claim_replay.py \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json
```

Success must say `"status": "supplied_dataset_verified"`, with two `mode: raw` cases,
600 samples each and `agent_packet_unchanged: true`. Its quality counts describe
what is actually present; it does not pretend every real case contains an invalid
or constant channel. Hash matching is not independent dataset-authenticity or
instrument-calibration certification.

For the browser check (development dependency only):

```bash
python -m pip install playwright
python -m playwright install chromium
python scripts/verify_claim_replay.py \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --browser-check
```

That command starts and stops its own loopback server. It checks all **600 positions
× 12 visible indicators × 2 cases**, raw values, trend/quality classes, displayed
value labels, exact chart timestamp/cursor index, 27 inventory entries and desktop/
mobile page width. No interpolation or gap filling is used. An assertion or missing
browser exits nonzero. No live endpoint is called.

Then visually inspect both incidents in Demo: scrub start/middle/end; inspect Tree
pressure's chart; open All 27 sensors; compare secondary temperature/flow/state
indicators; confirm unavailable channels stay dashed and constants neutral. Colors
compare with the first valid observation, not danger thresholds. The 600 observations
span 599 seconds; display converts Pa to MPa without changing the underlying values.
Any timezone ambiguity remains as encoded. These are retrospective windows, not a
live telemetry feed. Scrubbing never changes Muse's verdict or evidence.

## Supported live tools

| Tool | Audit-only v2 | Opt-in v3 | Boundary |
| --- | --- | --- | --- |
| `lookup_knowledge(topic)` | Yes | Yes | Exact public topics; source-tagged generic relationships, not installed well topology |
| `search_history()` | Yes | Yes | Same frozen training-only snapshot using **initial** sensors; additional queries do not rerank it |
| `request_sensor(sensor_name, source_id, purpose)` | No | Yes | Must cite that sensor's returned `knowledge:location:<sensor>` fact; public purpose ≤240 characters |
| `submit_audit(...)` | Yes | Yes | Existing scope-aware result fields, citations, numeric checks and bounded repairs; v3 version tag |
| Raw replay, filesystem, new classifier, equipment control, general topology traversal | No | No | Never registered as tools |

V3 uses **DiagnosticSession**, rather than maintaining a second budget. Its three
initial sensor queries are seeded and matched against the captured summaries before
Muse runs. Up to two new unique sensors remain; unavailable queries cost one, cached
repeats cost zero. Atomic session locking prevents concurrent double charges. Returned
summaries include numeric-quality metadata and a newly authorized measurement citation.
No raw samples, viewer inventory/presence, path, well, label or slider index enters
Muse. A generic location citation establishes where a variable is documented to
measure, not its fault-discriminating relevance; the public purpose still needs review.

The v3 protocol pins a digest of the frozen viewer-safe windows as well as source,
runtime, instructions, schema and documents. The server privately loads those same
windows; it never uses the browser's telemetry as input. A different raw file,
unrelated protocol, summary mismatch, wrong well partition or missing dataset fails
before model execution. The baseline prediction and original capture stay unchanged.
This is an interactive evidence audit, not a new classification evaluation.

Inside Muse draws new measurement nodes and the actual source-fact → request → summary
edges only after the respective Python tools execute. The Console marks the sensor
**Muse requested summary**; its moving raw playback remains viewer-only. Inventory
separates original summaries from new live requests. Initial evidence events are copied
before queries, so their recorded content cannot change retrospectively.

## Prepare optional active live mode (zero API requests)

Prepare **after** updating/installing the final code, using a fresh output directory.
Do not overwrite or edit any old protocol. Dataset and matching private protocol are
required for **both captured cases**; no summary-only substitute is allowed in v3.

```bash
python scripts/demo_claim_audit.py prepare-live \
  --capture .petromind/claim-audit-v1 \
  --out .petromind/demo-active-v3-smoke-001 \
  --max-cost-usd 0.5 --active-sensors \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json
```

Without raw files, omit `--active-sensors` for a fresh **v2 audit-only** protocol. It
reliably audits the original summaries and documents but cannot acquire measurements.
No old v2 protocol is silently upgraded to v3.

## One explicitly authorized paid smoke test

The following command **spends against the fresh protocol's estimated $0.50 cap**.
It requires your already exported `MODEL_API_KEY` in the server's shell. Keys never
belong in command arguments, source, browser payloads or chat. There is no `.env`
autoload. Do not run this command until you deliberately want the single live attempt.

```bash
python scripts/smoke_claim_live.py \
  --capture .petromind/claim-audit-v1 \
  --live .petromind/demo-active-v3-smoke-001 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --case fault_expectation \
  --authorize-paid-meta
```

No authorization flag means no app/API construction. The command refuses a used
protocol and a global cost cap over $0.50. It performs **one investigation**, not a
cohort. Existing bounds remain 6 turns, 8 tool calls, 4096 output tokens per response;
global reservations allow at most 12 HTTP requests including retries and 49152 output
tokens, subject to the smaller spending cap. Frozen price estimates are not invoice
guarantees. It writes a new `<request_id>.public.jsonl` with event receipt times,
plus the existing sanitized trace/result/ledger, without touching the capture.

Expected events are prepared evidence, actual tools, then completion or failure.
`requests`, `estimated_cost_usd` and `new_sensor_queries` report actual recorded usage.
A completed audit with zero sensor queries does **not** verify active acquisition:
Muse may reasonably decide no additional measurement can resolve the premise. No tool
call or successful conclusion is forced, and a failure is not converted to abstention.
The smoke command verifies the HTTP event route, not visual hierarchy or physical truth.

To observe the **same protocol** in the browser after that test:

```bash
python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --enable-live .petromind/demo-active-v3-smoke-001 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json
```

Captured replay remains free. Selecting Live and clicking Investigate starts **another
paid attempt** against the remaining global cap; the browser does not import the CLI
attempt automatically. To test the visual live route instead of the CLI route, serve
an unused prepared directory and click once. Watch events before completion, switch
Inside Muse, inspect the actual facts/measurements, then return to the operator summary.
A stopped run shows a reason; there is no silent captured-result fallback or automatic
retry. Closing the browser does not cancel the bounded server run; inspect its result
before starting another paid attempt. No automatic larger study is launched.

## Offline regression commands

```bash
python -m pytest -q
python scripts/check_claim_demo_browser.py \
  --url http://127.0.0.1:8765 \
  --mock-live-capture .petromind/claim-audit-v1 \
  --screenshots .petromind/local-browser-check
```

The second command requires Playwright and a running replay server. It uses explicit
constructed fixtures and mocked Meta responses for the sensor/streaming/failure paths;
its screenshots use genuine captured data only. It is **not** an actual paid Meta or
raw-dataset verification. `verify_claim_replay.py --browser-check` is the separate
actual supplied-dataset test.
