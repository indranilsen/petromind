# Sprint C: independent semantic review preparation

**Research-only. No paid calls, experiments, unblinding, production changes or
self-certified human scores.** This is a separate offline collection/aggregation
process. It never imports the Sprint C execution/scoring/accounting code and has
no evaluator-key or unblinding-map argument.

## Sources reviewed and access limitation

Prepared against PR #34 at **66de37ce7e645f2fc98244dd4d38fcf9ce0ee128**, including
`phase2/RESULTS.md`, `FAILURE_ANALYSIS.md`, `phase2/scoring.py`, the public synthetic
adapter/submission and evidence-provenance contracts, public M1 model/document
scopes, and the unchanged `synthetic-physics-v1.1` rubric. The executed source
remains **143928d0e4ea789f82ec3bdf091c66e06a2784a2**. Do not migrate its active
checkout or journal to this PR. #34 remains separate and unmerged.

The report says 70 declared cells, 64 completed final assessments, five output-
token-limit failures and one preserved interruption. Primary, secondary and repeat
cohorts remain separate. It reports literal citation gains and fewer incorrect
contradictions on some matched subsets, **not demonstrated semantic entailment**.
V3's extra advantage over V1 did not consistently replicate. This handbook does
not tell reviewers those identities or outcomes.

## Integration-readiness update

The actual **70-packet** export was securely accessed from the owner's preserved
snapshot. Only its blinded packet member, score-index metadata and manifest
commitments were opened. No answer key, hidden sensor vault, reference scores or
unblinding map was read/extracted. The selected export has 64 accepted submissions
and six noncompleted packets. An older 42-packet export was identified and not used.

Both score-export and outer snapshot commitments match the packet file.
Exact custody hashes and storage paths are retained only in the private owner receipts.
All initial evidence, **434 returned tool results**, **228 atomic propositions**
and final accepted submissions were preserved in both derived reviewer bundles.
No semantic scores were created. See `VALIDATION.md` for the actual checks and
limitations; `OWNER_RUNBOOK_MACOS.md` is the shortest owner handoff.

The review-only contract is now **sprint-c-human-semantic-review-v2**. It adds
accepted-result consistency checks, preservation verification, readable packet
summaries, optional per-packet forms and stricter custody checks. Frozen scoring
weights, definitions and original study artifacts are unchanged. Do not migrate
any in-progress v1 review: retain its pinned code and original bundle. V2 requires
a fresh output directory before distribution, never an in-place rewrite.

## Files

- `REVIEWER_HANDBOOK.md`: qualifications, independent verdict/entailment grading,
  calibration/scope discipline and neutral teaching examples (not case answers).
- `RUBRIC_MAPPING.md`: all frozen points, diagnostic-question mapping and penalties.
- `FROZEN_RUBRIC.md`: exact original public rubric snapshot. Git blob
  `39c559ec0686ef00a7c936142485d75b0ee32780` is verified before preparation.
- `workflow.py` + `scripts/semantic_review.py`: projection, preservation verification, blank forms,
  completeness checks, Cohen's kappa, disagreements, adjudication and process seal.

No real packet or completed form belongs in Git. Preserve all output in private
owner storage, separately from original Sprint C execution artifacts.

## Owner custody and separation

1. Appoint two qualified, distinct human reviewers and a distinct adjudicator.
   Ideally combine process/production engineering and independent hydraulic/
   uncertainty expertise. Keep real identities, qualifications, conflicts and
   prior familiarity in an owner-only register. Forms use R-A/R-B/R-C only.
   The study author/LLM is not a substitute independent reviewer.
2. Keep the evaluator/key, variant/cohort map, original scores, intervention
   prompts and results reports with the owner. Do not distribute them or ask
   reviewers to inspect the repository. The public model and received evidence
   are already embedded in each packet; no hidden sensor vault is needed.
3. Prepare in a **separate checkout/worktree**. All commands below read original
   packets; they do not open the accounting database, rerun scorers or invoke Meta.
4. Inspect the derived bundles for residual identity hints, private metadata and
   usability **before distribution**. Schema/text scanning is conservative, not
   proof of blinding. If it refuses data, investigate privately; do not disable
   screening, auto-rewrite model findings or edit the original export to pass.
5. Reviewer allocations randomize order separately while retaining the original
   random blind IDs. Both reviewers assess every packet. Repeats may be recognizable;
   style can suggest conditions. Record limitations; do not treat order randomization
   as proof that blinding or independence is perfect.

