# Post-freeze offline validation

No Muse requests were made. Estimated API spend: $0. Provider billing records
were not requested; no actual provider charge is claimed or inferred.

| Release | Baseline atomic macro recall | Mechanical points | Semantic total |
|---|---:|---:|---|
| v1, retained with calibration-isolation defect | 0.9000 | 27/29 | Not graded |
| v1.1, separately frozen corrected inputs | 1.0000 | 29/29 | Not graded |

The fixed baseline uses arithmetic and explicit proposition templates. These
numbers validate the interface and reference consistency; they do not demonstrate
LLM efficacy, general reasoning or industrial diagnosis accuracy. Both transcripts
and detailed scores are retained privately. No post-freeze reference verdict or
scoring-weight changes were made. See CHANGELOG.md for the v1 defect.

Verification: 16 current public interface tests and 6 private reproducibility /
physics tests passed. The latter cover cross-case calibration isolation, exact
regeneration, sensor error/missingness, numerical invariants, steady-state
counterpredictions and integrated storage conservation. All frozen file hashes
were checked after the baseline. No existing application, demo, real telemetry,
33-case evaluation or captured investigation file was modified. Production tests
were not rerun because this standalone release imports no application modules.

Independent source checks validate generic definitions and the published example,
not this synthetic installation. A production engineer has not certified its
industrial validity. No blind human semantic scoring has yet been performed.
