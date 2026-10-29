"""Read-only mechanical review and public demo projection of the captured pilot."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from .claim_evaluation import checked_protocol, verify_result
from .eval_protocol import digest
from .eval_runner import read_jsonl

CAPTURE_PROTOCOL = "58e8c6ba429a46730434f5b1b91b112c0ca7fd7b0e733fa3806b71c473bb6b84"
CAPTURE_ROWS_DIGEST = "e6d9bd1da4c69e4a52801186aa2561c95e717e99399edc5bf92e24e1fb767eac"
TASKS = ("fault_expectation", "published_example_consistency")

# Editorial annotations of these specific captured findings, never model output
# or a certification of their physical interpretation.
NOTES = {
    ("fault_expectation", "ungrounded"): [
        (
            "measured",
            "Endpoints and 600 valid samples establish an end-to-end increase; not monotonicity or cause.",
        ),
        (
            "measured",
            "Endpoints establish an end-to-end increase, not a hydrate diagnosis.",
        ),
        (
            "compatible_not_proven",
            "A supported observation does not establish the diagnostic conclusion. PARTIALLY_SUPPORTED applies to the mixed claim, not proof of fault 9.",
        ),
        (
            "missing_premise",
            "The retrieved record contains no necessary/sufficient fault-9 pressure criterion. Absence here is not proof no such engineering criterion exists.",
        ),
    ],
    ("fault_expectation", "grounded"): [
        (
            "measured",
            "The recorded delta is +291760 Pa. Quality metadata does not certify instrumentation correctness.",
        ),
        (
            "measured",
            "The recorded delta is +332220 Pa. Two endpoint increases do not establish a universal physical rule.",
        ),
        (
            "documentation_limit",
            "Fault-9 mechanism/location documentation does not state a necessary pressure response.",
        ),
        (
            "overlap_caution",
            "Historical overlap is unequal: event 9 matches three sensors; event 8 matches three sensors and one sensor. These are not equally corroborated comparisons.",
        ),
        (
            "scope",
            "The whole constructed claim mixes measured trends and an unestablished causal inference. Preserve that distinction.",
        ),
    ],
    ("published_example_consistency", "ungrounded"): [
        ("measured", "The endpoint increase is directly checkable."),
        ("measured", "The endpoint decrease is directly checkable."),
        (
            "reasonable_uncertainty",
            "The ungrounded condition did not receive the example. Withholding documentary verification is reasonable, not a false physical rejection.",
        ),
        (
            "scope",
            "The caution against claiming root cause is broader than a numeric check and still requires semantic review.",
        ),
    ],
    ("published_example_consistency", "grounded"): [
        (
            "measured",
            "Calibration matters to actual physical pressure; it is not needed merely to report the recorded endpoint values.",
        ),
        (
            "measured",
            "Recorded endpoints support a decrease; they do not establish monotonic decline or root cause.",
        ),
        (
            "documented_comparison",
            "The two recorded directions match the two cited published-example directions. Generalizability/specificity would be needed for a stronger diagnosis, not for this narrow comparison.",
        ),
        (
            "scope",
            "The source is an illustrative published example. A training analogue is not additional causal proof; no actual valve-state measurement was supplied.",
        ),
    ],
}

ACTIONS = {
    "fault_expectation": [
        {
            "kind": "DOCUMENT",
            "target": "Well-specific service-line schematic and sensor tag map",
            "purpose": "Check whether the proposed physical pathway applies to these measurement locations.",
            "status": "Not supplied. This alone cannot establish fault 9.",
        },
        {
            "kind": "DOCUMENT",
            "target": "Validated operating procedure distinguishing service-line hydrate from competing causes",
            "purpose": "Supply the missing necessity/specificity premise, if such a validated criterion exists.",
            "status": "Not supplied; its existence and adequacy are not verified.",
        },
        {
            "kind": "NO VERIFIED DISCRIMINATING TEST",
            "target": "Fault 9 versus competing causes",
            "purpose": "No source-backed discriminating test is available in this knowledge registry.",
            "status": "Do not invent a test or imply another pressure reading would resolve root cause.",
        },
    ],
    "published_example_consistency": [
        {
            "kind": "NO ADDITIONAL EVIDENCE FOR THIS CLAIM",
            "target": "Published example / Figure 3",
            "purpose": "Recorded directions and the retrieved caption establish this narrow directional comparison.",
            "status": "Source comparison only; independent engineering review remains pending.",
        },
        {
            "kind": "ONLY FOR A STRONGER CAUSAL CLAIM",
            "target": "Well-specific DHSV tag mapping and time-aligned valve-state / operating log",
            "purpose": "Check the actual valve state and operational context before interpreting a closure hypothesis.",
            "status": "Not supplied. Not required to say that two recorded directions match the example; not sufficient by itself to prove root cause.",
        },
    ],
}


def load_capture(directory):
    directory = Path(directory)
    p = json.loads((directory / "protocol.json").read_text())
    checked_protocol(p)
    if p["protocol_id"] != CAPTURE_PROTOCOL:
        raise ValueError(
            "This reviewed replay requires the unchanged claim-audit-v1 capture"
        )
    rows = read_jsonl(directory / "results.jsonl")
    expected = {(t, m) for t in TASKS for m in ("checker", "ungrounded", "grounded")}
    if len(rows) != 6 or {(r["task_id"], r["method"]) for r in rows} != expected:
        raise ValueError("Expected the six original completed pilot records")
    if digest(rows) != CAPTURE_ROWS_DIGEST:
        raise ValueError("Captured outputs differ from the reviewed original")
    tasks = {t["task_id"]: t for t in p["tasks"]}
    for row in rows:
        if row["protocol_id"] != p["protocol_id"] or row["status"] != "completed":
            raise ValueError("Replay requires successful original records")
        verify_result(row, tasks[row["task_id"]], p)
        if row["method"] != "checker" and len(row["result"]["findings"]) != len(
            NOTES[(row["task_id"], row["method"])]
        ):
            raise ValueError("Captured finding structure changed")
    return p, rows


def source_context(row):
    sources = {}
    for a in row["audit"]:
        r = json.loads(a["result_json"])
        for f in r.get("facts", []):
            sources[f["citation_id"]] = f
        for f in r.get("matches", []):
            sources[f["citation_id"]] = f
    return sources


def review_capture(directory):
    p, rows = load_capture(directory)
    review = []
    for r in rows:
        if r["method"] == "checker":
            continue
        for i, f in enumerate(r["result"]["findings"]):
            category, note = NOTES[(r["task_id"], r["method"])][i]
            review.append(
                {
                    "id": f"{r['task_id']}:{r['method']}:{i + 1}",
                    "statement": f["statement"],
                    "captured_verdict": f["verdict"],
                    "finding_digest": digest(f),
                    "source_ids": f["citations"],
                    "mechanically_received_citations": True,
                    "review_category": category,
                    "editorial_note": note,
                    "physical_correctness": None,
                    "engineering_review_required": True,
                }
            )
    return {
        "source_protocol_id": p["protocol_id"],
        "review_version": "claim-level-review-v1",
        "findings": review,
        "numeric_values_checked": sum(
            len(r["result"]["numeric_observations"])
            for r in rows
            if r["method"] != "checker"
        ),
        "citation_occurrences_checked": sum(
            len(f["citations"])
            for r in rows
            if r["method"] != "checker"
            for f in r["result"]["findings"]
        ),
        "repairs": sum(
            "error" in json.loads(a["result_json"]) for r in rows for a in r["audit"]
        ),
        "independent_engineering_review": False,
        "api_requests": 0,
        "limitations": [
            "Mechanical checks validate captured summaries, not raw sensor calibration or full time series.",
            "Training membership cannot be independently recomputed here without the raw dataset.",
            "Editorial notes are source/logic review, not an independent engineering sign-off.",
        ],
    }


def demo_cases(directory):
    p, rows = load_capture(directory)
    tasks = {t["task_id"]: t for t in p["tasks"]}
    cases = []
    for task_id in TASKS:
        audits = {
            r["method"]: r
            for r in rows
            if r["task_id"] == task_id and r["method"] != "checker"
        }
        packet = deepcopy(tasks[task_id]["packet"])
        for r in audits.values():
            # Explicit public projection: original result is unchanged.
            r["public_sources"] = source_context(r)
        cases.append(
            {
                "id": task_id,
                "title": "The pressure rise that does not prove hydrate"
                if task_id == TASKS[0]
                else "A match is not a root cause",
                "packet": packet,
                "observations": packet["observations"],
                "audits": {
                    method: {
                        "output": r["result"],
                        "sources": r["public_sources"],
                        "requests": r["requests"],
                        "usage": r["usage"],
                        "latency_seconds": r["latency_seconds"],
                        "contract_version": r["result"]["contract_version"],
                        "notes": [
                            {"category": cat, "text": note}
                            for cat, note in NOTES[(task_id, method)]
                        ],
                    }
                    for method, r in audits.items()
                },
                "reviewed_actions": deepcopy(ACTIONS[task_id]),
                "actions_attribution": "Editorial source/logic review; not new Muse output or engineering certification.",
                "source_protocol_id": p["protocol_id"],
                "source_digest": digest(audits["grounded"]["result"]),
                "remaining_budget": 5 - len(packet["observations"]),
                "review_status": "Independent engineering review pending",
            }
        )
    return cases
