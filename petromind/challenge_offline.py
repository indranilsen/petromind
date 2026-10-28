"""Descriptive M3 analysis only; no prompt fitting, parameter selection or API calls."""
from __future__ import annotations

from collections import Counter


def analyze_m3(rows):
    methods = {}
    for method in sorted({r["method"] for r in rows}):
        part = [r for r in rows if r["method"] == method]
        selected = [r["sensor_quality"]["P-PDG"] for r in part if "P-PDG" in r["sensor_quality"]]
        methods[method] = {"cases": len(part), "correct": sum(r["correct"] for r in part),
            "sensor_queries": sum(len(r["sensor_sequence"]) for r in part),
            "unavailable_queries": sum(not q["available"] for r in part for q in r["sensor_quality"].values()),
            "P_PDG_requested": len(selected), "P_PDG_quality": dict(Counter(q["quality_status"] for q in selected)),
            "P_PDG_constant_zero": sum(q["is_constant"] and q["constant_value"] == 0 for q in selected),
            "graph_calls": sum(r["graph_calls"] for r in part),
            "retrieval_calls": sum(r["retrieval_calls"] for r in part)}
    graphrag = [r for r in rows if r["method"] == "graphrag"]
    class7 = [r for r in graphrag if r["true_event"] == 7]
    anchors = []
    for row in class7:
        events = [e for e in row["retrieval_events"] if e["result"].get("matches")]
        labels = [e["result"]["matches"][0]["training_event"] for e in events]
        anchors.append({"case_id": row["case_id"], "prediction": row["prediction"],
                        "nearest_labels_in_query_order": labels,
                        "nearest_2_ever": 2 in labels})
    return {"methods": methods, "class7_graphrag_predictions": dict(Counter(r["prediction"] for r in class7)),
        "class7_retrieval_associations": anchors,
        "observations": ["Budget accounting charges every unique sensor query including unavailable readings",
            "M3 exposes sensor names, not unqueried target availability; no free missingness preview exists",
            "Constant zeros are retained as valid; constant alone does not establish low diagnostic information",
            "Historical distance averages relative median differences over shared available sensors only",
            "Constant-equal channels contribute zero distance; cases with different overlap can have comparable scores"],
        "not_established": ["Why Muse chose a sensor: summaries contain no model intent or private reasoning",
            "Retrieval caused anchoring: temporal association is not a controlled causal experiment",
            "A physical contradiction was ignored: requires domain-grounded review of the readings and interpretations",
            "Unavailable requests were avoidable for this target before the query was made"],
        "scope": "Descriptive analysis of frozen M3, never used to fit M4 prompts or parameters"}
