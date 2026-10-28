import json

import pandas as pd
import pytest

from petromind.data import load_incidents
from petromind.eval_protocol import freeze_protocol, validate_protocol
from petromind.agent import AgentConfig


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


def test_token_revision_scales_reservations_and_preserves_exact_cohort(dataset, prepared_protocol):
    original, _, split_path = prepared_protocol
    # Exercise JSON-loaded tuples/lists just like the user's persisted protocol.
    parent = json.loads(json.dumps(original))
    updated = freeze_protocol(dataset, split_path, expected_test=2, pilot_cases=1, budgets=(2,),
                              config=AgentConfig(max_output_tokens=4096), cohort_from=parent)
    assert updated["records"] == original["records"]
    assert updated["pilot_case_ids"] == original["pilot_case_ids"]
    assert updated["parent_protocol_id"] == original["protocol_id"]
    assert updated["protocol_id"] != original["protocol_id"]
    assert updated["prompt_digest"] == original["prompt_digest"]
    assert updated["per_run_transport"]["max_output_budget"] == 20 * 4096
    assert parent == json.loads(json.dumps(original))
    validate_protocol(updated, dataset)


def test_token_revision_cannot_change_prompts_or_sensor_budget(dataset, prepared_protocol):
    original, _, split_path = prepared_protocol
    with pytest.raises(ValueError, match="sensor budgets"):
        freeze_protocol(dataset, split_path, expected_test=2, pilot_cases=1, budgets=(3,), cohort_from=original)
    with pytest.raises(ValueError, match="other agent settings"):
        freeze_protocol(dataset, split_path, expected_test=2, pilot_cases=1, budgets=(2,),
                        config=AgentConfig(reasoning_effort="low"), cohort_from=original)


def test_token_revision_rejects_changed_data(dataset, prepared_protocol):
    original, _, split_path = prepared_protocol
    path = next(dataset.rglob("*.parquet"))
    frame = pd.read_parquet(path)
    frame["P-TPT"] = 321
    frame.to_parquet(path)
    with pytest.raises(ValueError, match="cohort or sensor budgets"):
        freeze_protocol(dataset, split_path, expected_test=2, pilot_cases=1, budgets=(2,), cohort_from=original)
