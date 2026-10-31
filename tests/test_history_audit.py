"""Constructed histories: no claims about the two unavailable real incidents."""

import json

import numpy as np
import pandas as pd
import pytest

from petromind.history_audit import (
    analyze_frame,
    export_fixture,
    timing,
    trajectory_svg,
)


def history():
    return pd.DataFrame(
        {
            "class": [0] * 10 + [102] * 600 + [2] * 5 + [None] * 2,
            "state": [0] * 5 + [1] * 5 + [0] * 607,
            "P-PDG": np.arange(617, dtype=float),
            "P-TPT": [0.0] * 617,
            "QGL": [None] * 617,
            "T-TPT": [20.0] * 617,
        },
        index=pd.date_range("2020", periods=617, freq="s"),
    )


def test_counts_distinguish_normal_transient_steady_and_unknown():
    frame = history()
    report, bounds, _ = analyze_frame(frame)
    assert report["samples_total"] == 617
    assert report["samples_before_first_transient"] == 10
    assert report["samples_in_initial_transient_run"] == 600
    assert report["samples_after_initial_transient_run"] == 7
    assert report["samples_in_all_transient_conditions"] == 600
    assert bounds[:2] == (10, 610)
    assert report["timing"]["recording_duration_seconds"] == 616
    assert report["regions"]["before_first_transient"][
        "class_annotation_categories"
    ] == {"annotated_normal_operation": 10}
    assert report["regions"]["before_first_transient"][
        "operational_annotation_categories"
    ] == {"open": 5, "shut_in": 5}
    assert (
        report["classifier_boundary"]["first_eligible_original_prediction_row_offline"]
        == 609
    )
    assert report["detector"]["status"] == "not_run_pending_data_review"
    assert report["detector"]["timing_relative_to_annotation"] != "never"


def test_zero_constant_missing_invalid_are_separate_and_absent_not_missing():
    frame = history()
    frame.loc[frame.index[2], "P-PDG"] = np.inf
    frame.loc[frame.index[3], "P-PDG"] = 1e13
    frame.loc[frame.index[4], "P-PDG"] = np.nan
    report, _, _ = analyze_frame(frame)
    sensors = {s["sensor"]: s for s in report["sensors"]}
    zero = sensors["P-TPT"]["quality_by_region"]["whole_record"]
    assert zero["is_constant"] and zero["available"] and zero["zero_count"] == 617
    assert (
        sensors["QGL"]["present"]
        and not sensors["QGL"]["quality_by_region"]["whole_record"]["available"]
    )
    assert not sensors["ABER-CKGL"]["present"]
    quality = sensors["P-PDG"]["quality_by_region"]["whole_record"]
    assert (
        quality["missing_count"] == 1
        and quality["extreme_count"] == 1
        and quality["nonfinite_count"] == 1
    )
    assert sensors["P-PDG"]["availability_transition_count"] > 0


def test_irregular_time_and_unknowns_reported_without_repair():
    frame = history()
    frame.index = frame.index.where(np.arange(617) != 3, pd.NaT)
    result, _ = timing(frame.index)
    assert (
        result["missing_timestamps"] == 1 and result["unknown_neighbor_intervals"] == 2
    )
    assert result["recording_duration_seconds"] is None
    frame = history()
    index = frame.index.to_list()
    index[3] = index[2]
    result, _ = timing(pd.DatetimeIndex(index))
    assert (
        result["duplicate_neighbor_pairs"] == 1
        and not result["ordered_unique_timestamps"]
    )
    result, _ = timing(pd.date_range("2020", periods=10, freq="2s"))
    assert (
        result["modal_positive_interval_seconds"] == 2
        and result["pairs_not_at_frozen_one_second_cadence"] == 9
    )


def test_annotation_categories_do_not_assume_every_prefix_is_normal():
    frame = history()
    frame.loc[frame.index[:3], "class"] = np.nan
    frame.loc[frame.index[3:5], "class"] = 103  # No such transient in authors Table 4.
    report, _, _ = analyze_frame(frame)
    counts = report["regions"]["before_first_transient"]["class_annotation_categories"]
    assert counts["unknown"] == 3 and counts["undocumented_code"] == 2
    assert (
        report["baseline_feasibility"]["status"]
        == "requires_review_not_automatically_approved"
    )
    channels = report["sensors"]
    assert all(c["trailing_annotated_normal_samples"] == 5 for c in channels)


