"""Toy numbers test contracts only; no mocked output is a capability result."""

import hashlib
import json
from dataclasses import asdict

import httpx
import pytest

from petromind.audit import AuditEntry, canonical, verify_audit
from petromind.claim_auditor import (
    ClaimAuditSession,
    citation_checker,
    run_auditor,
    tools,
)
from petromind.claim_evaluation import (
    analyze,
    load_captured,
    offline_check,
    pilot,
    prepare,
)
from petromind.eval_protocol import digest
from petromind.measurements import summarize
from petromind.meta_api import MetaAPIError, MetaResponsesClient


@pytest.fixture
def packet():
    return {
        "claim": "P-TPT rose, therefore hydrate is proved.",
        "constructed_evaluation_claim": True,
        "observations": {"P-TPT": summarize([1, 2, 3]).to_dict()},
        "baseline": {
            "prediction": 9,
            "confidence_calibrated": False,
            "probabilities": [],
        },
        "claimed_values": [{"sensor": "P-TPT", "metric": "delta", "value": 2}],
        "claim_citations": ["measurement:P-TPT"],
        "scope": "test fixture",
    }


def submission(verdict="NOT_ESTABLISHED", citations=("measurement:P-TPT",)):
    return {
        "verdict": verdict,
        "findings": [
            {
                "statement": "The pressure trend alone does not establish hydrate.",
                "premises": [
                    "P-TPT rose.",
                    "A sufficient causal criterion has not been supplied.",
                ],
                "basis": "unsupported",
                "verdict": verdict,
                "citations": list(citations),
                "missing_premise": "A validated criterion distinguishing alternative causes.",
                "next_evidence": "Obtain a validated diagnostic criterion and its applicability to these tags.",
                "justification": "An observed trend is not by itself a root-cause test.",
            }
        ],
        "numeric_observations": [{"sensor": "P-TPT", "metric": "delta", "value": 2}],
    }


@pytest.mark.parametrize(
    "verdict", ["SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_ESTABLISHED", "CONTRADICTED"]
)
def test_all_verdict_paths_and_no_physical_certification(packet, verdict):
    s = ClaimAuditSession(packet)
    result = s.dispatch("submit_audit", submission(verdict))
    assert (
        result["verdict"] == verdict
        and result["physical_correctness_verified"] is False
    )
    assert verify_audit(s.audit_trail)
    assert (
        s.dispatch("submit_audit", submission())["error"]["code"]
        == "investigation_closed"
    )


def test_missing_citation_is_not_automatic_falsity(packet):
    s = ClaimAuditSession(packet)
    assert (
        s.dispatch("submit_audit", submission(citations=()))["verdict"]
        == "NOT_ESTABLISHED"
    )
    s = ClaimAuditSession(packet)
    assert (
        s.dispatch("submit_audit", submission("CONTRADICTED", ()))["error"]["code"]
        == "missing_evidence"
    )
    assert s.result is None


@pytest.mark.parametrize(
    "sensor,metric,value",
    [
        ("P-PDG", "delta", 2),
        ("P-TPT", "delta", 3),
        ("P-TPT", "available", 1),
        ("P-TPT", "median", float("inf")),
    ],
)
def test_unobserved_wrong_and_nonfinite_values_rejected(packet, sensor, metric, value):
    s = ClaimAuditSession(packet)
    a = submission()
    a["numeric_observations"] = [{"sensor": sensor, "metric": metric, "value": value}]
    # Nonfinite payloads are rejected by the runner JSON decoder; direct validation must reject too.
    assert s._validate(a)[0] == "unobserved_or_inexact_value"


def test_repair_limit_duplicate_and_sanitized_diagnostics(packet):
    s = ClaimAuditSession(packet)
    a = submission()
    a["findings"][0]["citations"] = ["secret/fault-7.csv"]
    s.dispatch("submit_audit", a)
    s.dispatch("submit_audit", a)
    assert s.stop == "assessment_repeated_invalid_submission" and s.result is None
    assert "secret" not in canonical([asdict(e) for e in s.audit_trail])
    s = ClaimAuditSession(packet)
    for i in range(3):
        a = submission()
        a["findings"][0]["citations"] = [str(i)]
        s.dispatch("submit_audit", a)
    assert s.stop == "assessment_repair_limit" and s.result is None


