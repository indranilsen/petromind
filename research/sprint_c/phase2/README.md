# Sprint C Phase 2: reliable execution and separate confirmation

This isolated research phase stages a **maximum $30 additional cap**. Preparation
does not authorize spending. One explicit owner-local `authorize --additional-usd 30`
command records a versioned authorization before activation or any HTTP request.
Routine execution and resume require no repeated chat approvals after that decision.
No production, demo, classifier, v5 auditor, old capture or frozen benchmark changes.

## What changed and what remains unknown

The uploaded local export verifies 203 file commitments, an intact 99-event SQLite
chain/anchors, 49 requests, 48 settlements and one unverified request. Its SHA-256:
`98698f31e519da8d2265f5089741b4798dfc960be3a70e2ddea74722312314cf`.
The failed envelope and specific validation failure were not retained. The precise
cause of that historical request **cannot be reconstructed**, and is not asserted.

Reproducible defects in the earlier execution path:

- Receipt validation required `completed` before the agent could recognize a
  documented `incomplete` terminal response. A valid token-limited response was
  therefore mislabeled as unverifiable usage and could never reach model handling.
- All field failures became one generic code, and no redacted envelope witness was
  retained. HTTP errors similarly lost the status/category distinction upstream.
- One ended unverified request blocked all later cells forever. Merely replacing
  code invalidated the old execution identity, without an explicit migration path.
- Abrupt termination could leave a cell marker without a result, blocking scoring
  rather than preserving an explicit interrupted outcome and continuing untouched cells.

New field-specific errors and durable **whitelisted** diagnostics record terminal
status, model match, ID/body hashes, numeric usage, known error enums and output
item types. They exclude raw bodies, error messages, text, tool arguments, prompts,
credentials, reasoning and unknown field names. No unrestricted envelope is saved.
A nonterminal/malformed/mismatched receipt never settles. Valid bounded usage on
`completed`, `incomplete`, `failed` or `cancelled` synchronous responses can settle;
only a valid completed model response can execute tools. Incomplete or failed
output is not replayed/executed. No token-cap increase, continuation call or hidden
retry is used to turn a partial response into a completed scientific observation.
Missing cached counts conservatively use the standard input rate; malformed
provided counts, inconsistent sums and reservation overruns retain the full hold.

The fixed HTTPS endpoint, TLS, response/payload bounds, no proxy/redirect, zero
transport retry, original stateless encrypted reasoning replay and tool validation
remain. An unknown envelope's future exact text is deliberately unavailable: the
redacted witness retains the specific failed field and safe metadata for diagnosis.

