#!/usr/bin/env python3
"""Prepare a causal viewer replay from an exported local telemetry fixture. No API calls."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from petromind.monitoring_replay import prepare_monitoring


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--history-report", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    try:
        result = prepare_monitoring(a.capture, a.fixture, a.history_report, a.out)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(
            json.dumps(
                {
                    "status": "monitoring_precondition_failed",
                    "api_requests": 0,
                    "reason": str(error),
                    "instruction": "Use matching unchanged capture, exported fixture and private history report, plus a fresh --out.",
                }
            )
        )
        return 2
    print(
        json.dumps(
            {
                "status": "offline_monitoring_scored",
                "api_requests": 0,
                "cases": result["cases"],
                "out": str(a.out),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