## Exact preparation commands

Use a separate research checkout, not the pinned active execution worktree:

```bash
git fetch origin
git worktree add ../petromind-semantic-review \
  origin/research/sprint-c-semantic-review
cd ../petromind-semantic-review
```

From the existing **verified current** score export, use its existing
`blinded-review-packets.private.json`. The current `phase2/scores/index-*.json`
identifies the committed score directory; do not choose an older export simply
because its filename matches. Consult the verified owner certificate/manifest.
This tool does not need or read `reviewer-unblinding.private.json`.

Set owner-side paths (these are placeholders, not new exports):

```bash
export SPRINT_C_REVIEW_PACKETS=/absolute/path/to/verified/score-export/blinded-review-packets.private.json
export SPRINT_C_REVIEW_OUT=/absolute/private/path/semantic-review-v1
export SPRINT_C_PACKET_SHA256=the_existing_64_character_packet_hash_from_the_verified_FILE_MANIFEST

python scripts/semantic_review.py prepare \
  --packets "$SPRINT_C_REVIEW_PACKETS" \
  --expected-sha256 "$SPRINT_C_PACKET_SHA256" \
  --out "$SPRINT_C_REVIEW_OUT"
```

The expected hash must be that packet file's entry in the **previously verified**
manifest, not the archive SHA or a new self-authentication claim. The existing
score-package manifest is a JSON relative-path → SHA-256 mapping. If desired,
read ONLY its packet entry locally, without opening any evaluator or map:

```bash
python - <<'PY'
import json, os
from pathlib import Path
p = Path(os.environ['SPRINT_C_REVIEW_PACKETS'])
m = json.loads((p.parent / 'FILE_MANIFEST.json').read_text())
print(m['blinded-review-packets.private.json'])
PY
```

Verify the directory is the certified export before using that value. Preparation
requires exactly 70 unique existing IDs and refuses overwrite, mismatched hashes,
unknown packet fields, visible variant/reference metadata and prior semantic grades.
The review code/CLI, handbook, distributed bytes and scoring constants are pinned
in the new owner manifest before grading. A code change requires a fresh versioned
review bundle; no review-process definitions are changed after seeing grades.
It creates **new** projections only. Received evidence/final findings are retained;
host hashes/execution metadata and rejected submission bodies are omitted from
reviewer copies. The original packet file is unchanged and committed by hash.
Any real-data contract mismatch needs owner inspection; fixture success alone
cannot certify compatibility with all private packets.

## Distribute and collect

Give reviewer A **only** `$SPRINT_C_REVIEW_OUT/R-A/` and reviewer B **only**
`$SPRINT_C_REVIEW_OUT/R-B/`. Each contains 70 readable Markdown packets,
`packets.json`, the handbook/mapping/frozen rubric, `PACKET_INDEX.md`, its own blank
`review-form.json`, 70 individual `item-NNN.json` forms and a blank human attestation. Do not distribute the sibling folder or `owner/` manifest,
raw study archive, model prompts, key, scores or unblinding map. Use an approved
private channel; this tool sends nothing.

Reviewers save NEW completed files such as `completed-R-A.json` and
`completed-R-B.json`. Do not overwrite original distributed blanks: their hashes
are frozen. No collaboration before both independent forms are returned and
locked. Tell reviewers to notify the owner of missing context, disqualification
or actual identity/key exposure; do not "repair" their scientific answers.

Validate each returned file without reference answers:

```bash
python scripts/semantic_review.py validate --bundle "$SPRINT_C_REVIEW_OUT" \
  --role R-A --form /private/returns/completed-R-A.json
python scripts/semantic_review.py validate --bundle "$SPRINT_C_REVIEW_OUT" \
  --role R-B --form /private/returns/completed-R-B.json
python scripts/semantic_review.py compare --bundle "$SPRINT_C_REVIEW_OUT" \
  --a /private/returns/completed-R-A.json \
  --b /private/returns/completed-R-B.json \
  --out /private/review-comparison-v1
```

The validator checks coverage, fixed inputs, evidence pointer existence, permitted
fractions, rationales and human attestations. It cannot certify qualifications,
truthfulness, entailment, or distinguish AI prose from human prose.

## Disagreement/adjudication

