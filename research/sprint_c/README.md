# Sprint C: citation grounding and three-way verdict discipline

**Paid execution is currently blocked by a live-tested ledger/checkpoint
inconsistency. Do not resume or reset the preserved ledger. See [RESULTS.md](RESULTS.md)
for the exact failure, offline reproduction and reconciliation requirements.**

Strictly research-only. No production/demo integration is authorized by this
sprint, including after positive results. The original v5 path, captures,
classifiers, pages, M3 benchmark, synthetic v1.1 inputs and private scoring key
remain unchanged. The proposed future integration plan is separate and explicitly
**NOT AUTHORIZED FOR IMPLEMENTATION**.

## Controlled ablation

| Condition | Grounding addition | Verdict addition |
|---|---|---|
| V0 | none; exact PR #33 baseline prompt | none |
| V1 | compact evidence-to-claim map in existing finding fields | none |
| V2 | none | support / affirmative contradiction / neither |
| V3 | same as V1 | same as V2 |

All variants use PR #33 B's one-hop source-scoped lookup through the unchanged
trusted JSON-lines host. No graph expansion, new fact, retrieval helper, automatic
citation insertion, private required-citation list or new model tool was added.
The only scientific interventions are appended prompt instructions, preserved
literally in `interventions.py` and the frozen protocol. V1 distinguishes receipts,
model premises and source applicability; V2 distinguishes failed proof from
positive counterevidence while retaining warranted support and contradiction.

Per condition/case: fresh context, Muse Spark 1.3 standard mode, medium reasoning,
8 model turns, 24 tool calls, 4 graph/document context calls, 4,096 output tokens,
360 seconds, five sensors including initial/missing/frozen channels, no retries.
Public packets, tool schemas, initial measurements, sources, direct retrieval,
submission and frozen scoring are identical. Variant order rotates across the
opaque case-ID hash order; the one-case four-condition pilot is separate from
the fresh seven-case evaluation. No prompt changed after paid results.

Only one packet and permitted serialized results cross into the remote model.
There are no repository, file, shell, arbitrary URL or scoring tools. The host's
environment excludes MODEL_API_KEY. The owner orchestrator is trusted; it is not
an agent with a mounted private filesystem. Reuse PR #33's trust-boundary rules.
Scoring runs in separate owner processes after all model sessions end.

## Accounting policy

The original Session A/PR #33 directory remains the single historical root and
supplies the shared lock. Its original `session.json`, authorization, reservation
chain and captured estimates are never modified. The new subdirectory
`sprint-c-accounting-v1/` contains an exclusive one-time authorization policy,
append-only hash-linked events and an atomically replaced head checkpoint. Never
create a fresh replacement to recover capacity. Restore the entire root on
another owner machine. A missing/corrupted checkpoint, changed original file,
truncated chain or inconsistent settlement fails closed.

The new policy conservatively retains **all $9.88406950** historical reservations.
The captured $0.48093015 usage estimate is reconciled and displayed but is not a
settlement: old captures lack provider response IDs and request/response
commitments required by this new policy. It is neither added twice nor reclaimed.
Sprint C receives exactly **$10 additional**, with no transfer of the old
$0.11593050 unreserved capacity. Combined authorized ceiling is $20; Sprint C's
own charged balance cannot exceed $10.

Before HTTP, under the shared lock, reserve 2× serialized request bytes + 8,192
input framing tokens and the entire output cap. Persist and fsync the hash-linked
reservation and head checkpoint before releasing the lock and sending. The model
cannot influence the ledger. All money uses integer nanodollars at fixed standard
prices: input 1,250, cached input 150, output 4,250 nanodollars/token.

On a completed successful fixed-endpoint TLS response, trusted code validates
provider response ID, model, status, output envelope, integer/nonnegative usage,
total=input+output, cache<=input and tokens/cost within reserved bounds. A separate
settlement event links the request and response commitments, provider ID and
validated top-level usage. Only then is the unused hold available again. Text or
tool arguments claiming usage never enter settlement. Missing cache counts get
no cache discount. Provider IDs and settlements cannot be reused. Ledger replay
revalidates every receipt and its arithmetic under the frozen prices.

Unknown, failed, interrupted or unverifiable requests retain full reservations.
Unacknowledged/live requests block further HTTP. The v2 operational amendment
allows an owner to acknowledge a confirmed closed failed local transport using
a durable failed-attempt evidence digest; its FULL monetary hold remains charged.
This acknowledgment does not settle the request, mark it free, or retry its cell.
A merely interrupted request without evidence of closure still blocks execution. A crash between append and head update also fails
closed. At most one HTTP request is in flight globally; cumulative limits are
320 HTTP attempts and 1,310,720 reserved output tokens under the v2 amendment
(the original immutable policy records 256/1,048,576). This finite cumulative
allowance includes preserved v1 attempts plus the fresh v2 study; it adds no
money to the $10 authorization. No automatic retries.
The client uses the same fixed Meta endpoint, verified TLS, no redirects and
explicit owner workspace proxy opt-in as PR #33. No provider-side billing/admin
permission is available. Provider usage remains an estimate, not an invoice;
local trusted records are not provider-signed billing attestations.

