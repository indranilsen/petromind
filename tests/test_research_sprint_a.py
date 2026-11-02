"""Constructed software fixtures only. No paid requests or real 3W data."""

import json
from copy import deepcopy

import httpx
import pytest

from petromind.audit import canonical, verify_audit
from petromind.eval_protocol import DEFAULT_PRICES, source_digest
from petromind.knowledge import SENSORS, PhysicalKnowledge
from petromind.measurements import summarize
from petromind.meta_api import MetaAPIError, MetaResponsesClient
from research.sprint_a.benchmark import EXCHANGE_VERSION, validate_exchange
from research.sprint_a.core import (
    VARIANTS,
    ResearchSession,
    connected,
    mechanical,
)
from research.sprint_a.experiment import (
    ResearchClient,
    SessionLedger,
    load,
    prepare,
    run,
    score_case,
    summarize_rows,
)


@pytest.fixture
def exchange():
    public = {
        "task_id": "a" * 32,
        "constructed_evaluation_claim": True,
        "observations": {"P-PDG": summarize([10, 20, 30]).to_dict()},
        "baseline": {"prediction": 9},
        "candidate_faults": [9, 2],
        "claims": [
            {
                "claim_id": "c1",
                "statement": "Recorded P-PDG endpoint change equals 20 in this SOFTWARE FIXTURE.",
                "predicate": {
                    "kind": "metric_equal",
                    "sensor": "P-PDG",
                    "metric": "delta",
                    "value": 20,
                },
            }
        ],
        "scope": "Explicitly constructed software fixture, not a real incident.",
    }
    return {
        "exchange_version": EXCHANGE_VERSION,
        "author": "Independent test fixture author, not an engineer judgment",
        "frozen": True,
        "isolation": {
            "fit_groups": ["1" * 64],
            "development_groups": ["2" * 64],
            "excluded_test_groups": ["3" * 64],
            "history_provenance": "SOFTWARE FIXTURE. No actual historical incident.",
        },
        "facts": [f.public() for f in PhysicalKnowledge().facts],
        "cases": [
            {
                "public": public,
                "reference": {
                    "name": "PRIVATE_REFERENCE_SENTINEL",
                    "judgments": {"c1": "SUPPORTED"},
                    "review_status": "mechanical_source_scope",
                    "reference_basis": "Fixture arithmetic only.",
                },
                "source": {
                    "group": "2" * 64,
                    "partition": "development",
                    "evidence_digest": "4" * 64,
                },
                "history": [],
                "optional_summaries": {},
            }
        ],
    }


def make_session(exchange, variant="B_knowledge", optional=False):
    c = exchange["cases"][0]
    extra = {s: summarize([None]).to_dict() for s in SENSORS} if optional else {}
    return ResearchSession(c["public"], exchange["facts"], c["history"], variant, extra)


def submission(verdict="SUPPORTED", citations=None):
    return {
        "numeric_observations": [],
        "findings": [
            {
                "claim_id": "c1",
                "verdict": verdict,
                "citations": ["measurement:P-PDG"] if citations is None else citations,
                "missing_premise": "",
                "next_evidence": "",
                "public_justification": "Public fixture finding only.",
            }
        ],
    }


def test_independent_exchange_has_strict_public_private_split(exchange):
    validate_exchange(exchange)
    payload = canonical(make_session(exchange).initial_context())
    assert "PRIVATE_REFERENCE_SENTINEL" not in payload
    assert (
        "reference_basis" not in payload
        and "well_group" not in payload
        and "evidence_digest" not in payload
    )
    exchange["cases"][0]["public"]["true_event"] = 9
    with pytest.raises(ValueError, match="public_packet"):
        validate_exchange(exchange)
    with pytest.raises(ValueError, match="public_packet"):
        make_session(exchange)


@pytest.mark.parametrize("partition", ["fit_groups", "excluded_test_groups"])
def test_overlap_is_rejected(exchange, partition):
    exchange["isolation"][partition] = ["2" * 64]
    with pytest.raises(ValueError, match="partitions_overlap"):
        validate_exchange(exchange)


def test_no_held_out_test_case_admitted(exchange):
    exchange["cases"][0]["source"]["group"] = "3" * 64
    with pytest.raises(ValueError, match="outside_development"):
        validate_exchange(exchange)


