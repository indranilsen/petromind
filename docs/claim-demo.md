# PetroMind: follow the evidence

The frontend has been redesigned into a three-scene guided investigation.
Use the current [guided experience and replay setup](guided-investigation.md).
The sections below retain the original captured-audit and live-v2 boundaries.

A local interactive demonstration of two **captured real Muse Spark audits**:

- Recorded pressures rise, but the claim that they establish service-line hydrate
  outruns the supplied physical evidence.
- Recorded pressure directions match a documented fault-2 example, with no claim
  that example consistency proves root cause.

The visual centerpiece is the claim → premises → cited evidence → missing-premise
trace. Captured v1 text is unchanged. Editorial scope review and concrete requests
are labeled separately. [Claim-level review and expert packet](claim-level-review.md)
cover all 17 findings. No independent engineering certification is claimed.

## Fast setup

Python 3.10+ on macOS/Linux. No Node build, database, web service or UI dependency.
The application uses a loopback Python HTTP server and packaged HTML/CSS/JS.

```bash
python -m pip install -e '.[test,agent]'
python scripts/demo_claim_audit.py review \
  --capture .petromind/claim-audit-v1 \
  --out .petromind/claim-review-v1.json
python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1
```

Open **http://127.0.0.1:8765**. Replay makes no Meta calls and requires no API key
or raw dataset. The original reviewed capture is required; it is not bundled with
the repository. Datasets, credentials and private capture artifacts are not
committed. If using the supplied review archive, extract it into a local directory
and pass that directory as `--capture`. Its protocol must remain unchanged.

The server validates the original protocol, all six records, audit chains,
explicit numeric observations and source citations. A pinned semantic digest
rejects altered captured outputs. The API projects only public packets, results
and source context; no evaluation targets, test labels, wells or filenames.

Choose either example. **See the diagnosis → Ask Muse to investigate** reaches
the verdict in two clicks. This is explicitly captured replay, not a new live call.
Click a pressure sensor for its optional value/chart; no charts are visible by
default. **Explore evidence**, available after the verdict, opens the complete
source/measurement/output drawer. Switch actual Grounded / Ungrounded outputs
there. History includes the exact shared sensor names/counts. Live v2 remains
inside that drawer and requires separate explicit authorization/configuration.

The new optional private raw-data adapter can load and verify the original
600-point series; see the guided setup. Without raw data, measurements remain
endpoint comparisons, not fabricated time-series plots. Raw samples are viewer
only; Muse still receives only the fixed captured summary packet.

## Scope-aware live v2 (present, disabled by default)

No paid calls were run during this implementation. v2 has offline/mock validation,
not new paid efficacy evidence. The original v1 prompt/schema/protocol stay intact.

Only when a live execution is explicitly wanted, create a **new** protocol:

```bash
python scripts/demo_claim_audit.py prepare-live \
  --capture .petromind/claim-audit-v1 \
  --out .petromind/demo-live-v2
python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --enable-live .petromind/demo-live-v2
```

Use an already exported `MODEL_API_KEY`; never put it in the browser or a commit.
Preparation and server startup make zero Meta requests. **Live mode + Run live v2**
is the only UI path that calls Meta. There is no background experiment or automatic
cohort expansion. Live runs preserve the baseline and reuse exactly three already
charged sensors; there is no additional measurement tool. Recommendations do not
execute a test or reveal a future reading.

Each v2 finding has a scope (measured observation / documented comparison /
diagnostic conclusion). Supported findings have no missing premise at that scope;
stronger causal gaps belong in separate findings. Next evidence names one concrete
catalog target: document, sensor, descriptive computation, or an explicit
`no_verified_discriminating_test` for a public fault ID. Proposed operator documents
are marked unavailable, not fabricated as existing sources. No computation in
this registry is certified as a fault discriminator. These checks enforce structure
and catalog membership, not physical truth.

The shared durable cap is 12 HTTP attempts including retries, 49,152 reserved
output tokens and $2 in conservative estimated reservations using frozen prices.
This is not an invoice guarantee. Runs have bounded turns/repairs/timeouts,
idempotent request IDs, process locking and interrupted-intent protection.
Version/prompt/tools/source/runtime changes require a fresh live directory. Results
and sanitized traces are written there, never into the original capture. A failed
live run is shown as failed; it is never replaced with replay presented as live.

The server binds only 127.0.0.1, restricts Host/Origin, uses a per-process anti-CSRF
token and no CORS, whitelists static assets, and renders model text as text. The
API key remains in the existing server-side bounded Meta transport. This is a
local demo, not a multiuser production deployment or arbitrary-code sandbox.

## Verification

```bash
python -m pytest -q
```

The tests cover reviewed replay integrity, v1 preservation, v2 scope checks,
recommendation targets, missing/zero/valve distinctions, hidden-label isolation,
HTTP assets/data, origin/host rejection, live disabled by default, fresh protocols,
and a mocked end-to-end live request with durable cost reservation/idempotency.
Mocks validate behavior; they are not evidence of physical reasoning quality.

## Honest demo and evaluation boundaries

All four original audits completed for approximately $0.1081 (11 requests).
Grounded target agreement was 2/2 versus 1/2 ungrounded. The ungrounded model's
withheld documentary verification was reasonable because it lacked the source;
this is **not a demonstrated accuracy or causal graph improvement**. The existing
citation checker does not assess semantic entailment. Expert engineering review
of gaps, next steps and unsupported interpretations is still pending.

Conventional adaptive diagnosis achieved 60.6% on the frozen M3 cohort, versus
12.1% for direct Muse sensor-only, 3.0% with equipment graph and 15.2% with GraphRAG.
These results and all prior protocols remain unchanged. PetroMind audits the scope
of evidence; it does not certify root cause, deliver safety-certified operational
decisions, or autonomously control equipment.

See [the three-minute flow and submission description](hackathon-demo.md).

## Execution record for this PR

- Complete offline suite: **350 tests passed** (12 new tests).
- Actual capture review: **17 findings**, **18 exact numeric observations**,
  **33 received citation occurrences**, **3 bounded repairs**; physical grades null.
- Real Chromium replay checks: both actual examples at 1440×1080 and 390×844;
  claim selection, source/history tabs, overlap counts, condition comparison and
  unchanged original outputs passed. Zero JavaScript errors and paid requests.
- Wheel packaging includes all three web assets; Python static checks,
  JavaScript syntax and whitespace checks passed.
- Live v2: exercised through mocked HTTP only. No new paid model calls and no
  efficacy or engineering-certification claim.

The optional browser check can be reproduced against a running replay server:

```bash
python -m pip install playwright
python -m playwright install chromium
python scripts/check_claim_demo_browser.py --url http://127.0.0.1:8765
```

Playwright is a development-only check, not a runtime or default-test dependency.
The script refuses non-loopback URLs and never clicks the live action. Screenshot
files, when requested, are local ignored development artifacts, not fabricated
telemetry or model outputs.
