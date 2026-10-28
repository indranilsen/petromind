from dataclasses import replace

import pytest

from petromind.retrieval import IncidentRetriever
from petromind.session import DiagnosticSession
from petromind.splits import WellSplit, make_well_split


def test_deterministic_group_split_and_manifest_roundtrip(tmp_path):
    wells = [f"WELL-{i:05d}" for i in range(31)]
    split = make_well_split(wells)
    assert split == make_well_split(list(reversed(wells)) + wells[:10])
    assert not set(split.train_wells) & set(split.test_wells)
    assert set(split.train_wells) | set(split.test_wells) == set(wells)
    path = tmp_path / "split.json"
    split.save(path)
    assert WellSplit.load(path) == split
    split.validate_universe(wells)
    with pytest.raises(ValueError, match="match"):
        split.validate_universe(wells[:-1])
    with pytest.raises(ValueError, match="overlap"):
        WellSplit(("a", "b"), ("b", "c"))


def test_all_test_wells_are_excluded_and_bad_input_rejected(retriever, training, split):
    assert retriever.index_wells == frozenset(split.train_wells)
    assert not retriever.index_wells & set(split.test_wells)
    for well in split.test_wells + ("unknown-well",):
        with pytest.raises(ValueError, match="training wells only"):
            IncidentRetriever(training + (replace(training[0], well=well),), split)


def without_case_ids(matches):
    return [{k: v for k, v in m.items() if k != "case_id"} for m in matches]


def test_retrieval_only_uses_requested_measurements(frame, retriever):
    session = DiagnosticSession(frame, frame.columns, retriever=retriever)
    assert session.search_similar_incidents()["matches"] == []
    session.get_equipment_neighbors("P-TPT")
    assert session.search_similar_incidents()["matches"] == []
    session.get_sensor_history("P-TPT")
    first = session.search_similar_incidents()["matches"]
    assert first and all(m["matched_sensors"] == ["P-TPT"] for m in first)
    frame["T-TPT"] = 9999999999  # Unobserved evidence must not affect retrieval.
    other = DiagnosticSession(frame, frame.columns, retriever=retriever)
    other.get_sensor_history("P-TPT")
    assert other.search_similar_incidents()["matches"] == first
    session.get_sensor_history("T-TPT")
    assert all(m["shared_sensors"] == 2 for m in session.search_similar_incidents()["matches"])
    assert set(first[0]) == {"case_id", "training_event", "distance", "shared_sensors", "matched_sensors"}


def test_unobserved_historical_sensor_cannot_change_search(frame, training, split):
    changed = []
    for incident in training:
        measurements = incident.measurements.copy()
        measurements["T-TPT"] = 1e10
        changed.append(replace(incident, measurements=measurements))
    original = IncidentRetriever(training, split)
    modified = IncidentRetriever(changed, split)
    session = DiagnosticSession(frame, frame.columns)
    session.get_sensor_history("P-TPT")
    assert without_case_ids(original.search(session.observations)) == without_case_ids(modified.search(session.observations))
