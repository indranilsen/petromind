import json

import pandas as pd
import pytest

from petromind.data import load_incidents
from petromind.eval_protocol import freeze_protocol, validate_protocol


def test_exact_inventory_and_holdout_are_frozen(dataset, prepared_protocol):
    protocol, _, split_path = prepared_protocol
    split, by_id = validate_protocol(protocol, dataset)
    assert len(by_id) == 8
    train = {r.well for key, r in by_id.items() if key not in {
        row["case_id"] for row in protocol["records"] if row["partition"] == "test"}}
    assert not train & set(split.test_wells)
    assert len([r for r in protocol["records"] if r["partition"] == "test"]) == 2
    assert all(len(r["case_id"]) == 32 for r in protocol["records"])
    assert ".parquet" not in json.dumps(protocol["records"])
    with pytest.raises(ValueError, match="incident count"):
        freeze_protocol(dataset, split_path)  # Default MUST require the user's 33 cases.


def test_existing_split_is_mandatory(dataset, tmp_path):
    with pytest.raises(FileNotFoundError):
        freeze_protocol(dataset, tmp_path / "missing.json")


def test_dataset_change_is_detected_before_execution(dataset, prepared_protocol):
    protocol, _, _ = prepared_protocol
    path = next(dataset.rglob("*.parquet"))
    frame = pd.read_parquet(path)
    frame["P-TPT"] = 123
    frame.to_parquet(path)
    with pytest.raises(ValueError, match="content differs"):
        validate_protocol(protocol, dataset)


def test_protocol_and_source_drift_are_rejected(dataset, prepared_protocol, monkeypatch):
    protocol, _, _ = prepared_protocol
    modified = {**protocol, "budgets": [1]}
    with pytest.raises(ValueError, match="modified"):
        validate_protocol(modified, dataset)
    monkeypatch.setattr("petromind.eval_protocol.source_digest", lambda: "changed")
    with pytest.raises(ValueError, match="Code or runtime"):
        validate_protocol(protocol, dataset)
