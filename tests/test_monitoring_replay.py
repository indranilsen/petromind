"""Synthetic adapter, privacy and unchanged-capture regression tests."""

import hashlib
import json
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from petromind.audit import canonical
from petromind.claim_review import CAPTURE_PROTOCOL
from petromind.eval_protocol import digest
from petromind.incident_replay import sample
from petromind.knowledge import SENSORS
from petromind.measurements import summarize
from petromind.monitoring_replay import (
    load_monitoring,
    prepare_monitoring,
    project,
    read_fixture,
)


def fixture():
    columns = {"elapsed_seconds": list(range(1001))}
    for sensor in SENSORS:
        values = np.array(
            [10 + i % 7 if i < 350 else 1000 for i in range(1001)], dtype=float
        )
        if sensor == "QGL":
            values[:] = 0  # Legitimate constant zero.
        samples = [sample(v) for v in values]
        columns[sensor] = [p["value"] for p in samples]
        columns[sensor + "__quality"] = [p["quality"] for p in samples]
        columns[sensor + "__reason"] = [p["reason"] for p in samples]
    frame = pd.DataFrame(columns)
    observations = {
        s: summarize(frame[s].iloc[400:1000]).to_dict()
        for s in ("P-PDG", "P-TPT", "ABER-CKGL")
    }
    observations = json.loads(canonical(observations))
    packet = {"observations": observations, "baseline": {"prediction": 9}}
    case = {"id": "test-case", "observations": observations, "packet": packet}
    entry = {
        "file": "case-1.parquet",
        "present_sensor_ids": list(SENSORS),
        "samples": len(frame),
    }
    return frame, case, entry


def test_projection_preserves_actual_values_quality_and_600_summary_boundary():
    frame, case, entry = fixture()
    before = deepcopy(case)
    frame.loc[20, ["T-TPT", "T-TPT__quality", "T-TPT__reason"]] = [
        np.nan,
        "invalid",
        "nonfinite",
    ]
    frame.loc[21, ["T-TPT", "T-TPT__quality", "T-TPT__reason"]] = [
        np.nan,
        "missing",
        "missing_sample",
    ]
    r = project(frame, entry, case, 400)
    assert r["mode"] == "history" and r["timestamps"] is None
    assert r["elapsed_seconds"] == list(range(1001))
    assert r["workflow"]["checkpoint"]["index"] == 999
    assert r["viewer_series"]["T-TPT"]["samples"][20]["quality"] == "invalid"
    qgl = next(row for row in r["inventory"] if row["sensor"] == "QGL")
    assert qgl["valid_count"] == 1001 and not qgl["observed_by_muse"]
    assert case == before
    assert r["series"]["P-PDG"]["samples"][4]["value"] == frame["P-PDG"].iloc[4]
    assert "annotation" not in canonical(r["workflow"])


def test_wrong_mapping_missing_window_and_changed_measurement_fail_closed():
    frame, case, entry = fixture()
    with pytest.raises(ValueError):
        project(frame, entry, case, 402)
    frame.loc[405, "P-PDG"] = -100
    with pytest.raises(ValueError, match="captured"):
        project(frame, entry, case, 400)


def test_invalid_quality_cannot_masquerade_as_numeric_evidence():
    frame, case, entry = fixture()
    frame.loc[2, "T-TPT__quality"] = "missing"
    with pytest.raises(ValueError, match="quality"):
        project(frame, entry, case, 400)


