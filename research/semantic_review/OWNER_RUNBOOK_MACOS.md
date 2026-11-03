# Owner handoff — macOS, offline only

**Owner-only instructions. Do not send this document or study results to reviewers.**
No paid call, rerun, key, hidden sensor vault or unblinding map is needed. Work on a
copy of the review software; leave the original study checkout and export alone.

## 1. Locate the existing verified packet export

Use the owner's already verified Sprint C snapshot/local export. Locate its
existing `blinded-review-packets.private.json` and adjacent `FILE_MANIFEST.json`
using the owner's existing certified score index. Do not regenerate exports/IDs
with the scorer. The correct export contains 70 packets and 64 accepted final
submissions; an older export contains only 42 packets. Preparation refuses that
older export rather than silently reducing coverage.

Prefer the existing verified extracted copy. If unavailable, use the owner's
private recovery inventory to locate the archive, then extract only its exact
blinded packet member and manifests into private storage. Exact archive/member
paths and historical hashes belong in the owner's private custody receipt, not
this public runbook. Never give the entire archive or its private index to reviewers.

Use Python 3.10+ (tested here with 3.12). The review CLI needs only the standard
library. In your repository, create a separate worktree:

```bash
git fetch origin
git worktree add ../petromind-semantic-review \
  origin/research/sprint-c-semantic-review
cd ../petromind-semantic-review
umask 077
export REVIEW_PRIVATE="$HOME/PetroMind-private-semantic-review-v2"
mkdir -p "$REVIEW_PRIVATE"
chmod 700 "$REVIEW_PRIVATE"
export SPRINT_C_REVIEW_PACKETS=/absolute/path/to/your/verified-score-export/blinded-review-packets.private.json
export SPRINT_C_REVIEW_OUT="$REVIEW_PRIVATE/bundle-v2"
```

Keep the review software pinned once distributed. If a v1 review already started,
keep its original code/bundle; do not mix v1 and v2 forms or silently migrate it.

## 2. Read the prior SHA-256 commitment

Read only the existing manifest's packet entry, not scores or mapping files:

```bash
export SPRINT_C_PACKET_SHA256="$(python - <<'PY'
import json, os
from pathlib import Path
p = Path(os.environ['SPRINT_C_REVIEW_PACKETS'])
m = json.loads((p.parent / 'FILE_MANIFEST.json').read_text())
print(m['blinded-review-packets.private.json'])
PY
)"
shasum -a 256 "$SPRINT_C_REVIEW_PACKETS"
printf '%s\n' "$SPRINT_C_PACKET_SHA256"
```

Both must match the packet commitment in the owner's prior verified certificate
and manifest. Exact custody hashes remain private. A newly computed hash alone is
not historical authentication. If the certified export differs, stop and resolve
custody; do not edit inputs or replace the prior commitment with a new one.

## 3. Prepare and verify both private bundles

```bash
python scripts/semantic_review.py prepare \
  --packets "$SPRINT_C_REVIEW_PACKETS" \
  --expected-sha256 "$SPRINT_C_PACKET_SHA256" \
  --out "$SPRINT_C_REVIEW_OUT"
python scripts/semantic_review.py verify \
  --bundle "$SPRINT_C_REVIEW_OUT" \
  --packets "$SPRINT_C_REVIEW_PACKETS" \
  --expected-sha256 "$SPRINT_C_PACKET_SHA256" \
  --receipt "$REVIEW_PRIVATE/compatibility-v2.json"
```

Expect 70 packets, 64 accepted submissions, six without final submissions, 228
propositions and 434 tool results. Each role has 70 readable packets and 70 blank
item forms. `verify` compares the source, projections, results, accepted assessments,
blank forms, ordering and distributed bytes. Repeating it against the same bundle
with a NEW receipt filename produces byte-identical receipts. New preparations
randomize order using a recorded seed, so different bundles need not have identical
order/file hashes; source identities and scientific content stay fixed.

