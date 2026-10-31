"""Loopback-only claim demo: immutable real replay and explicitly enabled v2/v3 live."""

from __future__ import annotations

import json
import secrets
import threading
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import monotonic

from . import active_auditor
from .agent import AgentConfig
from .audit import canonical
from .claim_evaluation import checked_protocol
from .claim_review import demo_cases, load_capture, review_capture
from .eval_protocol import DEFAULT_PRICES, digest, runtime_versions, source_digest
from .eval_runner import append_json, read_jsonl, usage_and_cost
from .investigation_events import captured_events, received_event, tool_event
from .meta_api import MetaAPIError, MetaResponsesClient
from .replay_workflow import replay_workflow
from .science_evaluation import CostedClient, SpendingLedger
from .scope_auditor import (
    DOCUMENTS,
    INSTRUCTIONS,
    VERSION,
    ScopeAuditSession,
    run_scope_auditor,
    scope_tools,
)


def freeze_live(
    capture,
    out,
    max_cost=2,
    *,
    active_sensors=False,
    dataset=None,
    science_protocol=None,
):
    if type(max_cost) not in (int, float) or not 0 < max_cost <= 2:
        raise ValueError("Live estimated cap must be positive and no greater than $2")
    p, _ = load_capture(capture)
    out = Path(out)
    if out.exists():
        raise ValueError("Use a fresh live directory; never modify a captured protocol")
    config = AgentConfig(
        max_turns=6, max_tool_calls=8, max_output_tokens=4096, variant="sensor_only"
    )
    contract = active_auditor if active_sensors else None
    protocol = {
        "study": contract.VERSION if contract else VERSION,
        "active_sensors": bool(active_sensors),
        "parent_protocol_id": p["protocol_id"],
        "source_digest": source_digest(),
        "runtime": runtime_versions(),
        "prompt_digest": digest(contract.INSTRUCTIONS if contract else INSTRUCTIONS),
        "tools_digest": digest(contract.active_tools() if contract else scope_tools()),
        "documents_digest": digest(DOCUMENTS),
        "agent_config": asdict(config),
        "prices": DEFAULT_PRICES,
        "limits": {
            "pilot": {"requests": 12, "output_tokens": 49152, "estimated_usd": max_cost}
        },
        "note": "Explicit interactive executions only. Fresh v2/v3 has no new paid evaluation or engineering certification.",
    }
    if active_sensors:
        protocol["active_windows_digest"] = active_windows(
            capture, dataset, science_protocol
        )[1]
    protocol["protocol_id"] = digest(protocol)
    out.mkdir(parents=True)
    (out / "protocol.json").write_text(canonical(protocol) + "\n")
    return {
        "protocol_id": protocol["protocol_id"],
        "api_requests": 0,
        "contract_version": protocol["study"],
    }


def active_windows(capture, dataset, science_protocol):
    """Resolve frozen server-only windows, never browser replay as agent input."""
    from .incident_replay import raw_payload, resolve_window

    if dataset is None or not Path(dataset).is_dir() or science_protocol is None:
        raise ValueError(
            "Active queries require the actual dataset and private source protocol"
        )
    protocol, _ = load_capture(capture)
    windows, fingerprints = {}, {}
    for case in demo_cases(capture):
        window = resolve_window(case, protocol, dataset, science_protocol)
        projection = raw_payload(window, case)  # cadence + captured summary match
        fingerprints[case["id"]] = digest(projection)
        windows[case["id"]] = window
    return windows, digest(fingerprints)


