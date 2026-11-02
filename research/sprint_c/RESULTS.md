# Sprint C is inconclusive; paid execution stopped on accounting integrity

The citation-grounding and verdict-discipline interventions are implemented and
frozen, but the seven-case ablation did not complete. **Only one case has a
complete fresh four-condition comparison.** A log/checkpoint discrepancy stopped
paid execution, and a separate offline cross-session probe reproduced the same
class of storage inconsistency without any model or API call.

No production/demo code, successful capture, reference verdict, scoring weight,
physical rule or retrieval breadth changed. No missing money records were
synthesized, old reservations released, failed model cells silently retried, or
semantic grades invented. The spending machinery is a research implementation
whose hosted-workspace persistence was not reliable enough to finish this study;
it must not be described as validated production billing infrastructure.

## Matched scientific observation

Primary protocol: `sprint-c-citation-verdict-v2`, ID
`2f0bad897b33230ef1868b3d27fe690fed02b2646db7bca16a21b7f74016c227`.
V0 is an actual fresh rerun of PR #33's original prompt, not historical outputs.
Every condition uses the same PR #33 B one-hop retrieval, model/settings,
permissions, packets, five-sensor budget, sources and frozen submission contract.
Only the prescribed prompt suffixes differ.

The completed matched case was c-7a91: one supported observation and two
unestablished conclusions. It contains **no CONTRADICTED reference control**.

| Matched case only | V0 baseline | V1 grounding | V2 verdict | V3 combined |
|---|---:|---:|---:|---:|
| Evidence-qualified findings | 2/3 | 2/3 | 3/3 | 3/3 |
| Raw verdict matches | 2/3 | 2/3 | 3/3 | 3/3 |
| SUPPORTED recall | 1/1 | 1/1 | 1/1 | 1/1 |
| NOT_ESTABLISHED recall | 1/2 | 1/2 | 2/2 | 2/2 |
| CONTRADICTED recall | untested | untested | untested | untested |
| Incorrect CONTRADICTED, versus frozen reference | 1 | 1 | 0 | 0 |
| Unsupported causal SUPPORTED | 0 | 0 | 0 | 0 |
| Literal citation-contract misses | 0 | 0 | 0 | 0 |
| Independent citation entailment / semantic score | ungraded | ungraded | ungraded | ungraded |

V0/V1 marked a thermodynamic-feasibility proposition CONTRADICTED; V2/V3 left it
NOT_ESTABLISHED. All retained the supported measurement and declined chemical
material identification. This is a narrow, reference-relative observation, not
proof of general verdict improvement. One task cannot establish retained correct
contradiction handling or freedom from excessive abstention across the suite.
PR #33's earlier baseline sometimes differed on this case, underscoring the
stochastic single-sample limitation.

No claim on this matched case tested the prior missing-model-ID citation failure,
so this comparison does **not** establish a citation-grounding benefit. V1 also
completed c-6f03 with 4/4 evidence-qualified findings, but its other conditions did
not complete; it is an **unpaired descriptive capture**, not a treatment effect.
The partial V2 run for that case produced no accepted assessment and counts as
incomplete. Five other case groups were not attempted. The original calibration
and publication-scope discrepancies therefore lack a complete four-condition
retest. Full planned-denominator metrics remain in the machine-readable report,
clearly separated from the one-case matched comparison.

See [controlled results and redacted tool projection](results/controlled-v2.json).
It includes token, latency, completion, retrieval-byte, sensor-choice and
confusion metrics. It excludes hidden samples, free-text assessments, references
per atom, and private reviewer materials. Complete transcripts and blinded review
packets are preserved for the owner. Citation entailment, premise quality,
next-evidence usefulness and all 100-point totals remain null. The tested model
did not grade itself.

## Preserved execution history

V1 completed four pilot cells and the first four-condition suite case. Its next
case's first HTTP attempt ended with a connection error. The $0.09736050 maximum
reservation stayed fully charged. The initial policy treated every unresolved
hold as a live HTTP request, blocking all further calls.

Before examining scientific scores, an operational-only v2 amendment separated
confirmed closed local transports from active/unacknowledged requests. It did not
settle or release the failed hold. Finite cumulative attempt/output ceilings were
versioned to 320/1,310,720 to include old attempts and a completely fresh study;
the additional monetary ceiling stayed exactly $10. Prompts, packets, case order,
variant order, tools, model and settings matched v1 exactly. Archived v1 source
reconstructs the original frozen code digest byte for byte. V1 cells are not
pooled into v2's primary comparison.

V2 completed a fresh four-condition pilot, then five suite cells; a sixth stopped
on settlement integrity. Total across both versions and all stages: **122 HTTP
attempts**, **120 captured usage responses**, and **$0.81394670 in known-usage
estimated cost**. That is not a complete final bill or fully reconciled balance.
There were no automatic HTTP retries or same-cell retries. No further paid calls
were made after the integrity stop.