def test_historical_evidence_cannot_include_unqueried_sensor(exchange):
    exchange["cases"][0]["history"] = [
        {
            "case_id": "a" * 32,
            "training_event": 2,
            "distance": 0.1,
            "shared_sensors": 1,
            "matched_sensors": ["P-TPT"],
        }
    ]
    with pytest.raises(ValueError, match="snapshot_isolation"):
        validate_exchange(exchange)


def test_unknown_provenance_and_missing_scope_rejected(exchange):
    exchange["facts"][0].pop("scope")
    with pytest.raises(ValueError, match="fact_provenance"):
        validate_exchange(exchange)


def test_optional_provider_does_not_offer_free_availability_probe(exchange):
    exchange["cases"][0]["optional_summaries"] = {"P-TPT": summarize([None]).to_dict()}
    with pytest.raises(ValueError, match="cover_catalog"):
        validate_exchange(exchange)


def test_shared_five_sensor_limit_caching_and_missing_charges(exchange):
    session = make_session(exchange, optional=True)
    assert session.remaining_budget == 4
    initial = session.dispatch(
        "request_sensor", {"sensor_name": "P-PDG", "relevance": "Observed already."}
    )
    assert initial["cached"] and session.remaining_budget == 4
    for s in ["P-TPT", "QGL", "T-TPT", "ABER-CKGL"]:
        row = session.dispatch(
            "request_sensor",
            {"sensor_name": s, "relevance": "Fixture required evidence."},
        )
        assert not row["summary"]["available"]
    assert session.remaining_budget == 0
    denied = session.dispatch(
        "request_sensor",
        {"sensor_name": "P-ANULAR", "relevance": "Another fixture channel."},
    )
    assert denied["error"]["code"] == "sensor_budget_exhausted"
    assert session.dispatch(
        "request_sensor", {"sensor_name": "P-TPT", "relevance": "Cached missing query."}
    )["cached"]
    assert verify_audit(session.audit_trail)


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {},
        [],
        {"sensor_name": {}, "relevance": "x"},
        {"sensor_name": "CLASS", "relevance": "x"},
    ],
)
def test_invalid_sensor_arguments_are_safe(exchange, bad):
    session = make_session(exchange, optional=True)
    assert "error" in session.dispatch("request_sensor", bad)
    assert session.remaining_budget == 4


def test_zero_and_missing_are_different_for_baseline(exchange):
    claim = exchange["cases"][0]["public"]["claims"][0]
    claim["predicate"].update(metric="median", value=0)
    assert (
        mechanical(claim, {"P-PDG": summarize([0, 0]).to_dict()}, [], [])[0]
        == "SUPPORTED"
    )
    assert (
        mechanical(claim, {"P-PDG": summarize([None, None]).to_dict()}, [], [])[0]
        == "NOT_ESTABLISHED"
    )
    assert (
        mechanical(claim, {"P-PDG": summarize([1, 1]).to_dict()}, [], [])[0]
        == "CONTRADICTED"
    )


def test_source_scope_and_original_graph_do_not_certify_cause(exchange):
    session = make_session(exchange, "D_legacy_partial")
    graph = session.dispatch("get_equipment_neighbors", {"sensor_name": "P-TPT"})
    assert graph["equipment"] == ["tubing"]
    assert all(r["verification"] == "illustrative" for r in graph["relationships"])
    fact = {
        "claim_id": "c1",
        "predicate": {
            "kind": "fact",
            "subject": "P-PDG",
            "relation": "pressure_at",
            "object": "downhole_gauge",
            "scope": "well_specific",
        },
    }
    assert (
        mechanical(fact, session.observed, exchange["facts"], [])[0]
        == "NOT_ESTABLISHED"
    )
    fact["predicate"]["scope"] = "generic_documented_definition"
    assert mechanical(fact, session.observed, exchange["facts"], [])[0] == "SUPPORTED"


def test_connected_paths_use_only_real_source_edges_and_scopes(exchange):
    p = exchange["cases"][0]["public"]
    graph = connected(exchange["facts"], "fault:9", p)
    facts = {f["id"]: f for f in exchange["facts"]}
    assert 1 <= len(graph["facts"]) <= 24
    for path in graph["paths"]:
        assert len(path["edges"]) <= 2
        for edge in path["edges"]:
            f = facts[edge["fact_id"]]
            assert {edge["from"], edge["to"]} == {f["subject"], f["object"]}
            assert f["scope"] and f["provenance"]
    assert not any(
        f["subject"] == "fault:9" and f["object"] == "P-PDG" for f in graph["facts"]
    )


