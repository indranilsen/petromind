# Milestone 5 execution status and recommendation

2026-10-28. No paid Meta calls were executed.

Implemented the five-template provenance-tagged registry, precommit/execute/assess
agent, paired information-gain comparison, frozen development cohort selection,
updated statistical posterior on matched acquired data, durable request/token/
estimated-dollar caps, independent review packets and predeclared decision gate.

A real metadata-only [six-case cohort lock](m5-cohort-lock-v1.json) is committed
before any new scientific-model outcomes: one incident from each available class
1, 2, 5, 7, 8 and 9; three correct and three incorrect initial diagnoses across
five development wells. It uses the unmodified v4 parent metadata, not telemetry
or new outcomes. Lock ID:
`41e0e873b0ea7680082f98de52ad41c4caaca1804aac189c7339d1b6f2b3c808`.
Local prepare still must verify actual file hashes/runtime before creating the
final execution protocol. No normality or diagnostic result is fabricated.

Offline evidence: **316 tests pass**. All new end-to-end interactions use synthetic Parquet fixtures
and HTTP MockTransport. The two-case mocked pilot completes all six tasks using
12 mocked requests; the six-case mocked development matrix completes 18 tasks
using 36 mocked requests. This verifies plumbing, not Muse's scientific capability.
Tests deliberately use inconclusive synthetic assessments and do not claim a
successful experiment. No synthetic telemetry or outcome is substituted for a
real incident or added to earlier results.

A live pilot could not run because neither the real fitting/development Parquet
dataset nor MODEL_API_KEY is available in this execution environment. Existing
uploaded archives contain prior summaries/results, not the full telemetry needed
for new spectra, paired sample differences or pre-event references. Replaying
those summaries as new measurements would be invalid. Keep credentials local.

Recommendation: **PENDING for the new scientific-investigator capability**. The
current evidence does not justify GO or PARTIAL GO, nor does lack of execution
establish scientific NO GO. The provenance-aware auditor remains the defensible
fallback. This new research question differs from direct classification and M4
challenging; old failures do not settle it. A source-scoped, cost-capped two-case
pilot on the dataset owner's machine is the next justified feasibility check,
followed by engineering review before any expansion or UI work.

Known limits: published signatures are examples, valve tags may be unreliable,
reference normality is unverified, FFT concentration lacks a fault-specific
threshold, numeric predicate agreement is not physical inference, and the
information-gain model ignores missingness and novel signal features. Report
these limits and any unsupported claims rather than forcing discriminative
expectations or a successful assessment.

See [milestone5.md](milestone5.md) for exact commands, registry, fairness conditions,
spending assumptions and the frozen rubric. Preserve all M3/M4 results unchanged.
