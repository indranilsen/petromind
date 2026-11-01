# Saved replay / investigation UX verification

Verified offline in Chromium at 1440×900 and 390×844:

- Original two captured cases: automatic event order, provenance, pause/resume,
  restart/skip, gated assessment and reduced motion. Viewer replay available here
  is captured endpoints, not a fresh verification of original raw data.
- Saved v5 import/replay: explicitly synthetic software runs with mocked Meta
  transport; no actual successful v5 run was present. Browser screenshots carry
  a synthetic-fixture banner. Tests do not stand in for verifying live007.
- Saved replay defaults, mode separation, case availability, focused graph (at most
  ten received nodes), full expansion, source inspector, finding focus, concise
  summary and no future finding reveal were exercised. No browser Meta requests.
- Original Home / Demo / Technology browser checks include seven mocked live HTTP
  requests, active-sensor and failure paths; no JavaScript errors.

Source verification tests cover completed v5 contracts, selected case/parent,
audit and trace agreement, numeric/citation/scope checks, sensor accounting,
explicit original-window binding for active queries (including missing readings),
source/projection hashes, invalid/incomplete/ambiguous/mismatched/tampered runs,
symlinks, changed source files, optional public stream verification, omitted
request disclosure, and CLI import/check with zero API calls. Rehashing a forged
fact/history cannot bypass the source catalog/training-snapshot checks.

The existing model prompts, tool definitions, v5 validator/aggregation,
DiagnosticSession budget, statistical classifier, anomaly monitor, experimental
protocols and original capture files were not changed. The importer calls the
unchanged v5 structural checks; it does not change or scientifically regrade the
recorded result. No paid model calls were made.

The full offline suite passes with 545 tests; the explicit Chromium saved-replay
check is opt-in and was also run locally (24 tests pass with it enabled). Screenshots
were visually inspected; synthetic versus genuine original captures are separated.
For exact commands to verify the real v5 run on the user's machine and the scope
of artifact verification, see [saved-v5-replay.md](saved-v5-replay.md).
