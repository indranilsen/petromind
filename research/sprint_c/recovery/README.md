# Local-only recovery workflow — owner review required

Current decision: **BLOCKED** for further paid calls. This update made **zero API
calls**. See [the investigation](INVESTIGATION.md), the
[loss-bound proposal](results/reconciliation-proposal.json) and the
[unchanged remaining-cell plan](results/remaining-cells.json).

This is an owner-reviewed continuation of the same $10 Sprint C authorization.
It is not exact recovery, a fresh budget, a new experiment, a retry mechanism or
permission to modify the production demo. All original monetary bytes remain
unchanged. The old one-case scientific observation and semantic-review status are
unchanged.

## 1. Check out the research source locally

Run these steps on your trusted Mac/Linux machine, not in hosted ChatGPT Work.
Keep source, owner data, active money state and private evaluator off shared/synced
folders. Do not monitor a live money journal from another hosted execution session.

```bash
git clone --branch research/sprint-c-citation-verdict \
  https://github.com/indranilsen/petromind.git petromind-sprint-c
cd petromind-sprint-c
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,agent,experiments,audit]'
python -m pytest -q tests research/synthetic_challenge/tests research/synthetic_challenge/integration
```

For an existing clone, fetch/switch to the PR #34 branch without discarding local
changes. Verify its head matches the reviewed PR. Python 3.12 is recommended for
safe archive extraction; the runtime code supports the repository's Python 3.10+.

## 2. Recover the original preserved package without repairing it

Download the owner's `PetroMind-Sprint-C-PRIVATE.tar.gz` (also included in the
new private recovery bundle). Set absolute paths; the owner root must be new:

```bash
export PM_OWNER_ROOT="$HOME/.local/share/petromind-sprint-c-recovery"
export PM_ARCHIVE="/absolute/path/PetroMind-Sprint-C-PRIVATE.tar.gz"
mkdir -m 700 "$PM_OWNER_ROOT"
python - "$PM_ARCHIVE" "$PM_OWNER_ROOT" <<'PYEXTRACT'
import hashlib,sys,tarfile
from pathlib import Path
p=Path(sys.argv[1]);root=Path(sys.argv[2])/'preserved'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='329633ea62644929c0511d1e7495e97f8a0f14bdf7aa4408f5221d1f8066eff4'
root.mkdir(mode=0o700)
with tarfile.open(p) as t:t.extractall(root,filter='data')
PYEXTRACT
export PM_PACKAGE="$PM_OWNER_ROOT/preserved/PetroMind-Sprint-C-PRIVATE"
mkdir -m 700 "$PM_OWNER_ROOT/evaluator"
python - "$PM_PACKAGE/PetroMind-Sprint-B-PRIVATE-Evaluator.tar.gz" "$PM_OWNER_ROOT/evaluator" <<'PYEVAL'
import hashlib,sys,tarfile
from pathlib import Path
p=Path(sys.argv[1])
assert hashlib.sha256(p.read_bytes()).hexdigest()=='10f06578af1255e92bad13d1f4c8735c24c1f3d4f2e1947ad5cde3d45b5e5294'
with tarfile.open(p) as t:t.extractall(sys.argv[2],filter='data')
PYEVAL
export PM_PRIVATE_ROOT="$PM_OWNER_ROOT/evaluator/private_sprint_b"
python research/synthetic_challenge/integration/verify_readiness.py \
 --release-root research/synthetic_challenge --private-root "$PM_PRIVATE_ROOT" --repo-root .
python scripts/recover_sprint_c.py propose --package "$PM_PACKAGE" \
 --out "$PM_OWNER_ROOT/proposal.json"
python scripts/recover_sprint_c.py plan --package "$PM_PACKAGE" \
 --out "$PM_OWNER_ROOT/remaining-cells.json"
```

The proposal verifier checks all 136 original commitments, the old original budget
chain/configuration, readable Sprint C event links/receipts, unique provider IDs,
capture/result/stop counters and frozen source ceilings. It explicitly records the
failed cell's missing usage event. It does not repair the old head/log, infer a
missing provider response ID, or reclaim the uncertain requests. It refuses a
different incident or an unbounded/changed source. Review its assumptions.

## 3. Validate the actual local filesystem

Create the state directory on the filesystem you will actually use. The storage
check directory is fresh and disposable; do not point it at real accounting data.

```bash
export PM_STATE="$PM_OWNER_ROOT/continuation"
export PM_DB="$PM_STATE/continuation.sqlite"
export PM_RUN="$PM_STATE/run"
export PM_STORAGE="$PM_OWNER_ROOT/storage-check"
mkdir -m 700 "$PM_STATE"
python scripts/recover_sprint_c.py storage-validate \
 --directory "$PM_STORAGE" --owner-local
```

Prepare both terminals before starting the overlap test. In terminal A:

```bash
python scripts/recover_sprint_c.py storage-writer --directory "$PM_STORAGE"
```

