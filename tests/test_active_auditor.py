"""Constructed software fixtures, not evidence of live diagnostic efficacy."""

import json
from copy import deepcopy
from dataclasses import asdict

import httpx
import numpy as np
import pandas as pd
import pytest

from petromind.active_auditor import (
    VERSION,
    ActiveAuditSession,
    active_tools,
    run_active_auditor,
)
from petromind.audit import canonical, verify_audit
from petromind.investigation_events import tool_event
from petromind.measurements import summarize
from petromind.meta_api import MetaResponsesClient


@pytest.fixture
def active():
    window = pd.DataFrame(
        {
            "P-PDG": np.arange(600),
            "P-TPT": np.arange(600) + 10,
            "ABER-CKGL": [53.0] * 600,
            "T-TPT": [98765.0] * 600,
            "QGL": [None] * 600,
            "class": [109] * 600,
        },
        index=pd.date_range("2020", periods=600, freq="s"),
    )
    packet = {
        "claim": "Constructed claim only.",
        "constructed_evaluation_claim": True,
        "observations": {
            s: summarize(window[s]).to_dict() for s in ["P-PDG", "P-TPT", "ABER-CKGL"]
        },
        "baseline": {"prediction": 9},
        "claimed_values": [],
        "claim_citations": [],
        "scope": "fixture",
    }
    return ActiveAuditSession(packet, window), packet, window


def query(s, sensor):
    s.dispatch("lookup_knowledge", {"topic": sensor})
    return s.dispatch(
        "request_sensor",
        {
            "sensor_name": sensor,
            "source_id": "knowledge:location:" + sensor,
            "purpose": "Inspect the documented measurement; not a fault-discriminating rule.",
        },
    )


def assessment(sensor="T-TPT"):
    return {
        "verdict": "SUPPORTED",
        "findings": [
            {
                "statement": "Recorded value is constant.",
                "premises": ["Summary constant flag."],
                "basis": "measurement",
                "verdict": "SUPPORTED",
                "citations": ["measurement:" + sensor],
                "missing_premise": "",
                "next_evidence": {"kind": "none", "target": "", "purpose": ""},
                "justification": "Descriptive only.",
                "scope": "measured_observation",
            }
        ],
        "numeric_observations": [
            {"sensor": sensor, "metric": "median", "value": 98765.0}
        ],
    }


def test_source_required_before_charging_and_initial_evidence_private(active):
    s, packet, frame = active
    assert s.remaining_budget == 2 and s.new_sensor_queries == 0
    assert "98765" not in canonical(s.packet) and "class" not in canonical(s.packet)
    a = {
        "sensor_name": "T-TPT",
        "source_id": "knowledge:location:T-TPT",
        "purpose": "Check location.",
    }
    assert s.dispatch("request_sensor", a)["error"]["code"] == "sensor_source_required"
    assert s.remaining_budget == 2 and "T-TPT" not in s.packet["observations"]
    result = query(s, "T-TPT")
    assert result["summary"]["median"] == 98765 and result["remaining_budget"] == 1
    assert result["summary"]["is_constant"] and not result["cached"]
    assert s.dispatch("request_sensor", a)["cached"] and s.remaining_budget == 1
    assert (
        s.packet["baseline"] == packet["baseline"]
        and "T-TPT" not in packet["observations"]
    )
    frame.loc[:, "T-TPT"] = -1
    assert s.dispatch("request_sensor", a)["summary"]["median"] == 98765
    assert verify_audit(s.audit_trail)


def test_missing_costs_query_budget_rejects_sixth_and_cache_free(active):
    s, _, _ = active
    assert query(s, "QGL")["summary"]["available"] is False
    query(s, "T-TPT")
    assert s.remaining_budget == 0 and s.new_sensor_queries == 2
    assert query(s, "P-ANULAR")["error"]["code"] == "sensor_budget_exhausted"
    assert query(s, "P-PDG")["cached"]
    assert s.remaining_budget == 0 and "P-ANULAR" not in s.packet["observations"]
    assert verify_audit(s.audit_trail)


def test_invalid_sensor_and_source_no_sensitive_echo(active):
    s, _, _ = active
    for bad in ("/9/WELL-secret.parquet", [], None):
        r = s.dispatch(
            "request_sensor",
            {"sensor_name": bad, "source_id": "secret", "purpose": "public"},
        )
        assert r["error"]["code"] == "unknown_sensor"
    assert "WELL-secret" not in canonical([asdict(a) for a in s.audit_trail])
    assert s.remaining_budget == 2
    s.dispatch("lookup_knowledge", {"topic": "T-TPT"})
    r = s.dispatch(
        "request_sensor",
        {
            "sensor_name": "QGL",
            "source_id": "knowledge:location:T-TPT",
            "purpose": "public",
        },
    )
    assert r["error"]["code"] == "sensor_source_required"


