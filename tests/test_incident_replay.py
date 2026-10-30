"""Synthetic telemetry exercises real replay code; not a claimed 3W result."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from petromind.audit import canonical
from petromind.eval_protocol import digest
from petromind.incident_replay import (
    attach_replay,
    definitions,
    endpoints,
    raw_payload,
    sample,
)
from petromind.measurements import summarize


@pytest.fixture
def replay_fixture(tmp_path):
    root = tmp_path / "dataset"
    folder = root / "2"
    folder.mkdir(parents=True)
    frame = pd.DataFrame(
        {
            "class": [0] * 20 + [102] * 600,
            "state": [2] * 620,
            "P-PDG": np.linspace(100, 200, 620),
            "P-TPT": np.linspace(40, 20, 620),
            "ABER-CKGL": np.full(620, 53.0),
            "T-TPT": np.linspace(1, 2, 620),
        },
        index=pd.date_range("2020", periods=620, freq="s"),
    )
    frame.iloc[30, frame.columns.get_loc("P-TPT")] = np.nan
    frame.iloc[31, frame.columns.get_loc("P-TPT")] = np.inf
    frame.iloc[32, frame.columns.get_loc("P-PDG")] = 0
    path = folder / "WELL-00001_any_name.parquet"
    frame.to_parquet(path)
    well = "WELL-00001"
    cid = "a" * 32
    record = {
        "case_id": cid,
        "role": "development_pool",
        "well_group": hashlib.sha256(well.encode()).hexdigest(),
        "locator_hash": hashlib.sha256(
            path.relative_to(root).as_posix().encode()
        ).hexdigest(),
        "file_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    parent = {
        "development_wells": [well],
        "original_split": {"test_wells": ["WELL-00003"]},
        "retrieval_split": {"train_wells": ["WELL-00002"]},
        "records": [record],
    }
    parent["protocol_id"] = digest(parent)
    science = {"parent": parent, "case_ids": [cid]}
    science["protocol_id"] = digest(science)
    case = {
        "id": "fault_expectation",
        "observations": {
            s: json.loads(canonical(summarize(frame.iloc[20:][s]).to_dict()))
            for s in ["P-PDG", "P-TPT", "ABER-CKGL"]
        },
    }
    claim = {
        "source_protocol_id": science["protocol_id"],
        "tasks": [{"task_id": case["id"], "source_case_id": cid}],
    }
    return root, path, frame, science, claim, case


def test_no_raw_data_means_two_real_endpoints_never_a_fake_series(
    replay_fixture, tmp_path
):
    root, _path, _frame, science, claim, case = replay_fixture
    r = attach_replay(
        case, claim, dataset=tmp_path / "absent", science_protocol=science
    )
    assert r["mode"] == "endpoints" and r["timestamps"] is None and not r["can_play"]
    assert len(r["series"]["P-TPT"]["samples"]) == 2 and r["interpolation"] == "none"
    assert (
        r["series"]["P-TPT"]["samples"][0]["value"]
        == case["observations"]["P-TPT"]["first"]
    )
    assert (
        attach_replay(case, claim, dataset=root)["availability"]
        == "private_source_protocol_required"
    )


def test_raw_mapping_timestamps_gaps_zeros_units_and_private_projection(
    replay_fixture, monkeypatch
):
    root, path, frame, science, claim, case = replay_fixture
    # A tempting test file must never be opened just to discover a mapping.
    (root / "7").mkdir()
    (root / "7" / "WELL-00003_secret.parquet").write_bytes(b"not telemetry")
    actual_read = pd.read_parquet
    opened = []

    def checked(p, *args, **kw):
        opened.append(Path(p))
        assert Path(p) == path
        return actual_read(p, *args, **kw)

    monkeypatch.setattr("petromind.incident_replay.pd.read_parquet", checked)
    before = canonical(case)
    r = attach_replay(case, claim, dataset=root, science_protocol=science)
    assert r["mode"] == "raw" and r["can_play"] and len(r["timestamps"]) == 600
    assert (
        r["timestamps"][0] == frame.index[20].isoformat()
        and r["elapsed_seconds"][-1] == 599
    )
    assert r["series"]["P-TPT"]["samples"][10]["quality"] == "missing"
    assert r["series"]["P-TPT"]["samples"][11]["quality"] == "invalid"
    assert r["series"]["P-PDG"]["samples"][12] == {
        "value": 0.0,
        "quality": "valid",
        "reason": None,
    }
    assert set(r["series"]) == set(case["observations"]) and "T-TPT" not in r["series"]
    assert "class" not in r and "state" not in r and "source_case_id" not in r
    text = canonical(r)
    for secret in [
        "WELL-",
        "parquet",
        "true_event",
        "locator_hash",
        "file_hash",
        "well_group",
    ]:
        assert secret not in text
    assert all(p == path for p in opened) and canonical(case) == before
    assert "summary_only" in text and "Viewer-only" in r["visibility"]
    defs = definitions()
    assert defs["P-PDG"]["unit"] == "Pa"
    assert defs["P-PDG"]["location_fact"]["object"] == "downhole_gauge"
    assert defs["P-TPT"]["location_fact"]["object"] == "subsea_tree_transducer"


@pytest.mark.parametrize(
    "value,quality",
    [
        (None, "missing"),
        (np.nan, "missing"),
        (np.inf, "invalid"),
        ("bad", "invalid"),
        (1e13, "invalid"),
        (0, "valid"),
        (-5, "valid"),
    ],
)
def test_per_sample_quality_never_uses_zero_as_missing(value, quality):
    r = sample(value)
    assert r["quality"] == quality
    canonical(r)


def test_wrong_parent_or_changed_file_fails_closed(replay_fixture):
    root, path, _frame, science, claim, case = replay_fixture
    with pytest.raises(ValueError):
        attach_replay(
            case,
            {**claim, "source_protocol_id": "wrong"},
            dataset=root,
            science_protocol=science,
        )
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Frozen incident changed"):
        attach_replay(case, claim, dataset=root, science_protocol=science)


def test_missing_gap_not_replaced_and_timestamp_or_summary_mismatch_rejected(
    replay_fixture,
):
    _root, _path, frame, _science, _claim, case = replay_fixture
    window = frame.iloc[20:]
    bad = window.copy()
    bad.index = bad.index + pd.to_timedelta(np.arange(600), unit="s")
    with pytest.raises(ValueError, match="one-second"):
        raw_payload(bad, case)
    bad = window.copy()
    bad.iloc[0, bad.columns.get_loc("P-TPT")] = 10000
    with pytest.raises(ValueError, match="differs"):
        raw_payload(bad, case)
    assert raw_payload(window, case)["series"]["P-TPT"]["samples"][10]["value"] is None


def test_missing_and_constant_endpoint_summaries_are_not_synthetic(replay_fixture):
    *_, case = replay_fixture
    case["observations"]["ABER-CKGL"] = json.loads(
        canonical(summarize([None] * 600).to_dict())
    )
    r = endpoints(case)
    assert all(s["quality"] == "missing" for s in r["series"]["ABER-CKGL"]["samples"])
    case["observations"]["ABER-CKGL"] = json.loads(
        canonical(summarize([0] * 600).to_dict())
    )
    assert all(
        s["value"] == 0 for s in endpoints(case)["series"]["ABER-CKGL"]["samples"]
    )


def test_fitting_or_test_well_cannot_be_mapped_as_development(replay_fixture):
    root, _path, _frame, science, claim, case = replay_fixture
    science["parent"]["records"][0]["role"] = "fit"
    science["parent"].pop("protocol_id")
    science["parent"]["protocol_id"] = digest(science["parent"])
    science.pop("protocol_id")
    science["protocol_id"] = digest(science)
    claim["source_protocol_id"] = science["protocol_id"]
    with pytest.raises(ValueError, match="development"):
        attach_replay(case, claim, dataset=root, science_protocol=science)


def test_full_inventory_distinguishes_unknown_absent_and_unobserved(replay_fixture):
    from petromind.knowledge import SENSORS

    _, _, frame, _, _, case = replay_fixture
    fallback = endpoints(case)
    rows = {r["sensor"]: r for r in fallback["inventory"]}
    assert len(rows) == len(definitions()) == len(SENSORS) == 27
    assert rows["P-PDG"]["present_in_incident"] is True
    assert rows["T-TPT"]["present_in_incident"] is None
    assert rows["T-TPT"]["availability"] == "unknown"
    assert rows["T-TPT"]["observed_by_muse"] is False
    assert fallback["viewer_series"] == {}
    raw = raw_payload(frame.iloc[20:], case)
    rows = {r["sensor"]: r for r in raw["inventory"]}
    assert rows["T-TPT"]["present_in_incident"] is True
    assert rows["T-TPT"]["availability"] == "available"
    assert rows["T-TPT"]["observed_by_muse"] is False
    assert rows["QGL"]["present_in_incident"] is False
    assert rows["QGL"]["availability"] == "not_present"
    assert rows["P-PDG"]["observed_by_muse"] is True


def test_viewer_channels_are_whitelisted_real_samples_and_never_change_audit(
    replay_fixture,
):
    from petromind.knowledge import SENSORS

    _, _, frame, _, _, case = replay_fixture
    window = frame.iloc[20:].copy()
    window["QGL"] = [None] * 600
    window["ESTADO-DHSV"] = [0] * 600
    window["secret_filename"] = "hidden event metadata"
    before = canonical(case)
    raw = raw_payload(window, case)
    assert set(raw["series"]) == set(case["observations"])
    assert set(raw["viewer_series"]) == set(SENSORS) - set(case["observations"])
    assert (
        raw["viewer_series"]["T-TPT"]["samples"][15]["value"]
        == window["T-TPT"].iloc[15]
    )
    assert raw["viewer_series"]["ESTADO-DHSV"]["samples"][0]["value"] == 0
    rows = {r["sensor"]: r for r in raw["inventory"]}
    assert rows["QGL"]["present_in_incident"] is True
    assert rows["QGL"]["availability"] == "no_valid_measurements"
    assert rows["ESTADO-DHSV"]["valid_count"] == 600
    assert "hidden event metadata" not in canonical(raw)
    assert "secret_filename" not in canonical(raw)
    assert canonical(case) == before