def test_fact_and_history_capabilities_are_real_ablations(exchange):
    expected = {
        "A_sensor": {"submit_findings"},
        "B_knowledge": {"submit_findings", "lookup_knowledge"},
        "C_history": {"submit_findings", "lookup_knowledge", "search_history"},
        "D_legacy_partial": {
            "submit_findings",
            "get_equipment_neighbors",
            "search_history",
        },
        "E_connected": {"submit_findings", "lookup_knowledge"},
    }
    for variant in VARIANTS:
        session = make_session(exchange, variant)
        assert {t["name"] for t in session.model_tools()} == expected[variant]
    assert (
        make_session(exchange).model_tools()
        == make_session(exchange, "E_connected").model_tools()
    )


def test_history_labels_visible_only_in_explicit_legacy_projection(exchange):
    exchange["cases"][0]["history"] = [
        {
            "case_id": "f" * 32,
            "training_event": 2,
            "distance": 0.1,
            "shared_sensors": 1,
            "matched_sensors": ["P-PDG"],
        }
    ]
    for variant in ["C_history", "D_legacy_partial"]:
        row = make_session(exchange, variant).dispatch("search_history", {})
        assert ("training_event" in row["matches"][0]) == (
            variant == "D_legacy_partial"
        )
        assert "case_id" not in canonical(row)


def test_repairs_bounded_and_rejected_arguments_not_logged(exchange):
    session = make_session(exchange)
    invalid = submission(citations=["PRIVATE_REJECTED_SENTINEL"])
    first = session.dispatch("submit_findings", invalid)
    assert first["error"]["code"] == "unreceived_citation"
    session.dispatch("submit_findings", invalid)
    assert session.stop == "repeated_invalid_submission"
    assert "PRIVATE_REJECTED_SENTINEL" not in canonical(
        [a.arguments_json + a.result_json for a in session.audit_trail]
    )
    other = make_session(exchange)
    for i in range(3):
        other.dispatch("submit_findings", submission(citations=[f"bad:{i}"]))
    assert other.failures == 3 and other.stop == "assessment_repair_limit"


def test_contradiction_requires_positive_citation_but_missing_support_is_not_false(
    exchange,
):
    session = make_session(exchange)
    assert (
        session.dispatch("submit_findings", submission("CONTRADICTED", []))["error"][
            "code"
        ]
        == "contrary_evidence_required"
    )
    assert (
        session.dispatch("submit_findings", submission("NOT_ESTABLISHED", []))[
            "findings"
        ][0]["verdict"]
        == "NOT_ESTABLISHED"
    )


def test_unreceived_fact_cannot_be_cited_even_if_in_collection(exchange):
    session = make_session(exchange)
    target = "knowledge:location:P-PDG"
    assert (
        session.dispatch("submit_findings", submission(citations=[target]))["error"][
            "code"
        ]
        == "unreceived_citation"
    )
    session.dispatch("lookup_knowledge", {"topic": "P-PDG"})
    assert "findings" in session.dispatch(
        "submit_findings", submission(citations=[target])
    )


def test_research_records_semantic_errors_without_weakening_production(exchange):
    case = exchange["cases"][0]
    case["public"]["claims"][0]["predicate"] = {
        "kind": "causal_inference",
        "fault_type": 9,
        "quantifier": "sufficiency",
        "sensors": ["P-PDG"],
    }
    case["reference"]["judgments"]["c1"] = "NOT_ESTABLISHED"
    session = make_session(exchange)
    session.dispatch("submit_findings", submission())
    scored = score_case(
        case, session.result, session.observed, session.known, exchange["facts"]
    )[0]
    assert not scored["correct"] and scored["unsupported_causal_supported"]
    # This experimental acceptance is intentionally isolated from production v5.
    from petromind.atomic_auditor import VERSION

    assert VERSION != "sprint-a-atomic-research-v1"