def test_provenance_requires_context_actually_retrieved(packet):
    s = ClaimAuditSession(packet)
    a = submission()
    a["findings"][0]["citations"] = ["knowledge:valve:1"]
    assert s.dispatch("submit_audit", a)["error"]["code"] == "unknown_citation"
    facts = s.dispatch("lookup_knowledge", {"topic": "valve_codes"})["facts"]
    assert next(f for f in facts if f["id"] == "valve:1")["object"] == "open"
    assert all(f["provenance"] and f["locator"] and f["scope"] for f in facts)
    assert s.dispatch("submit_audit", a)["verdict"] == "NOT_ESTABLISHED"
    assert s.remaining_budget == 4


def test_no_unqueried_readings_hidden_metadata_or_old_tool_paths(packet):
    packet["true_event"] = 7
    packet["filename"] = "7/WELL-SECRET.parquet"
    s = ClaimAuditSession(packet)
    assert "true_event" not in s.packet and "WELL-SECRET" not in canonical(s.packet)
    for name in [
        "get_sensor_history",
        "submit_diagnosis",
        "submit_assessment",
        "execute_test",
    ]:
        assert (
            s.dispatch(name, {"sensor_name": "P-PDG"})["error"]["code"]
            == "tool_not_available"
        )
    assert s.remaining_budget == 4
    assert s.dispatch("lookup_knowledge", {"topic": "P-PDG"})[
        "facts"
    ]  # metadata, never its reading
    assert "P-PDG" not in s.packet["observations"]


def test_grounded_and_ungrounded_same_evidence_and_small_contract(packet):
    a, b = ClaimAuditSession(packet, grounded=False), ClaimAuditSession(packet)
    assert a.packet == b.packet and a.remaining_budget == b.remaining_budget
    assert [t["name"] for t in tools(False)] == ["submit_audit"]
    assert len(tools(True)) == 3
    assert (
        a.dispatch("lookup_knowledge", {"topic": "valve_codes"})["error"]["code"]
        == "tool_not_available"
    )
    assert a.dispatch("search_history", {})["error"]["code"] == "tool_not_available"


def test_history_is_observed_only_sanitized_and_not_proof(packet):
    history = [
        {
            "case_id": "a" * 32,
            "training_event": 2,
            "distance": 0.1,
            "shared_sensors": 1,
            "matched_sensors": ["P-TPT"],
        }
    ]
    s = ClaimAuditSession(packet, history=history)
    r = s.dispatch("search_history", {})
    assert (
        r["matches"][0]["citation_id"] == "analogue:0"
        and "not causal" in r["limitation"]
    )
    assert s.remaining_budget == 4
    history[0]["matched_sensors"] = ["P-PDG"]
    with pytest.raises(ValueError):
        ClaimAuditSession(packet, history=history)
    history[0]["filename"] = "2/secret.parquet"
    with pytest.raises(ValueError):
        ClaimAuditSession(packet, history=history)


def test_missing_and_zero_are_distinct_and_checker_is_honest(packet):
    packet["observations"]["P-TPT"] = summarize([0, 0, 0]).to_dict()
    packet["claimed_values"][0]["value"] = 0
    assert citation_checker(packet)["numeric_checks"][0]["matches"]
    packet["observations"]["P-TPT"] = summarize([None, None, None]).to_dict()
    r = citation_checker(packet)
    assert not r["numeric_checks"][0]["matches"] and r["verdict"] == "UNASSESSED"


def test_malformed_enums_and_unknown_topics_do_not_crash(packet):
    s = ClaimAuditSession(packet)
    a = submission()
    a["findings"][0]["basis"] = []
    assert s.dispatch("submit_audit", a)["error"]["code"] == "invalid_enum"
    assert (
        s.dispatch("lookup_knowledge", {"topic": []})["error"]["code"]
        == "unknown_topic"
    )
    for i in range(9):
        s.dispatch("lookup_knowledge", {"topic": "P-TPT"})
    assert (
        s.dispatch("lookup_knowledge", {"topic": "P-TPT"})["error"]["code"]
        == "context_limit"
    )


