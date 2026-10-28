import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace

import numpy as np
import pandas as pd
import pytest

from petromind.audit import verify_audit
from petromind.evaluation import Evaluator
from petromind.measurements import summarize
from petromind.session import DiagnosticSession


@pytest.mark.parametrize("budget", [0, 6, -1, True, 1.5, "5"])
def test_invalid_budget(frame, budget):
    with pytest.raises(ValueError):
        DiagnosticSession(frame, frame.columns, budget)


def test_five_queries_and_cache_after_exhaustion(session):
    names = session.list_sensors()
    for i, sensor in enumerate(names[:5]):
        response = session.get_sensor_history(sensor)
        assert response["remaining_budget"] == 4 - i
        assert response["cached"] is False
    assert session.get_sensor_history(names[5])["error"] == "sensor_budget_exhausted"
    response = session.get_sensor_history(names[0])
    assert response["cached"] is True
    assert response["remaining_budget"] == 0
    assert len(session.queries) == 5
    assert len(session.audit_trail) == 8


def test_cache_and_source_are_defensive_copies(frame):
    session = DiagnosticSession(frame, frame.columns, budget=1)
    original = session.get_sensor_history("P-TPT")
    original["summary"]["median"] = 999
    frame.loc[:, "P-TPT"] = 900
    assert session.get_sensor_history("P-TPT")["summary"]["median"] == 2
    with pytest.raises(TypeError):
        session.observations["P-TPT"] = None


@pytest.mark.parametrize("name", ["class", "state", "CLASS", "../8/WELL-fault.parquet", None, [], 5, "unknown"])
def test_invalid_sensor_is_sanitized_and_not_charged(session, name):
    assert session.get_sensor_history(name)["error"] == "unknown_sensor"
    assert session.get_equipment_neighbors(name)["error"] == "unknown_sensor"
    assert session.remaining_budget == 5
    assert "WELL-fault" not in str(session.audit_trail)


def test_missing_extreme_nonfinite_and_nonnumeric_are_charged():
    frame = pd.DataFrame({"P-TPT": [None, np.nan, np.inf, -1e42, "bad"],
                          "T-TPT": [1, np.nan, 3, 1e42, -np.inf]})
    session = DiagnosticSession(frame, ("P-TPT", "T-TPT", "QGL"), budget=3)
    missing = session.get_sensor_history("P-TPT")
    assert missing["summary"]["available"] is False
    assert missing["remaining_budget"] == 2
    mixed = session.get_sensor_history("T-TPT")["summary"]
    assert mixed["median"] == 2 and mixed["count"] == 2 and mixed["invalid_count"] == 3
    assert session.get_sensor_history("QGL")["summary"]["available"] is False
    assert session.remaining_budget == 0
    json.dumps(mixed, allow_nan=False)


def test_summary_does_not_overflow():
    result = summarize([1e12, -1e12, np.inf, -1e38])
    assert result.std == 1e12 and result.delta == -2e12


def test_immutable_audit_chain_records_failures_and_graph(session):
    session.get_sensor_history("P-TPT")
    snapshot = session.audit_trail
    session.get_equipment_neighbors("P-TPT")
    session.get_sensor_history("invalid")
    assert len(snapshot) == 1 and len(session.audit_trail) == 3
    with pytest.raises(FrozenInstanceError):
        snapshot[0].tool = "evaluate"
    assert verify_audit(session.audit_trail)
    tampered = (replace(snapshot[0], result_json="{}"),) + session.audit_trail[1:]
    assert not verify_audit(tampered)


def test_concurrent_budget_cannot_be_overspent(session):
    requests = list(session.list_sensors()) * 20
    with ThreadPoolExecutor(max_workers=12) as pool:
        responses = list(pool.map(session.get_sensor_history, requests))
    assert len(session.queries) == 5 and session.remaining_budget == 0
    assert any(r.get("error") == "sensor_budget_exhausted" for r in responses)
    assert verify_audit(session.audit_trail)


