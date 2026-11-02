# Accounting recovery investigation: facts, bounds, and unresolved causes

No API calls were made during this update. The original broken ledger/checkpoint,
old attempts, prompts, scoring and reviewer packets were preserved unchanged.

## Forensic preservation and exact-recovery search

The former scratch budget directory was no longer present. The owner-preserved
`PetroMind-Sprint-C-PRIVATE.tar.gz` was recovered instead and matched its previously
saved SHA-256 `329633ea62644929c0511d1e7495e97f8a0f14bdf7aa4408f5221d1f8066eff4`.
All **136** internal file commitments verified. An independent forensic ledger
copy was made and checked against the recovered source before recovery work.
The original ledger files are not used as a write target.

Four known saved/extracted copies contain the same 241-event readable prefix and
243-event head. No exact copy of the missing records was found in those copies.
Provider invoice/request-history records are unavailable. This is not an assertion
that the missing records cannot exist anywhere; exact transaction recovery has
**not** been established.

| Preserved item | SHA-256 |
|---|---|
| Sprint C readable event log | `eefd1b4ae7da840ff86e0dc7726ac5712a138a17cbef2bc720d2d752ba36810d` |
| Sprint C head checkpoint | `b0c5974aefc398cfe3538ece8a75bcca7938e9fcc510a205c00bcdeb4406e5e0` |

See [forensic hashes](results/forensic-preservation.json) and
[exact-copy search](results/exact-record-search.json). No monetary row was
fabricated, removed, reordered, repaired, or inserted into the old chain, and the
checkpoint was not moved backward.

## What the code and evidence establish

The old writer appends one complete hash-linked JSON event, fsyncs that file, then
writes/fsyncs a new head and replaces/fsyncs the directory. Those are **separate
persistence operations**, not a transaction across the two files. The shown code
has no event-log truncation/overwrite path. Its restart check correctly rejected
the inconsistent pair. This does not establish that its storage assumptions held.

The readable prefix is complete JSON with valid sequence/hash links: 121
reservations and 119 provider-envelope settlements, plus one closed-transport
acknowledgment. A torn final JSON record does not explain the actual preserved
shape. An ordinary interruption between append and checkpoint could leave the
checkpoint **behind** a durable log; it does not by itself explain an apparently
newer head with a shorter readable log. Stale/reverted visibility, independent
storage views, an outside write or broken persistence guarantees remain possible.

A further discrepancy exists outside the monetary writer: the final failed cell's
result metadata reports two usage responses, but its saved append-only model-event
log contains only **one** usage event. The preserved stop record and result both
report three HTTP attempts. Earlier text saying “120 captured usage responses”
reflected result metadata; only **119 usage events** actually survive in the
saved event files. No missing usage event is invented or used as a settlement.
This additional observation supports a broader persistence/visibility concern;
it does not identify the responsible storage component.

The original API-free probe preserved a log/head mismatch (430 vs 458) under a
writer and read-only monitor using advisory locks. A **new** disposable probe in
this update passed sequential append/readback, file/directory fsync, replacement,
lock exclusion/release, restart, concurrent-process snapshots, interrupted-append
and interrupted-checkpoint detection, interrupted SQLite rollback and divergent
view detection. Its separate hosted execution-session writer/reader also passed
500 iterations with an overlapping reader. Both outcomes are reported: a finite
pass does not erase the earlier reproducible failures or prove universal safety.

Two fresh execution calls expose different mount, PID and user namespace IDs,
while reporting the same boot-ID hash and logical device/inode values for the
probe directory. Thus they are not simply processes in one shared execution
namespace. This does **not** prove that their underlying files are separate copies
or identify the exact synchronization mechanism; advisory-lock equivalence cannot
be inferred from matching logical path/device/inode numbers alone.

| Hypothesis | Evidence and status |
|---|---|
| Cross-session visibility/synchronization | Supported as a concern by the original API-free mismatch and independent model-event discrepancy; exact mechanism unproven. |
| Separate mounts/snapshots | Fresh calls have distinct namespaces; actual backing-store/snapshot identity at the time of failure is unestablished. |
| Concurrent monetary writers | No second deliberate monetary writer was found. The independent read-only probe failed too. Namespace/file-lock assumptions still require validation. |
| Durability reordering / incomplete persistence | Possible; two-file commits were not atomic. Preserved evidence does not distinguish it from stale or overwritten views. |
| Partial JSON write | No partial final record in the readable prefix. This does not exclude loss of complete trailing records. |
| Arithmetic or model billing mistake | No arithmetic error found in the 119 readable settlements. Missing events prevent a complete balance. |

