# Captured claim-level review — October 28, 2026

This is a mechanical and source/logic review, **not independent engineering
certification**. The original outputs are unchanged. The reviewed archive SHA-256
is `501ce4e80c1d235fa66e70d42dbb123e9372524b3c9674bbca3a2e8fb2ce8a79`;
protocol `58e8c6ba429a46730434f5b1b91b112c0ca7fd7b0e733fa3806b71c473bb6b84`.
All six result records, source IDs, and audit chains verify. The 18 explicit
numeric observations exactly match the charged summaries; all 33 citation
occurrences refer to evidence actually supplied. Each audit inherited three
charged sensors, with zero new observations. Three audits needed one
`inconsistent_verdict` repair; all four completed within the original bound.
The recorded combined estimate is $0.1080808 for 11 requests. No new calls were made.

The data checked here are actual captured first/last/quality summaries, not raw
600-point traces or independent sensor calibration. They match the original M5
capture, reviewed earlier. The local workspace has no raw training dataset with
which to recompute analogue distances or independently recheck fitting-well
membership; the existing preparation path enforces those partitions.

## Every captured finding

`F9-U/G` means the fault-9 task, ungrounded/grounded; `F2-U/G` means the
published-example task. Ordinals follow the original output. A verified numeric
observation is not a verified physical explanation.

| Finding | What can be established | Remaining scope / expert question |
|---|---|---|
| F9-U1 | P-PDG first 24,103,160; last 24,394,920 Pa; delta +291,760 Pa; 600 valid samples. | End-to-end rise, not monotonicity or hydrate cause. |
| F9-U2 | P-TPT first 10,272,620; last 10,604,840 Pa; delta +332,220 Pa; 600 valid samples. | End-to-end rise, not a fault-specific response. |
| F9-U3 | The claim combines supported rises with a causal conclusion. | `PARTIALLY_SUPPORTED` applies to the combined statement; it must not imply partial proof of fault 9. |
| F9-U4 | No necessary fault-9 pressure rule was supplied to this condition. | Missing documentation is not falsity and does not prove no such rule exists anywhere. |
| F9-G1 | Same P-PDG endpoints and positive delta. | No instrumentation or causal validation follows from `variable` quality. |
| F9-G2 | Same P-TPT endpoints and positive delta. | A legitimate measured rise does not establish necessity/specificity. |
| F9-G3 | Retrieved fault-9 facts describe service-line hydrate obstruction; neither states a universal pressure signature. | Does a validated well-applicable criterion exist? No such criterion is provided here. |
| F9-G4 | Returned training events are 9, 8, 8. | Overlaps are **3, 3, 1 sensors**. Do not imply equal corroboration or a calibrated diagnostic likelihood. |
| F9-G5 | Whole-claim verdict separates observations from the unestablished inference. | Wording should preserve the difference between supporting a clause and establishing a diagnosis. |
| F2-U1 | P-PDG delta +424,620 Pa; 600 valid samples. | Numerical rise only. |
| F2-U2 | P-TPT delta −6,921,580 Pa; 600 valid samples. | Numerical fall only. |
| F2-U3 | The documentary example was not supplied to the ungrounded condition. | Its caution is reasonable; target disagreement is not a false physical rejection. |
| F2-U4 | Two recorded directions alone do not contain an exclusion test. | A general methodological caution, not an experimentally validated differential diagnosis. |
| F2-G1 | Same recorded P-PDG rise. | Calibration affects physical truth, not whether the stored endpoint numerically increased. |
| F2-G2 | Same recorded P-TPT fall. | Do not turn a recorded decrease into proof of valve closure. |
| F2-G3 | Returned Figure 3 example says P-PDG increases and P-TPT decreases; both directions match the recorded deltas. | **This narrow comparison is supported by the supplied record.** Generalizability is required only for a stronger diagnostic claim. |
| F2-G4 | Source scope is a published example, not a universal fault rule. | Example consistency and a class-2 analogue do not establish root cause or exclude alternatives. |

A direct check of the author manuscript on October 28 confirmed Figure 3's
pressure directions and Table 3's valve-code meanings. Section 2.5 also explicitly
notes that original tag mappings and pre-conversion units were not verified.
These checks establish what the document says, not the physical truth of a new
well diagnosis. The dataset.ini blob remains the existing pinned registry source;
no new per-well verification is claimed.