Primary sources checked 2026-11-02:
[Meta Responses](https://dev.meta.ai/docs/protocols/responses),
[response/usage schemas](https://dev.meta.ai/docs/api-reference/responses/schemas),
[errors](https://dev.meta.ai/docs/error-handling),
[standard pricing](https://dev.meta.ai/docs/pricing-rate-limits).
Frozen standard rates remain input $1.25/M, cached input $0.15/M, output $4.25/M.

## A small, separate account with cumulative reporting

The original DB/events, owner approval, proposal, failed requests and captures are
read-only evidence. Preparation pins the owner's exact export and verifies its
contents against the original 136-file package and frozen evaluator. After explicit authorization, a new
`phase2/journal.sqlite` imports **$5.35707335** in liabilities, including the entire
old $0.17884550 unresolved hold. No old request is retrospectively settled or free.

One proposed versioned policy binds the canonical DB, execution plan, code, archive and
storage certificate. Its hard limit is **$30 of new phase settlements plus full
unknown holds**, inside a cumulative $40 Sprint C authorization. The previous
$4.64292665 capacity is not added to the phase's $30 limit. PR #33 holds remain
reported separately. No automatic cap increase; no automatic same-cell retries.
The entire phase has at most 560 requests (70 declared cells x 8 frozen turns).

SQLite DELETE/EXTRA/fullfsync transactions reserve before HTTP, settle only verified
unique provider identities and retain immutable anchors. The journal genesis binds the explicit owner-authorization record. One owner lock excludes
concurrent phase runs; commands also hold the legacy owner lock. A fixed incident
registry is atomically advanced to this phase, disabling the old runner's gate.
It cannot activate a second account from an alternate output directory. The old
registry contents survive in the immutable source export; old transactions are untouched.

Once synchronous I/O exits, an append-only transport-closure event permits other
cells while retaining the full unknown liability. On restart, exclusive ownership
establishes the previous local runner ended; open requests are closed with that
explicit basis, retaining holds. Interrupted cells are marked and never silently
rerun. Torn capture bytes are retained and committed as interrupted evidence,
excluded from successful scoring. An intact committed SQLite tail missing its last
anchor may restore that single anchor; missing DB rows, extra anchors, other hash
or SQLite corruption stop execution. Hardware/custom-sync rollback of all independent
copies is outside trusted-owner guarantees. Keep the validated APFS workspace local.

## Frozen science, explicitly separate execution groups

| Group | Cells | Interpretation |
|---|---:|---|
| Existing archived runs | Unchanged | Exploratory history; two matched cases, two preserved failures |
| `confirmatory-v1` | 28 | Primary fresh seven-case x four-variant run under new execution handling |
| `remaining-v1` | 14 | Only previously untouched cells; secondary completion batch, reported separately |
| `confirmatory-repeat-v2` | 28 | Optional explicitly requested full repeat; never selectively replaces primary failures |

Default execution attempts confirmation first, then the remaining 14. All seven
cases, variant order, prompts, model `muse-spark-1.3`, medium reasoning, 4,096 output
tokens, eight turns, 360-second cell deadline, 24 tool calls, retrieval, tools,
five-sensor budget, output contract and scorer remain frozen. Each cell has a fresh
model context and fresh trusted-host session. The private evaluator/answer key is
never part of a model context. No model filesystem, shell or network tool is added.

Already attempted primary cells are never repeated by `run` or `resume`. Incomplete,
failed and interrupted outcomes stay visible. A complete optional repeat is its own
execution protocol and cohort; do not pool it with the primary or replace selected
primary outcomes. Repeated cases are not independent observations. The original
22-cell file and old reports are untouched; the new 14-cell group is exactly its
unattempted suffix. No synthetic reference or prompt tuning is allowed.

## Commands on the owner's existing Mac checkout

Use `/Users/isen/Personal/petromind`. Fetch/check out the exact new commit supplied
in the handoff response; don't edit the code or pull again after preparation.
The existing Python 3.12 `.venv` and validated owner root are reused.

```bash
cd /Users/isen/Personal/petromind
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[test,agent,experiments,audit]'
python -m pytest -q tests research/synthetic_challenge/tests research/synthetic_challenge/integration

# API free: verifies/imports evidence and stages the proposed policy.
bash scripts/sprint_c_phase2_mac.sh prepare

# Owner decision: records $30 additional authorization; no API requests.
bash scripts/sprint_c_phase2_mac.sh authorize --additional-usd 30
bash scripts/sprint_c_phase2_mac.sh validate

# Paid. Hidden key prompt; key lives only in a subshell and is cleared on exit.
bash scripts/sprint_c_phase2_mac.sh run
```

Preparation is idempotent for the same verified identity and refuses changed
source/state. Do not rerun the original `sprint_c_mac.sh prepare`, approve or run.
`final-export.tar.gz` must still be at the existing owner root, as created earlier.
No need to download the old archives again or rerun a certificate that remains valid.
If the certificate/current volume fails, return the error; no hosted fallback.

If interrupted or stopped, preserve state and resume only untouched cells:

```bash
bash scripts/sprint_c_phase2_mac.sh resume
```

Receipt/model failures retain evidence and permit other untouched cells. API errors
including authentication, 429, 5xx and connection/timeouts stop the batch rather than
spending through an outage; resume when corrected. Local infrastructure/corruption
or exhausted authorization also stops; return those errors rather than editing state.
Progress is printed at cell start, HTTP start and cell finish, including classified
reasons and accounting. No silent retries or private response text on the terminal.

After execution exits, these commands are API free:

```bash
bash scripts/sprint_c_phase2_mac.sh score
bash scripts/sprint_c_phase2_mac.sh report --export
```

Scoring holds the owner locks, validates all accounting/capture commitments, uses
the unchanged private evaluator and writes a fresh score snapshot. Repeating score
with identical inputs verifies/reuses its committed snapshot. Exports are immutable
snapshots under `/Users/isen/Personal/PetroMindSprintC/phase2/exports/`; the command
prints the archive path and SHA-256. Upload that private archive and SHA back here.
They include original export evidence, new accounting, captures, diagnostics,
coverage and blinded packets. Never publish them or send them to Muse.

If primary confirmation still has a failure and a full repeat is desired, the owner
can explicitly run the already declared repeat protocol, sharing the same $30 cap:

```bash
bash scripts/sprint_c_phase2_mac.sh run \
  --group confirmatory-repeat-v2 --authorize-repeat
bash scripts/sprint_c_phase2_mac.sh score
bash scripts/sprint_c_phase2_mac.sh report --export
```

This always schedules the full 28-cell repeat, not just the failed cell. Its resume
also requires both repeat flags. No repeated execution beyond this declared cohort
or automatic additional authorization is implemented.

## Analysis and independent review

Coverage reports per execution group and complete matched cases only. It includes
per-case qualified correctness, raw verdict agreement, full verdict confusion,
qualified SUPPORTED/NOT_ESTABLISHED/CONTRADICTED recall, incorrect contradiction,
reference-disagreeing abstention, unsupported causal support, literal citation
failures among raw verdict matches, tools, costs, holds, latency and completion.
Full-plan mechanical totals are separate from paired comparisons. Correctness and
citation qualification are distinct; literal citation checks do not prove entailment.

Blinded reviewer packets contain exact atomic propositions and scope, initial and
received tool evidence/model assumptions, submitted verdict/citations, missing
premise and next-evidence fields. A separate private unblinding map identifies the
execution group/variant. Qualified independent human review is not available here;
semantic entailment, scientifically justified abstention, premise quality and next
step usefulness remain **ungraded**, not assigned by Muse or this runner.

Current real evidence remains exploratory: across two matched cases V0/V1/V2/V3
have 4/6, 5/6, 5/6 and 6/6 qualified findings. Neither matched case supplies a true
CONTRADICTED control. No improvement claim follows yet. Confirmation is fresh
execution on previously inspected, correlated development cases, not unseen or
population-level validation. Never call mock execution a scientific experiment.

## Offline validation

Full local regression: **702 passed, 2 skipped**. The skips are the existing
optional-private check and the native-Mac-only surface test on hosted Linux.
The **41 phase regressions** cover terminal response variants, malformed/missing
usage, field errors, redaction, HTTP/JSON/timeout distinctions, cumulative caps,
ended holds, interruption/torn captures, rollback/tail anchors, single-owner
exclusion, duplicate IDs, idempotent cutover, anti-cloning, repeat authorization,
fresh contexts, encrypted replay and sanitized CLI failures. The native macOS CI
job includes these regressions and the existing APFS/full-flush storage checks.

[Offline validation receipt](OFFLINE_VALIDATION.json): the real frozen private
scorer was used after **42 mocked cells**, including all 28 confirmatory cells
(seven matched cases) and 14 historical-completion cells. Resume added zero
requests; groups remained separate, snapshots verified, and semantic grades stayed
null. Repeated exports preserved prior snapshots. All 48 actual archived settled
receipts also pass the new strict receipt rules. These are engineering checks,
**not new scientific results, an owner Mac certificate, or hosted paid execution**.