Commands refuse to overwrite. If preparation is interrupted, retain the partial
output and restart in a NEW directory. Do not delete locks, patch manifests or
reuse an output containing partial files. Validation/verification is read-only
except for a requested NEW receipt. Code changes require a fresh versioned bundle.

## 4. Inspect before distribution

Open `R-A/PACKET_INDEX.md` in a local Markdown viewer (no AI extension). Inspect
all 70 derived packets in both roles, not only one example:

- The same original 70 blind IDs occur in both roles, in separately shuffled order.
- Every packet clearly says accepted final submission or no final submission.
- The proposition, submitted finding, citations, governing model, initial readings
  and tool receipts are discoverable. Complete received content is retained below.
- No variant/intervention identity, reference answer, score, private evaluator path,
  provider/accounting identity or unblinding-map content appears.
- Public synthetic case/model IDs and physical rules are legitimate evidence;
  they are not target labels. Style and repeated cases can still compromise blinding.
- Returned validation feedback remains visible. Rejected argument bodies and host
  chain hashes are withheld; accepted assessment results are retained verbatim.

Schema/text screening is not proof of perfect blinding. If a hint or unknown field
is found, stop and document it privately. Do not silently edit findings, strip
scientific evidence, weaken screening or distribute a knowingly compromised bundle.
Re-run `verify` immediately before distribution. Keep owner receipts private.

## 5. Send exactly one folder to each reviewer

Appoint two distinct qualified humans and a third qualified adjudicator. Keep
names, credentials, conflicts and eligibility in a separate owner-only register.

- Reviewer A receives **only `R-A/`**.
- Reviewer B receives **only `R-B/`**.
- Neither receives `owner/`, the sibling folder, this runbook, study results, prompts,
  original archives, scores, keys or the unblinding map.

Use your approved private transfer channel. Optional private archives:

```bash
tar -czf "$REVIEW_PRIVATE/reviewer-A-v2.tar.gz" -C "$SPRINT_C_REVIEW_OUT" R-A
tar -czf "$REVIEW_PRIVATE/reviewer-B-v2.tar.gz" -C "$SPRINT_C_REVIEW_OUT" R-B
```

The software does not send anything. Do not publish these archives in GitHub or a
public link. Reviewers must not collaborate or consult AI for scientific grades.

## 6. Collect independent human forms

Recommended: reviewers copy `item-*.json` into a separate working directory, complete
all 70, and return those files plus their completed `human-attestation.json`.
They can work in batches without editing a 70-packet JSON document. The owner can
check an individual completed item without giving scientific feedback:

```bash
python scripts/semantic_review.py validate-item \
  --bundle "$SPRINT_C_REVIEW_OUT" --role R-A \
  --form "$REVIEW_PRIVATE/returns-A/item-001.json"
```

After every item is independently completed and the attestation is truthful:

```bash
python scripts/semantic_review.py assemble \
  --bundle "$SPRINT_C_REVIEW_OUT" --role R-A \
  --items "$REVIEW_PRIVATE/returns-A" \
  --attestation "$REVIEW_PRIVATE/returns-A/human-attestation.json" \
  --out "$REVIEW_PRIVATE/completed-R-A.json"
python scripts/semantic_review.py assemble \
  --bundle "$SPRINT_C_REVIEW_OUT" --role R-B \
  --items "$REVIEW_PRIVATE/returns-B" \
  --attestation "$REVIEW_PRIVATE/returns-B/human-attestation.json" \
  --out "$REVIEW_PRIVATE/completed-R-B.json"
```

Alternatively accept one newly saved, completed `review-form.json` per reviewer
as `completed-R-A.json` / `completed-R-B.json`; do not assemble duplicate formats.
No automated step fills judgments. Missing finals receive unassessed semantics,
not invented findings or successful abstentions. Original scoring treatment remains.

