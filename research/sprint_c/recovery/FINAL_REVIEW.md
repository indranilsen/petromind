# Final recovery and security review

Scope: PR #34 recovery implementation, API-free validation, same frozen v2 plan.
Zero paid calls. Original proposal and remaining-cell JSON are byte-identical to
the prior PR commit. No production/scientific source, prompts or private keys changed.

## Corrections from the final review

- macOS file commits now require `F_FULLFSYNC`. Accounting SQLite requires DELETE
  rollback journals, `synchronous=EXTRA`, `fullfsync=ON`, checked on every open.
- Initialization acquires the owner lock before activation/database writes; failed
  setup consumes no extra authorization and cannot overwrite a prior activation.
- Owner reviews bind a fixed home-directory authorization registry. Copying a
  forensic package cannot create a second registry/spender. Database, output and
  registry are checked against the certified local volume and excluded sync paths.
- Certificates are regenerated from all current witnesses when checked: exact
  required tests, report digests, nonce/device/inode, process overlap, 500 committed
  rows and head, and current APFS facts. A copied/modified certificate alone fails.
- The Mac helper verifies both preserved archives and evaluator commitments,
  orchestrates overlapping processes without manual terminal timing, prompts for
  the secret without echo, and cleans the environment on error/exit.
- Unexpected runner exceptions record a sanitized failure where the ledger remains
  valid; interrupted reservations retain holds. No exception text enters captures.
  Host captures are flushed after closure. Killed/partial captures block final audit.
- Offline audit precedes scoring, verifies accounting/capture/host chains and
  produces a private export with commitments while holding the owner lock.

## Safeguards and evidence

| Requirement | Enforcement / regression |
|---|---|
| Explicit approval | Proposal verification; v2 review digest, exact proposal ID, owner name, canonical DB/output and fixed registry; no default approval |
| Actual Mac storage | APFS block volume, sync-path exclusions, required full flush, exact certificate/current witnesses; Linux/hosted local gate rejected |
| Single spending account | Fixed incident registry, exclusive activation, reviewed paths and single-owner lock; copied package cannot change scope |
| Prior liabilities | Genesis binds unchanged proposal/review and entire $4.73195485 carry; PR #33 holds unchanged |
| Before HTTP | SQLite reservation commit plus immutable anchor completes before request guard returns; interrupted anchor blocks continuation |
| Trustworthy usage | Frozen fixed-endpoint TLS client, typed bounded usage, unique provider ID and request/response commitments; historical IDs rejected |
| Uncertain requests | Full unresolved reservation retained; invalid provider usage and interrupted-request regressions stop further spending |
| Corruption / rollback | SQLite integrity, all hashes, exact anchor set and activation identity; prefix rollback/tampering regressions |
| No attempted-cell replay | Unchanged plan excludes old six attempts; new markers are durable before cell execution; existing monetary tasks need captures |
| Private scoring / five sensors | Unchanged Bridge B, frozen tools and trusted host; existing isolation/budget tests; no model filesystem tool or scorer access |
| Concurrency | Entire execution/audit/score/export lifecycle owns one nonblocking lock; reservations additionally transactional |
| Historical preservation | Archive SHA + outer manifest + 136 inner commitments; independent original ledger copies remain read-only inputs |

These are trusted-owner controls, not protection against a malicious account owner
who removes all guards or uses another machine/account. The owner must exclude
custom sync, cloned live state and disk images backed by synced files. Local
device checks cannot prove those facts or hardware power-loss behavior.

## Accounting assumptions and budget

The original 19 archived cell sets count 122 attempted requests, with 119 surviving
unique validated settlements totaling $0.80901085. The missing usage event is
explicitly documented. Completeness/exclusive-client history and origin of local
TLS receipts remain owner assumptions; no provider invoice or exact lost events
were recovered. Frozen source limits yield maximum request hold $1.307648:
`(2*512000+8192)*$1.25/1e6 + 4096*$4.25/1e6`.

Three uncertain attempts retain $3.922944 in full global holds. Total carry is
$4.73195485 and conditional capacity is $5.26804515. Approval neither certifies
exact billing nor increases the existing $10 authorization. PR #33's $9.88406950
stays held; no old unreserved amount is transferred. Current prices must be checked
by the owner before running; a price increase requires a new reviewed policy.

[Forecast](results/budget-forecast.json): 17 completed historical cells average
$0.04674 known usage, maximum $0.06339. Projected 22-cell average is $1.03;
twice the historical maximum per cell is $2.79. Adding a full maximum request
reservation gives $4.10, below conditional capacity. Recommend **$0 extra now**.
This is planning evidence, not guaranteed completion or pooled scientific analysis.
The absolute maximum 176-request liability bound is much larger; it is not a
reason to authorize that amount. The guard stops before an unaffordable request.

## Validation and remaining limits

The recovery regressions cover mock valid/invalid usage, restart, unresolved holds,
caps, duplicate IDs, corruption, rollback, lock-before-activation, activation tamper,
Mac full-flush capability, hosted rejection, overlap/certificate tampering and unsafe
archives. [Offline simulation receipt](results/offline-final-validation.json)
records a full **22 mock-response** continuation with the real frozen private
evaluator, six matched groups, preserved c-6f03/V2 failure, no invented semantic
grades and a verified private export. **Mock outputs are never scientific results.**
Full regression validation: **661 passed, 2 skipped** on the hosted Linux runtime;
Bash syntax and diff checks passed. The skips are the existing optional-private
check and the native Mac check. A separate native macOS CI job runs the recovery
and trusted-host tests. Native Mac diskutil/APFS/full-flush behavior and the owner's actual disk are not
certified here; the mandatory owner-side probe must pass there before activation.

The one real fully matched v2 case remains inconclusive: V0/V1 2/3, V2/V3 3/3;
it lacks a contradicted control and model-ID citation test. Only real remaining
results and qualified blinded semantic review can establish intervention effects.
At most six complete matched groups are possible without replaying a failed cell.
Seven correlated development cases support no population-level claim. Positive
research results still require separate explicit approval before production use.

Primary durability references: [SQLite PRAGMAs](https://www.sqlite.org/pragma.html),
[SQLite atomic commit](https://www.sqlite.org/atomiccommit.html),
[Apple fsync/F_FULLFSYNC](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fsync.2.html),
[CPython fcntl constants](https://github.com/python/cpython/blob/3.12/Modules/fcntlmodule.c).
