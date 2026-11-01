#!/usr/bin/env python3
"""Launch an offline real-capture replay; live v2 requires separate explicit setup."""

import argparse
import errno
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from petromind.claim_demo import DemoApp, freeze_live, make_server
from petromind.claim_review import review_capture


class DemoInputError(ValueError):
    def __init__(self, code, field, instruction):
        self.code, self.field, self.instruction = code, field, instruction
        super().__init__(code)


def check_files(args):
    for name in ("protocol.json", "results.jsonl"):
        if not (args.capture / name).is_file():
            raise DemoInputError(
                "missing_capture_file",
                "capture",
                "Supply the unchanged claim-audit-v1 capture containing protocol.json and results.jsonl; do not regenerate its results.",
            )
    if (
        args.command in ("serve", "check")
        and args.monitoring is not None
        and not (args.monitoring / "viewer.json").is_file()
    ):
        raise DemoInputError(
            "missing_monitoring_bundle",
            "monitoring",
            "Run scripts/prepare_monitoring_replay.py with your exported local-fixture and matching history report, then pass its output directory to --monitoring. See docs/hackathon-readiness.md.",
        )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("serve", "check", "review", "prepare-live"):
        q = sub.add_parser(name)
        q.add_argument("--capture", type=Path, required=True)
        if name in ("serve", "check"):
            q.add_argument("--port", type=int, default=8765)
            q.add_argument(
                "--monitoring",
                type=Path,
                help="Explicit local viewer-only monitoring bundle",
            )
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
            if name == "prepare-live":
                q.add_argument("--max-cost-usd", type=float, default=2)
                q.add_argument("--active-sensors", action="store_true")
                q.add_argument("--dataset", type=Path, default=Path("../3W/dataset"))
                q.add_argument(
                    "--science-protocol",
                    type=Path,
                    default=Path(".petromind/science-m5-v1/protocol.json"),
                )
    a = p.parse_args()
    try:
        check_files(a)
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
            source = (
                json.loads(a.science_protocol.read_text()) if a.active_sensors else None
            )
            print(
                json.dumps(
                    freeze_live(
                        a.capture,
                        a.out,
                        max_cost=a.max_cost_usd,
                        active_sensors=a.active_sensors,
                        dataset=a.dataset,
                        science_protocol=source,
                    )
                )
            )
        else:
            source = (
                json.loads(a.science_protocol.read_text())
                if a.dataset.is_dir() and a.science_protocol.is_file()
                else None
            )
            app = DemoApp(
                a.capture,
                a.enable_live,
                dataset=a.dataset,
                science_protocol=source,
                monitoring_directory=a.monitoring,
            )
            if a.command == "check":
                replays = [
                    {
                        "case": c["id"],
                        "mode": c["replay"]["mode"],
                        "positions": c["replay"]["workflow"]["positions"],
                    }
                    for c in app.cases
                ]
                print(
                    json.dumps(
                        {
                            "status": "demo_inputs_verified",
                            "api_requests": 0,
                            "complete_monitoring_available": all(
                                r["mode"] == "history" for r in replays
                            ),
                            "replays": replays,
                            "live_configured": a.enable_live is not None,
                            "credential_present": bool(
                                os.getenv("MODEL_API_KEY", "").strip()
                            ),
                            "scope": "Input validation only; browser behavior, paid Meta connectivity and physical correctness are separate checks.",
                        }
                    )
                )
                return 0
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
    except DemoInputError as error:
        print(
            json.dumps(
                {
                    "error": error.code,
                    "field": error.field,
                    "instruction": error.instruction,
                    "api_requests": 0,
                }
            )
        )
        return 2
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            print(
                json.dumps(
                    {
                        "error": "port_in_use",
                        "field": "port",
                        "instruction": "Stop the old demo server with Ctrl+C or pass --port 8766.",
                        "api_requests": 0,
                    }
                )
            )
        else:
            print(
                json.dumps(
                    {
                        "error": "local_input_io_error",
                        "field": "local_files",
                        "instruction": "Check that the supplied capture, monitoring bundle and optional private source files exist and are readable. No endpoint fallback is substituted for a requested monitoring bundle.",
                    }
                )
            )
        return 2
    except (ValueError, KeyError, TypeError):
        print(
            json.dumps(
                {
                    "error": "demo_precondition_failed",
                    "instruction": "Verify the unchanged capture and matching replay/source or fresh live protocol. Run the check subcommand; see docs/hackathon-readiness.md. No input or result was repaired or substituted.",
                }
            )
        )
        return 2
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
