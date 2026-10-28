# Physical evidence coverage and decision

Audit date: 2026-10-28. No paid Meta calls. Prior M3/M4 protocols, results and
traces are unchanged. Sources were audited independently of held-out labels.

| Coverage | Documented evidence | Important limit |
| --- | --- | --- |
| Sensor semantics | 27 quantities, units and named equipment locations from [dataset.ini](https://github.com/petrobras/3W/blob/main/dataset/dataset.ini); pinned blob `4c4799e80e04a9cf8b10cb3f9a23f1c487797cc9` | Generic dataset declarations, not validated tags or each well's piping |
| Valve encoding | Authors' [Table 3](https://arxiv.org/html/2507.01048v1): 0 closed, 1 open, 0.5 another state | Distinct from operational `state` labels; not proof of a reliable individual transmitter |
| Fault mechanisms | Nine short descriptions in the authors' Section 2.4 | Descriptions do not define diagnostic thresholds |
| Example patterns | Authors' Figures 3–6: pressure directions for faults 2, 6 and 8; oscillations for fault 3 | Published examples, neither necessary nor sufficient signatures |
| Detailed discriminators | Not established here for faults 1, 4, 5, 7 and 9 | No invented cooling rules, hydrate boundaries or quantitative decision cutoffs |
| Normal references | Pre-window measured distributions can be computed | Normal operation cannot be inferred from merely preceding the window |

The valve encoding is a correction to our earlier **context coverage**, not a
correction of the numeric mapping Muse used: the mapping is documented in the
authors' paper but was absent from our supplied context. Still, interpreting a
constant open indicator as excluding an event requires more than this mapping.
The authors also note unresolved original tag/unit validation (Section 2.5).

The new graph contains sensor, equipment, fault, expectation and concept nodes.
Every edge has a stable ID, source/version, source locator, scope and epistemic
status. Source-backed generic placement is kept separate from the original
illustrative graph. Engineering hypotheses and empirical correlations have
separate status values; none is silently promoted to documented physics.

## Actual v4 trace findings

Archive SHA-256:
`9455c082fa0d49899bc2b8ea591de06479780935bd11758bef684f2aa42c45f8`.
All eight audit chains verify. Six Muse investigations completed without repair.

- Statistical initial selection: **6/12 missing queries**, all ABER-CKGL.
- Muse additional selection: **7/18 missing queries**.
- Thus 6/13 missing requests originated in the initial policy; 7/13 in Muse.
  These are repeated investigations of two incidents, not independent samples.
- Three graph calls occurred after sensor-budget exhaustion. Graph-only variants
  did not traverse the graph. Access alone did not demonstrate graph-guided selection.
- Two retrieval calls each returned five candidates. One used only P-TPT and all
  five analogues supported the incorrect baseline class. The other had mixed
  labels and two/three shared measurements.
- A retrospective two-shared-sensor filter of these **logged candidates only**
  changes coverage from 2/2 to 1/2 and conditional top-1 class agreement from
  1/2 to 1/1. Correct top-1 matches remain 1/2 overall. This is not an index rerun,
  a tuned retrieval rule or evidence of improved population performance.

## What can be concluded now

The sources support a more faithful **evidence audit** and carefully qualified
comparisons with example signatures. They do not establish a reliable nine-fault
hypothesis challenger. No revised physical claim has received engineering review.

**Recommendation:** prioritize a narrower evidence-auditing demo for the hackathon.
Do not authorize another paid pilot yet. First run the zero-API training/development
benchmark described in [grounding-development.md](grounding-development.md), and
review whether it leaves enough relevant evidence within five queries. A later
small pilot could test faithful use of documented facts, not presume detection or
classification improvement. Keep the original scientific decision gate unchanged.

**Execution limitation:** the real fitting/development dataset is not available in
this workspace. The trace analysis above is real; the new availability/retrieval
benchmark has been exercised on synthetic test fixtures only. No real-data
accuracy, availability-policy gain or reference efficacy is claimed.
