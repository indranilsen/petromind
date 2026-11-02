# What the original GraphRAG experiment actually tested

Research Session A · 2026-11-02 · read-only forensic review. No old experiment was
rerun, relabeled or tuned. Findings below distinguish direct code inspection,
locally verified development captures, and the prior M3 report.

## Finding

The original `graphrag` condition was **illustrative equipment-neighbor lookup
plus a separate median-based historical incident search**. The two tools supplied
context to Muse; they were not a connected retrieval system over verified
sensor–equipment–failure–physical-expectation paths. This was a legitimate bounded
prototype, but its name does not establish that a richer GraphRAG design was
fairly tested, or that any such design would improve classification.

The frozen results remain adaptive **20/33**, fixed **13/33**, sensor-only **4/33**,
equipment graph **1/33**, and GraphRAG **5/33**. GraphRAG was one case better than
sensor-only, not demonstrably better overall. The study did not establish a
classification advantage over the adaptive baseline or a causal effect of graph
access. These are classification results, not claim-auditing scores.

## Evidence inventory and limits

- Inspected GitHub history and actual file contents at the original M3 commit
  [153d8db](https://github.com/indranilsen/petromind/tree/153d8dbcdadc54d865755eaf33a9cf58fd0be02f).
  The equipment module has only its original framework introduction in its file
  history. Its lookup is unchanged; retrieval later gained optional overlap and
  informative-sensor filters. The original median distance remains the default.
- Read the current source-scoped knowledge package, original agent instructions,
  session budget boundary, evaluation code, and preserved
  [M3 offline report](../../docs/milestone3-failure-analysis.md).
- Verified the original claim capture and its M5 development lineage using
  `claim_review.load_capture` and `claim_evaluation.load_captured`. The capture
  and parent fingerprints agree. The parent manifest separates 15 fit groups,
  eight development groups, and eight excluded original test groups.
- The source development cohort was outcome-stratified/enriched in prior work;
  it is not a population sample. Four completed original claim-auditor outputs and their tool records are
  locally available. These are the old v1 captures, **not the latest successful
  v5 live artifact**. No old result was regraded under the research contract.
- Raw 3W data and original M3 per-request traces/results are absent here. M3
  frequency/error counts quoted below are inherited from the existing report,
  which names its source-results hash and protocol. They are not a fresh
  independent reconstruction of the full M3 audit chains.
- Captured history identifiers are fitting-index order hashes, not joins to the
  M5 manifest case IDs. Training-only provenance comes from the pinned constructor
  and its split guard; raw reindexing cannot be independently repeated here.

## Reconstructed original path

| Step | Actual behavior and source |
|---|---|
| Initial input | `agent.run_agent` supplied an opaque case identifier, five-sensor budget and known transient onset. Muse selected sensors; it did not receive a conventional classifier's initial diagnosis. This differs from the new auditor task. |
| Measurements | `DiagnosticSession.get_sensor_history` returned numeric/quality summaries for requested channels. New unique sensors, including missing channels, cost one; repeats were cached. The target label and source paths were not tool inputs. |
| Graph | [`EquipmentGraph.neighbors`](https://github.com/indranilsen/petromind/blob/153d8dbcdadc54d865755eaf33a9cf58fd0be02f/petromind/equipment.py) grouped 14 sensors into four equipment concepts, returning equipment and other catalog sensors in the group. Every association was explicitly illustrative. There were no failure nodes, physical thresholds, operating conditions or verified cause paths. |
| History query | `search_similar_incidents()` had no model-authored text query. The session passed only already observed sensor summaries to the training-only retriever. Graph results did not determine a connected historical query. |
| Ranking | [`IncidentRetriever.search`](https://github.com/indranilsen/petromind/blob/153d8dbcdadc54d865755eaf33a9cf58fd0be02f/petromind/retrieval.py) averaged `min(1, abs(median_a-median_b)/max(1, abs(median_a), abs(median_b)))` over shared available sensors. Sort ties followed index order; three matches were returned by default. |
| Returned history | Opaque training case ID, training-event label, rounded distance, shared count and matched sensor names. No historical waveforms or unqueried target readings. One shared channel was sufficient. |
| Prompt/action | [`agent_tools.INSTRUCTIONS`](https://github.com/indranilsen/petromind/blob/153d8dbcdadc54d865755eaf33a9cf58fd0be02f/petromind/agent_tools.py) explicitly warned against causal proof, described graph associations as illustrative, and supplied public fault names and sensor context. It asked Muse to choose informative sensors and finish with a fault category. It supplied no validated discriminating tests or hypothesis-specific physical expectations. |
| Model loop | `run_tool_agent` replayed tool results into a bounded Responses conversation. No separate physical simulator, trained graph embedder, contrastive verifier or connected evidence planner intervened. |
| Evaluation | [`eval_runner`](https://github.com/indranilsen/petromind/blob/153d8dbcdadc54d865755eaf33a9cf58fd0be02f/petromind/eval_runner.py) scored hidden fault labels; variants had distinct tools and could choose different sensors. One stochastic run per condition does not isolate graph causality. |

## Failure taxonomy

| Category | Concrete evidence | What is established; what is not |
|---|---|---|
| Retrieval failure / lossy representation | The distance discards direction, variability, temporal shape and physical operating context. Equal constant medians contribute zero distance. Overlap is not weighted or required to match. | A constructed unit regression demonstrates a one-sensor equal-zero analogue outranking a two-sensor near match. This proves a mathematical ranking possibility, not that a particular M3 decision was physically wrong for that reason. |
| Knowledge-coverage failure | The original graph contained only sensor/equipment associations. `P-TPT` was grouped as illustrative `tubing`; the later documented generic definition is a subsea-tree transducer. Neither graph is verified installed-well piping. | Missing fault-discriminating rules cannot be fixed by retrieving more neighbors. The current documented collection still has no universal necessary/sufficient fault-9 pressure rule. Absence here does not prove none exists in engineering literature. |
| Reasoning or scope failure | The preserved ungrounded v1 fault-9 audit marked the joint pressure-rise causal proposition `PARTIALLY_SUPPORTED`, while separately saying necessity was not established. The grounded v1 audit correctly separated measured rises and the unestablished cause. | An observable scope/composite-contract problem exists in these development outputs. It is not evidence that every M3 prediction ignored a received physical contradiction. The later v5 atomic fix already addresses the contract issue; no new production repair is proposed. |
| Task/evaluation mismatch | The original objective required a fault label even when source facts only established generic semantics or analogue similarity. A published example can support a narrow comparison without identifying root cause. | The current grounded v1 fault-2 audit supported the two-direction comparison while explicitly declining causal proof. That is useful scope reasoning, not a classification-accuracy result. |
| Protocol/implementation limitations | Names were visible but target availability was not free. Every new missing sensor consumed budget. Original graph and history tools did not return a sensor-selection utility estimate. | The prior report records unavailable unique queries: sensor-only 50/165, topology 50/165, GraphRAG 48/165, adaptive 48/165. This burden affected the statistical baseline too. It does not prove avoidability before querying. |

### What the old exports suggest, without proving

The existing M3 report records GraphRAG predicting fault 2 in 15 of 21 fault-7
cases; every such prediction had a preceding nearest fault-2 analogue. This is
consistent with anchoring, but it is **not a counterfactual causal test**. Similar
operating medians, low-overlap matches, differing chosen sensors, training coverage
and the model's interpretation can all contribute. No private intent transcript
is available. We do not infer anchoring merely from label agreement.

All Muse variants selected P-PDG across the 33 cases. The report records 26
constant-zero, four unavailable and three variable cases. Zero was correctly
retained as a legitimate measurement. Selection salience, domain priors or prompt
wording are hypotheses, not observed motives. No sensor exclusion or parameter
has been chosen using those held-out outcomes in this sprint.

The report also records five fault-6 cases absent from training. This is a
coverage limitation; it is not proof that the model had a sufficient physical
basis to infer fault 6 anyway. All 165 cells reportedly completed in the final
frozen run, so earlier pilot token-limit failures must not be substituted as the
explanation for its final accuracy.

### Were units and locations missing?

Not wholesale. The original prompt supplied public descriptions/units for core
pressure, temperature, choke and flow tags, including tree pressure. It would be
incorrect to attribute all errors to missing sensor names or units. What was
missing was a source-backed, scope-aware connection from those definitions to
validated discriminating expectations and applicable well conditions. Valve
codes were listed in the prompt without the later source-scoped mapping. None
of this establishes inadequate model pretraining as the cause.

## Intervention selected before new model outcomes

**E changes only the B lookup implementation:** query topic + already observed
sensor names + public candidate hypotheses seed a two-hop search over existing
source edges (both lookup directions explicitly recorded). At most 24 source
facts/24 paths are returned, with original IDs, provenance, status and scope.
No new causal edge, threshold or installed-well topology is created. Prompt,
model, public cases, output schema, budget and execution limits remain identical
to B. E can expose compatible alternative examples; it cannot manufacture the
missing discriminating rule.

A fixed offline fault-9 query returns 2 facts / 741 serialized bytes under B,
and 24 facts / 13,335 bytes under E, including the published fault-8 pressure
pair. **This is roughly 18× more context, not a demonstrated reasoning gain.**
Required causal-rule recall is null because no such rule is present. Whether
this context helps or distracts Muse remains unmeasured.

D preserves the original equipment algorithm and available captured development
history projection (including original training labels). It is named
`D_legacy_partial` because M3's raw pool, exact queries and trajectories cannot
be reproduced without its original artifacts. It is not passed off as a faithful
rerun, and its extra labels mean D-vs-E is not a single-variable comparison.

## Recommendation now

Retain the existing statistical engine and v5 scope-aware evidence auditor. Do
not deploy connected retrieval or restart fault classification on the strength
of these offline probes. Python is already safer and sufficient for the 12
formalized numeric/source-scope tasks (12/12); always abstaining earns only
1/3 macro recall. That ceiling is useful honesty, not a Muse success claim.

Use the released independent benchmark to test genuinely harder reasoning and
have engineering reviewers assess premise identification, source entailment and
next-evidence usefulness. A two-task, five-condition paid pilot is implemented
but blocked here by missing `MODEL_API_KEY`; zero real requests or paid before/
after results exist. Extra sensor usefulness is unassessed because no additional
raw summaries are available. The held-out classification cohort is unchanged.