## 7. Validate and lock both independent returns

```bash
python scripts/semantic_review.py validate --bundle "$SPRINT_C_REVIEW_OUT" \
  --role R-A --form "$REVIEW_PRIVATE/completed-R-A.json"
python scripts/semantic_review.py validate --bundle "$SPRINT_C_REVIEW_OUT" \
  --role R-B --form "$REVIEW_PRIVATE/completed-R-B.json"
shasum -a 256 "$REVIEW_PRIVATE/completed-R-A.json" "$REVIEW_PRIVATE/completed-R-B.json"
```

Lock/preserve these files before discussion. Validation checks format, received
pointers, coverage and attestations; it cannot certify human credentials or truth.
Actual key/variant exposure requires documented quarantine/reassignment, not a
false independence attestation. Do not alter scientific answers to pass validation.

## 8. Calculate agreement before adjudication

```bash
python scripts/semantic_review.py compare --bundle "$SPRINT_C_REVIEW_OUT" \
  --a "$REVIEW_PRIVATE/completed-R-A.json" \
  --b "$REVIEW_PRIVATE/completed-R-B.json" \
  --out "$REVIEW_PRIVATE/comparison-v2"
```

Keep raw agreement, nominal verdict kappa, linear-weighted fraction kappa, exclusions
and marginals. N/A/noncompletion is excluded explicitly; degenerate kappa is null.
Correlated cases/repeats do not support independent-sample confidence claims.

## 9. Conduct still-blinded adjudication

Give R-C the locked forms, received-evidence packets and comparison files only.
Do not give variant identities, reference answers or mechanical scores. R-C saves a
NEW completed copy of `adjudication.template.json` as `adjudication-complete.json`.
Every flagged difference requires an admissible resolution, evidence pointer and
rationale. Also inspect equal-grade narratives for material semantic disagreements;
R-C must attest `equal_grade_narratives_checked` and record material equal-grade
prose disagreements in `narrative_notes` with a review ID, evidence pointers and
rationale. Matching grades do not prove
agreement in reasoning. Do not average disagreements or rewrite original reviews.

## 10. Seal before any unblinding

```bash
python scripts/semantic_review.py finalize --bundle "$SPRINT_C_REVIEW_OUT" \
  --a "$REVIEW_PRIVATE/completed-R-A.json" \
  --b "$REVIEW_PRIVATE/completed-R-B.json" \
  --adjudication "$REVIEW_PRIVATE/adjudication-complete.json" \
  --out "$REVIEW_PRIVATE/sealed-v2"
```

Keep `seal.json`, both original review bytes, adjudication, fractions and reports.
Independent tallies and adjudicated tallies are separate. Unassessed semantic
subtotals stay null; known points are not rescaled. A process seal is not physical
certification or a digital signature against an attacker rewriting all local files.

Only **after** complete review and adjudication may the owner join by original
blind ID, privately, with the original map/scorer. Preserve the frozen 29 mechanical
+ 20 reference-atomic + 51 human points, penalties and abstention cap. This CLI
never opens the map or invents a combined /100 score. Keep primary/secondary/repeat
and original matched/all-planned denominators separate. Check the answer-free
private scorer import schema before bridging fractions; do not request/share answers.

## Reproducible offline checks

```bash
python -m unittest discover -s tests -p test_semantic_review_workflow.py -v
python -m pytest -q
```

The extended validation also read PR #34's pinned public research source in a
separate test workspace. If that source is present, all research tests can run with:

```bash
PYTHONPATH=.:tests python -m pytest -q -rs tests research --import-mode=importlib
```

`PYTHONPATH` preserves existing tests' cross-imports; importlib avoids duplicate
legacy test-module names. Never move the active study checkout or initialize a
study/accounting database just to run review tests. A real macOS/APFS check and an
opt-in local Chromium test may have platform-specific requirements. No live calls
or actual private evaluator package is required for these fixture tests.