## Why execution is blocked

The separate durable head checkpoint commits to sequence **243**, but the
readable event log ends at **241**. The entire 241-event readable prefix verifies
its hashes: 121 reservations, 119 settlements. It records $0.80901085 of settled
estimates and $0.23488350 in unresolved maximum-cost holds. **Those are prefix
amounts, not the complete account balance or remaining spending capacity.** The
observed transcript estimate and readable settlement prefix are distinct records;
neither is substituted for the missing records. PR #33's original $9.88406950
reservation chain remains unchanged and fully held.

The code correctly rejects the checkpoint mismatch on restart; all paid execution
is blocked. The head was not moved backward, the log was not truncated or reset,
and no missing reservation/settlement was reconstructed from model text. The
existing closed-hold acknowledgment does not authorize bypassing a broken chain.
See the exact [integrity receipt](results/accounting-blocker.json).

An offline test then ran a small fsynced append log plus atomically replaced head,
with writer and read-only monitor using the same advisory lock in separate hosted
execution sessions. It reproduced a mismatch: **430 readable log rows versus a
head of 458**, detected by both processes. This supports a cross-session storage
coherence blocker on the tested surface; it does not establish the underlying
filesystem implementation or prove a unique root cause. No API, credential,
private reference or production code was involved in the probe.

The relevant runnable probe is `scripts/sprint_c_storage_probe.py`. From two
separate execution sessions sharing an owner-selected **fresh** directory:

```bash
python scripts/sprint_c_storage_probe.py writer --directory "$PM_PROBE_NEW"
python scripts/sprint_c_storage_probe.py reader --directory "$PM_PROBE_NEW"
```

A passing finite probe is not a universal durability guarantee. For future paid
execution use a single trusted local owner runtime on a filesystem with verified
locking/durability, with progress emitted by the writer itself. Do not use
concurrent hosted tool sessions to inspect an active money ledger. Independently
reconcile the missing records or confirm maximum liabilities under a separately
versioned owner-reviewed reconciliation **before** any further use of this
existing authorization. This PR does not provide a reset/recovery command that
assumes the missing events were free.

## What is implemented and verified

- General evidence-to-claim attribution instructions in existing finding fields;
  no private required-citation list, auto-citation repair or new physical fact.
- Three-way verdict discipline with affirmative-counterevidence criteria and
  explicit retention of justified support/contradiction.
- Four frozen conditions, unchanged direct retrieval and fresh contexts.
- Immutable historical reconciliation; original conservative holds remain held,
  observed estimates displayed separately, exactly $10 new authorization.
- Locked hash-linked reservations before HTTP and append-only settlements linked
  to validated provider response IDs, usage and request/response commitments.
  Failed/unknown responses keep full monetary liability; duplicate and invalid
  settlements fail closed. The failed hosted persistence test is a material limit.
- 636 tests passed, one skipped; 22 new tests cover settlement, failure, restart,
  migration, concurrency, tampering, truncation/head mismatch, pricing, exhaustion,
  fixed permissions, four fresh contexts and closed-transport full-hold behavior.
- 36 frozen public entries and 34 private core entries verified; offline trusted
  host → sensor → graph → submission → separate frozen scorer passed.
- Offline scoring/reviewer export works despite blocked spending integrity:

```bash
python scripts/score_sprint_c_captures.py --out "$PM_SAVED_RUN" \
 --private-root "$PM_PRIVATE_ROOT"
python scripts/analyze_sprint_c.py --out "$PM_SAVED_RUN" \
 --private-root "$PM_PRIVATE_ROOT" --public-report "$PM_REPORT_NEW"
```

Use fresh scoring output destinations/files; the helper refuses to overwrite
preserved outputs. No key or paid call is required. Recovery instructions in the
private archive provide direct unchanged-scorer commands for already saved audit
bundles. Protocols, receipts, original and new ledgers (including the discrepancy),
full captures, failures, old source commitments and randomized reviewer packets
are preserved without altering historical identities.

## Research conclusion and production gate

**Inconclusive.** One completed matched case suggests the verdict procedure can
avoid one over-contradiction relative to the frozen rubric while retaining a
supported observation. Citation benefit, correct-contradiction preservation,
calibration/publication retests, cross-task reliability and independent semantic
validity remain unestablished. The benchmark is development reuse of seven
correlated tasks from one synthetic incident, not untouched generalization data.

The spending guard stopped instead of assuming an uncertain balance. The storage
blocker is a negative engineering finding, not a model-quality result or proof
that the full $10 was spent. Do not market the observed one-case difference as a
reliable improvement or deploy it. The [future plan](FUTURE_INTEGRATION_PLAN.md) is
**NOT AUTHORIZED FOR IMPLEMENTATION** and requires separate explicit owner approval.
