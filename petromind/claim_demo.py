"""Loopback-only claim demo: immutable real replay and explicitly enabled live v2."""

from __future__ import annotations

import json
import secrets
import threading
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import monotonic

from .agent import AgentConfig
from .audit import canonical
from .claim_evaluation import checked_protocol
from .claim_review import demo_cases, load_capture, review_capture
from .eval_protocol import DEFAULT_PRICES, digest, runtime_versions, source_digest
from .eval_runner import append_json, read_jsonl, usage_and_cost
from .meta_api import MetaAPIError, MetaResponsesClient
from .science_evaluation import CostedClient, SpendingLedger
from .scope_auditor import (
    DOCUMENTS,
    INSTRUCTIONS,
    VERSION,
    ScopeAuditSession,
    run_scope_auditor,
    scope_tools,
)


def freeze_live(capture, out, max_cost=2):
    if type(max_cost) not in (int, float) or not 0 < max_cost <= 2:
        raise ValueError("Live estimated cap must be positive and no greater than $2")
    p, _ = load_capture(capture)
    out = Path(out)
    if out.exists():
        raise ValueError("Use a fresh live directory; never modify a captured protocol")
    config = AgentConfig(
        max_turns=6, max_tool_calls=8, max_output_tokens=4096, variant="sensor_only"
    )
    protocol = {
        "study": VERSION,
        "parent_protocol_id": p["protocol_id"],
        "source_digest": source_digest(),
        "runtime": runtime_versions(),
        "prompt_digest": digest(INSTRUCTIONS),
        "tools_digest": digest(scope_tools()),
        "documents_digest": digest(DOCUMENTS),
        "agent_config": asdict(config),
        "prices": DEFAULT_PRICES,
        "limits": {
            "pilot": {"requests": 12, "output_tokens": 49152, "estimated_usd": max_cost}
        },
        "note": "Explicit interactive executions only. New v2 has no paid evaluation or engineering certification.",
    }
    protocol["protocol_id"] = digest(protocol)
    out.mkdir(parents=True)
    (out / "protocol.json").write_text(canonical(protocol) + "\n")
    return {
        "protocol_id": protocol["protocol_id"],
        "api_requests": 0,
        "contract_version": VERSION,
    }