def test_no_pre_history_is_not_fabricated():
    frame = history().iloc[10:].copy()
    report, _, _ = analyze_frame(frame)
    assert report["samples_before_first_transient"] == 0
    assert not report["baseline_feasibility"]["earlier_samples_exist"]
    assert all(c["pre_transient_mad"] is None for c in report["sensors"])


def test_plots_and_fixture_strip_sensitive_metadata_and_preserve_gaps(tmp_path):
    frame = history()
    frame.attrs["well"] = "WELL-secret"
    frame.loc[frame.index[2], "P-PDG"] = np.inf
    frame.loc[frame.index[3], "P-PDG"] = np.nan
    _report, bounds, seconds = analyze_frame(frame, before_seconds=5, after_seconds=600)
    svg = trajectory_svg(frame, seconds, bounds)
    assert "annotated transition is not a detector alert" in svg
    for private in ("WELL-secret", "2020-01-01", "102", "true_event"):
        if private == "102":
            continue  # Recorded numeric telemetry may legitimately equal 102.
        assert private not in svg
    fixture = export_fixture(
        tmp_path / "fixture", frame, seconds, (10, 610, 0, len(frame)), 1
    )
    data = pd.read_parquet(tmp_path / "fixture" / fixture["file"])
    assert "class" not in data and "state" not in data
    assert not isinstance(data.index, pd.DatetimeIndex) and data.attrs == {}
    assert data["P-PDG__quality"].iloc[2] == "invalid"
    assert data["P-PDG__quality"].iloc[3] == "missing"
    assert data["P-TPT"].iloc[0] == 0 and data["P-TPT__quality"].iloc[0] == "valid"
    assert data["elapsed_seconds"].iloc[-1] == 616
    assert len(fixture["sha256"]) == 64
    assert (
        "P-TPT" in fixture["present_sensor_ids"]
        and "ABER-CKGL" not in fixture["present_sensor_ids"]
    )
    assert "NOT anonymization" in fixture["warning"]


def test_invalid_timestamp_fixture_refused(tmp_path):
    frame = history()
    _report, bounds, seconds = analyze_frame(frame)
    idx = frame.index.to_list()
    idx[1] = idx[0]
    frame.index = pd.DatetimeIndex(idx)
    result = export_fixture(tmp_path / "out", frame, seconds, bounds, 1)
    assert result["status"] == "not_exported_invalid_timestamps"
    assert not (tmp_path / "out").exists()


def test_future_changes_do_not_enter_earlier_descriptive_statistics():
    first = history()
    second = first.copy()
    second.loc[second.index[10:], "P-PDG"] = 99999999.0
    a, _, _ = analyze_frame(first)
    b, _, _ = analyze_frame(second)
    aa = next(s for s in a["sensors"] if s["sensor"] == "P-PDG")
    bb = next(s for s in b["sensors"] if s["sensor"] == "P-PDG")
    assert (
        aa["quality_by_region"]["before_first_transient"]
        == bb["quality_by_region"]["before_first_transient"]
    )
    assert aa["pre_transient_mad"] == bb["pre_transient_mad"]
    # This checks offline partition statistics, not a nonexistent causal detector.
    assert a["detector"]["status"] == "not_run_pending_data_review"


def test_cli_missing_data_fails_without_output_or_model_calls(
    tmp_path, monkeypatch, capsys
):
    import runpy
    import sys

    source = tmp_path / "private.json"
    source.write_text("{}")
    out = tmp_path / "audit"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_incident_history.py",
            "--capture",
            str(tmp_path / "capture"),
            "--dataset",
            str(tmp_path / "absent"),
            "--science-protocol",
            str(source),
            "--out",
            str(out),
        ],
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("No API is allowed")

    monkeypatch.setattr("petromind.meta_api.MetaResponsesClient.create", forbidden)
    with pytest.raises(SystemExit) as result:
        runpy.run_path("scripts/audit_incident_history.py", run_name="__main__")
    assert result.value.code == 2 and not out.exists()
    report = json.loads(capsys.readouterr().out)
    assert (
        report["api_requests"] == 0
        and report["status"] == "history_audit_precondition_failed"
    )
