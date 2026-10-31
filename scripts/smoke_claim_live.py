#!/usr/bin/env python3
"""One explicitly authorized paid investigation over the actual streaming route.

Never run during offline tests. It neither expands cohorts nor grades physics.
"""

import argparse
import json
import sys
import threading
from pathlib import Path
from time import monotonic
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from petromind.audit import canonical
from petromind.claim_demo import DemoApp, make_server
from petromind.eval_runner import append_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument(
        "--live",
        type=Path,
        required=True,
        help="Fresh protocol prepared with --max-cost-usd 0.5 or less",
    )
    p.add_argument(
        "--case",
        choices=["fault_expectation", "published_example_consistency"],
        default="fault_expectation",
    )
    p.add_argument("--dataset", type=Path, default=Path("../3W/dataset"))
    p.add_argument(
        "--science-protocol",
        type=Path,
        default=Path(".petromind/science-m5-v1/protocol.json"),
    )
    p.add_argument(
        "--authorize-paid-meta",
        action="store_true",
        help="Explicitly authorize this single cost-capped live investigation",
    )
    a = p.parse_args()
    if not a.authorize_paid_meta:
        p.error(
            "No API request made. Add --authorize-paid-meta only when ready to spend against the fresh protocol cap."
        )
    try:
        import httpx

        source = (
            json.loads(a.science_protocol.read_text())
            if a.dataset.is_dir() and a.science_protocol.is_file()
            else None
        )
        app = DemoApp(a.capture, a.live, dataset=a.dataset, science_protocol=source)
        protocol = app.validate_live()
        if protocol["limits"]["pilot"]["estimated_usd"] > 0.5:
            raise ValueError(
                "Smoke test requires a global estimated cap no greater than $0.50"
            )
        if list(a.live.glob("*.jsonl")):
            raise ValueError("Smoke test requires an unused protocol directory")
        request_id = uuid4().hex
        output = a.live / (request_id + ".public.jsonl")
        server = make_server(app, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        start, events, row = monotonic(), [], None
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            with (
                httpx.Client(trust_env=False, timeout=360) as client,
                client.stream(
                    "POST",
                    url + "/api/live/stream",
                    headers={"Origin": url, "X-PetroMind-Token": app.token},
                    json={"case_id": a.case, "request_id": request_id},
                ) as response,
            ):
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    e = json.loads(line)
                    elapsed = monotonic() - start
                    append_json(output, {"elapsed_seconds": elapsed, "event": e})
                    events.append(e)
                    print(
                        canonical(
                            {
                                "kind": e["kind"],
                                "tool": e.get("tool"),
                                "elapsed_seconds": round(elapsed, 3),
                                "status": e.get("status"),
                                "code": e.get("code"),
                            }
                        ),
                        flush=True,
                    )
                    if e["kind"] == "completion":
                        row = e["row"]
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        print(
            canonical(
                {
                    "execution_mode": "explicit_live_smoke",
                    "actual_response_usage_recorded": bool(
                        row and row["usage"].get("input_tokens", 0) > 0
                    ),
                    "status": row["status"] if row else "failed",
                    "reason": row["reason"] if row else "no_completion",
                    "requests": row["requests"] if row else None,
                    "estimated_cost_usd": row["usage"]["estimated_cost_usd"]
                    if row
                    else None,
                    "tool_events": sum(e["kind"] == "tool_result" for e in events),
                    "new_sensor_queries": row.get("new_sensor_queries")
                    if row
                    else None,
                    "limitation": "Recorded arrival times and actual tool events; no physical correctness or sensor-selection benefit claim. Visual browser validation is separate.",
                }
            )
        )
        return 0 if row and row["status"] == "completed" else 2
    except (ValueError, OSError, KeyError, TypeError):
        print(
            canonical(
                {
                    "status": "smoke_precondition_failed",
                    "instruction": "Check unused fresh protocol <= $0.50, dataset requirements and exported MODEL_API_KEY. No automatic retry; inspect public trace before another run.",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
