"""Explicit read-only verification of saved v5 results; no API client creation.

Hashes establish internal consistency, not vendor authenticity or physical truth.
The selected source directory is explicit, never discovered by scanning user files.
"""

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path

from . import atomic_auditor as contract
from .audit import AuditEntry, canonical, verify_audit
from .claim_review import demo_cases, load_capture
from .eval_protocol import digest
from .investigation_events import received_event, tool_event
from .knowledge import PhysicalKnowledge

VERSION = "saved-investigation-v1"


def _read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 10_000_000:
        raise ValueError("Saved artifact must be a bounded regular file")
    raw = path.read_bytes()
    return raw, hashlib.sha256(raw).hexdigest()


def _json(raw):
    def reject_constant(_):
        raise ValueError("Nonfinite JSON")

    value = json.loads(raw, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError("Expected a saved JSON object")  # noqa: TRY004
    return value


def _verify_saved(
    capture, source, *, request_id=None, dataset=None, science_protocol=None
):
    source = Path(source)
    pbytes, phash = _read(source / "protocol.json")
    rbytes, rhash = _read(source / "results.jsonl")
    p = _json(pbytes)
    if digest({k: v for k, v in p.items() if k != "protocol_id"}) != p.get(
        "protocol_id"
    ):
        raise ValueError("Saved protocol digest mismatch")
    active = p.get("active_sensors") is True
    expected_version = contract.VERSION if active else contract.SCOPE_VERSION
    expected_prompt = contract.INSTRUCTIONS if active else contract.SCOPE_INSTRUCTIONS
    expected_tools = contract.active_tools() if active else contract.scope_tools()
    if (
        p.get("study") != expected_version
        or p.get("prompt_digest") != digest(expected_prompt)
        or p.get("tools_digest") != digest(expected_tools)
        or p.get("documents_digest") != digest(contract.DOCUMENTS)
        or p.get("history_projection_version") != "training-history-label-free-v1"
        or p.get("public_events_version") != "public-investigation-v2"
    ):
        raise ValueError("Matching saved v5 contract required")
    parent, _ = load_capture(capture)
    if p.get("parent_protocol_id") != parent["protocol_id"]:
        raise ValueError("Saved parent capture mismatch")
    rows = [_json(line) for line in rbytes.splitlines() if line.strip()]
    selected = [
        r for r in rows if request_id is None or r.get("request_id") == request_id
    ]
    if len(selected) != 1:
        raise ValueError("Select exactly one saved request with --request-id")
    row = selected[0]
    rid = row.get("request_id")
    if not isinstance(rid, str) or not re.fullmatch("[0-9a-f]{32}", rid):
        raise ValueError("Invalid saved request identifier")
    if (
        row.get("protocol_id") != p["protocol_id"]
        or row.get("contract_version") != expected_version
        or row.get("status") != "completed"
        or row.get("reason") != "claim_audit_submitted"
    ):
        raise ValueError("Only matching completed saved v5 audits can be replayed")
    case = next((c for c in demo_cases(capture) if c["id"] == row.get("case_id")), None)
    if case is None:
        raise ValueError("Saved case does not match the parent capture")
    # Active runs must be bound to the original private incident locator/window,
    # never to viewer telemetry or a guessed filename.
    windows = None
    if active:
        from .claim_demo import active_windows

        windows, window_digest = active_windows(capture, dataset, science_protocol)
        if window_digest != p.get("active_windows_digest"):
            raise ValueError("Saved diagnostic window mismatch")
    output = row.get("output")
    if (
        not isinstance(output, dict)
        or output.get("contract_version") != expected_version
    ):
        raise ValueError("Missing matching final assessment")
    if (
        set(output)
        != {
            "contract_version",
            "findings",
            "verdict",
            "numeric_observations",
            "independent_review_required",
            "physical_correctness_verified",
        }
        or output.get("physical_correctness_verified") is not False
        or output.get("independent_review_required") is not True
    ):
        raise ValueError("Unexpected saved assessment metadata")
    entries = tuple(AuditEntry(**a) for a in row["audit"])
    if not entries or not verify_audit(entries):
        raise ValueError("Saved audit hash chain mismatch")
    trace_raw, trace_hash = _read(source / (rid + ".jsonl"))
    trace = [_json(line) for line in trace_raw.splitlines() if line.strip()]
    intents = [e for e in trace if e.get("kind") == "intent"]
    if len(intents) != 1 or any(
        intents[0].get(k) != row.get(k)
        for k in ("case_id", "request_id", "protocol_id")
    ):
        raise ValueError("Saved trace identity mismatch")
    configs = [e["details"] for e in trace if e.get("kind") == "configuration"]
    if (
        len(configs) != 1
        or configs[0].get("prompt_version") != expected_version
        or configs[0].get("prompt_sha256")
        != hashlib.sha256(expected_prompt.encode()).hexdigest()
    ):
        raise ValueError("Saved prompt configuration mismatch")
    if (
        any(configs[0].get(k) != v for k, v in p["agent_config"].items())
        or configs[0].get("sensor_budget") != 5
        or p["agent_config"].get("model") != "muse-spark-1.3"
    ):
        raise ValueError("Saved model configuration mismatch")
    stops = [e["details"] for e in trace if e.get("kind") == "stop"]
    if len(stops) != 1 or any(
        stops[0].get(k) != row.get(k) for k in ("status", "reason", "requests")
    ):
        raise ValueError("Saved completion mismatch")
    recorded_results = [e["details"] for e in trace if e.get("kind") == "tool_result"]
    if len(recorded_results) != len(entries):
        raise ValueError("Incomplete saved tool-result trace")
    session = (
        contract.ActiveAuditSession(
            case["packet"], windows[case["id"]], history_labels_visible=False
        )
        if active
        else contract.ScopeAuditSession(case["packet"], history_labels_visible=False)
    )
    allowed_facts = {
        "knowledge:" + f.id: {**f.public(), "citation_id": "knowledge:" + f.id}
        for f in PhysicalKnowledge().facts
    }
    task = next(t for t in parent["tasks"] if t["task_id"] == case["id"])
    history = parent["histories"].get(task["source_case_id"], [])
    allowed_history = [
        {
            **{
                k: h[k]
                for k in ("case_id", "distance", "shared_sensors", "matched_sensors")
            },
            "citation_id": f"analogue:{i}",
        }
        for i, h in enumerate(history)
    ]
    events = [received_event(case["packet"], "saved")]
    requests = [e["details"] for e in trace if e.get("kind") == "tool_request"]
    if requests and (
        len(requests) != len(entries)
        or [e.get("sequence") for e in requests] != list(range(1, len(entries) + 1))
    ):
        raise ValueError("Incomplete or unordered saved request trace")
    if requests and [
        e["kind"] for e in trace if e["kind"] in {"tool_request", "tool_result"}
    ] != [kind for _ in entries for kind in ("tool_request", "tool_result")]:
        raise ValueError("Saved public event chronology mismatch")
    for i, (entry, recorded) in enumerate(zip(entries, recorded_results)):
        result = _json(entry.result_json)
        if (
            recorded.get("tool") != entry.tool
            or recorded.get("audit_sequence") != entry.sequence
            or recorded.get("audit_digest") != entry.digest
            or recorded.get("result") != result
            or recorded.get("arguments") != _json(entry.arguments_json)
        ):
            raise ValueError("Saved trace and audit disagree")
        if requests:
            request = requests[i]
            if request.get("tool") != entry.tool:
                raise ValueError("Saved request tool mismatch")
            public_request = {
                "kind": "tool_request",
                "mode": "saved",
                "sequence": entry.sequence,
                "tool": entry.tool,
                "title": "Recorded tool request",
            }
            if request.get("topic"):
                if request["topic"] not in session.topics() or request[
                    "topic"
                ] != _json(entry.arguments_json).get("topic"):
                    raise ValueError("Unknown saved public topic")
                public_request["topic"] = request["topic"]
            events.append(public_request)
        if entry.tool not in {
            "lookup_knowledge",
            "search_history",
            "request_sensor",
            "submit_audit",
        }:
            raise ValueError("Unknown saved tool")
        if "error" not in result:
            if entry.tool == "lookup_knowledge":
                for f in result.get("facts", []):
                    if allowed_facts.get(f.get("citation_id")) != f:
                        raise ValueError("Unrecognized saved source fact")
                    session._known.add(f["citation_id"])
            elif entry.tool == "search_history":
                if result.get("matches") != allowed_history or result.get(
                    "observed_sensors"
                ) != list(case["packet"]["observations"]):
                    raise ValueError(
                        "Saved history is not the permitted initial training snapshot"
                    )
                session._known.update(h["citation_id"] for h in allowed_history)
            elif entry.tool == "request_sensor":
                if not active:
                    raise ValueError("Unexpected saved sensor acquisition")
                acquired = session.dispatch(entry.tool, _json(entry.arguments_json))
                if acquired != result:
                    raise ValueError(
                        "Saved sensor result differs from verified original window"
                    )
            elif entry.tool == "submit_audit":
                if entry != entries[-1] or result != output:
                    raise ValueError("Saved final result mismatch")
                args = {
                    k: output[k]
                    for k in ("verdict", "findings", "numeric_observations")
                }
                if session._validate(args) is not None:
                    raise ValueError(
                        "Saved assessment fails v5 citation/numeric/scope checks"
                    )
        if "error" in result:
            # Public replay keeps the actual error identity but not rejected text.
            error = result["error"]
            if not re.fullmatch(r"[a-z_]+", error.get("code", "")) or not re.fullmatch(
                r"[A-Za-z0-9_\[\].]+", error.get("field", "")
            ):
                raise ValueError("Invalid saved structural error")
            event = {
                "kind": "tool_result",
                "mode": "saved",
                "sequence": entry.sequence,
                "tool": entry.tool,
                "validation": {"code": error["code"], "field": error["field"]},
                "title": "Recorded submission correction",
            }
        else:
            event = tool_event(asdict(entry), "saved")
            event.pop("history_scope", None)  # Narrative omitted; matches remain exact.
        events.append(event)
    if _json(entries[-1].result_json) != output or entries[-1].tool != "submit_audit":
        raise ValueError("Saved run has no final accepted assessment")
    observed = list(session.packet["observations"])
    if (
        row.get("observed_sensors") != observed
        or row.get("inherited_sensor_queries") != len(case["packet"]["observations"])
        or row.get("remaining_budget") != session.remaining_budget
        or row.get("new_sensor_queries")
        != (session.new_sensor_queries if active else 0)
    ):
        raise ValueError("Saved sensor budget accounting mismatch")
    events.append(
        {
            "kind": "completion",
            "mode": "saved",
            "status": "completed",
            "reason": row["reason"],
            "title": "Recorded investigation complete",
        }
    )
    public = {
        "version": VERSION,
        "case_id": case["id"],
        "contract_version": expected_version,
        "events": events,
        "disclosure": "Previously recorded investigation; presentation pacing, not token timing. Initial evidence is reconstructed from the matching frozen parent packet. Only recorded tool requests/results are shown. Rejected submission text and historical limitation prose are omitted; original error codes/fields and numerical matches are retained. "
        + (
            "Request events were recorded."
            if requests
            else "No request events were saved; only actual recorded results can be replayed."
        ),
        "verification_scope": "Artifact integrity, original-window binding and v5 structural checks; not vendor authenticity or physical certification.",
    }
    hashes = {
        "protocol.json": phash,
        "results.jsonl": rhash,
        rid + ".jsonl": trace_hash,
    }
    optional = source / (rid + ".public.jsonl")
    if optional.exists() or optional.is_symlink():
        raw, public_hash = _read(optional)
        captured_public = [
            _json(line)["event"] for line in raw.splitlines() if line.strip()
        ]
        actual_results = [e for e in captured_public if e.get("kind") == "tool_result"]
        if actual_results != [tool_event(asdict(e), "live") for e in entries]:
            raise ValueError("Saved public events and audit disagree")
        actual_requests = [
            e for e in captured_public if e.get("kind") == "tool_request"
        ]
        if actual_requests != requests:
            raise ValueError("Saved public request events disagree")
        received = [e for e in captured_public if e.get("kind") == "evidence_received"]
        if received != [received_event(case["packet"], "live")]:
            raise ValueError("Saved public input packet mismatch")
        hashes[optional.name] = public_hash
    if any(_read(source / name)[1] != h for name, h in hashes.items()):
        raise ValueError("Saved artifacts changed during verification")
    return public, hashes, rid


def verify_saved(
    capture, source, *, request_id=None, dataset=None, science_protocol=None
):
    try:
        return _verify_saved(
            capture,
            source,
            request_id=request_id,
            dataset=dataset,
            science_protocol=science_protocol,
        )
    except (KeyError, TypeError, AttributeError, IndexError):
        raise ValueError("Malformed saved investigation artifacts") from None


def import_saved(capture, source, out, **kwargs):
    out = Path(out)
    if out.exists():
        raise ValueError("Use a fresh saved replay output directory")
    if Path(source).resolve() in out.resolve().parents:
        raise ValueError("Derived replay must be outside the original run directory")
    public, hashes, rid = verify_saved(capture, source, **kwargs)
    manifest = {
        "version": VERSION,
        "source_directory": str(Path(source).resolve()),
        "request_id": rid,
        "source_hashes": hashes,
        "projection_digest": digest(public),
    }
    out.mkdir(parents=True)
    (out / "manifest.json").write_text(canonical(manifest) + "\n")
    # Only this explicitly constructed projection is ever sent to a browser.
    (out / "replay.json").write_text(canonical(public) + "\n")
    return {
        "status": "saved_v5_verified_and_imported",
        "case_id": public["case_id"],
        "events": len(public["events"]),
        "api_requests": 0,
    }


def load_saved(capture, bundle, **kwargs):
    manifest = _json(_read(Path(bundle) / "manifest.json")[0])
    if manifest.get("version") != VERSION:
        raise ValueError("Unknown saved replay version")
    public, hashes, _ = verify_saved(
        capture,
        manifest["source_directory"],
        request_id=manifest["request_id"],
        **kwargs,
    )
    if (
        hashes != manifest["source_hashes"]
        or digest(public) != manifest["projection_digest"]
        or _json(_read(Path(bundle) / "replay.json")[0]) != public
    ):
        raise ValueError("Saved replay source or projection changed")
    return public
