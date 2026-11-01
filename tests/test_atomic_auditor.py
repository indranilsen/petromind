"""Public live006 findings reused as immutable regression inputs, not regraded runs."""

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict
from itertools import product
from pathlib import Path

import httpx
import pytest

from petromind.atomic_auditor import (
    ATOMIC_VERDICTS,
    SCOPE_VERSION,
    ScopeAuditSession,
    active_tools,
    aggregate_verdict,
    run_scope_auditor,
)
from petromind.audit import canonical, verify_audit
from petromind.meta_api import MetaResponsesClient
from petromind.reliable_auditor import ScopeAuditSession as V4Session

FIXTURE = Path(__file__).parent / "fixtures/live006-public-assessment.json"


def public_fixture():
    return json.loads(FIXTURE.read_text())


def packet():
    return {
        "claim": "Constructed claim: measured pressure rises establish service-line hydrate.",
        "constructed_evaluation_claim": True,
        "observations": public_fixture()["observations"],
        "baseline": {"prediction": 9},
        "claimed_values": [],
        "claim_citations": [],
        "scope": "Public regression input; not a new live investigation.",
    }


def session(cls=ScopeAuditSession):
    s = cls(packet(), history_labels_visible=False)
    for topic in ("P-PDG", "P-TPT", "fault:9"):
        s.dispatch("lookup_knowledge", {"topic": topic})
    return s


def atomic_copy():
    # Expected future contract input, never written back as a live result.
    a = deepcopy(public_fixture()["recorded_assessment"])
    for key in (
        "contract_version",
        "independent_review_required",
        "physical_correctness_verified",
    ):
        a.pop(key)
    a["findings"][-1]["verdict"] = "NOT_ESTABLISHED"
    return a


def original_submission():
    a = atomic_copy()
    a["findings"][-1]["verdict"] = "PARTIALLY_SUPPORTED"
    return a


def test_actual_public_findings_aggregate_without_partial_atomic_finding():
    before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    a = atomic_copy()
    s = session()
    r = s.dispatch("submit_audit", a)
    assert "error" not in r and r["contract_version"] == SCOPE_VERSION
    assert r["verdict"] == "PARTIALLY_SUPPORTED"
    assert [f["verdict"] for f in r["findings"]] == ["SUPPORTED"] * 3 + [
        "NOT_ESTABLISHED"
    ]
    assert r["findings"] == a["findings"] and s.remaining_budget == 2
    assert not r["physical_correctness_verified"] and r["independent_review_required"]
    assert verify_audit(s.audit_trail)
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == before
    assert (
        public_fixture()["recorded_assessment"]["findings"][-1]["verdict"]
        == "PARTIALLY_SUPPORTED"
    )


def test_v4_still_accepts_original_and_rejects_new_aggregation():
    assert "error" not in session(V4Session).dispatch(
        "submit_audit", original_submission()
    )
    assert (
        session(V4Session).dispatch("submit_audit", atomic_copy())["error"]["code"]
        == "inconsistent_verdict"
    )
    r = session().dispatch("submit_audit", original_submission())
    assert r["error"]["code"] == "atomic_verdict_required"
    assert r["error"]["field"] == "findings[3].verdict"


@pytest.mark.parametrize("verdicts", list(product(ATOMIC_VERDICTS, repeat=3)))
def test_declared_conjunction_aggregation(verdicts):
    expected = (
        "CONTRADICTED"
        if "CONTRADICTED" in verdicts
        else (
            "SUPPORTED"
            if set(verdicts) == {"SUPPORTED"}
            else "NOT_ESTABLISHED"
            if set(verdicts) == {"NOT_ESTABLISHED"}
            else "PARTIALLY_SUPPORTED"
        )
    )
    assert aggregate_verdict(verdicts) == expected


@pytest.mark.parametrize("verdicts", [[], ["PARTIALLY_SUPPORTED"], ["unknown"]])
def test_aggregate_invalid_inputs_rejected(verdicts):
    with pytest.raises(ValueError):
        aggregate_verdict(verdicts)


def test_incorrect_overall_rejected_without_changing_findings():
    a = atomic_copy()
    a["verdict"] = "SUPPORTED"
    before = deepcopy(a)
    s = session()
    r = s.dispatch("submit_audit", a)
    assert r["error"]["code"] == "inconsistent_overall_verdict"
    assert "PARTIALLY_SUPPORTED" in r["error"]["correction"]
    assert a == before and s.result is None


