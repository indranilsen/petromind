# Research Session A: GraphRAG forensics and atomic evidence auditing

This is an isolated, removable research package, not a hackathon UI redesign or
production model change. Read [the forensic report](FORENSICS.md) first and
[the actual offline receipt](results/offline-v2.json) for measured results.

## What ran

On November 2, 2026, a new protocol froze 12 clearly constructed atomic claims
from the two previously inspected, captured development incidents. The source
cohort was outcome-stratified/enriched in earlier work; these correlated tasks
are neither untouched generalization examples nor population accuracy evidence. Reference
coverage is 5 SUPPORTED / 5 NOT_ESTABLISHED / 2 CONTRADICTED. Sources are the
existing 90 provenance-tagged knowledge facts. The original well split and
capture lineage are checked; no raw M3 test measurements or labels are loaded.

The full-source deterministic baseline got **12/12**. It checks exact values,
directions, availability, generic definitions, code mappings, comparison scope,
known mathematical constraints with compatible documented units, and missing
necessary/sufficient rules. It does **not** read the private answer key. Public
formal propositions are given to both it and Muse. This is a strong but
human-formalized baseline, not a natural-language parser or independent physical
truth verifier. Its perfect result leaves no accuracy headroom on this simple
set; additional Muse value must be demonstrated on independently authored tasks
or independently reviewed reasoning/gap identification, not asserted here.

Always answering NOT_ESTABLISHED gets 5/12 accuracy and **1/3 macro recall**.
Numerical and source-scope reference checks are not an LLM-generated key, but
neither are they independent engineering certification. All free-text physical
interpretations, missing-premise correctness and usefulness of next evidence
remain explicitly **unreviewed/null**, not automatically correct.

The paid pilot command was invoked with authorization and stopped **before HTTP**
because this environment lacks `MODEL_API_KEY`. Real model attempts: **0**.
Estimated usage/reservations: **$0**. Remaining conservative Session-A cap: **$5**.
Actual provider billing is unavailable. No model improvement is claimed.

## Controlled conditions

| Variant | Context/tool difference | Important limit |
|---|---|---|
| A_sensor | Initial evidence + submit; no knowledge/history lookup | Correct evidence-limited abstention is separately reported; lack of access is not mislabeled a reasoning error. |
| B_knowledge | Existing exact-topic, source-scoped knowledge lookup | Same frozen fact pool as E. |
| C_history | B plus captured training-only history snapshots | Labels suppressed; only initially observed shared sensors, with unequal overlap explicit. |
| D_legacy_partial | Original illustrative `EquipmentGraph.neighbors` + history with original training labels | Partial algorithm reconstruction, not an M3 rerun. Extra labels and different knowledge make it a multi-factor comparison. |
| E_connected | B's lookup replaced by bounded two-hop source-edge expansion seeded by query, observed sensors and public candidate faults | The **only targeted intervention**. No prompt, schema, sensor budget or facts change relative to B. More returned context is explicitly measured as a cost. |

Every condition uses Muse Spark 1.3, medium reasoning, eight model turns,
16 tool calls, 4,096 output tokens per request, 180-second run deadline, four
context calls and no transport retries. Five-sensor accounting includes inherited
summaries; missing requests cost one, repeats are cached. The current capture
provides no extra raw summaries, so active requests are unavailable rather than
fabricated. Imported cases can provide a complete backend catalog, including
real declared missing summaries; unqueried target availability is never supplied.

Pilot task selection is frozen: one supported numerical observation and one
unestablished causal inference. Five methods × two tasks; no automatic full run.
Variant order is hash-counterbalanced before execution. The full 12-task matrix
requires a separate explicit `evaluate` command and shares the same aggregate
spending cap. Do not run it until pilot outputs have been reviewed.

## Reproduce locally

Use the feature branch/merged research code, Python 3.12 and the unchanged private
capture and M5 run. These are not included in a public clone.

```bash
python -m pip install -e '.[test,agent]'
python scripts/research_sprint_a.py prepare \
  --capture .petromind/claim-audit-v1 \
  --science-run .petromind/science-m5-v1 \
  --out .petromind/research-a-local-v1 \
  --max-cost-usd 5
python scripts/research_sprint_a.py offline \
  --out .petromind/research-a-local-v1
```

After exporting your existing `MODEL_API_KEY` in this shell, run **only**:

```bash
python scripts/research_sprint_a.py pilot \
  --out .petromind/research-a-local-v1 \
  --authorize-paid-meta
```

This is already authorized research, not another consent step. Never paste the
key into GitHub, a trace, a benchmark or this chat. The runner does not read `.env`
implicitly. No server/UI needs to be running. A missing credential produces a
blocked status, not a model failure or substituted replay.

Use a fresh `--out` after code/runtime/reference changes; never edit the frozen
protocol in place. New output directories **do not reset spending**. Every study
shares `.petromind/research-session-a-budget/`, hard-capped at $5 estimated total,
80 HTTP attempts and 327,680 reserved output tokens. Do not delete/change that
ledger to evade the Session-A aggregate cap. Unknown interrupted tasks are never
silently retried. Tests inject temporary ledgers and mocked HTTP only.

Reservations use twice serialized request bytes plus 8,192 framing tokens and
the full output cap. Each reservation is locked, hash-linked, persisted before
HTTP and never released, including on lost/failed responses. This intentionally
may stop before known usage reaches $5. Prices are the repository's frozen
October 27 estimates, not independently reverified provider billing. The existing
public-demo $2 safeguard is untouched.

## Results and review

Private local output files:

- `protocol.json`: source/runtime/configuration hashes, exact prompt, tools and rubric.
- `benchmark.private.json`: frozen public evidence plus separate private references/lineage.
- `public-cases.json`: the model-safe initial cases, with no private references or future summaries.
- `results.jsonl`: all successes and failures; atomic judgments, citation checks,
  sensor sequence, context calls, rejected-submission codes, latency, tokens and estimated cost.
- `traces/`: actual sanitized tool results and hash-linked audits. No raw response bodies,
  encrypted/private reasoning or rejected argument contents.
- `report.json`: full and paired-pilot summaries, required-fact retrieval probes,
  missing-evidence vs reasoning categories and the aggregate spending receipt.
- `expert-review-packets.private.json`: claims, measured evidence, source checks
  and specific review questions. Review the actual model output/traces alongside these.
- `execution-status.json`: a configuration blocker if credentials are missing.

The fixed-key score measures evidence-task resolution, not fault classification.
It requires matching the reference **and** appropriate received citations for
formal supported/contradicted claims. Evidence-conditioned verdict correctness is
reported separately: an A auditor may appropriately abstain on a documentation
claim it cannot inspect, even though it cannot resolve the full-source task.
A B/E auditor that fails to retrieve an available required fact is separated
from one that receives it and reasons incorrectly. Required-fact precision/
recall is a formal-ID proxy, not independently judged semantic relevance.

Open expert claims can be compared with an external frozen key, but citation
existence cannot prove their entailment. Free-text physical correctness and
specificity/executability of recommended next evidence require a reviewer.
Do not use field presence or model self-grading as that review.

The research submission interface deliberately records semantically wrong
SUPPORTED causal answers so they can be measured. Production v5 continues to
reject unsupported diagnostic conclusions. Research results use a distinct
contract and are **not compatible Demo saved investigations**. This is not a
loosening or replacement of the public auditor's safeguards.

## Independent benchmark handoff

See [ADAPTER.md](ADAPTER.md). Do not request, inspect or influence another
session's unreleased key. Import only its already frozen release. The reader
hashes references before any model call; later changes require a fresh protocol.

## Tests

```bash
python -m pytest tests/test_research_sprint_a.py -q
python -m pytest -q
```

Actual execution here: **33 research tests passed; full suite 582 passed,
1 opt-in browser test skipped**. Tests cover partition/label isolation,
provenance, exact quotes, scope/contra evidence, original median ranking behavior,
source-only connected paths, tool ablations, sensor/cache/missing budgets,
bounded repairs/privacy, constant-abstention scoring, aggregate reservations,
pre-HTTP cap refusal, immutable references and mocked five-condition execution.
No Home/Demo/Technology, production Python source or frozen experimental artifact
was changed. This research lives outside `petromind/`, preserving the production
source digest used by existing protocols.

The initial unpaid v1 receipt is preserved. A fresh v2 protocol adds paired-report
code with unchanged cases, references, prompt and tools; no frozen file is edited
in place. Both preparations share the same $5 session ledger and used zero API
requests. All paired model deltas remain null until actual matched runs exist.