**Gross reservations can exceed $10 over time** because completed requests are
settled. The enforced limit is settled estimated spending plus all outstanding
maximum-cost holds, never the sum of historical holds and their replacements.
Historical record amounts themselves never decrease.

## Reproduce

Recover the complete private evaluator, PR #33 run and ORIGINAL ledger from the
owner's preserved packages. Do not initialize an empty historical root. With a
checkout of this PR and Python >=3.10 (Python 3.12 recommended for safe extraction):

```bash
python -m pip install -e '.[test,agent,experiments,audit]'
python -m pytest -q tests research/synthetic_challenge/tests research/synthetic_challenge/integration
python scripts/research_sprint_c.py authorize \
 --ledger-directory "$PM_ORIGINAL_LEDGER" --prior-run "$PM_PRIOR_INTEGRATION_RUN"
python scripts/research_sprint_c.py prepare \
 --out "$PM_OWNER_ROOT/sprint-c-new" --private-root "$PM_PRIVATE_ROOT" \
 --ledger-directory "$PM_ORIGINAL_LEDGER"
```

`authorize` is exclusive and must not be rerun after recovery; reuse the existing
policy. The real study's preflight receipt and frozen protocol are preserved.
Add `--platform-proxy` to prepare only for an owner runtime that needs its trusted
configured proxy; install `httpx[socks]` when required. Secrets belong only in the
owner process environment, never a prompt, trace or committed configuration.

```bash
read -rsp 'Meta API key: ' MODEL_API_KEY; echo
export MODEL_API_KEY
python scripts/research_sprint_c.py pilot \
 --out "$PM_OWNER_ROOT/sprint-c-new" --private-root "$PM_PRIVATE_ROOT"
python scripts/research_sprint_c.py suite \
 --out "$PM_OWNER_ROOT/sprint-c-new" --private-root "$PM_PRIVATE_ROOT"
unset MODEL_API_KEY
# Only after all model sessions end:
python scripts/research_sprint_c.py score --stage pilot \
 --out "$PM_OWNER_ROOT/sprint-c-new" --private-root "$PM_PRIVATE_ROOT"
python scripts/research_sprint_c.py score --stage suite \
 --out "$PM_OWNER_ROOT/sprint-c-new" --private-root "$PM_PRIVATE_ROOT"
python scripts/analyze_sprint_c.py --out "$PM_OWNER_ROOT/sprint-c-new" \
 --private-root "$PM_PRIVATE_ROOT" --public-report "$PM_OWNER_ROOT/public-summary.json"
```

Do not issue new paid runs merely to reproduce existing outputs. Archived audits
can be scored with the unchanged private standard-library evaluator without a key.
Never replay an unknown interrupted attempt silently. A new protocol/output
folder does not reset the additional authorization, original history or limits.

## Interpretation and independent review

Primary mechanical results use the unchanged scorer and explicitly report literal
citation requirements separately from raw labels. Citation receipt membership is
not scientific entailment. Confusions, reference-disagreeing abstentions and
contradictions do not automatically prove a semantic error in ambiguous wording.
Review packets have randomized IDs without prompt/variant identity; the separate
unblinding map stays with the owner. Premise formatting can still reveal a
condition, so blinding is imperfect. Two qualified independent reviewers should
grade the unchanged rubric and document adjudication. The tested model never
grades itself. Semantic entailment, missing-premise quality, next-evidence utility
and full 100-point totals remain null without those reviews.

This is development reuse of a frozen independently authored benchmark, not an
untouched holdout. Seven correlated tasks from one synthetic incident, one
stochastic sample/cell and no completed independent semantic review cannot
establish population accuracy, robust generalization or deployment safety.

## Preserved operational correction

V1's four-condition pilot and first suite case completed, then a connection error
stopped the first request for the next case. Its full $0.09736050 hold was retained.
No scientific scores were inspected to choose a correction. V2 distinguishes a
confirmed closed transport from an active HTTP request while retaining its full
maximum liability. It has an immutable operational-policy amendment and a linked
closure record. Source in archive/v1_source reconstructs the original protocol's
code digest exactly. Both protocols, every attempt and the full ledger survive.

The v2 primary study uses fresh contexts for a new four-condition pilot and all
seven suite cases. Prompts, case order, variant order, model settings, source
access, retrieval and schema match v1 byte for byte. Older cells are not pooled
into the v2 scientific comparison. Before v2 calls, execution-controls.json fixed
at most two stage resumptions after confirmed connection failures, continuing
only unattempted cells; the same failed cell is never retried. All old/new costs
and unknown holds remain inside the same additional $10 authorization.
