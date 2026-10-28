# PetroMind claim auditor: bounded capability pilot

PetroMind asks Muse Spark to distinguish an observed physical measurement from a
conclusion that the measurement does not establish. The statistical engine keeps
its diagnosis. The auditor names premises, checks available evidence, retrieves
source-scoped context, and proposes the smallest next evidence needed. It cannot
control equipment or establish a certified root cause.

This feature is implemented and offline-tested. **Its live capability gate is
PENDING. No claim-auditor Muse output or interactive demo has been validated yet.**

## Run the minimum experiment

Use the existing Python environment and an exported `MODEL_API_KEY`. Do not put
credentials in commands, commits, protocols, screenshots, or uploads. No new
infrastructure, model fitting, or dependency is required beyond `.[test,agent]`.

```bash
python -m pip install -e '.[test,agent]'
python -m pytest -q
python scripts/evaluate_claims.py prepare \
  --science-run .petromind/science-m5-v1 \
  --dataset ../3W/dataset \
  --out .petromind/claim-audit-v1 \
  --max-cost-usd 2
python scripts/evaluate_claims.py check --out .petromind/claim-audit-v1
```

`prepare` requires the original M5 directory including protocol, results, and
traces. It checks both nested protocol hashes, development membership and well
isolation, audit chains, and the actual charged sensor summaries. It fails rather
than constructing missing measurements. The new protocol contains constructed
claims, frozen observed evidence, private review targets, source/code/knowledge
hashes, model settings, prices, limits, and rubric. **Do not send the full protocol
to Muse.** The runner explicitly whitelists the public packet.

The optional dataset argument loads only the existing fitting/development well
partitions, validates file fingerprints, and materializes training-only analogue
responses using the captured observed sensors. Original M3 test measurements are
never opened. Retrieval exports opaque case IDs, training class, relative-median
distance, and matched sensor names, never wells, paths or unqueried readings.
Omitting `--dataset` supports a source-capture-only smoke test; history then
returns no matches and the protocol records retrieval as disabled. Such a run
must not be presented as validation of historical retrieval.

After reviewing the frozen claims and rubric, the explicitly invoked pilot is:

```bash
python scripts/evaluate_claims.py pilot --out .petromind/claim-audit-v1
```

It runs **two tasks**, each with checker, ungrounded Muse, and grounded Muse.
There are four Muse investigations, six model turns/eight tool calls per
investigation, 4,096 output tokens per response, and global limits of 24 HTTP
attempts including retries, 98,304 reserved output tokens, and $2 in conservative
estimated reservations. Reservations use the existing frozen Meta price snapshot
and a byte-based input bound; they are not an invoice guarantee. Defaults cannot
expand the benchmark. There is intentionally no `full` command.

Completed and failed tasks are not selectively retried. An interrupted task's
intent blocks automatic restart. A process lock prevents simultaneous runners.
Changed code/runtime, sources, prompts or schemas require a fresh output directory
and protocol. Never edit an old protocol, result or trace to fix a run.

## Small interface and division of work

The ungrounded condition has one submission tool; the grounded condition adds two
context tools. Both receive identical claims, baseline prediction/probabilities,
quality metadata and already charged observed measurements. No hidden event labels,
well identities, filenames, evaluation targets, or new target measurements enter
the agent context.

| Tool | Purpose |
|---|---|
| `lookup_knowledge(topic)` | Muse chooses a public sensor, fault, or valve-code topic; Python returns graph facts, citations, status, scope and provenance. |
| `search_history()` | Returns only the frozen training analogues for the charged evidence; single-sensor similarity is explicitly limited. |
| `submit_audit(verdict, findings, numeric_observations)` | Muse decomposes and evaluates the claim, identifies premises/gaps and proposes next evidence. |

Each finding has a statement, short public premises, epistemic basis, verdict,
received citation IDs, missing premise, next evidence and public justification.
There is no alternative-fault argument, relational cross-reference schema, silent
coercion, or fallback successful abstention. The verdicts are `SUPPORTED`,
`PARTIALLY_SUPPORTED`, `NOT_ESTABLISHED`, and `CONTRADICTED`.

Python checks source IDs were actually received, exact summary values, finite
numbers, shape and terminal state. Unsupported claims may have empty citations;
a missing citation is not a false claim. A contradiction submission must cite
positive evidence, but whether that evidence actually contradicts the statement
requires semantic review. It cannot be established by an ID check. Numeric values
in the explicit observations list are checked; physical prose and numbers embedded
in prose still require review.

The initial invalid assessment can receive at most two repairs. An identical
invalid repeat terminates immediately. Rejection logs retain static codes, fields
and correction instructions rather than rejected payloads. Valid public findings
are exported; private reasoning, encrypted reasoning and vendor response bodies
are not. This is a tool boundary, not an arbitrary-code sandbox.