The graph's extracted source records are consistent with the comparison. This
review does not independently reconstruct the authors' raw example, verify every
instrument tag, or certify the physical applicability of that example to this well.

## Historical overlap, explicitly

For the fault-9 task, the event-9 match (distance 0.143509) shares ABER-CKGL,
P-PDG and P-TPT. The first event-8 match (0.170863) shares those same three sensors.
The second event-8 match (0.171286) shares **only P-TPT**. All are relative-median
similarity results. A single sensor and a three-sensor comparison are not equal
amounts of corroborating evidence; the distances are not probabilities.

For the fault-2 task, all three returned analogues are event 2 and share P-PDG
and P-TPT. This is still similarity, not a causal or exclusion criterion.

## Valve-state encoding and its limits

The registered author manuscript [Table 3](https://arxiv.org/html/2507.01048v1)
documents ESTADO sensor encodings: **0 closed, 1 open, 0.5 other**. This is a
source-backed generic encoding, not a measured valve position. Neither captured
audit queried valve-code context, and neither packet contains ESTADO-DHSV.
Operational `state`/`class` labels are different fields and must never substitute
for observations. ABER-CKGL is choke opening, not an ESTADO-DHSV measurement:
53% constant is observed in the first case; all 600 samples are missing in the
second. Do not infer DHSV state from either.

The knowledge registry also points to [dataset.ini](https://github.com/petrobras/3W/blob/main/dataset/dataset.ini),
pinned to blob `4c4799e80e04a9cf8b10cb3f9a23f1c487797cc9`. Its tag meanings and
generic locations are not verified per-well topology.

## Recommended evidence: candid limits

The captured fault-9 suggestions ("independent diagnostic test" / "verified
signature") identify a need but **do not specify an executable discriminating
test**. A single controlled example cannot establish a universal necessity rule.
The current registry contains descriptive computations, not verified fault-9
versus fault-8 discriminating procedures. There is no justified five-sensor
recipe to invent here.

Concrete requests are: the approved well-specific service-line schematic and
sensor tag map, then an operator-validated fault-isolation procedure with
applicability and differential criteria. These documents are **not supplied**;
their existence and adequacy are not established. A schematic alone cannot prove
the diagnosis. Extra sensor values would need a defensible interpretation rule.

For the fault-2 **comparison**, no extra evidence is needed to match the two
recorded directions to the returned example. Actual DHSV instrument-state and
operating logs, well-specific tag mapping and differential criteria would be
requests for a **stronger closure/root-cause claim**, not prerequisites for the
limited example comparison. Neither a valve code nor a tag map alone certifies
root cause.

## Concise independent expert-review packet

Review all four actual outputs in `completed-review-packets.json` from the original
capture, using the table above and the cited manuscript/dataset documentation.
The demo's **Download claim-level review** produces all 17 findings, their
source IDs/digests, and mechanical/editorial notes. It does not supply grades.

Please answer, with source/locator and scope:

1. Do the fault-9 sources supplied here establish any necessary or sufficiently
   specific joint pressure response? If not, is the identified missing premise
   stated accurately without asserting that no such rule could exist?
2. Is the limited Figure 3 directional comparison justified while the causal
   interpretation remains unestablished? Are the stronger-claim requests scoped
   separately rather than imposed on an already supported comparison?
3. Does the analogue discussion accurately reflect overlaps 3/3, 3/3, 1/3?
   Is it overstating diagnostic evidence or merely describing ambiguity?
4. Are the encoded valve meanings correctly distinguished from actual actuator
   position, instrument validity and hidden operational/class labels?
5. Which proposed next document/measurement is realistic and would address the
   specific premise? Is it sufficient, merely necessary, or unavailable? If no
   verified discriminating test is available, confirm that uncertainty explicitly.

Leave `physical_correctness` ungraded until an independent qualified reviewer
answers. Do not ask Muse to grade itself. Original benchmark gate remains
**PENDING**. The latest user instruction authorizes this narrowly disclosed demo;
its existence does not retroactively pass the research gate or change results.