Hosted paid execution remains prohibited. The successful new finite test is not
presented as a repaired hosted storage service.

## Conservative proposal, not exact monetary reconstruction

The frozen runner refuses serialized request payloads above **512,000 bytes**,
uses an input bound of **2 × bytes + 8,192**, and caps output at **4,096 tokens**.
At the frozen standard rates this gives a global maximum request reservation:

`(1,032,192 × 1,250 + 4,096 × 4,250) nanodollars = $1.307648`.

The 19 archived cell attempt/result sets account for **122 HTTP attempts**; their
per-cell result files and stop counters agree on that total. All readable
reservations map to those cells. The reviewed source's single-request guard and
243-event head are consistent with at most that reservation count; no unidentified
extra client is assumed. Completeness of those captures and exclusive use of the
authorization are **explicit owner-review assumptions**, not provider-certified
facts. A different incident/count or source ceiling makes the verifier fail.

The 119 readable settlements have unique provider response IDs, validated usage,
correct arithmetic and links to readable request reservations. Their total is
$0.80901085. They are trusted local HTTPS-envelope receipts, not signed provider
billing records. The three other attempts receive **no settlement credit**:
each is charged the global maximum, even when a smaller readable reservation or
an observed usage estimate exists. No missing-event type, UUID or amount is
reconstructed.

| Conservative Sprint C carry-forward | USD |
|---|---:|
| 119 verified local settlement estimates | 0.80901085 |
| 3 uncertain attempts × global maximum | 3.92294400 |
| Proposed carried Sprint C liability | **4.73195485** |
| Existing Sprint C ceiling | 10.00000000 |
| Capacity only after explicit owner review | **5.26804515** |

PR #33's **$9.88406950** historical reservations remain held separately. Its
$0.48093015 observed estimate is not reclaimed or added a second time. The older
unreserved $0.11593050 is not transferred into Sprint C. No additional money is
authorized by this proposal. The readable $0.23488350 unresolved prefix holds are
covered by the larger three global maximum holds; they are not discarded or
charged twice. This deliberately gives up all unused capacity of those uncertain
requests for this continuation.

[The complete proposal](results/reconciliation-proposal.json) includes the source
and forensic commitments, receipt-ID commitments, arithmetic, assumptions and
owner-review requirement. Its identifier is
`b51a6501e191516e2fbf7324b00680a48e1ed2e5ad9ac59ac5fee6ef7f2fcd11`.
No review or real continuation database was created on the owner's behalf here.
The proposal is not an activated account balance.

## Local continuation design and readiness

The optional local continuation uses SQLite transactions with FULL synchronous
commits, append-only event-table triggers, immutable per-event anchor files and
one owner lock for the complete lifecycle. A reservation's committed row and
anchor must both persist before HTTP. Settlement releases only validated new
usage; uncertain new requests keep full holds and stop execution. Restart checks
SQLite integrity, all event hashes, carry-forward identity and the complete anchor
set. A rolled-back database prefix, missing anchor, duplicate settlement, recycled
historical response ID or changed pricing/ceiling fails closed.

The new journal does not pretend to contain the old history. Its genesis is an
explicit **conservative carry-forward** linked to the immutable proposal and owner
review. Approval is tied to one canonical database/output location. Exclusive
activation and a registry at the selected forensic package prevent ordinary
output-directory changes from resetting the budget or replaying cells. Do not
clone an active package/journal to create a second spender. This is a trusted-owner
local design, not tamper-proof protection against an operator who destroys every
independent anchor/approval copy.

The plan permits **22 originally unattempted v2 suite cells only**, preserving
case/variant order, prompts, model/settings, schemas, sources, retrieval depth and
five-sensor policy. The six original attempts are excluded, including the failed
V2 cell. If every permitted cell succeeds, at most six of seven cases become
complete matched groups; the preserved failure is never silently rerun. The new
local scoring path merges unchanged old captures with new ones, runs the frozen
private evaluator after model execution closes, and produces matched metrics and
fresh blinded semantic-review packets. It does not fabricate semantic grades.

**Current decision: BLOCKED for further paid execution.** Hosted execution is
unsafe/unverified; the conservative loss proposal has not received owner approval,
and no storage certificate exists for the owner's local machine. The tested local
workflow is prepared, but neither gate is inferred from this offline update.
Once the owner explicitly reviews the proposal and certifies their local surface,
that local workflow may activate the bounded continuation; it never authorizes
hosted execution, new money, production integration or a rewrite of old results.
