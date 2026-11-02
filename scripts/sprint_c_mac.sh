#!/bin/bash
# Run from the reviewed repository root. No secret is saved by this script.
set -euo pipefail
umask 077
test "$(uname -s)" = Darwin || { echo 'Use your trusted Mac.' >&2; exit 1; }
PM_ROOT="$HOME/Library/Application Support/PetroMindSprintC"
PM_PACKAGE="$PM_ROOT/preserved/PetroMind-Sprint-C-PRIVATE"
PM_PRIVATE="$PM_ROOT/evaluator/private_sprint_b"
PM_DB="$PM_ROOT/continuation/continuation.sqlite"
PM_RUN="$PM_ROOT/continuation/run"
PM_CERT="$PM_ROOT/storage-check/certificate.json"
PM_PYTHON="$PWD/.venv/bin/python"
test -x "$PM_PYTHON"
cli() { "$PM_PYTHON" scripts/recover_sprint_c.py "$@"; }
case "${1:-}" in
  prepare)
    cli prepare --archive "${2:-$HOME/Downloads/PetroMind-Sprint-C-Recovery-LOCAL-PRIVATE.tar.gz}" --directory "$PM_ROOT"
    cli storage-check --directory "$PM_ROOT/storage-check" --owner-local
    echo "Inspect $PM_ROOT/proposal.json and research/sprint_c/recovery/INVESTIGATION.md before approval."
    ;;
  approve)
    test -n "${2:-}" || { echo 'Supply your name as the second argument.' >&2; exit 1; }
    cli review --proposal "$PM_ROOT/proposal.json" --accept-proposal-id b51a6501e191516e2fbf7324b00680a48e1ed2e5ad9ac59ac5fee6ef7f2fcd11 --owner "$2" --db "$PM_DB" --out "$PM_ROOT/owner-review.json"
    cli init --owner-local --package "$PM_PACKAGE" --proposal "$PM_ROOT/proposal.json" --review "$PM_ROOT/owner-review.json" --certificate "$PM_CERT" --db "$PM_DB"
    ;;
  run)
    # A subshell and EXIT trap also clear the environment on errors/interruption.
    (
      trap 'unset MODEL_API_KEY' EXIT
      IFS= read -r -s -p 'Meta API key (hidden): ' MODEL_API_KEY
      echo
      export MODEL_API_KEY
      cli run --owner-local --package "$PM_PACKAGE" --proposal "$PM_ROOT/proposal.json" --review "$PM_ROOT/owner-review.json" --certificate "$PM_CERT" --db "$PM_DB" --plan "$PM_ROOT/remaining-cells.json" --out "$PM_RUN" --private-root "$PM_PRIVATE"
    )
    ;;
  score)
    cli audit --package "$PM_PACKAGE" --out "$PM_RUN" --db "$PM_DB" --proposal "$PM_ROOT/proposal.json" --review "$PM_ROOT/owner-review.json" --certificate "$PM_CERT"
    cli score --package "$PM_PACKAGE" --out "$PM_RUN" --db "$PM_DB" --proposal "$PM_ROOT/proposal.json" --review "$PM_ROOT/owner-review.json" --private-root "$PM_PRIVATE" --destination "$PM_ROOT/final-comparison"
    ;;
  export)
    cli export --package "$PM_PACKAGE" --out "$PM_RUN" --db "$PM_DB" --proposal "$PM_ROOT/proposal.json" --review "$PM_ROOT/owner-review.json" --certificate "$PM_CERT" --destination "$PM_ROOT/final-export"
    ;;
  *) echo 'Usage: bash scripts/sprint_c_mac.sh prepare [archive] | approve "Your name" | run | score | export' >&2;exit 2 ;;
esac