## Frozen task coverage and limitations

Eight **constructed evaluation claims** reuse actual already observed summaries
from two M5 development incidents. They are not represented as expert diagnoses.
The tasks test these narrow distinctions:

1. A correctly quoted numerical pressure change.
2. An incorrectly quoted numerical pressure change.
3. A missing opening measurement described as observed.
4. The reversed assertion that ESTADO-DHSV code 1 means closed.
5. A fault-9 pressure expectation asserted as necessary and sufficient.
6. Consistency with the two documented pressure directions in a published fault-2
   example, explicitly without claiming root cause.
7. The same plausible pattern upgraded to a proven DHSV-closure cause.
8. A **conditional** assertion that one shared historical sensor confirms a fault.
   No historical match is fabricated; the conditional task is not a retrieval
   relevance benchmark.

The two source incidents were already inspected in M5. This is disclosed
capability-development selection, not an untouched generalization benchmark.
Eight correlated tasks are not eight independent incidents. The source cohort
was outcome-stratified. No population accuracy or comparison with M3 is justified.
The sole supported diagnostic inference offered is *published-example
consistency*, not proof of the fault. The source-capture-only workspace has no raw
600-point timeline; it cannot honestly supply an interactive raw-sensor replay.

The two pilot tasks are fixed before any new API execution:
`fault_expectation` and `published_example_consistency`. One tests missing
physical premises; the other guards against false rejection of a deliberately
limited supported statement. The eight-task benchmark is frozen for review, but
only these two tasks are enabled for paid execution.

## Predeclared grading and decision gate

The deterministic comparator checks explicit claimed values and citation
existence/presence. It reports `UNASSESSED` for the physical verdict. Its limits
are intentional and visible: source existence cannot prove entailment.

Deterministic checks validate exact numeric observations, received source IDs,
audit integrity, accounting, completion, latency, requests and estimated cost.
The analyzer replays successful context/submission calls against the frozen
packet to detect result modification. It also reports agreement with constructed
review targets, explicitly **not physical truth**.

Independent engineering review must assess verdict correctness, the missing
premise, whether next evidence is realistic/specific/sufficient, unsupported
claims introduced by the auditor, and useful reasoning beyond the checker.
Do not ask Muse to review itself. Use `completed-review-packets.json`, which
contains actual outputs, the supplied packet, returned context and common
source-scoped knowledge. Review without incident labels or constructed targets.
Copy `review-template.json` to a new file, identify the reviewer, and give a
source-based rationale for each output. Unfilled reviews are never zero errors.

```bash
cp .petromind/claim-audit-v1/review-template.json \
   .petromind/claim-audit-v1/independent-reviews.json
# Complete the independent review, then:
python scripts/evaluate_claims.py analyze \
  --out .petromind/claim-audit-v1 \
  --reviews .petromind/claim-audit-v1/independent-reviews.json
```

The frozen gate requires all four Muse outputs completed and independently
reviewed; grounded completion and mechanically checked numeric/citation fidelity
must be 100%; both grounded verdicts must be independently correct, with no false
rejection of the supported task and zero introduced unsupported claims. At least
one grounded output must identify a correct missing premise beyond the checker,
and at least one must propose specific sufficient next evidence. Matching a
constructed target alone cannot open the gate.

`BOUNDED_DEMO_GO` authorizes only a demo of these reviewed claim types.
`NARROW_SCOPE` means narrow claims/evidence types and freeze a new pilot.
`PENDING` means insufficient execution or review; it does not mean failure of
Muse generally. One stochastic draw cannot establish causal graph benefit, and
an ungrounded auditor that performs equally well remains a relevant limitation.
No UI is built before this gate. No automated physical verifier is claimed.

## Demo and submission after the gate

The defining moment should expose a specific leap: a real pressure trend matches
a documented example, but neither the example nor an analogue establishes the
claimed root cause. Highlight the observed premise, the source's limited scope,
the missing causal criterion and the next document/measurement needed. Use only
captured real Muse outputs for replay and identify replay prominently. A mock is
never a successful live investigation.

Keep the original statistical diagnosis visible. A future timeline needs actual
charged raw telemetry, not a reconstructed curve from summary numbers. Show only
documented graph edges with their generic scope; mark illustrative relationships.
Preserve live integration through the existing Meta Responses client.

Submission disclosures remain mandatory: adaptive statistics achieved 20/33
(60.6%) on M3, versus 4/33 (12.1%) for direct sensor-only Muse and 5/33 (15.2%)
for GraphRAG; graph-only Muse achieved 1/33 (3.0%). These experiments are unchanged
and do not establish classification improvement from GraphRAG. Graph verification
extends only to source documentation. PetroMind is engineering decision support,
not root-cause certification, a safety-certified operational decision, or an
autonomous equipment controller.
