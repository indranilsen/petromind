import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from petromind.data import IneligibleIncident, load_incidents, read_incident
from petromind.pipeline import prepare_investigation


def test_pipeline_uses_shared_split_and_train_only_public_catalog(dataset, tmp_path):
    path = tmp_path / "split.json"
    prepared = prepare_investigation(dataset, split_path=path)
    repeated = prepare_investigation(dataset, split_path=path)
    assert prepared.split == repeated.split
    assert prepared.session.case_id != repeated.session.case_id
    assert prepared.training_incidents + prepared.test_incidents == 8
    assert prepared.session._retriever.test_wells == frozenset(prepared.split.test_wells)
    assert not prepared.session._retriever.index_wells & set(prepared.split.test_wells)
    assert not {"class", "state"} & set(prepared.session.list_sensors())
    with pytest.raises(ValueError, match="seed"):
        prepare_investigation(dataset, seed=1, split_path=path)
    incidents = load_incidents(dataset)
    train_path = next(r.path for r in incidents if r.well in prepared.split.train_wells)
    with pytest.raises(ValueError, match="test partition"):
        prepare_investigation(dataset, split_path=path, incident_path=train_path)
    test_path = next(r.path for r in incidents if r.well in prepared.split.test_wells)
    assert prepare_investigation(dataset, split_path=path, incident_path=test_path)


def test_target_only_column_does_not_leak_into_catalog(dataset):
    prepared = prepare_investigation(dataset)
    incidents = load_incidents(dataset)
    target = next(r for r in incidents if r.well in prepared.split.test_wells)
    frame = pd.read_parquet(target.path)
    frame["P-SECRET"] = 12345
    frame.to_parquet(target.path)
    other = prepare_investigation(dataset, incident_path=target.path)
    assert "P-SECRET" not in other.session.list_sensors()
    assert "P-SECRET" not in other.session._measurements


def test_loader_strips_labels_paths_and_time_index(dataset):
    records = load_incidents(dataset)
    assert len(records) == 8
    record = records[0]
    assert record.event in {2, 8}  # Trusted evaluator-side record only.
    assert len(record.measurements) == 600
    assert isinstance(record.measurements.index, pd.RangeIndex)
    assert "class" not in record.measurements and "state" not in record.measurements


@pytest.mark.parametrize("damage", ["no_transient", "mixed_labels", "short", "bad_cadence", "nan_labels"])
def test_loader_rejects_bad_windows(dataset, damage):
    path = next(dataset.rglob("*.parquet"))
    frame = pd.read_parquet(path)
    if damage == "no_transient":
        frame["class"] = 0
    elif damage == "mixed_labels":
        frame.iloc[20, frame.columns.get_loc("class")] = 0
    elif damage == "short":
        frame = frame.iloc[:50]
    elif damage == "bad_cadence":
        frame.index = pd.date_range("2020-01-01", periods=len(frame), freq="2s")
    elif damage == "nan_labels":
        frame["class"] = np.nan
    frame.to_parquet(path)
    with pytest.raises(IneligibleIncident):
        read_incident(path)


@pytest.mark.parametrize("budget,reveal,entry", [(1, False, "scripts/demo_investigation.py"),
                                                (5, True, "scripts/demo_investigation.py"),
                                                (5, False, "demo.py")])
def test_cli_real_parquet_synthetic_fixture(dataset, tmp_path, budget, reveal, entry):
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, str(root / entry), "--dataset", str(dataset),
               "--budget", str(budget), "--split", str(tmp_path / "protocol.json")]
    if reveal:
        command.append("--reveal")
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    kinds = [r["kind"] for r in rows]
    assert kinds.count("sensor_query") == budget
    assert kinds.count("graph_query") == budget
    assert "historical_retrieval" in kinds and "final_diagnosis" in kinds
    final = next(r["result"] for r in rows if r["kind"] == "final_diagnosis")
    assert final["remaining_budget"] == 0 and final["evidence"]
    assert "WELL-" not in result.stdout and str(dataset) not in result.stdout
    if reveal:
        assert kinds[-1] == "evaluation_only"
        assert kinds.index("evaluation_only") > kinds.index("final_diagnosis")
    else:
        assert "true_event" not in result.stdout and "evaluation_only" not in kinds


def test_cli_failure_does_not_echo_dataset_path(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / "scripts/demo_investigation.py"),
                             "--dataset", str(tmp_path / "8/WELL-secret")],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert "WELL-secret" not in result.stderr and "WELL-secret" not in result.stdout


def test_legacy_graph_exports_and_safe_factory(dataset, tmp_path, monkeypatch):
    from graph_tools import Investigation, make_graph, summarize
    monkeypatch.chdir(tmp_path)
    prepared = prepare_investigation(dataset)
    target = next(r for r in load_incidents(dataset) if r.well in prepared.split.test_wells)
    session = Investigation(target.path, budget=1)
    assert session.get_sensor_history("P-TPT")["remaining_budget"] == 0
    assert not hasattr(session, "evaluate")
    graph = make_graph()
    assert graph["P-TPT"]["tubing"]["verification"] == "illustrative"
    assert summarize(pd.Series([1., 2., 3.]))["median"] == 2
