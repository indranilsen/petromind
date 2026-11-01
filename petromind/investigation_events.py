"""Public UI projection of actual audit entries; never vendor/private reasoning."""

import json
from copy import deepcopy

VERSION = "public-investigation-v2"


def received_event(packet, mode):
    return {
        "kind": "evidence_received",
        "mode": mode,
        "sequence": 0,
        "title": "Classifier hypothesis and fixed evidence prepared for Muse"
        if mode == "live"
        else "Captured evidence packet supplied to Muse",
        "hypothesis": packet["baseline"]["prediction"],
        "claim": packet["claim"],
        "observations": deepcopy(packet["observations"]),
        "note": "Already charged summaries, not raw playback or extra viewer channels.",
    }


def tool_event(entry, mode):
    result = json.loads(entry["result_json"])
    args = json.loads(entry["arguments_json"])
    tool = entry["tool"]
    event = {
        "kind": "tool_result",
        "mode": mode,
        "sequence": entry["sequence"],
        "tool": tool,
        "audit_digest": entry["digest"],
        "title": {
            "lookup_knowledge": "Muse retrieves source-backed graph facts",
            "search_history": "Muse compares restricted training history",
            "request_sensor": "Muse requests a documented sensor summary",
            "submit_audit": "Muse submits its public claim assessment",
        }.get(tool, "Tool response"),
    }
    if "error" in result:
        # Rejected submission text/arguments never enter the public event stream.
        error = result["error"]
        event.update(
            title="Python rejects a submission; bounded repair may follow"
            if tool == "submit_audit"
            else "Python rejects a tool request",
            validation={
                k: error[k]
                for k in ("code", "field", "instruction", "correction")
                if k in error
            },
        )
    elif tool == "lookup_knowledge":
        event.update(topic=args.get("topic"), facts=result.get("facts", []))
    elif tool == "search_history":
        event.update(
            matches=result.get("matches", []),
            observed_sensors=result.get("observed_sensors", []),
            history_scope=result.get("limitation"),
            note="Similarity is empirical; compare actual shared-sensor overlap, not causal proof.",
        )
    elif tool == "request_sensor":
        event.update(
            {
                k: result[k]
                for k in (
                    "sensor",
                    "summary",
                    "cached",
                    "remaining_budget",
                    "citation_id",
                    "source_id",
                    "purpose",
                    "scope",
                )
            }
        )
    elif tool == "submit_audit":
        event["assessment"] = result
        event["validation"] = {
            "status": "passed",
            "by": "Python",
            "physical_correctness_verified": False,
        }
    return event


def captured_events(packet, row):
    return (
        [received_event(packet, "captured")]
        + [tool_event(e, "captured") for e in row["audit"]]
        + [
            {
                "kind": "completion",
                "mode": "captured",
                "status": row["status"],
                "reason": row["reason"],
                "title": "Captured investigation completed",
            }
        ]
    )


def request_event(details):
    """Whitelist public request metadata. Never forward submission text/reasoning."""
    from .knowledge import PhysicalKnowledge

    known = {"lookup_knowledge", "search_history", "request_sensor", "submit_audit"}
    tool = details.get("tool")
    event = {
        "kind": "tool_request",
        "mode": "live",
        "tool": tool if tool in known else "unrecognized_tool",
        "sequence": details["audit_sequence"],
        "title": "Actual tool request; awaiting Python result",
    }
    if tool == "lookup_knowledge":
        arguments = details.get("arguments")
        topic = arguments.get("topic") if isinstance(arguments, dict) else None
        facts = PhysicalKnowledge().facts
        topics = (
            {f.subject for f in facts} | {f.object for f in facts} | {"valve_codes"}
        )
        if isinstance(topic, str) and topic in topics:
            event["topic"] = topic
    return event
