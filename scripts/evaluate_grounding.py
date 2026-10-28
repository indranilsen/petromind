#!/usr/bin/env python3
"""Offline knowledge/availability/retrieval study. No Meta API client is invoked."""
from pathlib import Path
import sys
import argparse
import json
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from petromind.grounding_offline import audit_pilot_archive, benchmark
from petromind.knowledge import PhysicalKnowledge


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    audit = commands.add_parser('trace-audit')
    audit.add_argument('--archive', type=Path, required=True)
    run = commands.add_parser('benchmark')
    run.add_argument('--dataset', type=Path, required=True)
    run.add_argument('--cohort-from', type=Path, required=True)
    run.add_argument('--out', type=Path, required=True)
    commands.add_parser('knowledge')
    args = parser.parse_args(argv)
    if args.command == 'trace-audit':
        result = audit_pilot_archive(args.archive)
    elif args.command == 'knowledge':
        result = PhysicalKnowledge().graph()
    else:
        result = benchmark(args.dataset, json.loads(args.cohort_from.read_text()), args.out)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