def fake_capture(root):
    """Synthetic unit fixture, deliberately unlike a scientific benchmark result."""
    root.mkdir()
    group = lambda w: hashlib.sha256(w.encode()).hexdigest()
    parent = {
        "retrieval_split": {"train_wells": ["fit"], "test_wells": ["dev", "test"]},
        "development_wells": ["dev"],
        "original_split": {"train_wells": ["fit", "dev"], "test_wells": ["test"]},
        "records": [
            {"case_id": c, "role": "development_pool", "well_group": group("dev")}
            for c in ("a" * 32, "b" * 32)
        ],
    }
    parent["protocol_id"] = digest(parent)
    p = {"parent": parent, "case_ids": ["a" * 32, "b" * 32]}
    p["protocol_id"] = digest(p)
    (root / "protocol.json").write_text(canonical(p))
    (root / "traces").mkdir()
    rows = []
    for c, pt, aber in [
        ("a" * 32, [1, 2, 3], [53] * 3),
        ("b" * 32, [3, 2, 1], [None] * 3),
    ]:
        summaries = {
            s: summarize(v).to_dict()
            for s, v in {"ABER-CKGL": aber, "P-TPT": pt, "P-PDG": [1, 2, 3]}.items()
        }
        entries = []
        for s, v in summaries.items():
            entries.append(
                AuditEntry.create(
                    len(entries) + 1,
                    "get_sensor_history",
                    {"sensor_name": s},
                    {
                        "sensor": s,
                        "summary": v,
                        "cached": False,
                        "remaining_budget": 5 - len(entries) - 1,
                    },
                    entries[-1].digest if entries else "0" * 64,
                )
            )
        row = {
            "case_id": c,
            "method": "muse_physical",
            "status": "completed",
            "protocol_id": p["protocol_id"],
            "audit_digest": entries[-1].digest,
            "sensor_quality": summaries,
            "sensor_sequence": list(summaries),
            "initial_hypothesis": {"prediction": 9, "probabilities": []},
            "true_event": 5,
            "filename": "5/SECRET",
        }
        rows.append(row)
        (root / "traces" / (c + ".jsonl")).write_text(
            canonical(
                {
                    "kind": "task_started",
                    "case_id": c,
                    "method": "muse_physical",
                    "protocol_id": p["protocol_id"],
                }
            )
            + "\n"
            + canonical(
                {"kind": "audit_snapshot", "entries": [asdict(a) for a in entries]}
            )
            + "\n"
        )
    (root / "results.jsonl").write_text("".join(canonical(r) + "\n" for r in rows))
    return root


def test_freeze_from_verified_capture_no_labels_and_offline_checker(tmp_path):
    src = fake_capture(tmp_path / "source")
    out = tmp_path / "out"
    r = prepare(src, out)
    assert r["tasks"] == 8 and not r["historical_retrieval_enabled"]
    p = json.loads((out / "protocol.json").read_text())
    for t in p["tasks"]:
        assert "true_event" not in canonical(t["packet"]) and "SECRET" not in canonical(
            t["packet"]
        )
    assert len(offline_check(out)["results"]) == 8
    assert analyze(out)["gate"] == "PENDING"
    with pytest.raises(ValueError):
        prepare(src, out)
    p["tasks"][0]["packet"]["claim"] = "modified"
    (out / "protocol.json").write_text(canonical(p))
    with pytest.raises(ValueError):
        offline_check(out)


def test_capture_rejects_forged_observations_audits_and_test_membership(tmp_path):
    src = fake_capture(tmp_path / "source")
    path = src / "results.jsonl"
    original = path.read_text()
    rows = [json.loads(l) for l in original.splitlines()]
    rows[0]["sensor_quality"]["P-TPT"]["median"] = 100
    path.write_text("".join(canonical(r) + "\n" for r in rows))
    with pytest.raises(ValueError, match="mismatch"):
        load_captured(src)
    path.write_text(original)
    p = json.loads((src / "protocol.json").read_text())
    p["parent"]["records"][0]["well_group"] = hashlib.sha256(b"test").hexdigest()
    p["parent"].pop("protocol_id")
    p["parent"]["protocol_id"] = digest(p["parent"])
    p.pop("protocol_id")
    p["protocol_id"] = digest(p)
    (src / "protocol.json").write_text(canonical(p))
    with pytest.raises(ValueError):
        load_captured(src)


def mock_factory(monkeypatch, callback):
    monkeypatch.setenv("MODEL_API_KEY", "unit-test-not-real")

    def factory(**kwargs):
        return MetaResponsesClient(**kwargs, transport=httpx.MockTransport(callback))

    return factory


def response(name, args, n=1):
    return httpx.Response(
        200,
        json={
            "status": "completed",
            "error": None,
            "output": [
                {
                    "type": "function_call",
                    "call_id": f"call{n}",
                    "name": name,
                    "arguments": canonical(args),
                }
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 10,
                "input_tokens_details": {"cached_tokens": 0},
            },
        },
    )


