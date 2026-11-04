# PR #38 final verification

Evidence requirements now prefer the recorded structured `next_evidence.purpose`.
Otherwise they quote the original missing premise in context, preserving negation,
conditions and unfamiliar terminology. Each displayed requirement names its source
finding; the original premise remains expandable when a structured request is used.
No free-text keyword is interpreted as a physical rule or proposed procedure.
An explicit `no_verified_discriminating_test` remains a limitation, including when
its purpose is absent. The exact accepted assessment and citations are unchanged.

The browser verifier checks the focused default, every full-graph node's original
details, exact received edge triples, disconnected entities, label bounds and font
size, real pointer-drag panning, zoom/reset, selected-finding focus/highlighting,
page overflow and Operator Console state after switching back. Desktop, tablet
and mobile use the same checks. One older CSS override forced graph type captions
to 8px; it now uses 10px. No graph library, inferred edges or topology were added.

Local validation includes the genuine original v1 captures and an explicitly
labeled synthetic UI layout fixture exceeding 48 entities. The latter extends
only in-memory software-test records, not saved files, model outputs or scientific
benchmarks. These checks do **not** verify the owner's actual saved-v5 artifacts.
Those artifacts and the complete monitoring bundle remain unavailable here.

## Owner's real saved-v5 check

Stop the demo server and run from a checkout containing the latest PR #38:

```bash
git fetch origin
git switch polish/operator-investigation-ux
git pull --ff-only origin polish/operator-investigation-ux
python -m pip install -e '.[test,agent,audit]' playwright
python -m playwright install chromium
```

The following paths must point to the owner's original capture, existing verified
saved replay and matching monitoring bundle. Do not regenerate those recordings.
The screenshot output directory must not already exist.

```bash
python scripts/verify_operator_experience.py \
  --capture "$HOME/Personal/petromind/.petromind/claim-audit-v1" \
  --saved-run "$HOME/Personal/petromind/.petromind/judge-v5-replay-v1" \
  --monitoring "$HOME/Personal/petromind/.petromind/monitoring-demo-v1" \
  --screenshots "/tmp/petromind-pr38-real-v5"
```

Success must report `status: passed`, `saved_v5: actual imported run`, zero paid
requests, zero JavaScript errors and unchanged exact outputs. Inspect the generated
desktop/mobile `finding`, `selected-evidence`, `full-graph` and `operator-complete`
screenshots. `full_graph_entities` reports each case/viewport's actual count; it is
not hardcoded to 48. This is an offline replay check and never enables live mode.

The focused fixes are ready for review. Complete this real-artifact check before
calling the owner's saved-v5 demonstration verified. No automatic merge.