class DemoApp:
    def __init__(
        self,
        capture,
        live_directory=None,
        client_factory=MetaResponsesClient,
        *,
        dataset=None,
        science_protocol=None,
    ):
        self.cases = demo_cases(capture)
        self.review = review_capture(capture)
        self.protocol, captured_rows = load_capture(capture)
        from .incident_replay import attach_replay, definitions

        for case in self.cases:
            case["sensor_definitions"] = definitions()
            case["replay"] = attach_replay(
                case, self.protocol, dataset=dataset, science_protocol=science_protocol
            )
            case["replay"]["workflow"] = replay_workflow(case["replay"])
            case["captured_activity"] = {}
            case["investigation_events"] = {}
            for method in ("grounded", "ungrounded"):
                row = next(
                    r
                    for r in captured_rows
                    if r["task_id"] == case["id"] and r["method"] == method
                )
                case["investigation_events"][method] = captured_events(
                    case["packet"], row
                )
                activities = []
                for entry in row["audit"]:
                    value = json.loads(entry["result_json"])
                    args = json.loads(entry["arguments_json"])
                    activities.append(
                        {
                            "sequence": entry["sequence"],
                            "tool": entry["tool"],
                            "topic": args.get("topic"),
                            "error": value.get("error"),
                            "verdict": value.get("verdict"),
                            "fact_count": len(value.get("facts", [])),
                            "match_overlap": [
                                m["shared_sensors"] for m in value.get("matches", [])
                            ],
                        }
                    )
                case["captured_activity"][method] = activities
        self.live_directory = Path(live_directory) if live_directory else None
        self.client_factory = client_factory
        self.lock = threading.Lock()
        self.token = secrets.token_urlsafe(32)
        self.active_sensors = False
        self._active_windows = {}
        self._active_windows_digest = None
        if self.live_directory:
            preview = json.loads((self.live_directory / "protocol.json").read_text())
            if preview.get("active_sensors"):
                self._active_windows, self._active_windows_digest = active_windows(
                    capture, dataset, science_protocol
                )
                self.active_sensors = True
        self.live_version = active_auditor.VERSION if self.active_sensors else VERSION
        self.live_limits = (
            self.validate_live()["limits"]["pilot"] if self.live_directory else None
        )

    def validate_live(self):
        p = json.loads((self.live_directory / "protocol.json").read_text())
        checked_protocol(p)
        contract = active_auditor if self.active_sensors else None
        if (
            p["study"] != self.live_version
            or bool(p.get("active_sensors")) != self.active_sensors
            or (
                self.active_sensors
                and p.get("active_windows_digest") != self._active_windows_digest
            )
            or p["parent_protocol_id"] != self.protocol["protocol_id"]
            or p["source_digest"] != source_digest()
            or p["runtime"] != runtime_versions()
            or p["prompt_digest"]
            != digest(contract.INSTRUCTIONS if contract else INSTRUCTIONS)
            or p["tools_digest"]
            != digest(contract.active_tools() if contract else scope_tools())
            or p["documents_digest"] != digest(DOCUMENTS)
        ):
            raise ValueError("Fresh matching live protocol required")
        return p

    def live(self, case_id, request_id, *, on_public_event=None):
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
                session = (
                    active_auditor.ActiveAuditSession(
                        case["packet"], self._active_windows[case_id], history=history
                    )
                    if self.active_sensors
                    else ScopeAuditSession(case["packet"], history=history)
                )
                ledger = SpendingLedger(
                    self.live_directory / "reservations.jsonl", p, "pilot"
                )
                client = CostedClient(
                    self.client_factory,
                    ledger,
                    {"request_id": request_id, "case_id": case_id},
                )
                if on_public_event:
                    on_public_event(received_event(session.packet, "live"))

                def record_event(e):
                    append_json(
                        trace, {"kind": e.kind, "details": json.loads(e.details_json)}
                    )
                    if on_public_event and e.kind == "tool_result":
                        on_public_event(
                            tool_event(asdict(session.audit_trail[-1]), "live")
                        )

                start = monotonic()
                try:
                    runner = (
                        active_auditor.run_active_auditor
                        if self.active_sensors
                        else run_scope_auditor
                    )
                    result = runner(
                        session,
                        client,
                        AgentConfig(**p["agent_config"]),
                        on_event=record_event,
                    )
                finally:
                    client.close()
                row = {
                    "request_id": request_id,
                    "case_id": case_id,
                    "protocol_id": p["protocol_id"],
                    "contract_version": self.live_version,
                    "status": result.status,
                    "reason": result.reason,
                    "output": session.result,
                    "usage": usage_and_cost(
                        result.events, result.requests, p["prices"]
                    ),
                    "latency_seconds": monotonic() - start,
                    "requests": result.requests,
                    "new_sensor_queries": session.new_sensor_queries
                    if self.active_sensors
                    else 0,
                    "remaining_budget": session.remaining_budget,
                    "observed_sensors": list(session.packet["observations"]),
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
                        "live_version": app.live_version,
                        "live_limits": app.live_limits,
                        "capabilities": {
                            "tools": (["request_sensor"] if app.active_sensors else [])
                            + [
                                "lookup_knowledge",
                                "search_history",
                                "submit_audit",
                            ],
                            "new_sensor_queries": app.active_sensors,
                            "history_scope": "Frozen training-only snapshot from initial sensors; additional queries do not rerank.",
                            "well_topology_traversal": False,
                            "knowledge_graph": "Source-scoped facts by public topic; not per-well topology",
                            "inherited_sensor_summaries": 3,
                            "shared_budget": 5,
                        },
                    },
                )
            files = {
                "/": ("index.html", "text/html"),
                "/demo": ("index.html", "text/html"),
                "/technology": ("index.html", "text/html"),
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
            if self.path not in {"/api/live", "/api/live/stream"}:
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
                if self.path == "/api/live/stream":
                    if app.live_directory is None:
                        raise ValueError("Live disabled")
                    app.validate_live()
                    self.send_response(200)
                    self.send_header(
                        "Content-Type", "application/x-ndjson; charset=utf-8"
                    )
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Connection", "close")
                    self.send_header(
                        "Content-Security-Policy",
                        "default-src 'none'; frame-ancestors 'none'",
                    )
                    self.end_headers()
                    connected = True

                    def emit(event):
                        nonlocal connected
                        if connected:
                            try:
                                self.wfile.write((canonical(event) + "\n").encode())
                                self.wfile.flush()
                            except OSError:
                                connected = False

                    try:
                        row = app.live(
                            body["case_id"], body["request_id"], on_public_event=emit
                        )
                        emit(
                            {
                                "kind": "completion",
                                "mode": "live",
                                "status": row["status"],
                                "reason": row["reason"],
                                "title": "Live investigation finished",
                                "row": row,
                            }
                        )
                    except MetaAPIError as e:
                        emit({"kind": "failure", "mode": "live", "code": e.code})
                    except (ValueError, KeyError, TypeError, OSError):
                        emit(
                            {
                                "kind": "failure",
                                "mode": "live",
                                "code": "live_precondition_failed",
                            }
                        )
                    self.close_connection = True
                    return
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