Immediately run the reader in terminal B while the writer is active. Activate
the same venv and set `PM_STORAGE` to the **same absolute path**:

```bash
python scripts/recover_sprint_c.py storage-reader --directory "$PM_STORAGE"
```

After both finish, in terminal A:

```bash
python scripts/recover_sprint_c.py storage-certify --directory "$PM_STORAGE"
```

Certification requires matching nonce/device/inode witnesses, different process
IDs, actual overlap, completed writer/readback, every safety check and no
observed divergence. A failed or non-overlapping probe does not grant a certificate;
repeat only in a **new disposable probe directory**, never by editing a failed
report. A hosted certificate is rejected by the local paid gate even if its finite
checks passed. A finite pass is not a proof of universal crash durability.

## 4. Explicitly review the conservative loss accounting

Read `proposal.json` and the investigation. The proposal carries $4.73195485 of
Sprint C liabilities, including $3.922944 in global maximum holds for the three
uncertain attempts. Its conditional remaining capacity is $5.26804515; PR #33's
$9.88406950 remains held separately. Neither figure is a provider invoice.

**This is the owner approval step. Do not run it unless you accept the stated
completeness, source-bound and trusted-receipt assumptions.** It approves a loss
bound, not exact history, extra funding, hosted use or production changes.

```bash
python scripts/recover_sprint_c.py review \
 --proposal "$PM_OWNER_ROOT/proposal.json" \
 --accept-proposal-id b51a6501e191516e2fbf7324b00680a48e1ed2e5ad9ac59ac5fee6ef7f2fcd11 \
 --owner "Indranil Sen" --db "$PM_DB" \
 --out "$PM_OWNER_ROOT/owner-review.json"
python scripts/recover_sprint_c.py init --owner-local \
 --package "$PM_PACKAGE" --proposal "$PM_OWNER_ROOT/proposal.json" \
 --review "$PM_OWNER_ROOT/owner-review.json" \
 --certificate "$PM_STORAGE/certificate.json" --db "$PM_DB"
```

Initialization is exclusive, registers the one canonical continuation database,
and writes a conservative-carry-forward genesis. The original ledger remains
unchanged. Never create a second active clone or overwrite the registered state.
The reviewed run directory is fixed to `$PM_STATE/run`; changing output directories
cannot replay completed cells or reset the account. Missing capture records for
already reserved local cells cause a safe stop.

## 5. Run only the permitted remaining cells

Confirm the provider's current standard rates do not exceed the frozen estimates;
otherwise stop for a new reviewed pricing policy without editing old prices.
Supply the key in your local process environment with input echo/history disabled:

```bash
read -rsp 'Meta API key: ' MODEL_API_KEY; echo
export MODEL_API_KEY
python scripts/recover_sprint_c.py run --owner-local \
 --package "$PM_PACKAGE" --proposal "$PM_OWNER_ROOT/proposal.json" \
 --review "$PM_OWNER_ROOT/owner-review.json" \
 --certificate "$PM_STORAGE/certificate.json" --db "$PM_DB" \
 --plan "$PM_OWNER_ROOT/remaining-cells.json" --out "$PM_RUN" \
 --private-root "$PM_PRIVATE_ROOT"
unset MODEL_API_KEY
```

Use Bash for `read -rsp`; on macOS start `bash` first if your interactive shell is
zsh. The key is never written to this package, a prompt, a log, Git or Library.
No server/UI needs to run. Progress comes from the single owner process.

The new journal carries the entire conservative liability, retains uncertain new
holds, and enforces the existing $10 cap before HTTP. Existing cumulative ceilings
remain 320 attempts and 1,310,720 reserved output tokens including the old 122
attempts. No automatic transport retry, failed-cell replay, prompt change or
new retrieval is allowed. Every response settlement is tied to its new reservation,
validated provider ID, usage and request/response commitments. No old response can
be reused to settle a new request. Any failure stops; do not delete state to resume.

## 6. Score offline after model execution ends

```bash
python scripts/recover_sprint_c.py score --package "$PM_PACKAGE" \
 --out "$PM_RUN" --private-root "$PM_PRIVATE_ROOT" --db "$PM_DB" \
 --destination "$PM_OWNER_ROOT/final-comparison"
```

The scorer takes the owner lock, refuses active execution, preserves the old failed
cell, merges only permitted new cells, checks host hashes and uses the unchanged
private evaluator. `suite/coverage.json` contains full-plan and matched-case
metrics; blinded reviewer packets and a separate unblinding map are created.
All semantic scores remain ungraded until qualified independent review.
Do not give any full package, reference answers, score file or other case packet
to Muse. No failed/completed cell is rerun to improve its score. At most six cases
can become complete matched groups under this no-replay plan.

Preserve the full continuation DB, immutable anchors, activation/registry, review,
storage witnesses and run captures together with their final digest. Never resume
from a stale backup that discards already attempted requests. No result authorizes
production/demo integration; a separate explicit owner approval remains required.