def test_hidden_metadata_is_removed_and_evaluation_separate(frame):
    frame["class"], frame["state"] = 108, 8
    frame["filename"] = "/dataset/8/WELL-00019_event8.parquet"
    frame.attrs["source_path"] = "/dataset/8/WELL-00019_event8.parquet"
    frame.columns.name = "event8"
    session = DiagnosticSession(frame, ["P-TPT", "T-TPT"])
    outputs = [session.list_sensors(), session.get_sensor_history("P-TPT"),
               session.get_equipment_neighbors("T-TPT"), session.search_similar_incidents()]
    text = json.dumps(outputs) + str(session.audit_trail) + str(session._measurements)
    for secret in ("108", "event8", "filename", "WELL-00019", "/dataset/8/", "class", "state"):
        assert secret not in text
    for attr in ("evaluate", "incident", "_labels", "_df", "true_event"):
        assert not hasattr(session, attr)
    assert not session._measurements.attrs and session._measurements.columns.name is None
    evaluator = Evaluator(session.case_id, 8)
    with pytest.raises(ValueError, match="sealed"):
        evaluator.reveal(session)
    session.submit_diagnosis(2, .4, ["P-TPT"])
    assert evaluator.reveal(session)["true_event"] == 8


@pytest.mark.parametrize("pred,confidence,evidence", [
    (0, .5, ["P-TPT"]), (10, .5, ["P-TPT"]), (True, .5, ["P-TPT"]),
    (2., .5, ["P-TPT"]), (2, np.nan, ["P-TPT"]), (2, np.inf, ["P-TPT"]),
    (2, -.1, ["P-TPT"]), (2, 1.1, ["P-TPT"]), (2, True, ["P-TPT"]),
    (2, 10**400, ["P-TPT"]), (2, .5, []), (2, .5, ["T-TPT"]),
    (2, .5, ["P-TPT", "P-TPT"]), (2, .5, [["P-TPT"]]), (2, .5, "P-TPT")])
def test_diagnosis_validation(session, pred, confidence, evidence):
    session.get_sensor_history("P-TPT")
    assert session.submit_diagnosis(pred, confidence, evidence)["error"] == "invalid_diagnosis"
    assert session.diagnosis is None


def test_missing_evidence_cannot_support_diagnosis():
    session = DiagnosticSession(pd.DataFrame({"QGL": [np.nan]}), ["QGL"])
    session.get_sensor_history("QGL")
    assert session.submit_diagnosis(2, .5, ["QGL"])["error"] == "invalid_diagnosis"


def test_submission_seals_investigation_and_binds_evaluator(session):
    session.get_sensor_history("P-TPT")
    result = session.submit_diagnosis(2, .7, ["P-TPT"])
    result["supporting_observations"]["P-TPT"]["median"] = -1
    assert session.observations["P-TPT"].median == 2
    assert session.diagnosis.evidence == ("P-TPT",)
    for response in (session.list_sensors(), session.get_sensor_history("P-TPT"),
                     session.get_equipment_neighbors("P-TPT"), session.search_similar_incidents(),
                     session.submit_diagnosis(8, .9, ["P-TPT"])):
        assert response["error"] == "investigation_closed"
    assert Evaluator(session.case_id, 2).reveal(session)["correct"]
    with pytest.raises(ValueError, match="different"):
        Evaluator("other-case", 2).reveal(session)


def test_only_allowlisted_tool_names_and_arguments(session):
    for tool in ("evaluate", "__dict__", "_measurements", "read_file", []):
        assert session.dispatch(tool, {})["error"] == "unknown_tool"
    for args in ({}, {"sensor_name": "P-TPT", "path": "/8/secret"}, None):
        assert session.dispatch("get_sensor_history", args)["error"] == "invalid_arguments"
    assert session.dispatch("get_sensor_history", {"sensor_name": "P-TPT"})["summary"]["available"]


def test_graph_assumptions_and_non_sensor_query_limits(session):
    result = session.get_equipment_neighbors("P-TPT")
    assert "T-TPT" in result["neighbor_sensors"]
    assert all(e["verification"] == "illustrative" and e["provenance"] for e in result["relationships"])
    assert "not verified per-well" in result["note"]
    for _ in range(19):
        session.get_equipment_neighbors("P-TPT")
    assert session.get_equipment_neighbors("P-TPT")["error"] == "graph_budget_exhausted"
    for _ in range(10):
        session.search_similar_incidents()
    assert session.search_similar_incidents()["error"] == "retrieval_budget_exhausted"
    assert session.remaining_budget == 5


@pytest.mark.parametrize("top_k", [0, 11, True, None, 1.2, 10**400])
def test_invalid_retrieval_limit(session, top_k):
    assert session.search_similar_incidents(top_k)["error"] == "invalid_top_k"