def test_missing_retrieval_and_reasoning_error_are_separate(exchange):
    case = exchange["cases"][0]
    case["public"]["claims"][0]["predicate"] = {
        "kind": "fact",
        "subject": "P-PDG",
        "relation": "pressure_at",
        "object": "downhole_gauge",
        "scope": "generic_documented_definition",
    }
    case["_variant"] = "B_knowledge"
    result = submission("NOT_ESTABLISHED", [])
    missed = score_case(
        case, result, case["public"]["observations"], [], exchange["facts"]
    )[0]
    assert missed["failure_category"] == "available_source_not_retrieved"
    assert missed["evidence_conditioned_verdict_correct"]
    wrong = score_case(
        case,
        result,
        case["public"]["observations"],
        ["knowledge:location:P-PDG"],
        exchange["facts"],
    )[0]
    assert wrong["failure_category"] == "formal_reasoning_or_citation_error"


def test_always_abstaining_cannot_get_high_macro_score():
    rows = []
    for v in ["SUPPORTED", "NOT_ESTABLISHED", "CONTRADICTED"]:
        rows.append(
            {
                "variant": "A_sensor",
                "status": "completed",
                "latency_seconds": 0,
                "scores": [
                    {
                        "scorable": True,
                        "reference": v,
                        "correct": v == "NOT_ESTABLISHED",
                        "unsupported_causal_supported": False,
                        "failure_category": None,
                        "evidence_conditioned_verdict_correct": v == "NOT_ESTABLISHED",
                    }
                ],
            }
        )
    assert summarize_rows(rows)["A_sensor"]["macro_recall"] == pytest.approx(1 / 3)


def test_aggregate_ledger_cannot_be_reset_with_another_protocol(tmp_path):
    ledger = SessionLedger(tmp_path / "budget")
    p = {"protocol_id": "a", "prices": DEFAULT_PRICES, "max_estimated_usd": 5}
    task = {"task_id": "t", "variant": "A_sensor"}
    for i in range(4):
        p["protocol_id"] = str(i)
        ledger.reserve(p, task, 4096, 800000)  # ~$1.017 each.
    before = len(ledger.rows())
    with pytest.raises(MetaAPIError, match="research_session_spending_cap"):
        SessionLedger(tmp_path / "budget").reserve(p, task, 4096, 800000)
    assert len(ledger.rows()) == before
    with pytest.raises(ValueError):
        SessionLedger(tmp_path / "different", cap=5.01)
    rows = ledger.rows()
    rows[0]["estimated_usd_reserved"] = 0
    ledger.path.write_text("\n".join(canonical(r) for r in rows) + "\n")
    with pytest.raises(ValueError, match="reservation_chain_modified"):
        ledger.rows()


def test_request_guard_reserves_before_each_http_and_privacy(
    exchange, tmp_path, monkeypatch
):
    monkeypatch.setenv("MODEL_API_KEY", "mock-only")
    out = tmp_path / "run"
    before = source_digest()
    prepare(out, exchange=exchange, ledger_directory=tmp_path / "budget")
    assert (
        source_digest() == before
    )  # Research files do not enter production source digest.
    seen = []

    def callback(request):
        payload = json.loads(request.content)
        assert "PRIVATE_REFERENCE_SENTINEL" not in canonical(payload)
        assert "private_references" not in canonical(payload)
        assert len(SessionLedger(tmp_path / "budget").rows()) == len(seen) + 1
        seen.append(payload)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "error": None,
                "output": [
                    {
                        "type": "function_call",
                        "name": "submit_findings",
                        "call_id": "c1",
                        "arguments": canonical(submission()),
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 10},
            },
        )

    def factory(**kw):
        return MetaResponsesClient(**kw, transport=httpx.MockTransport(callback))

    value = run(out, authorize_paid=True, factory=factory)
    assert value["api_requests"] == 5 and len(seen) == 5
    rows = [
        json.loads(line) for line in (out / "results.jsonl").read_text().splitlines()
    ]
    assert all(r["status"] == "completed" and r["audit_valid"] for r in rows)
    assert all(r["scores"][0]["correct"] for r in rows)
    run(out, authorize_paid=True, factory=factory)
    assert len(seen) == 5  # No silent reruns, including fresh process resume.


def test_missing_credential_is_blocker_not_model_result(
    exchange, tmp_path, monkeypatch
):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    out = tmp_path / "run"
    prepare(out, exchange=exchange, ledger_directory=tmp_path / "budget")
    result = run(
        out,
        authorize_paid=True,
        factory=lambda **kw: pytest.fail("must not construct client"),
    )
    assert result["status"] == "blocked" and result["api_requests"] == 0
    assert not (out / "results.jsonl").exists()
    assert SessionLedger(tmp_path / "budget").summary()["http_reservations"] == 0


