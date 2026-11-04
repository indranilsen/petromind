# Submission alignment and cleanup audit

## Scope

This cleanup updates product wording and current entry-point documentation. It
preserves experiment implementations, frozen artifacts, prompts, budgets, audit
records, reviewer isolation, working routes and replay behavior. No paid calls or
new evaluation are part of the cleanup.

## Verified narrative boundary

The primary demonstration uses real Petrobras 3W measurements and Meta Muse Spark
for evidence investigation. The separate Extension uses controlled synthetic
hydraulics. Neither a classification label nor a model-scoped synthetic finding
is certified physical root cause.

The supplied submission draft associates **20/33 (60.6%)** with “Adaptive Reasoning
(Sensors + GraphRAG).” The repository does not support that attribution:

- [Evaluation runner](../petromind/eval_runner.py): fixed/adaptive use a sensor-only
  session, no retriever and `model.run`, not the Muse `run_agent` path.
- [Baselines](../petromind/baselines.py): predefined training-ranked versus adaptive
  posterior-weighted sensor selection under the Gaussian statistical classifier.
- [Variants](../petromind/variants.py): the Muse configurations are `sensor_only`,
  `topology` and `graphrag`.
- [Frozen-study definitions](evaluation.md#compared-configurations): graph and
  analogue retrieval are disabled for both statistical baselines. The evaluated
  GraphRAG variant adds equipment context and similar training incidents; later
  source-backed engineering knowledge is a separate capability.

The counts and descriptive 5× / 4× ratios are unchanged. They compare whole
configurations, not an isolated causal benefit of adaptivity or GraphRAG. README,
submission text and visible result descriptions retain the statistical boundary.
**The owner must use this correction when finalizing any external submission or
recorded narration; no external video or portal content was changed here.**

## Open-PR review

Both open PRs were reviewed from their actual changed-file patches, including
public research reports, implementation, accounting/review safeguards and tests.
No PR was closed: neither has a demonstrable merged replacement. Branches remain.

| PR | Disposition | Evidence and reason |
| --- | --- | --- |
| [#34](https://github.com/indranilsen/petromind/pull/34) | Retain open | Unique `research/sprint_c` recovery/phase-2 execution, terminal-receipt settlement validation, immutable SQLite journaling, APFS durability checks, preserved protocols/results and regression tests. The synthetic Extension is a replay UI, not a replacement for these reliability or research records. |
| [#36](https://github.com/indranilsen/petromind/pull/36) | Retain open | Unique isolated AI semantic-review workflow with source commitments, provider-family separation, bounded reservations, freeze-before-adjudication and unchanged human fields. Existing human-review tooling and the Demo do not supersede it. AI review is not qualified human validation. |

Reviewed heads: #34 `66de37ce7e645f2fc98244dd4d38fcf9ce0ee128`; #36
`9273f89ad0339bb98a2255993d8284f21e11a839`. This review is not approval to run or
merge either research track, nor certification of its results.

## Documentation and assets

The concise README is the current entry point. Its prior implementation/tooling
content is preserved in [an archive](archive/implementation-history.md).
The [documentation index](README.md) separates current product/setup guidance,
scientific records and earlier UI snapshots. Existing URLs and dated receipts are
retained; historical UI guides and screenshots carry status notices.

The initial tracked-file audit found no broken relative Markdown destinations,
identical image bytes, tracked logs/caches or credential-pattern matches. Referenced
screenshots, prototype scripts and research records were retained. No asset or
remote branch was deleted merely because it appeared old or unreferenced.
A pattern scan cannot establish that the full Git history has never exposed a secret.

## Remaining owner checks

- Verify the real saved-v5/monitoring artifacts on the recording machine; those
  private inputs are not supplied by the public repository.
- Confirm any public demo/video links and authenticated submission requirements.
- Correct the unsupported adaptive + GraphRAG attribution in external materials.
- The mobile page-overflow assertion in the wider saved-replay smoke previously
  reproduced on unchanged main; this wording cleanup does not redesign navigation.

## Cleanup validation

- Five focused tests passed: the Technology publication/scope tests, four-route
  HTTP/security smoke, synthetic optional-endpoint isolation and original-output
  preservation tests. These use existing software fixtures, not the owner's real
  monitoring or saved-v5 bundle.
- A quick browser text smoke visited Home, Demo, Extension and Technology with
  existing fixtures. Four navigation links, unchanged five-row counts, zero
  JavaScript errors and zero paid/live requests were checked. Home and Extension
  screenshots were visually inspected.
- JavaScript syntax, changed Python test/helper Ruff checks and Git whitespace
  checks passed. The documented `check` and `serve` CLI help accepts the shown flags.
- All local Markdown link destinations and referenced `scripts/*.py` paths resolve.
  All 133 audited backend/research/fixture files remain byte-identical; the prior
  README is preserved in its archive with only relative links adjusted.
- No full suite, scientific experiment, model call, signed-in portal action or
  private real-recording validation was performed. External link availability and
  authenticated delivery access were not certified by the local link scan.
