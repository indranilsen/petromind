# Live assessment recommendation repair (v4)

The reviewed live run reached Meta, retrieved three knowledge topics and history,
then exhausted six turns after two rejected submissions. Both errors were
`unknown_next_target` at `findings[0].next_evidence`. Rejected arguments were
sanitized, so the exact submitted target and purpose cannot be reconstructed.
No accepted assessment exists for that run. The regression below reproduces its
interaction pattern using constructed invalid arguments, not recovered model text.

## Focused change

New live protocols use `claim-auditor-v4-active-recommendations` (active sensors)
or `claim-auditor-v4-scope-recommendations` (fixed evidence). Older modules,
experimental protocols and captured outputs are unchanged. The demo refuses an
old live protocol rather than editing or silently upgrading it.

The recommendation object remains three strings: `kind`, `target`, `purpose`.
The schema enumerates public target IDs. Initial context explicitly maps each
kind to its allowed IDs and gives syntax examples. Python still validates
kind/target consistency, lengths, empty purpose and supported-scope consistency.
Examples do not prescribe a verdict, establish a document's existence, or execute
a test. No unsupported alternative or invalid assessment becomes a successful
abstention.

Errors now distinguish shape/type, unknown kind, unknown target, excess length,
missing purpose and nonempty fields for `none`. Each identifies the exact field
and gives a correction. Unknown targets receive the selected kind's public list.
Recorded errors also contain safe structural diagnostics: recognized kind,
string-type flags, target membership and whether purpose is nonempty. Raw rejected
targets, purposes, statements and private reasoning are never echoed or stored.
Public UI events continue to show only error code, field and correction.

Unchanged: six model turns, eight tool calls, at most two assessment repairs
(initial rejection plus two repairs), immediate stop for an identical repeated
invalid submission, five unique sensors, cache/missing accounting, citations,
physical-evidence checks, training-only history and label-free live history.
A six-turn run may stop before using both repair opportunities; there is no extra
model call or automatic retry. These changes improve the contract, not physical
correctness or demonstrated model reliability.

## Run after merging

Stop the old server with Ctrl+C. From the repository with your Python environment
activated:

```bash
git pull --ff-only
python -m pip install -e '.[test,agent,audit]'
python -m pytest -q

python scripts/demo_claim_audit.py prepare-live \
  --capture .petromind/claim-audit-v1 \
  --out .petromind/readiness-live-005 \
  --max-cost-usd 0.50 \
  --active-sensors \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json
```

Use a fresh output name if `readiness-live-005` already exists. Never edit or
reuse `readiness-live-004`. Preparation makes zero API requests. It must report
`claim-auditor-v4-active-recommendations`.

With `MODEL_API_KEY` already exported, run **one** capped smoke investigation:

```bash
python scripts/smoke_claim_live.py \
  --capture .petromind/claim-audit-v1 \
  --live .petromind/readiness-live-005 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --case fault_expectation \
  --authorize-paid-meta
```

This is paid and uses the existing conservative estimated-cost cap, not an invoice
guarantee. Do not also click a live browser investigation with this directory;
that would be another paid investigation. CLI output is not imported as a new
browser execution. Share the resulting protocol and JSONL records for review;
never upload the key, dataset or private source protocol.

For an interactive browser run **instead of the CLI smoke**, serve the unused
fresh protocol:

```bash
python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --monitoring .petromind/monitoring-demo-v1 \
  --enable-live .petromind/readiness-live-005
```

Open http://127.0.0.1:8765/demo, hard-refresh, select **Live Muse API · paid**,
complete monitoring/diagnosis and click Investigate once. A failed run remains
failed; captured playback is separate and unchanged.

## Verification scope

Offline tests cover all five recommendation kinds, exact correction fields,
sanitized errors, unchanged legacy validation, repeated submissions, bounded
repairs, unqueried citations, numeric mismatch, five-sensor accounting, fresh
protocol enforcement, and mocked four-retrieval/invalid-submission/repair sequences
for both fixed and active evidence. Mock success does not prove Muse will repair a
real submission. No independent engineering correctness claim follows from these
checks. The implementation environment has neither the exported API credential nor
the original local dataset, so no new paid test was executed here.