def test_unqueried_citations_rejected_and_repairs_remain_bounded(active):
    s, _, _ = active
    a = assessment()
    assert s.dispatch("submit_audit", a)["error"]["code"] == "unknown_citation"
    s.dispatch("submit_audit", a)
    assert s.stop == "assessment_repeated_invalid_submission"
    assert query(s, "T-TPT")["error"]["code"] == "investigation_closed"


def test_new_observation_can_be_cited_without_changing_baseline(active):
    s, packet, _ = active
    query(s, "T-TPT")
    result = s.dispatch("submit_audit", assessment())
    assert result["contract_version"] == VERSION and result == s.result
    assert result["physical_correctness_verified"] is False
    assert s.packet["baseline"] == packet["baseline"]
    assert query(s, "QGL")["error"]["code"] == "investigation_closed"


def test_history_remains_initial_snapshot_and_same_overlap(active):
    s, packet, _ = active
    history = [
        {
            "case_id": "a" * 32,
            "training_event": 2,
            "distance": 0.1,
            "shared_sensors": 1,
            "matched_sensors": ["P-PDG"],
        }
    ]
    s._history = history
    query(s, "T-TPT")
    r = s.dispatch("search_history", {})
    assert r["observed_sensors"] == list(packet["observations"])
    assert r["matches"][0]["shared_sensors"] == 1 and "initial" in r["limitation"]
    event = tool_event(asdict(s.audit_trail[-1]), "live")
    assert event["observed_sensors"] == list(packet["observations"])


def test_actual_runner_queries_only_selected_sensor_and_public_events(
    active, monkeypatch
):
    s, _, _ = active
    calls, events = [], []
    actions = [
        ("lookup_knowledge", {"topic": "T-TPT"}),
        (
            "request_sensor",
            {
                "sensor_name": "T-TPT",
                "source_id": "knowledge:location:T-TPT",
                "purpose": "Check temperature at documented tree transducer.",
            },
        ),
        ("submit_audit", assessment()),
    ]

    def callback(request):
        body = json.loads(request.content)
        text = canonical(body)
        assert (
            "viewer_series" not in text
            and "true_event" not in text
            and "109" not in text
        )
        if len(calls) < 2:
            assert "98765" not in text
        name, args = actions[len(calls)]
        calls.append(body)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "error": None,
                "output": [
                    {
                        "type": "function_call",
                        "name": name,
                        "call_id": str(len(calls)),
                        "arguments": canonical(args),
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 10},
            },
        )

    monkeypatch.setenv("MODEL_API_KEY", "mock-only")
    client = MetaResponsesClient(transport=httpx.MockTransport(callback))
    try:
        result = run_active_auditor(
            s, client, on_event=lambda e: events.append((len(calls), e.kind))
        )
    finally:
        client.close()
    assert (
        result.status == "completed" and len(calls) == 3 and s.new_sensor_queries == 1
    )
    assert (2, "tool_result") in events
    assert {t["name"] for t in active_tools()} == {
        "request_sensor",
        "lookup_knowledge",
        "search_history",
        "submit_audit",
    }
    e = tool_event(asdict(s.audit_trail[1]), "live")
    assert (
        e["sensor"] == "T-TPT"
        and e["remaining_budget"] == 1
        and e["summary"]["median"] == 98765
    )
    assert verify_audit(s.audit_trail)


def test_initial_summary_mismatch_fails_closed(active):
    _, packet, frame = active
    wrong = deepcopy(packet)
    wrong["observations"]["P-PDG"]["median"] = -1
    with pytest.raises(ValueError, match="differs"):
        ActiveAuditSession(wrong, frame)


@pytest.mark.parametrize(
    "reading,quality",
    [
        (None, "missing"),
        (float("inf"), "invalid"),
        (1e13, "invalid"),
        (0.0, "constant"),
    ],
)
def test_extra_measurement_quality_and_zero_are_preserved(active, reading, quality):
    _, packet, window = active
    window["T-TPT"] = reading
    s = ActiveAuditSession(packet, window)
    r = query(s, "T-TPT")
    assert r["summary"]["quality_status"] == quality
    assert s.remaining_budget == 1
    if reading == 0:
        assert r["summary"]["available"] and r["summary"]["median"] == 0


def test_concurrent_repeat_charges_only_once(active):
    from concurrent.futures import ThreadPoolExecutor

    s, _, _ = active
    s.dispatch("lookup_knowledge", {"topic": "T-TPT"})
    args = {
        "sensor_name": "T-TPT",
        "source_id": "knowledge:location:T-TPT",
        "purpose": "Inspect temperature.",
    }
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(lambda _: s.dispatch("request_sensor", args), range(8)))
    assert sum(not r["cached"] for r in rows) == 1
    assert s.new_sensor_queries == 1 and s.remaining_budget == 1
    assert verify_audit(s.audit_trail)
