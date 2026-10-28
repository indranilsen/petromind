#!/usr/bin/env python3
"""Bounded M4 feasibility experiment, separate from all M3 outputs."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    try:
        from petromind.challenge_cli import main
    except ModuleNotFoundError as exc:
        if exc.name != "httpx":
            raise
        raise SystemExit("Install dependencies: python -m pip install -e '.[test,agent]'") from None
    raise SystemExit(main())
