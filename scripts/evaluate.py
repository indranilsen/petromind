#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    try:
        from petromind.eval_cli import main
    except ModuleNotFoundError as exc:
        if exc.name != "httpx":
            raise
        raise SystemExit("Install evaluation dependencies: python -m pip install -e '.[test,agent]'") from None
    raise SystemExit(main())
