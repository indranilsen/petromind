# PetroMind: hackathon runbook

**Monitoring → anomaly → statistical diagnosis → Muse investigation → source-backed
assessment.** This is a local demonstration of evidence auditing, not validated
industrial early warning or root-cause certification. Home / Demo / Technology
remain the only pages. Synthetic Challenge is deferred.

For the v5 atomic/composite verdict contract and offline verification, see
[atomic assessments](atomic-assessment.md). Previous live protocols must not be reused.

## Clean setup and required local files

Use Python 3.12 (offline CI also covers 3.10), then install:

```bash
python -m venv .venv312
source .venv312/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test,agent,audit]'
```

The public repository contains the application, knowledge package and tests. It
**does not include** the original 3W dataset, private evaluation protocols, unchanged
claim capture, or real telemetry projections. A fresh clone alone cannot replay
these incidents. Keep those authorized local artifacts outside version control:

- `.petromind/claim-audit-v1`: unchanged reviewed `protocol.json` and `results.jsonl`.
- `../3W/dataset`: your separately obtained 3W data; needed for original-source
  verification and active live v5, not required once a bounded viewer bundle exists.
- `.petromind/science-m5-v1/protocol.json`: matching private source protocol.
- An exported history `local-fixture` and its matching offline `report.json`.

If your previous fixture export exists, prepare the missing monitoring bundle:

```bash
python scripts/prepare_monitoring_replay.py \
  --capture .petromind/claim-audit-v1 \
  --fixture .petromind/history-audit-fixture-v1/local-fixture \
  --history-report .petromind/history-audit-fixture-v1/report.json \
  --out .petromind/monitoring-demo-v1
```

Use your actual export directory if it has a different name, and a fresh output
directory. To create an export from original files instead, use the exact
[history export instructions](monitoring/run.md). Do not regenerate or edit frozen
experiments to make setup pass.

## Check, then launch (no paid calls)

```bash
python scripts/demo_claim_audit.py check \
  --capture .petromind/claim-audit-v1 \
  --monitoring .petromind/monitoring-demo-v1

python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --monitoring .petromind/monitoring-demo-v1
```

Open **http://127.0.0.1:8765/demo** (Home is `/`, Technology is `/technology`).
Stop an old server with Ctrl+C and hard-refresh after updating the code. For a
port conflict add `--port 8766` and open that port. The check command does not bind
a server, call Meta, disclose the key, or certify physical correctness. For this
full journey its output must show `complete_monitoring_available: true` and two
`history` replays with 3,001 positions. An endpoint-only capture is honestly labeled
and does not establish successful continuous replay.

A missing viewer bundle now reports `missing_monitoring_bundle` with a preparation
instruction. A missing capture reports `missing_capture_file`; a busy server port
reports `port_in_use`. Other mismatches remain failures, never silent repairs.

## Three-minute walkthrough and fallback

Use the [timed judge script](hackathon-demo.md). Both recordings start at index 0.
All 3,001 positions are retained; the two pressure indicators and secondary
channels use actual selected samples, with no interpolation. Play advances at
10× recorded time; scrubbing is navigation through the recording, not fabricated
measurements or a claim of prospective operation.

The fixed rule first alerts at 14:32 and 31:02 in the supplied clips. Both original
classifier windows complete at 39:59. Alert earlier and wait for the original
window; do not move or refit it. The first alert predates the annotation substantially:
this is a specificity limitation, not verified early fault detection.

Click Investigate once. Captured public events unfold automatically with explicitly
artificial presentation pacing. The transcript and graph expose only already
revealed records. Pause/resume, restart or show the completed recorded assessment.
The final assessment is brought into view automatically. Mobile keeps the
conversation primary; expand the graph to inspect source facts. A citation or
similar analogue does not prove physical entailment.

For a network/API failure, show the actual stopped state, then explicitly switch
to the captured execution mode and say **“This is a previously recorded Muse run,
not a new live call.”** Captured mode requires no network/model key. The same
verified measurements and unchanged public outputs remain available. There is no
automatic captured-result substitution and no automatic paid retry.

## Exactly one optional live smoke investigation

No real paid smoke was run in the readiness workspace: the API credential and
full original dataset were unavailable. HTTP mocks verify software paths only.
The following steps are for deliberate local authorization, after installing the
final source and exporting `MODEL_API_KEY` in your shell. Never paste the key into
chat, command arguments, a browser, or Git. There is no `.env` autoload.

First verify original raw inputs, then prepare an **unused** capped v5 protocol.
These commands make no Meta requests:

```bash
python scripts/verify_claim_replay.py \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json

python scripts/demo_claim_audit.py prepare-live \
  --capture .petromind/claim-audit-v1 \
  --out .petromind/readiness-live-001 \
  --max-cost-usd 0.50 --active-sensors \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json
```

