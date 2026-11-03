# Final integration-readiness receipt

This validates the review workflow, **not scientific judgments**. No independent
human scores were generated and no real forms were filled by an LLM.

## Actual export compatibility

The owner's preserved the verified recovery snapshot was accessed
securely. Only score-index metadata, manifest commitments and the blinded packet
member were opened. No actual owner key, hidden sensor vault, reference-score
file or unblinding map was opened/extracted. The older 42-packet export was not used.

The selected existing packet file matches both its score-export manifest
and outer snapshot manifest. Exact packet commitments and snapshot storage paths
are private custody metadata, recorded only in the owner-side verification receipts.

| Check | Actual result |
|---|---:|
| Original blinded packet count / unique IDs | 70 / 70 |
| Accepted final submissions | 64 |
| No final accepted submission | 6 |
| Atomic propositions | 228 |
| Returned tool results | 434 |
| Preserved accepted tool-result assessments matching stored finals | 64 / 64 |
| Readable Markdown packets per reviewer | 70 |
| Blank individual item forms per reviewer | 70 |
| Distributed files per reviewer | 147 |
| Real semantic grades created | 0 |
| Paid API requests | 0 |

`prepare` succeeded against the real frozen schema. The fresh v2 `verify` command
then compared every projected initial packet, returned result, accepted assessment,
blind ID, form, readable copy, randomized order and distributed file hash against
the original source. All passed. Original source bytes were unchanged afterward.
Two verification receipts for the same bundle were byte-identical. The full
owner receipt contains distributed-file commitments and stays private; only
aggregate compatibility counts are published here; custody metadata is not.

No new schema fields were needed to admit the export. Checks were strengthened,
not bypassed. Accepted result bodies are now retained as well as the final
submission, unknown submission/error payload fields fail closed, and acceptances
must match the source final exactly. All returned scientific results are retained.
Rejected submission arguments and host-chain metadata remain explicitly withheld
from reviewer projections; validation feedback is preserved. Original source bytes
remain authoritative and unchanged. Host-chain authenticity was not independently
recertified from the separate original transcripts in this task.

## Reviewer experience and blinding

Both reviewer bundles retain the same original IDs and evidence in separately
shuffled order. All blank grades remain null and attestations false. Summaries
show each proposition alongside its submitted finding, citation IDs, premises,
gaps and next evidence, followed by the governing model, initial readings, receipt
index and full authoritative projection. Noncompleted assessments have an explicit
NO FINAL SUBMISSION heading and no invented finding.

Readable copies were checked automatically for all packets and manually inspected
for a representative accepted and noncompleted packet. This is a presentation/
completeness check, not a scientific assessment. Reviewers can use one item form
at a time, work in batches and return an attestation only when finished. Assembly
refuses wrong roles, missing/duplicate packets and invalid/incomplete judgments.

Schema/text checks found no intervention-identity/reference-answer metadata in the
projected export. Initial investigator instructions were identical within each of
the seven public cases across its captured conditions. Public case/model IDs remain
legitimate context. Model style, citations and repeated cases can still suggest a
condition: neither automated screening nor random order proves perfect blinding.
The owner must inspect all distributed files and disclose or quarantine concerns.

Equal grades can conceal disagreement in meaning. The adjudicator must check
narratives, record material same-grade issues in `narrative_notes`, and resolve
flagged grade differences without editing either original independent form.
Independent verdict tallies and adjudicated tallies are now correctly separated.

## Offline regression results

- **36 semantic-review regression tests passed**.
- Extended public repository + research suite: **754 passed, 2 skipped, 14 subtests
  passed** (Python 3.12; final run 38.50 seconds).
- Skips: opt-in local Chromium saved-investigation check and native macOS/APFS
  surface check. Neither was claimed executed on this Linux host.
- Ruff formatting/lint, byte-compilation, CLI help and whitespace checks passed.
- Public text sources were restored from PR #35 at
  `7d544a0ed82ed11f6ceeba9ac6b6c8a7609a21e4`; the unchanged Sprint C research/test
  additions were restored separately from PR #34 at
  `66de37ce7e645f2fc98244dd4d38fcf9ce0ee128` for extended testing. Restored files
  were verified against their upstream Git blob hashes. Only semantic-review
  changes are proposed in this PR; the study checkout/journal was not migrated.
- Existing fixture tests require a local Git HEAD. Cross-test imports require
  `PYTHONPATH=.:tests` with importlib collection for duplicate legacy module names.
  Initial collection/bootstrap failures were resolved by correcting the test
  workspace, not by changing the frozen study tests or weakening checks.

Reproduce review tests without extra runtime dependencies:

```bash
python -m unittest discover -s tests -p test_semantic_review_workflow.py -v
python -m compileall -q research/semantic_review scripts/semantic_review.py
python scripts/semantic_review.py --help
```

If PR #34's unchanged source is present in a separate test workspace:

```bash
PYTHONPATH=.:tests python -m pytest -q -rs tests research --import-mode=importlib
```

See `OWNER_RUNBOOK_MACOS.md` for exact original-file preparation and verification
commands; no private answer key is required.

## Contract and score preservation

Review-only version: `sprint-c-human-semantic-review-v2`. Existing v1 bundles and
source exports are not rewritten. Future distribution uses a fresh v2 directory.
The original frozen rubric remains byte-identical to Git blob
`39c559ec0686ef00a7c936142485d75b0ee32780`.

The original **29 mechanical + 20 frozen-reference atomic + 51 human semantic**
weights, penalties, recall conditions and abstention cap are unchanged. Independent
human verdicts are diagnostic findings, not replacement reference labels. This
workflow leaves combined /100 scores null rather than silently impersonating the
original private evaluator. Owner-side fraction import requires confirming the
answer-free scorer interface after review; no key or unblinding access is needed
for preparation, collection, agreement or sealing.

## Remaining limitations and recommendation

**Ready for owner review and merge consideration, then controlled distribution.**
Do not merge automatically. Technical preparation now works on the actual export;
scientific independence still requires qualified distinct humans, conflict checks,
all-file owner leakage inspection and blinded adjudication. No packet has been
sent on the owner's behalf and no scientific benefit is established by these tests.

Native macOS/APFS behavior and opt-in Chromium were not executed here. The expected
hash relies on the owner's prior verified custody, not a new independent archive
certification. File seals are consistency commitments, not physical certification
or signatures resisting an attacker rewriting all local files. The private scorer
import schema still needs owner confirmation before a post-review combined score.
