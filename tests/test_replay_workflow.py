"""Checkpoint policy uses loaded evidence boundaries, never labels or thresholds."""

from copy import deepcopy

import pytest

from petromind.replay_workflow import replay_workflow


def raw():
    return {
        "mode": "raw",
        "timestamps": [
            "2020-01-01T00:00:00",
            "2020-01-01T00:00:02",
            "2020-01-01T00:00:05",
        ],
        "series": {"P-TPT": {"samples": [{"value": 1}] * 3}},
        "viewer_series": {},
    }


def test_trigger_uses_complete_loaded_evidence_and_actual_timestamps():
    replay = raw()
    before = deepcopy(replay)
    w = replay_workflow(replay)
    assert w["positions"] == 3 and w["elapsed_seconds"] == [0, 2, 5]
    assert w["checkpoint"]["index"] == 2
    assert w["checkpoint"]["timestamp"] == replay["timestamps"][-1]
    assert not w["checkpoint"]["historical_operational_alarm"]
    assert w["checkpoint"]["retrospective"]
    assert replay == before


def test_trigger_does_not_depend_on_readings_or_hidden_labels():
    first = raw()
    second = deepcopy(first)
    second["series"]["P-TPT"]["samples"] = [{"value": None}] * 3
    second["true_event"] = 9
    second["private_locator"] = "must-not-export"
    assert replay_workflow(first) == replay_workflow(second)
    assert "must-not-export" not in str(replay_workflow(second))


def test_endpoint_comparison_has_no_timestamp_or_continuous_sample_count():
    r = {
        "mode": "endpoints",
        "sample_labels": ["First valid", "Last valid"],
        "timestamps": None,
        "can_play": False,
        "series": {"P-TPT": {"samples": [{"value": 1}, {"value": 2}]}},
        "viewer_series": {},
    }
    w = replay_workflow(r)
    assert w["positions"] == 2 and w["counter_unit"] == "captured endpoints"
    assert w["elapsed_seconds"] is None and w["checkpoint"]["timestamp"] is None
    r["can_play"] = True
    with pytest.raises(ValueError):
        replay_workflow(r)


@pytest.mark.parametrize(
    "times", [[], ["2020"], ["2020", "2020"], ["2021", "2020"], [None, "2020"]]
)
def test_bad_timestamps_fail_closed(times):
    r = raw()
    r["timestamps"] = times
    with pytest.raises(ValueError):
        replay_workflow(r)


def test_inconsistent_channel_lengths_rejected():
    r = raw()
    r["viewer_series"]["QGL"] = {"samples": [{"value": 0}]}
    with pytest.raises(ValueError, match="share the timeline"):
        replay_workflow(r)
