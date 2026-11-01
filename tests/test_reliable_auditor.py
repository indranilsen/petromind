"""Offline regression fixtures; no real Meta requests or physical certification."""

import json
from copy import deepcopy
from dataclasses import asdict

import httpx
import pandas as pd
import pytest

from petromind.audit import canonical, verify_audit
from petromind.measurements import summarize
from petromind.meta_api import MetaResponsesClient
from petromind.reliable_auditor import (
    EXAMPLES,
    SCOPE_VERSION,
    TARGETS,
    VERSION,
    ActiveAuditSession,
    ScopeAuditSession,
    active_tools,
    run_active_auditor,
    run_scope_auditor,
    scope_tools,
)
from petromind.scope_auditor import ScopeAuditSession as LegacySession


def packet():
    return {
        "claim": "Constructed numerical claim, not an expert diagnosis.",
        "constructed_evaluation_claim": True,
        "observations": {
            s: summarize([1, 2, 3]).to_dict() for s in ["P-PDG", "P-TPT", "ABER-CKGL"]
        },
        "baseline": {"prediction": 9},
        "claimed_values": [],
        "claim_citations": [],
        "scope": "fixture",
    }


def submission(n=None, verdict="SUPPORTED"):
    return {
        "verdict": verdict,
        "findings": [
            {
                "statement": "Recorded P-TPT endpoint increased.",
                "premises": ["First 1, last 3."],
                "basis": "measurement",
                "verdict": verdict,
                "citations": ["measurement:P-TPT"],
                "missing_premise": ""
                if verdict == "SUPPORTED"
                else "No verified discriminating criterion supplied.",
                "next_evidence": deepcopy(EXAMPLES["none"] if n is None else n),
                "justification": "Endpoint comparison only, not proof of cause.",
                "scope": "measured_observation"
                if verdict == "SUPPORTED"
                else "diagnostic_conclusion",
            }
        ],
        "numeric_observations": [{"sensor": "P-TPT", "metric": "delta", "value": 2}],
    }


@pytest.mark.parametrize(
    "n,code,field",
    [
        ({}, "invalid_next_evidence_shape", "next_evidence"),
        (
            {"kind": [], "target": "", "purpose": ""},
            "invalid_next_evidence_type",
            "next_evidence.kind",
        ),
        (
            {"kind": "unknown", "target": "", "purpose": ""},
            "invalid_next_kind",
            "next_evidence.kind",
        ),
        (
            {"kind": "none", "target": "none", "purpose": ""},
            "none_target_must_be_empty",
            "next_evidence.target",
        ),
        (
            {"kind": "none", "target": "", "purpose": "No more evidence"},
            "none_purpose_must_be_empty",
            "next_evidence.purpose",
        ),
        (
            {"kind": "document", "target": "well:made_up", "purpose": "Check"},
            "unknown_next_target",
            "next_evidence.target",
        ),
        (
            {
                "kind": "sensor",
                "target": "knowledge:location:P-TPT",
                "purpose": "Check",
            },
            "unknown_next_target",
            "next_evidence.target",
        ),
        (
            {
                "kind": "no_verified_discriminating_test",
                "target": "9",
                "purpose": "Check",
            },
            "unknown_next_target",
            "next_evidence.target",
        ),
        (
            {"kind": "sensor", "target": "P-TPT", "purpose": "  "},
            "missing_next_purpose",
            "next_evidence.purpose",
        ),
        (
            {"kind": "sensor", "target": "x" * 121, "purpose": "Check"},
            "next_target_too_long",
            "next_evidence.target",
        ),
        (
            {"kind": "sensor", "target": "P-TPT", "purpose": "x" * 351},
            "next_purpose_too_long",
            "next_evidence.purpose",
        ),
    ],
)
def test_specific_safe_errors(n, code, field):
    s = ScopeAuditSession(packet())
    result = s.dispatch("submit_audit", submission(n))
    assert result["error"]["code"] == code
    assert result["error"]["field"] == "findings[0]." + field
    assert s.result is None and s.remaining_budget == 2
    assert verify_audit(s.audit_trail)


@pytest.mark.parametrize("kind", list(EXAMPLES))
def test_valid_recommendation_paths_and_no_coercion(kind):
    s = ScopeAuditSession(packet())
    a = submission(EXAMPLES[kind], "SUPPORTED" if kind == "none" else "NOT_ESTABLISHED")
    before = deepcopy(a)
    r = s.dispatch("submit_audit", a)
    assert "error" not in r and r["contract_version"] == SCOPE_VERSION
    assert r["findings"] == before["findings"] and a == before
    assert not r["physical_correctness_verified"]
    assert s.dispatch("submit_audit", a)["error"]["code"] == "investigation_closed"


def test_rejections_keep_diagnostics_but_never_echo_sensitive_values():
    s = ScopeAuditSession(packet())
    n = {
        "kind": "document",
        "target": "/9/private-well-file",
        "purpose": "secret reasoning and hidden label",
    }
    r = s.dispatch("submit_audit", submission(n))
    e = r["error"]
    assert e["diagnostics"] == {
        "kind": "document",
        "target_is_string": True,
        "target_in_kind_catalog": False,
        "purpose_is_string": True,
        "purpose_nonempty": True,
    }
    assert e["syntax_example"] == EXAMPLES["document"]
    stored = canonical([asdict(a) for a in s.audit_trail])
    assert "/9/private" not in stored and "secret reasoning" not in stored
    assert json.loads(s.audit_trail[-1].arguments_json) == {}


