# PetroMind platform: Home, Demo, Technology

Exactly three top-level pages are served by the existing loopback Python app:
`/`, `/demo`, `/technology`. Home explains overlapping symptoms, incomplete data
and the distinction between prediction and cause. Demo contains Operator Console
and Inside Muse; Technology exposes component responsibilities and prior results.
There is no separate Simulation, Research or Inside Muse page.

## Replay: no key and no paid calls

```bash
python -m pip install -e '.[test,agent]'
python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json
```

Open **http://127.0.0.1:8765**. Use the Home CTA or Demo navigation. Stop a previous
server with Ctrl+C and hard-refresh Cmd+Shift+R after pulling new code.
The original reviewed capture is required and is not committed in this repository.

In Demo, explore the sensors, reveal the statistical hypothesis, then choose
**Investigate with Muse · captured replay**. Advance **Next recorded event** to
inspect actual source lookups, analogue retrieval, rejected submissions/repairs
and the final public findings. This is not a new model run or a timed reenactment.
Switch to Inside Muse at any point. Incident, playback position, execution mode
and received evidence remain in memory while switching views/pages.

The classifier output is the original frozen statistical result, not a fresh
classifier recomputation on the viewer's selected timestamp. Changing the slider
never changes the captured claim audit. All 27 catalog channels are discoverable;
12 indicators have a visual hierarchy. Extra verified raw channels are viewer-only.

## Live: fresh protocol and explicit operator action

Use an already exported `MODEL_API_KEY` in the server terminal. Never put it in
the browser, command arguments, repository or chat. Preparing the protocol makes
**zero API requests** and refuses to overwrite an existing directory.

```bash
python scripts/demo_claim_audit.py prepare-live \
  --capture .petromind/claim-audit-v1 \
  --out .petromind/demo-platform-live-v1 \
  --max-cost-usd 1

python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --enable-live .petromind/demo-platform-live-v1
```

In Demo choose **Live Muse API · v2 · paid**, reveal the classifier hypothesis,
and explicitly click **Investigate with Muse Spark · live API**. This is the
spending action. Merely opening the site, replaying or preparing a protocol does
not invoke Meta. Use a fresh output directory for a different code/runtime build;
old code-matching protocols and all experimental artifacts stay unchanged.

The global protocol cap is configurable up to $2 estimated (example above $1),
12 requests and 49,152 output tokens. Each investigation retains the existing
6-turn, 8-tool-call, 4,096-output-token-per-response bounds and bounded repairs.
Prices are frozen estimates, not an invoice guarantee. Reservations apply across
requests/runs. Refreshing or losing the stream does not automatically retry;
closing the browser does not cancel an already started bounded server run.
Credentials, spend limits, retries and schema checks remain in the existing client
and ledger. Live v2 is separate from the original captured v1 outputs.

## Actual live capabilities

| Capability | This live claim-auditor mode |
|---|---|
| Statistical hypothesis and observed measurements | Receives the original fixed packet of three already charged summaries |
| Knowledge graph/documentation | `lookup_knowledge`: documented, source-scoped facts by exact public topic |
| Historical retrieval | `search_history`: restricted prepared training-only analogues using those observations; actual overlap counts shown |
| Claim decomposition and assessment | `submit_audit`: existing scope-v2 public findings, citations, premises, gaps and next-evidence targets |
| New sensor acquisition | **Not exposed** in this mode; extra viewer channels cannot become evidence |
| General or per-well topology traversal | **Not exposed**; generic graph facts do not establish exact installed topology |
| Private model reasoning | Never displayed or exported; observable tool actions and public submitted findings only |
| Python validation | Exact numbers/received citations, structural consistency, bounded repairs and budgets; not physical correctness |

DiagnosticSession supports sensor acquisition/caching and a strict shared
five-sensor budget elsewhere in the repository. The present auditor inherits
three summaries, leaves two slots unconsumed and cannot query more. We do not
animate sensor requests or graph traversals that this mode cannot perform.

## One event projection, two views

`investigation_events.py` projects actual hash-linked audit entries into received
packet metadata, tool results, retrieved facts/matches, sanitized validation
errors and public assessments. Rejected submission text is omitted. Captured and
live work use the same public shapes and graph renderer. NDJSON from
`POST /api/live/stream` flushes tool events as the existing runner completes them;
its completion record contains the actual result, never a substituted capture.
The original non-streaming endpoint remains supported and idempotent.

Inside Muse connects the hypothesis, constructed claim, received measurements,
actual tool requests, returned source relationships, empirical matches, submitted
findings and missing premises. Click a node for exact data/provenance. Measurement
selection highlights its corresponding instrument. Edges express recorded evidence
use or model citations, not physical causation or verified piping. Only returned
facts appear; no extra viewer readings are silently included. Numeric validation
is attributed to Python, interpretations to Muse, and editorial explanations are
identified. The original full captured outputs remain in the evidence drawer.

## Synthetic challenge and verification limits

Synthetic Challenge is a clearly labeled **not-enabled** mode with an explanation.
There is no supplied, independently defensible signal/root-cause scenario and
fitted statistical bundle in this workspace. We prioritized the real historical
path rather than hard-code a favorable mismatch or suggest validated physics.
No synthetic root cause, invented telemetry or synthetic model success is shown.

Raw 3W data and a real Meta credential are absent in the implementation workspace.
The real-data adapter remains available for the user's local dataset. Here it
honestly falls back to captured actual endpoints with Play disabled. No continuous
real replay or new paid efficacy result was verified here.

## Checks

```bash
python -m pytest -q
# Optional browser regression check against an already running replay server:
python scripts/check_claim_demo_browser.py \
  --url http://127.0.0.1:8765 \
  --screenshots .petromind/platform-screenshots \
  --mock-live-capture .petromind/claim-audit-v1
```

Playwright/browser installation is a development-only prerequisite; it is not
required to run the app. `--browser /absolute/path/to/chromium` can select an
existing Chromium executable. The optional mocked live test uses a temporary
protocol and HTTP MockTransport, never Meta or real secrets, and saves no mocked
live screenshots. It blocks the second response until the browser has observed
the first tool result and evidence graph, then verifies the new final result.
368 offline tests passed. Desktop/mobile browser checks passed, including two
mocked live responses and an explicitly synthetic raw-widget test for playback,
zeros, missing/invalid samples, viewer-only values and chart gaps. Screenshots
show only original captured work. No frozen M3/M4/M5 artifacts change.