def test_mocked_agent_decomposes_retrieves_submits_without_labels(packet, monkeypatch):
    received = []

    def callback(request):
        body = json.loads(request.content)
        received.append(body)
        if len(received) == 1:
            return response("lookup_knowledge", {"topic": "fault:9"})
        return response("submit_audit", submission(), 2)

    factory = mock_factory(monkeypatch, callback)
    client = factory(max_requests=3, max_output_budget=12288)
    try:
        s = ClaimAuditSession(packet)
        r = run_auditor(s, client)
    finally:
        client.close()
    assert (
        r.status == "completed"
        and r.requests == 2
        and s.result["verdict"] == "NOT_ESTABLISHED"
    )
    assert all("true_event" not in canonical(p) for p in received)
    assert verify_audit(s.audit_trail)


def test_no_key_before_intents_and_cost_cap_before_http(tmp_path, monkeypatch):
    out = tmp_path / "out"
    prepare(fake_capture(tmp_path / "source"), out, max_cost=0.000001)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with pytest.raises(MetaAPIError, match="missing_or_invalid_api_key"):
        pilot(out)
    assert not (out / "traces").exists()
    calls = []
    factory = mock_factory(monkeypatch, lambda r: calls.append(r))
    report = pilot(out, client_factory=factory)
    assert calls == [] and report["gate"] == "PENDING"
    assert report["summary"]["grounded"]["completed"] == 0


def test_mock_pilot_no_auto_expansion_review_gate_and_tamper(tmp_path, monkeypatch):
    out = tmp_path / "out"
    prepare(fake_capture(tmp_path / "source"), out)

    def callback(request):
        body = json.loads(request.content)
        # This is a fabricated contract-test response, never evidence of Muse capability.
        context = json.loads(body["input"][0]["content"][0]["text"])
        a = submission()
        a["numeric_observations"][0]["value"] = context["observations"]["P-TPT"][
            "delta"
        ]
        return response("submit_audit", a)

    factory = mock_factory(monkeypatch, callback)
    r = pilot(out, client_factory=factory)
    assert r["api_requests"] == 4 and r["gate"] == "PENDING"
    assert r["summary"]["grounded"]["unsupported_auditor_claims"] is None
    assert len((out / "results.jsonl").read_text().splitlines()) == 6
    assert pilot(out, client_factory=factory)["api_requests"] == 4
    reviews = json.loads((out / "review-template.json").read_text())
    with pytest.raises(ValueError):
        analyze(out, reviews)
    for x in reviews:
        x.update(
            reviewer="Synthetic test reviewer",
            independent_engineering_review=True,
            verdict_correct=False,
            missing_premise_correct=False,
            next_evidence_specific_and_sufficient=False,
            value_beyond_checker=False,
            unsupported_auditor_claims=1,
            rationale="Unit-test failure fixture, not an actual review.",
        )
    assert analyze(out, reviews)["gate"] == "NARROW_SCOPE"
    reviews[0]["output_digest"] = "invalid"
    with pytest.raises(ValueError):
        analyze(out, reviews)
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text().splitlines()]
    next(x for x in rows if x["method"] == "grounded")["result"]["verdict"] = (
        "SUPPORTED"
    )
    (out / "results.jsonl").write_text("".join(canonical(x) + "\n" for x in rows))
    with pytest.raises(ValueError):
        analyze(out)


def test_prepare_materializes_training_only_history_without_unobserved_values(
    tmp_path, monkeypatch, training, split
):
    src = fake_capture(tmp_path / "source")
    out = tmp_path / "out"
    monkeypatch.setattr(
        "petromind.grounding_offline.load_development_cohort",
        lambda *_: (split, {}, training),
    )
    result = prepare(src, out, dataset=tmp_path / "unused")
    assert result["historical_retrieval_enabled"]
    p = json.loads((out / "protocol.json").read_text())
    task = p["tasks"][0]
    s = ClaimAuditSession(
        task["packet"], history=p["histories"][task["source_case_id"]]
    )
    history = s.dispatch("search_history", {})
    assert history["matches"]
    for match in history["matches"]:
        assert set(match["matched_sensors"]) <= set(task["packet"]["observations"])
        assert "well" not in match and "path" not in match and "summaries" not in match
    assert "private" not in canonical(history)
