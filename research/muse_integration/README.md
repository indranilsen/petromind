# Controlled Muse investigation of the frozen synthetic challenge

This research-only runner integrates Sprint A's bounded Responses client with
Sprint B's unchanged owner-side JSON-lines trusted host. It does not use Sprint
A's benchmark importer, rewrite synthetic propositions, or import private answers
into the model session. Production UI, classifiers, v5 policies and captures are
unchanged.

## What B and E mean here

Both receive exactly one frozen case packet, including its case-local M1 physics,
time-series, uncertainty, initial charged sensors and atomic propositions. Both
have identical prompts and tool schemas: `query_sensor`, `lookup_graph(node)`,
`read_document(id)` and `submit_audit`. One-hop B retrieval is direct source-scoped
node lookup; two-hop E retrieval additionally follows the frozen connected graph.
The owner bridge supplies the fixed hop count; the model cannot override it.
Both retain provenance, epistemic status, scope and applicability on every edge.
No additional causal facts or measurements are invented by expansion.

This is a **synthetic adaptation** of A's variants, not a rerun of its exact-topic
3W knowledge importer. It isolates an offered retrieval-depth change. Resulting
context size, later query choices and measurement acquisition can differ; realized
trajectories are not controlled to be identical. The initial packet already gives
substantial M1 knowledge, limiting incremental headroom. Graph history references
can be returned under either condition; the historical-record tool is disabled in
both. Thus this B/E pair cannot isolate full historical-retrieval effects. Secondary
A/C/D conditions are not implemented or substituted for B/E coverage.

## Security boundary

Muse runs remotely as a text/function-call API. It receives no filesystem,
repository search, Python, shell, browser, generic network, arbitrary URL or
scorer tools. The local owner orchestrator can read private files; it is not the
model's runtime. The subprocess host reads one case-specific sensor vault and
receives a scrubbed environment without API credentials. It never reads the key.
Every context starts with one packet; there is no previous-response ID or shared
conversation. Only allowed serialized results return to Muse. Other cases,
unqueried measurements, private scores and reference answers never enter it.

Never attach this runner's owner filesystem to an additional autonomous agent
with file tools. The existing host is a transport, not an OS sandbox. Agentic
file access would require the separate UID/container boundary described in
Sprint B's integration guide. No such file tools are offered in these remote
API experiments.

The existing HTTP client retains the fixed `https://api.meta.ai/v1/responses`
endpoint, no redirects, no retries, bounded body/context size and explicit output
limits. The optional **owner-selected** `--platform-proxy` route uses workspace
HTTPS_PROXY and SSL_CERT_FILE with TLS verification. Their values are never
logged or supplied to Muse. It supports SOCKS or HTTP CONNECT because the hosted
workspace supplies these routes; direct transport remains the local default.
Install `httpx[socks]` if using the workspace SOCKS route. No vendor built-in
web/search tool is enabled. API keys come only from MODEL_API_KEY.

## Cumulative authorization, without resetting history

`IntegrationLedger` requires the original Session A budget directory. Its
`session.json` is retained byte for byte. A new `authorization-v2.json` records
the explicit cumulative $10 authorization and pins the old reservation prefix.
The same `reservations.jsonl` and `lock` are used; every old reservation still
counts. Legacy A runners also use that lock and cannot independently exceed
the upgraded total: their unchanged $5 limit can fail earlier. Do not run a new
copy with a different ledger or delete history to create spending capacity.
The demo's independent $2 cap is unchanged.

Each HTTP attempt first reserves 2 × serialized request bytes + 8,192 input
framing tokens plus all 4,096 possible output tokens at checked standard prices
($1.25/$4.25 per million). The reservation is hash-linked, locked, appended and
fsynced **before** HTTP. It is never released, including after errors or missing
usage. Limits are cumulative $10, 80 HTTP attempts and 327,680 reserved output
tokens; each cell has 8 turns, 24 function calls, 4 context calls and 360 seconds.
The host enforces five charged sensors and at most two submission repairs.
A client-side conservative estimate is not a provider-enforced invoice ceiling.
No provider billing/settings permission is available to this runner.

## Reproduce

Use the original ledger, or recover its **complete** saved checkpoint with the
private integration run archive. Never initialize an empty replacement to evade
prior spend. Recover and verify the private evaluator using Sprint B's
[guide](../synthetic_challenge/INTEGRATION_GUIDE.md). Do not use `python -O`.

```bash
python -m pip install -e '.[test,agent,experiments,audit]'
python -m pytest -q tests research/synthetic_challenge/tests research/synthetic_challenge/integration
python research/synthetic_challenge/integration/verify_readiness.py \
  --release-root research/synthetic_challenge \
  --private-root "$PM_PRIVATE_ROOT" --repo-root .
python research/synthetic_challenge/integration/offline_smoke.py \
  --release-root research/synthetic_challenge \
  --private-root "$PM_PRIVATE_ROOT" --out "$PM_OWNER_ROOT/offline-smoke-new"
python scripts/research_muse_integration.py prepare \
  --out "$PM_OWNER_ROOT/new-study-v2" --private-root "$PM_PRIVATE_ROOT" \
  --ledger-directory "$PM_ORIGINAL_SESSION_A_LEDGER"
```

Add `--platform-proxy` to **prepare** only if the owner runtime requires its
configured network proxy. The choice is frozen into the new protocol. Enter the
API key using a non-echoing terminal read (do not put it into this document):

```bash
read -rsp 'Meta API key: ' MODEL_API_KEY; echo
export MODEL_API_KEY
python scripts/research_muse_integration.py pilot \
  --out "$PM_OWNER_ROOT/new-study-v2" --private-root "$PM_PRIVATE_ROOT"
python scripts/research_muse_integration.py suite \
  --out "$PM_OWNER_ROOT/new-study-v2" --private-root "$PM_PRIVATE_ROOT"
unset MODEL_API_KEY
```

Only a fully completed paired pilot unlocks `suite`. The full suite repeats the
pilot case in fresh contexts, not as an additional independent sample. Attempt
records are exclusive by stage/case/variant: unknown interrupted attempts are
never silently replayed. A genuinely corrected implementation needs a new
protocol/directory, keeps all earlier attempts and uses the SAME ledger.
After every model session ends, score separately (no key is required):

```bash
python scripts/research_muse_integration.py score --stage pilot \
  --out "$PM_OWNER_ROOT/new-study-v2" --private-root "$PM_PRIVATE_ROOT"
python scripts/research_muse_integration.py score --stage suite \
  --out "$PM_OWNER_ROOT/new-study-v2" --private-root "$PM_PRIVATE_ROOT"
```

The frozen scorer's 29-point mechanical score does not certify its 71-point
semantic component. Missing cases are counted as missing by the full-suite
scorer, including during pilot scoring. Review packets have randomized IDs with
method identity kept in a separate owner-only unblinding file. Two independent
qualified reviewers should use the unchanged rubric and document adjudication.
Retrieval depth may be inferable from tool contents; blinding is not guaranteed.
No full 100-point score is issued without that review.

## Protocol history

The first integration v1 launch stopped before HTTP because its preflight only
allowed SOCKS while the workspace supplied HTTP CONNECT. It had zero requests
and zero reservations. The correction permits owner-configured CONNECT while
preserving endpoint restriction and verified TLS; a new v2 protocol was frozen
before any real response. The original blocked attempt/protocol are preserved.
No benchmark content, weights, answer key or production source changed.