@pytest.mark.parametrize(
    "citations,basis",
    [
        (["knowledge:example:8:P-PDG", "knowledge:example:8:P-TPT"], "documented"),
        (["measurement:P-PDG", "measurement:P-TPT"], "measurement"),
        (["knowledge:fault:9:equipment", "knowledge:fault:9:mechanism"], "documented"),
    ],
)
def test_no_example_measurement_or_mechanism_proves_fault9(citations, basis):
    a = atomic_copy()
    a["verdict"] = "SUPPORTED"
    f = a["findings"][-1]
    f.update(
        verdict="SUPPORTED",
        basis=basis,
        citations=citations,
        missing_premise="",
        next_evidence={"kind": "none", "target": "", "purpose": ""},
    )
    s = session()
    result = s.dispatch("submit_audit", a)
    assert result["error"]["code"] == "verified_causal_rule_unavailable"
    assert s.result is None


@pytest.mark.parametrize(
    "mutation,code",
    [
        (
            lambda a: a["findings"][0].update(citations=["measurement:QGL"]),
            "unknown_citation",
        ),
        (lambda a: a["findings"][0].update(citations=[]), "missing_evidence"),
        (lambda a: a["findings"][3].update(missing_premise=""), "missing_gap"),
        (
            lambda a: a["numeric_observations"][0].update(value=-1),
            "unobserved_or_inexact_value",
        ),
        (lambda a: a["findings"][2].update(basis="hypothesis"), "scope_basis_mismatch"),
    ],
)
def test_integrity_and_scope_checks_preserved(mutation, code):
    a = atomic_copy()
    mutation(a)
    s = session()
    assert s.dispatch("submit_audit", a)["error"]["code"] == code
    assert s.result is None


def test_repeat_and_distinct_repairs_do_not_turn_invalid_into_abstention():
    a = original_submission()
    s = session()
    s.dispatch("submit_audit", a)
    s.dispatch("submit_audit", a)
    assert s.stop == "assessment_repeated_invalid_submission" and s.result is None
    s = session()
    for i in range(3):
        a["findings"][0]["statement"] += str(i)
        s.dispatch("submit_audit", a)
    assert s.stop == "assessment_repair_limit" and s.result is None
    assert s.remaining_budget == 2 and verify_audit(s.audit_trail)


def test_schema_keeps_global_partial_but_forbids_atomic_partial():
    schema = active_tools()[-1]["parameters"]["properties"]
    assert "PARTIALLY_SUPPORTED" in schema["verdict"]["enum"]
    assert (
        "PARTIALLY_SUPPORTED"
        not in schema["findings"]["items"]["properties"]["verdict"]["enum"]
    )
    assert set(schema["findings"]["items"]["properties"]) == {
        "statement",
        "premises",
        "basis",
        "verdict",
        "citations",
        "missing_premise",
        "next_evidence",
        "justification",
        "scope",
    }


def test_mock_real_public_findings_corrected_without_causal_upgrade(monkeypatch):
    s = ScopeAuditSession(packet(), history_labels_visible=False)
    actions = [
        ("lookup_knowledge", {"topic": t}) for t in ["P-PDG", "P-TPT", "fault:9"]
    ]
    actions += [
        ("submit_audit", original_submission()),
        ("submit_audit", atomic_copy()),
    ]
    bodies = []

    def callback(request):
        body = json.loads(request.content)
        assert "ATOMIC SCOPE CONTRACT v5" in body["instructions"]
        assert "true_event" not in canonical(body) and "viewer_series" not in canonical(
            body
        )
        name, args = actions[len(bodies)]
        bodies.append(body)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "error": None,
                "output": [
                    {
                        "type": "function_call",
                        "name": name,
                        "call_id": str(len(bodies)),
                        "arguments": canonical(args),
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 10},
            },
        )

    monkeypatch.setenv("MODEL_API_KEY", "mock-only")
    client = MetaResponsesClient(transport=httpx.MockTransport(callback))
    try:
        result = run_scope_auditor(s, client)
    finally:
        client.close()
    assert result.status == "completed" and len(bodies) == 5
    assert s.result["findings"][-1]["verdict"] == "NOT_ESTABLISHED"
    assert s.result["contract_version"] == SCOPE_VERSION
    assert "atomic_verdict_required" in canonical(bodies[-1])
    assert verify_audit(s.audit_trail)
    rejected = next(e for e in s.audit_trail if '"error"' in e.result_json)
    assert json.loads(rejected.arguments_json) == {}
    assert "true_event" not in canonical([asdict(e) for e in s.audit_trail])
