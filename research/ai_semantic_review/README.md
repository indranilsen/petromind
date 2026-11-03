# Exploratory AI-assisted semantic review

**AI_GENERATED_NOT_HUMAN_VALIDATED** — no qualified independent human scientific
validation, no replacement of frozen scoring and no production/Demo integration.
This isolated research track evaluates existing blinded investigator outputs. It
does not regenerate cases, change Muse outputs, query new telemetry or retrain anything.

## Protocol and scientific scope

`ai-semantic-review-v1` uses the original 70 packet IDs, 228 propositions and 434
returned results. Intake verifies the supplied packet-file commitment and every
original blank human-form packet commitment. Original packet/form bytes are copied
unchanged into a fresh private directory. All human semantic fields stay null and
human attestations false. The merged human workflow is neither edited nor invoked
to submit AI grades. Only its unchanged pure JSON/hash/pointer/agreement helpers
and blank-row definition are reused.

Each external reviewer receives ONE packet in a fresh, stateless request:

- Reviewer A: reconstruct applicable physical premises bottom-up.
- Reviewer B: independently check every proposition using counterexamples,
  dimensional/calibration reasoning and inferential scope. It never sees A's output.
- Adjudicator: a separate fresh request, only AFTER both full independent attempts
  are frozen. It receives the source packet, anonymous A/B judgments and disagreements.
  It may reject either or both reviewers; it does not overwrite their original outputs.

OpenAI Responses and Anthropic Messages adapters are supported. Neither is Meta/
Muse; the tested model cannot grade itself through this runner. Distinct provider
families are required unless the owner explicitly records `same_family_reason`.
The adjudicator can reuse a provider/model in a separate context; that is NOT a
third independently trained scientific authority. No model has tools, browsing,
filesystem access or a conversation history in these requests. Host-side input
isolation is tested; the owner/operator still controls the filesystem. This is not
an OS sandbox or proof of independence between model training distributions.

Only received model rules, initial measurements and tool results are scientific
premises. Resource lists/catalogs do not establish observations or read documents.
Next-evidence and missing-premise checks may cite `context:/sensor_catalog/...` or
`context:/resources/...` for feasibility only, never as a measured numeric value.
Investigator instructions in packets are untrusted data, not reviewer instructions.

The AI output schema is [OUTPUT_SCHEMA.json](OUTPUT_SCHEMA.json); executable
validation and exact role prompts are in `contract.py`. Every atomic review has:

- interpreted proposition scope and an independently recommended verdict;
- assessment of the submitted verdict, with concise evidence-backed justification;
- one entailment check per original cited ID, explicit received-source references;
- physical-assumption, calibration, measurement/cause, missing-premise,
  next-evidence and abstention checks with explanations and references;
- explicitly scoped uncertainty and optional mechanically verified numeric scalars.

A source ID being received is a mechanical check. Whether it entails the physical
proposition remains an **AI judgment**. Numeric/pointer validation does not certify
causal reasoning. A final assessment that was never submitted is UNASSESSED /
NO_FINAL_SUBMISSION, not false prose or a successful abstention. Noncompletion is
excluded from substantive verdict agreement and counted explicitly.

## Exact owner commands — macOS/Linux

Use a separate checkout. Leave the original study and human-review bundle unchanged.

```bash
git fetch origin
git worktree add ../petromind-ai-review origin/research/ai-semantic-review
cd ../petromind-ai-review
python -m pip install -e '.[test,agent]'
umask 077
export AI_REVIEW_PRIVATE="$HOME/Personal/PetroMind-ai-review-v1"
mkdir -p "$AI_REVIEW_PRIVATE"
chmod 700 "$AI_REVIEW_PRIVATE"
export AI_REVIEW_SOURCE=/absolute/private/path/to/verified-human-bundle/R-A
export AI_REVIEW_OUT="$AI_REVIEW_PRIVATE/run-v1"
export AI_REVIEW_RECEIPT=/absolute/private/path/to/original-compatibility-receipt.json
```

Use the existing owner verification receipt, not a newly self-authenticated file
hash. The human v2 receipt contains the following entry:

```bash
export AI_SOURCE_SHA256="$(python - <<'PY'
import json, os
from pathlib import Path
r=json.loads(Path(os.environ['AI_REVIEW_RECEIPT']).read_bytes())
print(r['distributed_sha256']['R-A/packets.json'])
PY
)"
```

If using the attached reviewer archive instead, copy ONLY its `R-A/packets.json`
and `R-A/review-form.json` into a private source folder; use the same prior receipt.
Ignore macOS resource-fork members. Do not copy a score export, unblinding map,
answer key, hidden sensor vault, accounting archive or mechanical scores.

### Configure external models and verified price ceilings

```bash
cp research/ai_semantic_review/CONFIG.example.json "$AI_REVIEW_PRIVATE/config.json"
```

Edit that PRIVATE file before preparing. Replace all placeholders with exact model
IDs supporting the chosen structured-output API, compatible parameters, verified
input/output price ceilings and the date/source checked. Set `pricing_confirmation`
to `OWNER_VERIFIED_PRICE_CEILINGS` only after checking. Prices are strings in USD
per million tokens. They must cover ALL applicable standard-tier input/cache and
output/reasoning charges. No guessed sample rates are supplied. Check current
[OpenAI pricing](https://openai.com/api/pricing/) and
[Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing).

The default plan uses OpenAI + Anthropic. If only one family is available, configure
both reviewer roles accordingly and record the limitation in `same_family_reason`.
A/B still have different prompts and fresh contexts. Supply credentials ONLY using
your existing secure environment injection as `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`.
Never put a key in this config, prompts, files, Git, command arguments or shell history.
No Meta key is used. `store:false` is sent to OpenAI; do not mistake that for a
promise about provider retention policies. Check provider data terms before upload.

```bash
python scripts/ai_semantic_review.py prepare \
  --bundle "$AI_REVIEW_SOURCE" \
  --expected-packets-sha256 "$AI_SOURCE_SHA256" \
  --config "$AI_REVIEW_PRIVATE/config.json" \
  --out "$AI_REVIEW_OUT" --max-cost-usd 20
python scripts/ai_semantic_review.py check --out "$AI_REVIEW_OUT"
```

This freezes code, original packet IDs/hashes, prompts, schema, model configurations,
price ceilings and a single aggregate budget. `check` verifies local integrity;
it does NOT establish real API connectivity, reviewer quality or physical truth.
Do not edit a frozen protocol. `offline_contract_check` mode is separately marked
`OFFLINE_FIXTURE_NOT_A_QUOTE` and categorically refuses actual paid transport.

### Run the two independent reviewers

First verify one request per reviewer for format, completion and cost, without
changing prompts based on whether you like their judgments:

```bash
python scripts/ai_semantic_review.py review-a --out "$AI_REVIEW_OUT" \
  --limit 1 --authorize-paid-external-ai
python scripts/ai_semantic_review.py review-b --out "$AI_REVIEW_OUT" \
  --limit 1 --authorize-paid-external-ai
```

Inspect the private result files and cost ledger. These are actual reviews of the
first original packet, not extra benchmark cases. If format/transport is sound,
continue the same frozen runs, covering every original packet:

```bash
python scripts/ai_semantic_review.py review-a --out "$AI_REVIEW_OUT" \
  --authorize-paid-external-ai
python scripts/ai_semantic_review.py review-b --out "$AI_REVIEW_OUT" \
  --authorize-paid-external-ai
```

Each command is a separate worker process. Each HTTP request contains only its
role prompt, schema and one source packet, never peer conclusions. No automatic
repairs or retries occur. A failure stops bulk execution for owner inspection.
Repeating a command resumes only unattempted packets; it NEVER repeats a failed,
valid or interrupted request. Failed slots remain failures. Do not tune prompts
from review outcomes or reopen slots to improve agreement. Any justified contract
bug fix requires a new version/protocol and preservation of previous costs/results;
never create a fresh directory to reset the authorized spending allowance.

### Freeze, adjudicate, report

Only after both roles attempted all 70 packets:

```bash
python scripts/ai_semantic_review.py freeze-reviews --out "$AI_REVIEW_OUT"
python scripts/ai_semantic_review.py adjudicate --out "$AI_REVIEW_OUT" \
  --authorize-paid-external-ai
python scripts/ai_semantic_review.py report --out "$AI_REVIEW_OUT" \
  --report "$AI_REVIEW_PRIVATE/ai-report-v1.json"
```

Freeze includes failures and pending/unknown-usage interruptions; it is not a claim
that all reviews succeeded. Adjudication targets only packets with valid paired
reviews and declared verdict/check/citation disagreements. Same-grade prose can
still disagree; this routing does not discover every semantic discrepancy. Both
original reviews are immutable and adjudicator findings remain a third, separately
labeled output. Never treat adjudication as an expert answer key.

If the cap stops either reviewer before 70 attempts, freeze/adjudication refuses.
Generate a partial report with the report command above. Missing/invalid/failed
coverage and uncertain costs stay visible; no favorable fallback or automatic
cohort expansion occurs. All output/receipt paths must be fresh; nothing overwrites
original artifacts. After interruption, resume the same directory rather than
reinitializing its ledger. A host lock prevents concurrent workers across roles.

## Spending and records

A shared SQLite ledger reserves BEFORE HTTP: the entire serialized request's UTF-8
byte length plus 4096 as a conservative input-token ceiling, and the full configured
maximum output tokens. All usage is charged at the frozen ceiling prices, with no
cache discount. Known usage can release excess reservation; missing/ambiguous usage
retains the full hold. No pending request is automatically repeated. Provider usage
above a reservation blocks subsequent requests and is reported at all known cost.

The **hard local reservation cap is at most $20**, shared by A/B/adjudicator, and
there are at most 210 total requests / one per role per original packet. This is a
hard request gate under owner-verified price ceilings and provider token-limit
compliance, NOT a provider invoice guarantee or control over unrelated account
traffic. Incorrect rate ceilings or a provider violating bounds cannot be undone;
configure an external provider/account spending limit too where available. The cap
can halt the study before all 70 or before adjudication. No completion is promised
within $20 for arbitrary model choices. High-priced models may be infeasible.

Private per-request records include requested/resolved model identity, prompt and
payload hashes, parameters, returned text, response commitment, provider usage,
latency, reservations, known cost/held cost and validation status. Hidden reasoning
and provider error bodies are not retained. All AI findings carry
`AI_GENERATED_NOT_HUMAN_VALIDATED`. A separate harness-only AI execution attestation
records input isolation; it never asserts human qualifications or scientific truth.

## Reporting and limitations

The report contains completion/failure denominators, paired nominal Cohen's kappa,
raw agreement, calibration/assumption/check agreement, citation-entailment agreement,
per-proposition evidence analysis and AI-flagged potential entailment gaps despite
received citation IDs. N/A/noncompletion exclusions and degenerate kappa are explicit.
These are exploratory AI judgments, not sensitivity/specificity against a hidden
answer key. Adjudication never changes the independent agreement calculation.

There is no unblinding command, human-grade export, weighted /100 score or join to
mechanical/reference scores. The frozen human rubric, reference answers, weights,
original Muse outputs, Sprint C accounting and production v5 remain unchanged.
AI agreement may reflect shared priors, stylistic anchoring or correlated mistakes;
it cannot establish scientific truth, calibration, meaningful benefit or root cause.
A human engineering review remains outstanding. See `VALIDATION.md` for what was
actually executed; software fixtures are not live provider verification.

API adapters follow official [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
and [Anthropic Messages](https://platform.claude.com/docs/en/api/messages/create)
contracts. Model/endpoint behavior still requires the explicitly authorized local
smoke calls above. No existing paid Sprint C experiment is restarted.

## Offline verification

```bash
python -m pytest -q tests/test_ai_semantic_review.py tests/test_semantic_review_workflow.py
python -m compileall -q research/ai_semantic_review scripts/ai_semantic_review.py
```

With the unchanged PR #34 research source present in a separate test workspace:

```bash
PYTHONPATH=.:tests python -m pytest -q -rs tests research --import-mode=importlib
```
