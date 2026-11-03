# Offline validation receipt

This is software validation, not an independent semantic review.

- **19 standalone regression tests passed** on Python 3.12.
- Ruff formatting and lint checks passed for the new Python files.
- Byte-compilation and CLI help checks passed.
- Each integration fixture prepares 70 synthetic software packets, generates two
  independently ordered blank forms and exercises owner-side aggregation.
- Tests cover source commitments, unknown/private fields, prior scores, evidence
  pointers, incomplete/duplicate reviews, ordinal and nominal kappa, degenerate
  marginals, N/A/noncompletion, adjudication completeness, changed process code,
  exact original reviewer bytes and hash-sealed outputs.
- The frozen rubric snapshot is checked against upstream Git blob
  `39c559ec0686ef00a7c936142485d75b0ee32780` during preparation.

Reproduce without extra runtime dependencies:

```bash
python -m unittest discover -s tests -p test_semantic_review_workflow.py -v
python -m compileall -q research/semantic_review scripts/semantic_review.py
python scripts/semantic_review.py --help
```

No actual Sprint C packet export was available in this workspace. No qualified
human review was conducted, no private key/map was opened, no paid API was called,
and no original experiment or production file was modified. The full upstream
repository suite was not executed in this partial checkout. Successful fixture
projection does not certify all private export shapes or perfect blinding.

Owner acceptance before distribution: verify the existing packet-file commitment,
run preparation on the original 70-packet export, inspect every derived bundle for
residual identity leaks and usable evidence context, appoint qualified independent
reviewers, and retain the original immutable artifacts. Do not bypass a preparation
refusal or silently reconstruct missing evidence.