def test_repeat_immediately_stops_and_distinct_repairs_remain_bounded():
    a = submission({"kind": "none", "target": "none", "purpose": ""})
    s = ScopeAuditSession(packet())
    s.dispatch("submit_audit", a)
    s.dispatch("submit_audit", a)
    assert s.stop == "assessment_repeated_invalid_submission"
    assert s.result is None
    s = ScopeAuditSession(packet())
    for i in range(3):
        a["findings"][0]["next_evidence"]["target"] = str(i)
        s.dispatch("submit_audit", a)
    assert s.stop == "assessment_repair_limit" and s.result is None


def test_legacy_validation_unchanged_and_schema_lists_only_public_catalogs():
    bad = submission({"kind": "none", "target": "none", "purpose": ""})
    assert (
        LegacySession(packet()).dispatch("submit_audit", bad)["error"]["field"]
        == "findings[0].next_evidence"
    )
    for schema in (scope_tools(), active_tools()):
        enum = schema[-1]["parameters"]["properties"]["findings"]["items"][
            "properties"
        ]["next_evidence"]["properties"]["target"]["enum"]
        assert set(enum) == {v for values in TARGETS.values() for v in values}


def test_missing_citations_wrong_values_and_scope_still_rejected():
    for change, code in [
        (
            lambda a: a["findings"][0].update(citations=["measurement:QGL"]),
            "unknown_citation",
        ),
        (
            lambda a: a["findings"][0].update(
                missing_premise="Stronger conclusion missing"
            ),
            "scope_mismatch",
        ),
        (
            lambda a: a["numeric_observations"][0].update(value=999),
            "unobserved_or_inexact_value",
        ),
    ]:
        s = ScopeAuditSession(packet())
        a = submission()
        change(a)
        assert s.dispatch("submit_audit", a)["error"]["code"] == code
        assert s.result is None


@pytest.mark.parametrize("active", [False, True])
def test_mock_original_four_lookups_invalid_submission_then_success(
    monkeypatch, active
):
    p = packet()
    a = submission()
    if active:
        frame = pd.DataFrame(
            {sensor: list(range(600)) for sensor in p["observations"]},
            index=pd.date_range("2020", periods=600, freq="s"),
        )
        p["observations"] = {
            sensor: summarize(frame[sensor]).to_dict() for sensor in p["observations"]
        }
        a["numeric_observations"][0]["value"] = 599
        s = ActiveAuditSession(p, frame, history_labels_visible=False)
    else:
        s = ScopeAuditSession(p, history_labels_visible=False)
    bad = deepcopy(a)
    bad["findings"][0]["next_evidence"] = {
        "kind": "none",
        "target": "none",
        "purpose": "",
    }
    actions = [
        ("lookup_knowledge", {"topic": t}) for t in ["P-PDG", "P-TPT", "fault:9"]
    ]
    actions += [
        ("search_history", {}),
        ("submit_audit", bad),
        ("submit_audit", a),
    ]
    calls = []

    def callback(request):
        body = json.loads(request.content)
        text = canonical(body)
        assert "recommendation_targets" in text and "true_event" not in text
        if len(calls) == 5:
            assert (
                "none_target_must_be_empty" in text
                and "findings[0].next_evidence.target" in text
            )
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
        r = (run_active_auditor if active else run_scope_auditor)(s, client)
    finally:
        client.close()
    assert r.status == "completed" and len(calls) == 6
    assert s.result["contract_version"] == (VERSION if active else SCOPE_VERSION)
    assert s.remaining_budget == 2
    assert verify_audit(s.audit_trail)


def test_active_shared_budget_cache_and_hidden_measurements():
    frame = pd.DataFrame(
        {s: list(range(600)) for s in ["P-PDG", "P-TPT", "ABER-CKGL", "T-TPT", "QGL"]},
        index=pd.date_range("2020", periods=600, freq="s"),
    )
    frame["class"] = 109
    p = packet()
    p["observations"] = {s: summarize(frame[s]).to_dict() for s in p["observations"]}
    s = ActiveAuditSession(p, frame)
    assert s.contract_version == VERSION and "T-TPT" not in s.packet["observations"]
    for sensor in ["T-TPT", "QGL", "P-ANULAR"]:
        s.dispatch("lookup_knowledge", {"topic": sensor})
        r = s.dispatch(
            "request_sensor",
            {
                "sensor_name": sensor,
                "source_id": "knowledge:location:" + sensor,
                "purpose": "Inspect measurement, not a proven fault rule.",
            },
        )
    assert r["error"]["code"] == "sensor_budget_exhausted" and s.remaining_budget == 0
    assert (
        "class" not in s.packet["observations"]
        and "P-ANULAR" not in s.packet["observations"]
    )
