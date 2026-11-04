"""Read-only adapter for the pinned c-7a91 showcase; never a saved-v5 importer.

No evaluator key, hidden sensor vault, transport reasoning or executable artifact
code is loaded. Only the previously received host packet/results are projected.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

VERSION = "synthetic-hydraulic-replay-v1"
# Owner-supplied, already verified showcase commitments. No research results in Git.
MANIFEST_SHA256 = "8e0eba8f09efc4b14fb1ea9e4b2be29b0c394d1aba50f44a006bd4c1b71203b3"
HOST_SHA256 = "acc1a8e0ec3ddffda69ebd9f992426fb500d2ba12799a7ff6c56b0b328447f4d"
FILES = {
    "README.md",
    "STORY.md",
    "captured-investigation.json",
    "computed-evidence.json",
    "evidence-flow.svg",
    "evidence.png",
    "original-host-audit.UNCHANGED.json",
    "verification.json",
    "verify_package.py",
}


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("Nonfinite JSON value")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def _read(root, name):
    path = root / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("Invalid synthetic source file")
    return path.read_bytes()


def _summary(measurement):
    # Display-only summary of the received GOOD samples; original samples retained.
    samples = measurement["samples"]
    good = [
        s["value"] for s in samples if s["quality"] == "GOOD" and s["value"] is not None
    ]
    return {
        "available": bool(good),
        "count": len(good),
        "total": len(samples),
        "first": good[0] if good else None,
        "last": good[-1] if good else None,
        "delta": good[-1] - good[0] if good else None,
        "summary_role": "Python display summary of received GOOD samples; not a new observation",
    }


def load_synthetic(directory):
    """Fail closed on modified/other cases. Does not execute supplied verifier."""
    root = Path(directory)
    manifest_raw = _read(root, "MANIFEST.json")
    if hashlib.sha256(manifest_raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Unrecognized synthetic manifest commitment")
    manifest = _json(manifest_raw)
    if set(manifest) != FILES:
        raise ValueError("Unexpected synthetic manifest")
    data = {name: _read(root, name) for name in FILES}
    if any(
        hashlib.sha256(raw).hexdigest() != manifest[name] for name, raw in data.items()
    ):
        raise ValueError("Synthetic source commitment mismatch")
    if (
        hashlib.sha256(data["original-host-audit.UNCHANGED.json"]).hexdigest()
        != HOST_SHA256
    ):
        raise ValueError("Unrecognized synthetic recording")
    audit = _json(data["original-host-audit.UNCHANGED.json"])
    projected = _json(data["captured-investigation.json"])
    receipt = _json(data["verification.json"])
    previous = "0" * 64
    for sequence, entry in enumerate(audit):
        if (
            set(entry)
            != {"sequence", "tool", "arguments", "result", "previous", "digest"}
            or entry["sequence"] != sequence
            or entry["previous"] != previous
            or hashlib.sha256(
                _canonical({k: v for k, v in entry.items() if k != "digest"})
            ).hexdigest()
            != entry["digest"]
        ):
            raise ValueError("Invalid synthetic host chain")
        previous = entry["digest"]
    packet = audit[0]["result"]
    tools = [e["tool"] for e in audit]
    if (
        packet["case_id"] != "c-7a91"
        or packet["synthetic"] is not True
        or tools
        != [
            "initial_packet",
            "query_sensor",
            "query_sensor",
            "lookup_graph",
            "read_document",
            "read_document",
            "submit_audit",
        ]
        or projected["initial_packet"] != packet
        or len(projected["events"]) != 6
        or receipt["case_id"] != "c-7a91"
        or receipt["recorded_requests"] != 6
        or receipt["sensor_budget"] != 5
    ):
        raise ValueError("Unsupported synthetic metadata")
    for original, projection in zip(audit[1:], projected["events"], strict=True):
        if any(
            projection[k] != original[k]
            for k in ("sequence", "tool", "arguments", "result")
        ):
            raise ValueError("Synthetic event differs from original")
        args = projection["model_requested_arguments"]
        applied = {**args, "hops": 1} if original["tool"] == "lookup_graph" else args
        if applied != original["arguments"]:
            raise ValueError("Unexpected synthetic bridge arguments")
    accepted = audit[-1]["result"]
    if (
        accepted.get("accepted") is not True
        or accepted["assessment"] != projected["final_assessment"]
    ):
        raise ValueError("Synthetic final output differs")
    initial = packet["initial_measurements"]
    observed = dict(initial)
    for entry in audit[1:3]:
        sensor = entry["arguments"]["sensor"]
        if sensor in observed or entry["result"]["sensor"] != sensor:
            raise ValueError("Unexpected synthetic sensor accounting")
        observed[sensor] = entry["result"]
    if set(observed) != {"P-TPT", "P-MON-CKP", "T-TPT", "SYN-Q-PROD", "SYN-P-SEP"}:
        raise ValueError("Synthetic sensor accounting differs")
    # Original accepted output remains intact; UI commentary is explicitly editorial.
    # Gate the positive headline on the actual accepted premise, not hidden truth.
    premise = "Pressures plus flow show increased effective R_L with stable separator"
    if premise not in accepted["assessment"]["findings"][2]["premises"]:
        raise ValueError("Expected scoped hydraulic premise unavailable")
    events = [
        {
            "kind": "evidence_received",
            "mode": VERSION,
            "sequence": 0,
            "synthetic": True,
            "title": "Initial synthetic pressures, temperature and M1 received",
            "hypothesis_label": "Hydrate candidate · constructed handoff",
            "hypothesis_scope": "Synthetic candidate, not a statistical classifier output",
            "claim": packet["claim"],
            "observations": {s: _summary(m) for s, m in initial.items()},
            "measurements": deepcopy(initial),
            "documents": [{**packet["model"], "citation_id": "model:M1"}],
            "recorded_timestamp": None,
        }
    ]
    for original, projection in zip(audit[1:], projected["events"], strict=True):
        seq, tool, result = original["sequence"], original["tool"], original["result"]
        events.append(
            {
                "kind": "tool_request",
                "mode": VERSION,
                "sequence": seq,
                "tool": tool,
                "title": "Recorded Muse tool request",
                "arguments": deepcopy(projection["model_requested_arguments"]),
                "recorded_timestamp": None,
            }
        )
        event = {
            "kind": "tool_result",
            "mode": VERSION,
            "sequence": seq,
            "tool": tool,
            "audit_digest": original["digest"],
            "result": deepcopy(result),
            "recorded_timestamp": None,
        }
        if tool == "query_sensor":
            event.update(
                title="Muse receives " + result["sensor"],
                sensor=result["sensor"],
                summary=_summary(result),
                measurement=deepcopy(result),
                citation_id=result["id"],
                remaining_budget=5 - len(initial) - seq,
            )
        elif tool == "lookup_graph":
            event.update(
                title="Muse retrieves hypothesis-scoped graph relationships",
                facts=[
                    {
                        **edge,
                        "citation_id": edge["id"],
                        "relation": edge["predicate"],
                        "status": edge["epistemic_status"],
                        "scope": edge["scope_limitations"],
                    }
                    for edge in result["edges"]
                ],
            )
        elif tool == "read_document":
            event.update(
                title="Muse reads " + result["id"],
                documents=[{**result, "citation_id": result["id"]}],
            )
        elif tool == "submit_audit":
            event.update(
                title="Muse submits the accepted synthetic audit",
                assessment=deepcopy(result["assessment"]),
            )
        events.append(event)
    events.append(
        {
            "kind": "completion",
            "mode": VERSION,
            "status": "completed",
            "reason": "accepted_recorded_synthetic_audit",
            "recorded_timestamp": None,
        }
    )
    return {
        "version": VERSION,
        "public_events_version": "public-investigation-v2",
        "id": "c-7a91",
        "synthetic": True,
        "events": events,
        "assessment": deepcopy(accepted["assessment"]),
        "model": deepcopy(packet["model"]),
        "initial_sensors": list(initial),
        "sensor_budget": 5,
        "recording": {
            "requests": 6,
            "duration_seconds": receipt["recorded_latency_seconds"],
            "estimated_cost_usd": receipt["recorded_estimated_cost_usd"],
            "event_timestamps": "unavailable",
            "host_final_digest": previous,
        },
        "scope": "Controlled synthetic M1 hydraulics, not Petrobras measurements; edited replay pacing, not original event timing.",
        "editorial_conclusion": "Hydraulic evidence supports increased effective resistance under synthetic model M1. The specific cause remains unidentified.",
        "conclusion_basis": "Scoped editorial interpretation of received evidence, not an additional or upgraded atomic Muse verdict. The accepted aggregate remains PARTIALLY_SUPPORTED; the hydrate-cause finding remains NOT_ESTABLISHED.",
        "selection": "Post-hoc showcase selection, not an unbiased accuracy estimate. Graph lookup followed sensor acquisition.",
        "independent_human_review": False,
    }