def test_fixture_hash_schema_and_time_checks(tmp_path):
    frame, _, entry = fixture()
    path = tmp_path / entry["file"]
    frame.to_parquet(path)
    entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert read_fixture(tmp_path, entry).equals(frame)
    entry["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="checksum"):
        read_fixture(tmp_path, entry)
    entry["file"] = "../private.parquet"
    with pytest.raises(ValueError, match="filename"):
        read_fixture(tmp_path, entry)


def test_extra_private_columns_and_bad_times_rejected(tmp_path):
    frame, _, entry = fixture()
    for bad in (
        frame.assign(class_label=9),
        frame.assign(elapsed_seconds=[0] * len(frame)),
    ):
        path = tmp_path / entry["file"]
        bad.to_parquet(path)
        entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with pytest.raises(ValueError):
            read_fixture(tmp_path, entry)


def test_loading_regenerates_allowlist_and_does_not_trust_alerts_or_private_fields(
    tmp_path,
):
    frame, case, entry = fixture()
    replay = project(frame, entry, case, 400)
    replay["true_event"] = "PRIVATE_SENTINEL"
    replay["workflow"]["monitor"]["trace"][0]["alerted"] = True
    replay["workflow"]["onset"] = "PRIVATE_SENTINEL"
    replay["inventory"][0]["path"] = "PRIVATE_SENTINEL"
    payload = {
        "version": "monitoring-replay-v1",
        "capture_protocol": CAPTURE_PROTOCOL,
        "cases": {
            case["id"]: {"packet_digest": digest(case["packet"]), "replay": replay}
        },
    }
    (tmp_path / "viewer.json").write_text(canonical(payload))
    clean = load_monitoring(tmp_path, [case])
    assert "PRIVATE_SENTINEL" not in canonical(clean)
    assert not clean["cases"][case["id"]]["replay"]["workflow"]["monitor"]["trace"][0][
        "alerted"
    ]
    case["packet"]["baseline"]["prediction"] = 2
    with pytest.raises(ValueError, match="packet"):
        load_monitoring(tmp_path, [case])


def test_private_annotation_only_used_for_offline_scoring(tmp_path, monkeypatch):
    frame, case, entry = fixture()
    frame.to_parquet(tmp_path / entry["file"])
    entry["sha256"] = hashlib.sha256(
        (tmp_path / entry["file"]).read_bytes()
    ).hexdigest()
    case2 = deepcopy(case)
    case2["id"] = "other"
    entry2 = {**entry, "file": "case-2.parquet"}
    (tmp_path / entry2["file"]).write_bytes((tmp_path / entry["file"]).read_bytes())
    manifest = {
        "version": "local-telemetry-review-v1",
        "cases": [entry, entry2],
        "dataset_license": {},
    }
    (tmp_path / "manifest.json").write_text(canonical(manifest))
    rows = []
    for i, c in enumerate((case, case2), 1):
        rows.append(
            {
                "case_alias": f"case-{i}",
                "task_id": c["id"],
                "classifier_boundary": {"original_window_start_row_offline": 500},
                "review_clip": {"start_row_offline": 100},
                "offline_annotation_reference": {"first_transient_row": 500},
            }
        )
    report = {
        "version": "history-audit-v1",
        "status": "actual_local_files_audited",
        "cases": rows,
    }
    path = tmp_path / "private-report.json"
    path.write_text(canonical(report))
    monkeypatch.setattr(
        "petromind.monitoring_replay.demo_cases", lambda _: [case, case2]
    )
    a = prepare_monitoring(None, tmp_path, path, tmp_path / "a")
    report["cases"][0]["offline_annotation_reference"]["first_transient_row"] = 600
    path.write_text(canonical(report))
    b = prepare_monitoring(None, tmp_path, path, tmp_path / "b")
    assert a["cases"][0]["first_alert_index"] == b["cases"][0]["first_alert_index"]
    assert (tmp_path / "a/viewer.json").read_bytes() == (
        tmp_path / "b/viewer.json"
    ).read_bytes()
    assert (
        a["cases"][0]["alert_minus_annotation_seconds_OFFLINE_ONLY"]
        != b["cases"][0]["alert_minus_annotation_seconds_OFFLINE_ONLY"]
    )


def test_absent_channel_cannot_have_unacknowledged_recordings():
    frame, case, entry = fixture()
    entry["present_sensor_ids"].remove("QGL")
    with pytest.raises(ValueError, match="Absent"):
        project(frame, entry, case, 400)