class DemoApp:
    def __init__(
        self, capture, live_directory=None, client_factory=MetaResponsesClient
    ):
        self.cases = demo_cases(capture)
        self.review = review_capture(capture)
        self.protocol, _ = load_capture(capture)
        self.live_directory = Path(live_directory) if live_directory else None
        self.client_factory = client_factory
        self.lock = threading.Lock()
        self.token = secrets.token_urlsafe(32)
        if self.live_directory:
            self.validate_live()

    def validate_live(self):
        p = json.loads((self.live_directory / "protocol.json").read_text())
        checked_protocol(p)
        if (
            p["study"] != VERSION
            or p["parent_protocol_id"] != self.protocol["protocol_id"]
            or p["source_digest"] != source_digest()
            or p["runtime"] != runtime_versions()
            or p["prompt_digest"] != digest(INSTRUCTIONS)
            or p["tools_digest"] != digest(scope_tools())
            or p["documents_digest"] != digest(DOCUMENTS)
        ):
            raise ValueError("Fresh scope-v2 live protocol required")
        return p

    def live(self, case_id, request_id):
        if self.live_directory is None:
            raise ValueError("Live execution is disabled")
        if (
            not isinstance(request_id, str)
            or len(request_id) != 32
            or any(c not in "0123456789abcdef" for c in request_id)
        ):
            raise ValueError("Invalid request identifier")
        case = next((c for c in self.cases if c["id"] == case_id), None)
        if case is None:
            raise ValueError("Unknown demo case")
        if not self.lock.acquire(blocking=False):
            raise ValueError("An investigation is already running")
        try:
            import fcntl

            with (self.live_directory / "live.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                p = self.validate_live()
                for row in read_jsonl(self.live_directory / "results.jsonl"):
                    if row["request_id"] == request_id:
                        if row["case_id"] != case_id:
                            raise ValueError(
                                "Request ID already belongs to another case"
                            )
                        return row
                # Validate credentials before durable intent; no HTTP is made here.
                probe = self.client_factory(max_requests=1, max_output_budget=4096)
                probe.close()
                trace = self.live_directory / (request_id + ".jsonl")
                if trace.exists():
                    raise ValueError(
                        "Interrupted request cannot be automatically retried"
                    )
                append_json(
                    trace,
                    {
                        "kind": "intent",
                        "request_id": request_id,
                        "case_id": case_id,
                        "protocol_id": p["protocol_id"],
                    },
                )
                task = next(
                    t for t in self.protocol["tasks"] if t["task_id"] == case_id
                )
                history = self.protocol["histories"].get(task["source_case_id"], ())
                session = ScopeAuditSession(case["packet"], history=history)
                ledger = SpendingLedger(
                    self.live_directory / "reservations.jsonl", p, "pilot"
                )
                client = CostedClient(
                    self.client_factory,
                    ledger,
                    {"request_id": request_id, "case_id": case_id},
                )
                start = monotonic()
                try:
                    result = run_scope_auditor(
                        session,
                        client,
                        AgentConfig(**p["agent_config"]),
                        on_event=lambda e: append_json(
                            trace,
                            {"kind": e.kind, "details": json.loads(e.details_json)},
                        ),
                    )
                finally:
                    client.close()
                row = {
                    "request_id": request_id,
                    "case_id": case_id,
                    "protocol_id": p["protocol_id"],
                    "contract_version": VERSION,
                    "status": result.status,
                    "reason": result.reason,
                    "output": session.result,
                    "usage": usage_and_cost(
                        result.events, result.requests, p["prices"]
                    ),
                    "latency_seconds": monotonic() - start,
                    "requests": result.requests,
                    "new_sensor_queries": 0,
                    "inherited_sensor_queries": len(case["observations"]),
                    "audit": [asdict(a) for a in session.audit_trail],
                    "physical_correctness_verified": False,
                }
                append_json(self.live_directory / "results.jsonl", row)
                return row
        finally:
            self.lock.release()


def make_server(app, port=8765):
    assets = Path(__file__).with_name("web")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # No request/body or key logging.

        def allowed_host(self):
            return self.headers.get("Host") in {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }

        def send(self, status, body, content_type="application/json"):
            data = (
                canonical(body) if content_type == "application/json" else body
            ).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.allowed_host():
                return self.send(403, {"error": "host_not_allowed"})
            if self.path == "/api/cases":
                return self.send(
                    200,
                    {
                        "cases": app.cases,
                        "replay": "Captured real Muse v1 outputs; independent engineering review pending.",
                    },
                )
            if self.path == "/api/review":
                return self.send(200, app.review)
            if self.path == "/api/status":
                return self.send(
                    200,
                    {
                        "live_enabled": app.live_directory is not None,
                        "token": app.token,
                        "live_version": VERSION,
                    },
                )
            files = {
                "/": ("index.html", "text/html"),
                "/app.js": ("app.js", "text/javascript"),
                "/style.css": ("style.css", "text/css"),
            }
            if self.path not in files:
                return self.send(404, {"error": "not_found"})
            file, kind = files[self.path]
            return self.send(200, (assets / file).read_text(), kind)

        def do_POST(self):
            origins = {
                f"http://127.0.0.1:{self.server.server_port}",
                f"http://localhost:{self.server.server_port}",
            }
            if (
                not self.allowed_host()
                or self.headers.get("Origin") not in origins
                or self.headers.get("X-PetroMind-Token") != app.token
            ):
                return self.send(403, {"error": "origin_or_token_rejected"})
            if self.path != "/api/live":
                return self.send(404, {"error": "not_found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if (
                    not 0 < length <= 1024
                    or self.headers.get("Content-Type") != "application/json"
                ):
                    raise ValueError()
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict) or set(body) != {"case_id", "request_id"}:
                    raise ValueError()
                row = app.live(body["case_id"], body["request_id"])
                return self.send(200, row)
            except MetaAPIError as e:
                return self.send(400, {"error": e.code})
            except (ValueError, KeyError, TypeError, OSError):
                return self.send(
                    400,
                    {
                        "error": "live_precondition_failed",
                        "instruction": "Check enabled mode, fresh protocol and remaining cap. Interrupted tasks are not retried.",
                    },
                )

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
