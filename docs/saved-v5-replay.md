# Verified saved v5 replay and focused evidence

Three execution choices remain distinct:

- **Original captured investigation · v1**: unchanged frozen evaluation records.
- **Saved verified v5 investigation**: an explicitly imported completed run; no API calls.
- **Live Muse API · paid**: a new execution, available only with separate live setup.

A saved run is preferred when available for the initially selected incident.
The other incident remains available with its original capture. No arbitrary local
files are discovered or imported automatically. HOME / DEMO / TECHNOLOGY remain
unchanged. Prompts, tool definitions, v5 validation/aggregation, classifier windows,
monitoring, five-query accounting and evaluation records are unchanged.

## Verify and import your actual saved run (zero API calls)

The Work environment **does not contain the latest successful v5 run**. Its
protocol, findings, runtime, cost and completion have not been verified here.
Implementation uses explicitly labeled synthetic software fixtures; no older run
is substituted as the newest investigation.

First locate the actual output on your machine:

```bash
find .petromind -maxdepth 2 -name results.jsonl -print
ls -lah .petromind/readiness-live-007
```

Use the actual completed v5 directory below; `007` is only the expected example.
Do not change files in it. Stop the old server, install the merged code, then:

```bash
git pull --ff-only
python -m pip install -e '.[test,agent,audit]'

python scripts/demo_claim_audit.py import-saved \
  --capture .petromind/claim-audit-v1 \
  --run .petromind/readiness-live-007 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --out .petromind/judge-v5-replay-v1
```

Use a fresh output directory. Success reports `saved_v5_verified_and_imported`,
case alias, event count and `api_requests: 0`. If a run directory contains several
result rows, supply `--request-id` for the exact request you intend to replay.
Ambiguous, failed, incomplete, v4 or mismatched runs are rejected, never upgraded.

The import reads source artifacts and writes a **new derived bundle** only. Its
private manifest records the source location and SHA-256 hashes. Keep this bundle
local and out of version control. Active-sensor runs require the original dataset
and private science protocol to verify their original diagnostic window, including
any new summaries. Filenames/class labels are never used to guess the case.

Check and serve:

```bash
python scripts/demo_claim_audit.py check \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --monitoring .petromind/monitoring-demo-v1 \
  --saved-run .petromind/judge-v5-replay-v1

python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --monitoring .petromind/monitoring-demo-v1 \
  --saved-run .petromind/judge-v5-replay-v1
```

Open http://127.0.0.1:8765/demo and hard-refresh. Do **not** add `--enable-live`:
this walkthrough makes no paid calls and needs no API key. The check should show
`saved_replays: 1`; the imported case defaults to saved playback when it is the
initial case. Verify the **Saved v5** badge before recording. Use the original
captured option to compare without changing any artifact.

The server revalidates original files and derived projection on every startup.
Changes to either invalidate the import; no silent repair or captured fallback
occurs. Missing source files also fail, rather than accepting the derived JSON as
self-authenticating. Do not delete or move the source run after import.

## What verification establishes

Checks include protocol digest, matching v5 prompt/tool/document identities,
parent capture identity, case binding, original active-window digest, audit hash
chain, trace/audit agreement, completion and final-output agreement, returned
citations, numeric equality, source-fact catalog membership, permitted initial
training history, and five-sensor accounting. New summaries are replay-checked
against the original window through the bounded session. Source hashes are
recorded and checked again before use. Optional CLI `.public.jsonl` records are
checked against the trace/audit and matching initial packet when present.

**These are consistency checks, not a vendor signature or physical certification.**
The historical software `source_digest` and runtime metadata are not asserted to
match today's changed presentation code. The unchanged v5 model-facing contract
is checked explicitly. No model output is generated, repaired or regraded.

## Authentic chronology and deliberate omissions

Public requests/results come from the selected trace and hash-linked audit.
Initial evidence is reconstructed from the matching frozen parent packet because
the browser route did not always persist a public received-input event. If no
request events were saved, playback discloses this and shows results only. A
partial request trace or incomplete result trace is rejected. Timing is explicitly
**presentation pacing, not model token timing**.

Rejected submission text/arguments, local paths, raw protocols, hidden labels and
private metadata are not sent to the browser. Saved replay retains rejection
codes/fields but omits correction prose and historical-limitation prose; that
omission is disclosed. Final public findings, facts, numerical matches, citations,
request/result order and recorded verdicts are preserved. No fictional tool calls,
reasoning, physical relationships or model commentary are inserted.

## Judge-facing presentation

The graph defaults to at most ten already-received nodes around the selected
event/finding, with only edges from the full recorded projection. A disconnected
hypothesis is left disconnected. A missing source link is not drawn as causation.
**Show all evidence** restores every received node/edge. Full labels wrap rather
than truncate; the full desktop graph may scroll horizontally, while mobile uses
one readable column. All entities remain inspectable, including provenance.

The takeaway counts actual SUPPORTED measured/source findings and actual
NOT_ESTABLISHED causal findings. It does not hard-code fault 9 or reinterpret old
unscoped results. Exact justifications, source IDs, missing premises and next
requests are expandable. A compatible example does not uniquely identify a cause;
whether that fault always causes the pattern is a separate question.

## Reproduce offline tests and browser screenshots

```bash
python -m pytest -q
```

Optional explicit Chromium check (software fixtures; zero model calls):

```bash
python -m pip install playwright
python -m playwright install chromium
PETROMIND_BROWSER_CHECK=1 \
PETROMIND_SCREENSHOTS=.petromind/saved-replay-browser-v1 \
python -m pytest tests/test_saved_investigation.py -q
```

For an existing browser executable, also set `PETROMIND_CHROMIUM=/path/to/chromium`.
Synthetic screenshots carry an unmistakable software-fixture banner. They do not
establish that your real saved run imported successfully. The original recorded
cases can also be checked using `scripts/verify_guided_investigation.py` with
`--capture`, optional `--monitoring`, `--browser`, and a fresh `--screenshots` path.
The test suite never calls Meta; mocked HTTP requests are not live verification.
