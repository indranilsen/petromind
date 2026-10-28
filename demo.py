"""Legacy CLI entry point; --incident remains an optional evaluator-only input."""
from petromind.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