Now choose **one** execution route, not both. This CLI command explicitly spends
against the estimated global $0.50 cap and runs one investigation:

```bash
python scripts/smoke_claim_live.py \
  --capture .petromind/claim-audit-v1 \
  --live .petromind/readiness-live-001 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --case fault_expectation \
  --authorize-paid-meta
```

Inspect the new `.public.jsonl`, result and usage. Expect actual `tool_request`
and `tool_result` events and completion **or failure**. A completed investigation
with zero additional sensor requests does not verify active acquisition. That
behavior is not forced. No authorization flag means no app/API execution. The
script refuses a used protocol and a cap over $0.50. The cap uses frozen estimates,
not an invoice guarantee. No larger evaluation is launched.

**UI alternative instead of the CLI smoke:** serve the same **unused** protocol
with the command below, select Live Muse API · paid, and click Investigate exactly
once. This is the route for observing actual Meta events in the browser:

```bash
python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --monitoring .petromind/monitoring-demo-v1 \
  --enable-live .petromind/readiness-live-001
```

Do not run the paid CLI first and then click Live: the browser does not import
that CLI attempt, so the click would be a second paid investigation. Do not retry
silently after failure; inspect the saved attempt. Closing the browser does not
cancel an already bounded server run. Requests for extra sensors require returned
source-backed sensor-location context and share the original five-query budget.

## Historical-label boundary

Newly prepared interactive live protocols pin `training-history-label-free-v1`:
retrieval omits the `training_event` field from both tool responses and their
public audit entries. Training-only source validation remains server-side; overlap,
distance and citation IDs remain available. A fresh protocol is required, not an
in-place edit to an existing run. Tool arguments, prompts, budgets and diagnostic
policy are unchanged. Prior evaluation sessions keep their original defaults.

**Frozen captured audits are an explicit exception:** their six returned training
analogues included training-event categories. These are training labels, not the
held-out target's label, but the captures are not label-free historical evidence.
They are preserved exactly rather than retrospectively redacted. Do not claim a
label-free historical contract for those past runs. This limitation is separate
from the continued isolation of hidden target labels, source paths and well IDs.

## Reproduce verification and screenshots

```bash
python -m pytest -q
python -m pip install playwright
python -m playwright install chromium
python scripts/verify_monitoring_browser.py \
  --capture .petromind/claim-audit-v1 \
  --monitoring .petromind/monitoring-demo-v1 \
  --screenshots .petromind/readiness-monitoring-shots
python scripts/verify_guided_investigation.py \
  --capture .petromind/claim-audit-v1 \
  --monitoring .petromind/monitoring-demo-v1 \
  --screenshots .petromind/readiness-investigation-shots
```

Node.js is used only by an offline public-graph contract test; without Node that
one test is skipped. It is not required to serve this buildless application.

Use fresh screenshot directories; an optional `--browser /absolute/path/to/chromium`
selects an installed executable. Scripts start/stop loopback-only servers. They
make no paid calls. Full automatic completion is tested without Skip; Skip is
checked separately. Source-prefix order, provenance inspection, pause/resume,
rewind, visible final assessment and reduced-motion behavior are checked at
1440×900 and 390×844. Real-measurement screenshots remain private/local.

## Deployment and judge practicality

The supported deployment is a **trusted local Python process**, with the recorded
bundle and capture already validated before presenting. A static-only host cannot
run the Python tools or Meta proxy. Public multi-user/cloud hosting has not been
validated and is not shipped as a last-minute change: the backend deliberately
binds loopback and validates Host/Origin/token, with no public authentication,
quota isolation or hosted credential lifecycle. Do not work around these controls
by binding `0.0.0.0` or disabling checks. Screen recording / a supervised laptop
walkthrough is the reliable submission path. Document local-data requirements
rather than claiming a fresh public clone has a self-contained incident package.

## Scientific limits to state aloud

- Original statistical predictions use fixed retrospective 600-sample windows;
  the monitor does not make them early online predictions.
- Two annotation-centered development clips cannot validate false-alarm rate or
  industrial alarm performance. The observed prefix is not certified normal.
- Knowledge lookup selects vetted topic facts, not installed-well topology.
  Published examples are not universal or discriminating physical rules.
- Original M3 adaptive/fixed scores were 20/33 and 13/33; Muse sensor-only/graph/
  GraphRAG scores were 4/33, 1/33 and 5/33. No classification advantage is claimed.
- Claim-audit examples are constructed evaluation claims over actual measurements.
  Small correlated pilots and correct citations do not certify physical reasoning.
- Independent engineering review, root-cause proof, safe operational advice and
  active sensor-selection benefit remain unestablished. This is decision support,
  not an autonomous equipment controller.