`compare` creates the blinded agreement report, exact disagreement fields and an
`adjudication.template.json`. Give the still-blinded adjudicator both locked
reviews, received-evidence bundles and disagreement list, **not** the variant map,
reference answers, mechanical scores or results reports. Independent assessment
is complete before this discussion. Do not let reviewers retroactively overwrite
independent grades to make agreement look better.

The adjudicator must also check equal-grade narratives for material scientific disagreements and attest `equal_grade_narratives_checked`; matching numeric grades do not establish agreement in meaning. Record material same-grade prose disagreements in `narrative_notes`, which are preserved in the sealed adjudication. The adjudicator may choose either rating or a third admissible rating, but must
resolve every conflicting grade/interpretation/flag or penalty event with a
receipt pointer and rationale. No automatic averaging or half-credit compromise.
Review penalty event identity carefully; semantically duplicate errors must count
once per category even if reviewers used different error IDs. Material prose
conflicts that happen to have equal grades still need human inspection; the
software cannot detect all such disagreements. Confirmed blinding breaches
require documented quarantine/reassignment and preservation of the original form,
not a falsely independent attestation. Report suspected/style-based concerns.

Save NEW `/private/adjudication-complete.json`, then:

```bash
python scripts/semantic_review.py finalize --bundle "$SPRINT_C_REVIEW_OUT" \
  --a /private/returns/completed-R-A.json \
  --b /private/returns/completed-R-B.json \
  --adjudication /private/adjudication-complete.json \
  --out /private/sealed-semantic-review-v1
```

Finalization refuses incomplete adjudication, changed reviewer bytes, changed
packets or changed distributed materials. It preserves both original form bytes,
adjudicator records, resolved fields, fractions, pre-penalty semantic subtotals
and a hash seal. If resolved fields differ from R-A's prose, the adjudicator's
separate rationale is authoritative; neither original narrative is rewritten.
The seal certifies process/file consistency, **not physical truth**.

## Agreement and final reporting

- Preferred verdict: nominal Cohen's kappa and raw exact agreement, including
  UNDETERMINABLE as a review category. NO_SUBMISSION and N/A are excluded and counted.
- Fractions: exact agreement and **linear-weighted** Cohen's kappa on 0 / 0.5 / 1.
  N/A pairs are excluded with counts. Degenerate marginals yield null kappa,
  not an artificial perfect value. Report marginals and small denominators.
- Report atomic and packet-level agreement separately; do not treat all atoms,
  cases or repeated runs as independent samples. No significance test or naive
  confidence interval is produced. Reference disagreements/ambiguous wording are
  research findings, not permission to alter the frozen key.
- The 51-point human subtotal is incomplete if any dimension is N/A; known points
  are shown without rescaling. Missing final assessments are not semantically
  wrong prose or blanket abstentions. Keep their original end-to-end treatment.

**Only after both reviews and adjudication are sealed** may the owner join
`review-fractions.json` by existing blind review ID to the separate unblinding map
and original scorer exports. Do not regenerate IDs or rewrite scores. Keep primary,
secondary and repeat groups separate; reapply the exact pre-existing matched-case
sets and also retain all-planned denominators. Report semantic changes alongside,
not in place of, raw verdict and literal citation metrics. Audit blinding concerns
and reviewer exclusions in the final report.

This tool intentionally does not open that map or compute a new frozen /100 total.
The public contracts do not expose the private scorer's review-import field names.
The owner must verify that **interface/schema only**, without sharing answers,
then translate the eight named fractions exactly into the unchanged evaluator's
review format. Apply the existing 29 mechanical + 20 atomic-reference + 51 human
weights, original penalties and 40-point blanket-abstention cap. Preserve null
instead of inventing totals where inputs are missing. An additional owner bridge
needs that answer-free import contract; no private answer key is needed merely
to prepare/distribute/collect this review.

## Validation and owner workflow

See [VALIDATION.md](VALIDATION.md) for exact regression counts, real-export
compatibility and unresolved limitations. The reproducible `verify` command writes
an owner-only, hash-bound preservation receipt without filling any grades.

See [OWNER_RUNBOOK_MACOS.md](OWNER_RUNBOOK_MACOS.md) for preparation, verification,
private distribution, batch item forms, collection, agreement, adjudication and
sealing. Reviewers must receive only their assigned reviewer folder, never this
owner-facing runbook, validation results, study results or PR discussion.
