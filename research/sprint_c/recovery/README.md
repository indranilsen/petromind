# Sprint C: Mac execution guide

**No paid hosted execution. No owner approval or Mac certification is inferred.**
This is research only, under the existing $10 Sprint C authorization. Read
[INVESTIGATION.md](INVESTIGATION.md) and [FINAL_REVIEW.md](FINAL_REVIEW.md).
No production changes, journal repair, reservation reset or attempted-cell replay.

## 1. Source and dependencies

Use a trusted Mac, Python **3.12**, Git, and writable local **APFS**. Quit other
Sprint C runners. Exclude source and data from custom sync/restore tools during
execution. Never use Desktop, Documents, iCloud, Dropbox, OneDrive, Google Drive,
network shares or disk images stored there. Keep one active Mac/account. The
registry cannot prevent deliberate destruction of all guards or copying them to
a different computer. Do not expose owner files to an agent with filesystem tools.

The final handoff supplies the exact reviewed commit. Replace `REVIEWED_COMMIT`
below with that SHA, not a moving branch name. Use a new checkout; do not discard
an existing working tree.

```bash
bash
set -euo pipefail
umask 077
mkdir -p "/Users/isen/Personal"
cd "/Users/isen/Personal"
git clone https://github.com/indranilsen/petromind.git petromind-sprint-c
cd petromind-sprint-c
git fetch origin research/sprint-c-citation-verdict
git checkout --detach REVIEWED_COMMIT
git status --short
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,agent,experiments,audit]'
python -m pytest -q tests research/synthetic_challenge/tests research/synthetic_challenge/integration
```

`git status --short` must be empty. Keep this commit unchanged through execution,
audit, scoring and export; do not pull or edit code mid-continuation.

## 2. Download, verify, prepare and certify (API free)

