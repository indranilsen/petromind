#!/usr/bin/env python3
"""Source-checkout entry point for a bounded Muse investigation."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    try:
        from petromind.muse_cli import main
    except ModuleNotFoundError as exc:
        if exc.name != "httpx":
            raise
        raise SystemExit("Install Muse dependencies: python -m pip install -e '.[agent]'") from None
    raise SystemExit(main())