def test_frozen_references_and_contract_changes_fail_closed(exchange, tmp_path):
    out = tmp_path / "run"
    prepare(out, exchange=exchange, ledger_directory=tmp_path / "budget")
    _p, data = load(out)
    data["cases"][0]["reference"]["judgments"]["c1"] = "NOT_ESTABLISHED"
    (out / "benchmark.private.json").write_text(canonical(data))
    with pytest.raises(ValueError, match="benchmark_modified"):
        load(out)
    with pytest.raises(ValueError, match="fresh_output"):
        prepare(out, exchange=exchange, ledger_directory=tmp_path / "budget")


def test_submission_schema_and_numeric_quote_contract_match(exchange):
    session = make_session(exchange)
    schema = session.model_tools()[0]["parameters"]
    assert set(schema["required"]) == {"findings", "numeric_observations"}
    wrong = submission()
    wrong["numeric_observations"] = [
        {"sensor": "P-PDG", "metric": "delta", "value": 999}
    ]
    assert (
        session.dispatch("submit_findings", wrong)["error"]["code"]
        == "numeric_quote_mismatch"
    )
    assert "999" not in canonical([a.result_json for a in session.audit_trail])
    wrong["numeric_observations"][0]["value"] = 20
    assert "findings" in session.dispatch("submit_findings", wrong)


def test_cross_sensor_constraint_requires_observation_and_compatible_units(exchange):
    p = {
        "kind": "cross_sensor_constraint",
        "left_sensor": "P-PDG",
        "right_sensor": "P-TPT",
        "metric": "median",
        "operator": "gt",
    }
    claim = {"predicate": p}
    observations = deepcopy(exchange["cases"][0]["public"]["observations"])
    assert (
        mechanical(claim, observations, exchange["facts"], [])[0] == "NOT_ESTABLISHED"
    )
    observations["P-TPT"] = summarize([1, 2, 3]).to_dict()
    assert mechanical(claim, observations, exchange["facts"], [])[0] == "SUPPORTED"
    assert mechanical(claim, observations, [], [])[0] == "NOT_ESTABLISHED"
    claim["predicate"]["operator"] = "lt"
    assert mechanical(claim, observations, exchange["facts"], [])[0] == "CONTRADICTED"


def test_original_median_distance_can_prefer_one_equal_constant_over_two_sensors():
    from pathlib import Path
    from types import SimpleNamespace

    from petromind.retrieval import IncidentRetriever
    from petromind.splits import WellSplit

    single = SimpleNamespace(
        path=Path("opaque-a"), well="fit", event=2, measurements={"P-PDG": [0, 0]}
    )
    double = SimpleNamespace(
        path=Path("opaque-b"),
        well="fit",
        event=7,
        measurements={"P-PDG": [0, 0], "P-TPT": [21, 21]},
    )
    retriever = IncidentRetriever([single, double], WellSplit(("fit",), ("dev",)))
    rows = retriever.search({"P-PDG": summarize([0, 0]), "P-TPT": summarize([20, 20])})
    assert (
        rows[0]["training_event"] == 2
        and rows[0]["shared_sensors"] == 1
        and rows[0]["distance"] == 0
    )
    assert rows[1]["shared_sensors"] == 2
    # This reproduces a mathematical ranking possibility, not an original M3 incident.


def test_cap_refusal_precedes_http_even_with_a_valid_client(
    exchange, tmp_path, monkeypatch
):
    monkeypatch.setenv("MODEL_API_KEY", "mock-only")
    out = tmp_path / "run"
    prepare(out, exchange=exchange, ledger_directory=tmp_path / "budget")
    p, _data = load(out)
    p["max_estimated_usd"] = 0.00001
    ledger = SessionLedger(tmp_path / "budget")

    def callback(request):
        pytest.fail("A rejected reservation must not reach HTTP")

    def factory(**kw):
        return MetaResponsesClient(**kw, transport=httpx.MockTransport(callback))

    client = ResearchClient(
        p, ledger, {"task_id": "t", "variant": "A_sensor"}, factory=factory
    )
    try:
        with pytest.raises(MetaAPIError, match="research_session_spending_cap"):
            client.create(
                {"max_output_tokens": 4096, "input": "fixture"},
                deadline=__import__("time").monotonic() + 2,
            )
        assert client.requests == 0 and len(ledger.rows()) == 0
    finally:
        client.close()
