# Frozen rubric → review questions

Authority: the unchanged `synthetic-physics-v1.1` rubric supplied alongside this
handbook. This process adds diagnostic annotations and a human collection format;
it does not change the benchmark's weights, reference answers, labels or penalties.

| Frozen dimension | Points | Treatment |
|---|---:|---|
| Measurement correctness | 12 | Existing scorer. Human uncertainty/observation flags can question scientific interpretation; do not silently rewrite mechanical points. |
| Availability | 5 | Existing scorer; review calibration/missing/frozen applicability separately. |
| Citation accuracy | 8 | Existing 4 membership points preserved; **4 entailment points** from `citation_entailment`. |
| Document scope | 8 | `document_scope`: generic definitions, published example, synthetic premise versus incident truth. |
| Atomic verdicts | 20 | Existing frozen-key macro recall and exact statement/evidence contract, unchanged. Human preferred verdict/validity are separate independent judgments, not replacement labels. |
| Causal leaps | 8 | `causal_leaps`: observation versus causal/material identification; unsupported-certainty flags. |
| Missing premises | 6 | `missing_premises`: concrete premise and its inferential role. |
| Historical analogue | 5 | `historical_analogue`: actual overlap and absent discriminators, not a causal probability. |
| Hypothesis comparison | 6 | `hypothesis_comparison`: at least two mechanisms and an applicable counterprediction. |
| Sensor acquisition | 8 | `sensor_acquisition`: discriminating acquisition when required, relevance/availability and bounded means of obtaining evidence. A recommendation is not acquisition. |
| Necessity and sufficiency | 6 | `necessity_sufficiency`: conditional implication, converse and non-identifiability. |
| Structured output | 5 | Existing first-pass/repair/invalid-submission scoring, unchanged. |
| Cost/tool efficiency | 3 | Existing accounting/tool bounds, unchanged. Reviewers do not get identities, costs or execution-group metrics. |

The eight human fractions total **51 points**, before penalties. The original
mechanical subtotal is **29**; frozen reference-atomic scoring contributes another
**20**. These three amounts must not be conflated. Human per-atom scientific
validity, calibration flags and abstention annotations carry no additional points.
The collector will not invent a combined /100 score from missing scorer inputs.

Frozen review fractions: 0 / 0.5 / 1. Missing review is incomplete, never full
credit. N/A is explicitly incomplete and is not normalized away. The supplied
frozen rubric's full/partial/zero anchors govern each packet-level dimension.

Frozen penalties are recorded as distinct error events and applied **after** the
original weighted score, floor zero:

| Category identifier | Deduction per distinct event |
|---|---:|
| invented_reading | 15 |
| fabricated_citation | 15 |
| unsupported_causal_certainty | 10 |
| ignoring_supplied_contradiction | 10 |
| generic_topology_transfer | 10 |
| correlation_as_causation | 10 |
| unavailable_frozen_irrelevant_sensor | 2 |

One error can fall in multiple categories as the frozen rubric permits; duplicate
narrations of the same error within one category must not be counted twice.
Stable event IDs, atom IDs, evidence pointers and rationale support adjudication.
Do not deduct penalties from just the 51-point semantic subtotal and call the
result the frozen total. Blanket-abstention capping (40/100), separate SUPPORTED/
CONTRADICTED recall thresholds (0.8), required acquisition and missing-submission
rules remain with the existing frozen evaluator. This workflow does not change
them or treat human disagreement as authority to edit the key.

## Scientific questions → form fields

These diagnostic annotations explain *why* a frozen dimension earned its fraction;
they do not create additional weighted scores.

| Handbook question | Atomic form field | Frozen dimensions informed |
|---|---|---|
| Scientific validity | `preferred_verdict`, `scientific_validity`, `interpretation_target` | Independent diagnostic comparison; frozen atomic reference score stays separate |
| Citation entailment | `citation_entailment` | Citation accuracy: human 4 points |
| Synthetic assumptions | `flags.assumption_misuse` | Document scope; necessity/sufficiency |
| Measurements versus cause | `flags.measurement_cause_conflation` | Causal leaps |
| Calibration uncertainty | `flags.calibration_overreach` | Causal leaps; missing premises; hypothesis comparison |
| Unestablished versus contradicted | `flags.unjustified_contradiction` | Causal leaps; necessity/sufficiency |
| Missing premise | `flags.missing_premise_vague` | Missing premises |
| Feasible next evidence | `flags.next_evidence_not_feasible` | Sensor acquisition; hypothesis comparison |
| Unsupported causal certainty | `flags.unsupported_causal_certainty` | Causal leaps; documented penalty events if applicable |
| Excessive abstention | `flags.excessive_abstention` | Hypothesis comparison; necessity/sufficiency; frozen recall/cap remain separate |

Every annotation requires received-evidence pointers and a rationale. Neither
pointer validity nor a completed annotation proves scientific correctness.
