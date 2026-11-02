# Version history

## synthetic-physics-v1.1

Corrects cross-case mutation in the PRIVATE generator: it now deep-copies each
case's sensor payloads before withdrawing calibration assurance in one case.
The original shared list incorrectly propagated that flag into three later cases,
whose local model premises specified GOOD calibration. This was a genuine input /
reference inconsistency discovered by the first post-freeze offline baseline.

Reference judgments, numerical physics, prescribed uncertainties and scoring
weights are unchanged. The corrected input preserves the intended isolated
calibration intervention. A specific cross-case isolation regression check was
added to the private numerical suite. v1.1 is separately frozen before evaluation.

## synthetic-physics-v1 — retained, known defect

`archive/v1/` preserves the original public inputs, adapter, rubric, source notes,
tests and FREEZE.json. The original private generator, key, vault, freeze and
baseline transcript are retained in the owner's private archive. Its original
offline baseline result was 27/29 mechanical points; supported-atom recall 0.7,
NOT_ESTABLISHED recall 1.0 and CONTRADICTED recall 1.0. No human semantic total
was assigned. The affected calibration flags caused the baseline to abstain on
physical-pressure assertions. These are not model-efficacy measurements.

No paid model ran against either version before freeze. Do not combine scores
across versions or describe v1.1 as an untouched evaluation of original v1.
