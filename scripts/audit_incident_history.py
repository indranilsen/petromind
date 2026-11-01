#!/usr/bin/env python3
"""Audit only the two frozen development incident histories. Never invokes Meta."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from petromind.history_audit import run_history_audit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--science-protocol", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--before-seconds", type=int, default=1800)
    p.add_argument("--after-seconds", type=int, default=1200)
    p.add_argument(
        "--export-local-fixture",
        action="store_true",
        help="Optional local-only numeric projection; NOT permission to upload or publish telemetry",
    )
    a = p.parse_args()
    try:
        source = json.loads(a.science_protocol.read_text())
        result = run_history_audit(
            a.capture,
            a.dataset,
            source,
            a.out,
            before_seconds=a.before_seconds,
            after_seconds=a.after_seconds,
            export=a.export_local_fixture,
        )
        print(json.dumps(result))
        return 0
    except (ValueError, OSError, KeyError, TypeError, StopIteration, ImportError):
        print(
            json.dumps(
                {
                    "status": "history_audit_precondition_failed",
                    "api_requests": 0,
                    "instruction": "Install .[test,agent,audit]; use the actual local dataset, unchanged capture and matching private protocol, and a fresh --out directory. No endpoint fallback or synthetic report is substituted.",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
