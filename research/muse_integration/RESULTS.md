# Connected graph retrieval: live study is inconclusive

**No measured improvement on the three completed pairs.** Both B and E received
7/11 evidence-qualified atomic findings under the unchanged frozen scorer, and
matched 9/11 verdict labels before its exact-citation requirement. E returned
2.17 times as much retrieval context. This is not proof of equivalence or a
negative result on the entire seven-case benchmark: four pairs are incomplete,
the cases are correlated, and independent semantic review remains ungraded.

Actual Meta Muse Spark 1.3 API calls ran November 2, 2026. Standard mode, medium
reasoning, identical prompts, initial packets, tool schemas and execution limits;
fresh context for each case/variant/stage. The protocol was frozen before the
first paid response. No intervention changed after inspecting model outcomes.

## Directly comparable observations

Paired subset: c-13df, c-6f03, c-80b2; 11 atomic statements per method.

| Metric | B: direct scoped lookup | E: connected two-hop lookup |
|---|---:|---:|
| Completed matched cases | 3 | 3 |
| Evidence-qualified atomic findings | 7/11 | 7/11 |
| Raw verdict matches (not the primary score) | 9/11 | 9/11 |
| SUPPORTED recall, evidence-qualified | 3/5 | 3/5 |
| NOT_ESTABLISHED recall | 3/5 | 3/5 |
| CONTRADICTED recall | 1/1 | 1/1 |
| Incorrectly supported causal claims | 0 | 0 |
| API requests | 21 | 21 |
| Retrieved document/graph JSON bytes | 8,139 | 17,640 |
| Sum of model-run latency, seconds | 80.31 | 85.62 |
| Known-usage estimated cost | $0.166824 | $0.143832 |
| Semantic score / full 100-point total | ungraded | ungraded |

The cost difference reflects reported cached tokens and response lengths; it does
not establish E is cheaper generally. Context bytes count returned document/graph
JSON, not tokens or total request history. Both used the same underlying frozen
public source pool, and every returned edge retained provenance and limitations.
Relevance precision, semantic completeness, applicability and citation entailment
require human judgment and have **no automatic success grade** here.

## What changed and what did not

The original [forensics](../sprint_a/FORENSICS.md) found illustrative equipment
neighbors plus a separate median-based historical retriever. It did not retrieve
connected verified sensor/equipment/physical-expectation paths. Its 33-incident
classification scores are a separate task, not evidence-auditing measurements.

Here B's exact-node one-hop lookup is replaced by E's two-hop expansion through
the frozen synthetic graph. The model requests the same schema; the bridge fixes
the depth. Synthetic equations remain declared assumptions, not installed-well
facts. Source provenance is retained rather than promoted to causal certainty.
No new chemical rule or fitted discriminating threshold is introduced.

This is a synthetic adaptation, not a faithful import of Session A's 3W exact-topic
lookup. Both initial packets already include substantial M1 assumptions/equations,
which reduce the incremental knowledge available from graph retrieval. B/E offer
different breadth; actual later tool selections can differ. The observed pair
comparison estimates the offered retrieval intervention, not an identical-query
counterfactual with every downstream choice held fixed.

## Observable failure mechanisms

Full submissions and exact permitted tool results are retained in the owner-only
run archive. The [public trace projection](results/controlled-v2.json) retains
case/variant/tool sequence, graph IDs, document IDs, result sizes and host event
hashes; it omits measurements, free-text assessments and private answer keys.
The examples below describe scored error categories without publishing the key.

| Finding | Evidence in actual traces | Interpretation and limit |
|---|---|---|
| Evidence-limited claims were over-contradicted relative to the frozen contract | Both variants' calibration and publication-scope submissions chose CONTRADICTED for the same two propositions, while their justifications explicitly acknowledged unavailable calibration or non-transferable example scope. | This is a reference-verdict disagreement, not proof that Muse ignored uncertainty. Independent reviewers should inspect the wording distinction between “not established” and a falsified physical claim. No reference was changed. |
| Receipt availability did not ensure the scorer's literal citation requirement | Two otherwise matching supported findings per method cited received graph/measurement IDs but omitted literal `model:M1`, which was already in the initial packet and explicitly required by the frozen key. E additionally returned relevant equation/counterprediction edges. | The unchanged scorer withholds those findings. This is an exact citation-contract failure, not missing knowledge retrieval or demonstrated incorrect physics. Semantically equivalent provenance is not automatically credited. |
| Additional retrieved context did not change the atomic outcome | Paired context grew from 8,139 to 17,640 bytes, including mechanism alternatives, conditional predictions and evidence gaps. Scored findings and label matches were identical. | More context was observed; additional reasoning benefit was not. Three dependent cases cannot establish general ineffectiveness or equivalence. |
| Acquisition was bounded but repetitive across tasks | Both methods requested SYN-Q-PROD and SYN-P-SEP in all completed paired cases, exhausting five charged slots including the initial three. No unavailable/frozen sensor requests or cache hits occurred. | The flow query can test a constant-flow drift explanation under its stated calibration. Necessity/usefulness of every additional request is not automatically graded. |
| Material uncertainty was retained | Both methods declined hydrate material identification in the paired completed cases and named missing chemical/phase/material evidence. | Narrow observed behavior, not broad evidence of safe industrial deployment. Premise quality and proposed next tests remain ungraded. |
| Completion was limited by the reservation guard | One further B cell completed; E made one request but its next request was denied. Three case pairs were never started. | This is a budget-induced execution failure, not a physical-reasoning failure. Do not use the resulting unequal full-suite scores as a treatment-effect comparison. |