Download [PetroMind-Sprint-C-Recovery-LOCAL-PRIVATE.tar.gz](https://chatgpt.com/library?file_id=libfile_dee28c425f6c81918a50e113a8cc6d98&account_id=personal)
from ChatGPT Library to Downloads. Required SHA-256:

`f8df9fb71ded437ea6ac47f5d0ae0a820395c55b1b7fcbe3cd262049936ff7bb`

Use this exact preserved archive without recompressing it. Its embedded guide and
hosted certificates are historical evidence; **this guide supersedes them**.

```bash
bash scripts/sprint_c_mac.sh prepare "$HOME/Downloads/PetroMind-Sprint-C-Recovery-LOCAL-PRIVATE.tar.gz"
```

This creates a **new** protected root at
`/Users/isen/Personal/PetroMindSprintC`. It verifies the outer SHA and
manifest, rejects unsafe tar members, verifies all **136** original commitments,
extracts the frozen private evaluator and verifies its readiness. The original
inner archive SHA is
`329633ea62644929c0511d1e7495e97f8a0f14bdf7aa4408f5221d1f8066eff4`;
the evaluator archive SHA is
`10f06578af1255e92bad13d1f4c8735c24c1f3d4f2e1947ad5cde3d45b5e5294`.
Original evidence remains untouched. The generated proposal and **22-cell** plan
must match preserved copies exactly.

The helper tests your actual APFS surface, flush/atomic-replace behavior, lock
exclusion/release, restart, interrupted writes/transactions, divergent views and
concurrent snapshots. It starts separate writer/reader processes with **actual
overlap**, then checks all 500 rows and witnesses. Mac file flushes require working
`F_FULLFSYNC`; accounting SQLite requires journal DELETE, `synchronous=EXTRA`,
`fullfsync=ON`. A finite pass cannot prove universal power-loss/hardware safety.
Hosted tests cannot certify your Mac. Every paid gate revalidates current witnesses.

If preparation fails, stop and return the error. Never edit witnesses or recreate
active state. An API-free failed preparation may be inspected before selecting a
fresh disposable probe; it has neither spent money nor approved reconciliation.

## 3. Inspect, then explicitly approve

```bash
cat "/Users/isen/Personal/PetroMindSprintC/proposal.json"
cat research/sprint_c/recovery/INVESTIGATION.md
cat research/sprint_c/recovery/FINAL_REVIEW.md
cat research/sprint_c/recovery/results/budget-forecast.json
```

Approval assumes all 19 saved execution-cell sets account for **122** HTTP attempts,
no other client used the authorization, the **119** unique local HTTPS-envelope
receipts are trustworthy, and the frozen 512,000-byte payload, 4,096-output-token
and price bounds applied. Local evidence supports the bound conditionally; it
cannot certify exclusive-client history or replace provider billing records.

The accepted liability is **$4.73195485**: $0.80901085 in settlements plus three
global maximum holds of $1.307648. Only after approval and local certification does
**$5.26804515** become usable under the existing $10 cap. PR #33's **$9.88406950
remains held**. This accepts a conservative loss bound, not exact history, new
funds, retries, hosted execution or production integration. Confirm current provider
standard rates do not exceed frozen input $1.25/M and output $4.25/M; if they do,
stop for a separately reviewed policy. Never edit old prices.

**Run this only after choosing to accept the assumptions.** Replace the name:

```bash
bash scripts/sprint_c_mac.sh approve "YOUR NAME"
```

Only proposal ID
`b51a6501e191516e2fbf7324b00680a48e1ed2e5ad9ac59ac5fee6ef7f2fcd11`
is accepted. The review binds one canonical database and `run` directory.
A fixed registry under `~/.local/share/petromind-sprint-c-authorizations/`, outside
copied packages, consumes that activation. The owner lock precedes activation and
database creation. A failed activation does not grant a second journal; return the
error instead of deleting guards. Never clone an active account.

## 4. Execute only the permitted cells

```bash
bash scripts/sprint_c_mac.sh run
```

The helper reads `MODEL_API_KEY` with echo disabled, exports it only in a subshell,
and clears it on every exit. Do not paste it into commands, Git, JSON, a document
or chat, and do not use `set -x`. No website/server is needed. Muse receives only
the current public case and frozen five-sensor tools, never the evaluator,
reference answers, other case packets or filesystem tools.

Only the **22 never-attempted v2 suite cells**, in original order, may execute.
All six old attempts, including failed c-6f03/V2, remain excluded. No transport
retry. Reservations commit and anchor before HTTP; only validated provider usage
releases a hold. Unresolved requests retain full liability. Any accounting, API,
usage, isolation or persistence error stops. Preserve every file after a stop.
A normally recorded failure prints `STOPPED_NO_RETRY`. Do not repeatedly run it to
improve coverage; return the stop/error before deciding whether another untouched
cell is safe. A process kill can leave incomplete captures, which intentionally
block audit/scoring rather than silently dropping an attempt.

## 5. Audit, score and return a private export

After execution exits, including a normally recorded failure:

```bash
bash scripts/sprint_c_mac.sh score
bash scripts/sprint_c_mac.sh export
```

Audit takes the single-owner lock and verifies original commitments, review and
continuation identity, SQLite integrity/hash chain/anchors, allowed attempt order,
result equality, request counts and host chains. Corrupt/missing captures stop
scoring/export. The unchanged private evaluator scores preserved v2 and allowed
new captures. Full-plan totals and complete matched-case comparisons are distinct;
different protocol versions are not pooled for scientific inference.

`final-comparison/suite/coverage.json` contains evidence-qualified correctness,
raw verdict agreement, per-verdict recall, incorrect contradictions,
reference-disagreeing abstentions, unsupported causal support, literal citation
failures, tool use, usage estimates, latency and completion. Blinded packets and
an unblinding map are separate files. Semantic entailment, premise quality and
next-evidence usefulness stay null pending qualified independent review.

Export prints a SHA-256 and creates:

`/Users/isen/Personal/PetroMindSprintC/final-export.tar.gz`

It contains accounting/anchors/activation/registry, review, storage witnesses,
captures, source commit, final audit and file commitments, plus scored comparisons
and blinded packets when scoring succeeded. Upload the **private archive and its
printed SHA-256** back here for independent review. Keep original archives and
live state. Never publish the export or give it to Muse. Existing destinations are
not overwritten; do not repeat score/export into the same directory.

These are correlated synthetic development cases that already informed the
interventions. At most **six** complete matched groups are possible without
replaying the preserved failure. No outcome authorizes production use.
