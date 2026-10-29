#!/usr/bin/env python3
"""Launch an offline real-capture replay; live v2 requires separate explicit setup."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from petromind.claim_demo import DemoApp, freeze_live, make_server
from petromind.claim_review import review_capture


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("serve", "review", "prepare-live"):
        q = sub.add_parser(name)
        q.add_argument("--capture", type=Path, required=True)
        if name == "serve":
            q.add_argument("--port", type=int, default=8765)
            q.add_argument("--dataset", type=Path, default=Path("../3W/dataset"))
            q.add_argument(
                "--science-protocol",
                type=Path,
                default=Path(".petromind/science-m5-v1/protocol.json"),
            )
            q.add_argument(
                "--enable-live", type=Path, metavar="FRESH_PROTOCOL_DIRECTORY"
            )
        else:
            q.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    try:
        if a.command == "review":
            if a.out.exists():
                raise ValueError("Use a fresh review output file")
            a.out.parent.mkdir(parents=True, exist_ok=True)
            result = review_capture(a.capture)
            a.out.write_text(json.dumps(result, indent=2) + "\n")
            print(
                json.dumps(
                    {
                        "findings": len(result["findings"]),
                        "api_requests": 0,
                        "independent_engineering_review": False,
                    }
                )
            )
        elif a.command == "prepare-live":
            print(json.dumps(freeze_live(a.capture, a.out)))
        else:
            source = (
                json.loads(a.science_protocol.read_text())
                if a.dataset.is_dir() and a.science_protocol.is_file()
                else None
            )
            app = DemoApp(
                a.capture, a.enable_live, dataset=a.dataset, science_protocol=source
            )
            server = make_server(app, a.port)
            print(
                f"PetroMind: http://127.0.0.1:{server.server_port} — captured replay; live {'explicitly enabled' if a.enable_live else 'disabled'}",
                flush=True,
            )
            try:
                server.serve_forever()
            finally:
                server.server_close()
        return 0
    except (ValueError, OSError, KeyError, TypeError):
        print(
            json.dumps(
                {
                    "error": "demo_precondition_failed",
                    "instruction": "Use the unchanged reviewed claim-audit-v1 directory; see docs/claim-demo.md.",
                }
            )
        )
        return 2
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
