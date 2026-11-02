#!/bin/bash
# Research phase with the proposed $30 maximum; explicit owner-local authorization required.
set -euo pipefail
umask 077
test "$(uname -s)" = Darwin || { echo 'Run on your validated Mac.' >&2; exit 1; }
PM_PYTHON="$PWD/.venv/bin/python"
test -x "$PM_PYTHON"
PM_ACTION="${1:-}"
case "$PM_ACTION" in
  run|resume)
    (
      trap 'unset MODEL_API_KEY' EXIT
      IFS= read -r -s -p 'Meta API key (hidden): ' MODEL_API_KEY
      echo
      export MODEL_API_KEY
      "$PM_PYTHON" scripts/sprint_c_phase2.py "$@"
    ) ;;
  prepare|authorize|validate|score|report) "$PM_PYTHON" scripts/sprint_c_phase2.py "$@" ;;
  *) echo 'Usage: bash scripts/sprint_c_phase2_mac.sh prepare|authorize|validate|run|resume|score|report [options]' >&2;exit 2 ;;
esac