No model private reasoning was requested, exported or inferred. Hypotheses about
attention, anchoring or intent are not asserted from final verdicts alone.

## Full plan and execution accounting

Seven cases × B/E were planned. Three pairs completed; c-7a91 completed under B
only, and E stopped before submission. c-42e8, c-9bc4 and c-a57c were unattempted.
Consequently the history-transfer, contrary hydraulic-ratio and supported
resistance-identification tasks lack complete paired coverage. The hardest
quantitative diagnostic contrasts therefore remain unevaluated in this study.

The separate one-case paired pilot completed, then that case repeated within the
suite in fresh contexts as predeclared. Pilot and suite are not independent samples.
The pilot was used only to check interface/completion, not to tune retrieval.
The first v1 launch had zero HTTP calls due to a proxy preflight defect; v2 fixed
HTTP CONNECT acceptance before any paid response and preserves the blocked record.

Unchanged full-suite mechanical outputs, counting missing findings as wrong:
B **14.1732/29**, E **11.0087/29**. These have unequal completion and **must not be
interpreted as B outperforming E**. The full planned denominators were 23 atomic
statements per method: B 10/23 evidence-qualified, E 7/23. These document
operational incompleteness, not a matched scientific comparison. No full 100-point
score was fabricated; the 71 semantic points remain ungraded.

| Aggregate across pilot and suite | Amount |
|---|---:|
| Real HTTP requests / responses with usage | 64 / 64 |
| Input tokens / cached input tokens | 782,034 / 627,211 |
| Output tokens (including reported reasoning usage) | 45,487 |
| Usage-based estimated API cost | $0.48093015 |
| Conservative reservations retained | $9.88406950 |
| Unreserved remainder of cumulative $10 cap | $0.11593050 |
| Provider invoice / enforced project ceiling | unavailable |

The ledger counts serialized opaque reasoning replay and repeated history
conservatively at 2× request bytes plus framing. This explains much of the gap
between reserved and observed estimates. **No reservations were released or
recomputed downward to extend the run.** The next request would exceed the
remaining conservative allowance and was not sent. No secondary variants ran.
The original Session A ledger/configuration and its history were preserved;
the production demo's separate $2 cap is untouched.

Meta's [official pricing](https://dev.meta.ai/docs/pricing-rate-limits), checked
November 2, lists standard Spark at $1.25 input, $0.15 cached input and $4.25
output per million tokens. Token-based estimated cost is not an invoice.

## Verification and recovery

- 36 public freeze entries and 34 private core entries verified unchanged.
- Saved private evaluator archive recovered and regenerated byte for byte;
  its fixed baseline reproduced 29/29 mechanical points, semantic total null.
- Offline trusted-host query → graph → submit → separate-score smoke passed.
- 614 tests passed, one skipped; 65 targeted research tests passed separately;
  six private physics/reproducibility tests passed.
- Explicit tests cover fresh contexts, no private/credential payloads, tool/path
  rejection, graph scope, cache/missing sensors, five-sensor cap, structured
  repairs, original-ledger preservation, tamper detection, concurrent reservation,
  budget exhaustion and persisted reservation before a failed HTTP request.
- Production source and both merged frozen research packages are byte-unchanged.

See [commands and trust boundary](README.md),
[public protocol projection](results/protocol-v2.public.json) and
[verification receipt](results/verification.json). The private archive preserves
v1/v2 protocols, host audits, sanitized public-assessment traces, scorer outputs,
blinded reviewer packets/unblinding maps, full original ledger checkpoint and
recovery scripts. No credentials are included. Preserve the ledger on recovery;
starting another directory does not authorize new spending.

## Hackathon-safe conclusion

“We found the original GraphRAG prototype retrieved equipment associations and
historical similarities, rather than connected physical evidence. We built an
isolated, source-aware investigation path and tested a controlled connected
retrieval variant. In the three completed synthetic pairs, connected retrieval
returned more context but did not improve the frozen atomic score. The full
comparison remains inconclusive because the reservation budget stopped further
coverage and expert semantic review is pending.”

Do not claim improved fault-classification accuracy, statistically significant
benefit, certified hydraulic realism, or production readiness. Keep the existing
demo and v5 auditor unchanged. Next work, if separately authorized, should retain
the frozen benchmark and intervention, complete coverage under a separately
versioned spending plan, and obtain independent blinded semantic review.
