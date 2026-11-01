"""Software tests only: artificial signals do not establish physical validity."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from petromind.causal_monitor import CausalMonitor, MonitorConfig, monitor_trace
from petromind.incident_replay import sample


def trace_values(n=450):
    return {
        s: {"samples": [sample(10 + i % 7 if i < 350 else 1000) for i in range(n)]}
        for s in MonitorConfig().sensors
    }


def test_rule_matches_pre_scoring_frozen_spec():
    spec = json.loads(Path("docs/monitoring/rule-v1.json").read_text())
    c = MonitorConfig()
    assert list(c.sensors) == spec["sensors"]
    assert c.z_min == spec["absolute_robust_z_min"]
    assert c.warmup_seconds == spec["warmup_seconds"]
    assert c.persistence_seconds == spec["persistence_seconds"]
    assert c.minimum_reference_samples == spec["minimum_reference_samples"]
    assert c.maximum_gap_seconds == spec["maximum_gap_seconds"]


def test_reference_uses_only_completed_warmup_and_persistence_is_real_seconds():
    rows = monitor_trace(range(450), trace_values())
    assert all(r["state"] == "warmup" for r in rows[:300])
    assert rows[350]["state"] == "pending"
    assert rows[379]["new_alert"] is False
    assert rows[380]["new_alert"] is True
    assert sum(r["new_alert"] for r in rows) == 1
    assert rows[-1]["alerted"]


def test_arbitrary_changed_future_cannot_change_any_prefix_decision():
    original = trace_values()
    changed = deepcopy(original)
    for stream in changed.values():
        stream["samples"][360:] = [sample(-1e8)] * 90
    a = monitor_trace(range(450), original)
    b = monitor_trace(range(450), changed)
    prefix = monitor_trace(
        range(360), {s: {"samples": v["samples"][:360]} for s, v in original.items()}
    )
    assert a[:360] == b[:360] == prefix


@pytest.mark.parametrize("value", [0, 100, None, float("inf"), 1e13])
def test_zero_constant_missing_and_invalid_never_create_a_mad_scale(value):
    series = {s: {"samples": [sample(value)] * 450} for s in MonitorConfig().sensors}
    rows = monitor_trace(range(450), series)
    assert rows[-1]["state"] == "reference_unavailable"
    assert not any(r["alerted"] for r in rows)


@pytest.mark.parametrize("bad", [sample(None), sample(float("inf")), sample(1e13)])
def test_unavailable_resets_persistence_even_when_other_pressure_deviates(bad):
    series = trace_values()
    series["P-TPT"]["samples"][370] = bad
    rows = monitor_trace(range(450), series)
    assert rows[370]["state"] == "measurement_unavailable"
    assert not rows[400]["alerted"]
    assert rows[401]["new_alert"]


def test_gap_resets_persistence_and_does_not_count_unobserved_time():
    times = list(range(450))
    times[370:] = [t + 100 for t in times[370:]]
    rows = monitor_trace(times, trace_values())
    assert rows[370]["gap_reset"]
    assert not rows[399]["alerted"]
    assert rows[400]["new_alert"]


def test_one_signal_is_not_a_two_signal_alert():
    series = trace_values()
    series["P-TPT"]["samples"] = [sample(10 + i % 7) for i in range(450)]
    assert not any(r["alerted"] for r in monitor_trace(range(450), series))


def test_too_few_reference_observations_fail_closed():
    series = trace_values()
    series["P-PDG"]["samples"][:100] = [sample(None)] * 100
    assert monitor_trace(range(450), series)[-1]["state"] == "reference_unavailable"


@pytest.mark.parametrize("time", [-1, float("inf"), float("nan")])
def test_invalid_time_rejected(time):
    with pytest.raises(ValueError):
        CausalMonitor().step(time, {})


def test_nonmonotonic_or_duplicate_time_rejected():
    m = CausalMonitor()
    m.step(1, {})
    with pytest.raises(ValueError):
        m.step(1, {})


def test_hidden_or_annotation_fields_have_no_effect():
    a, b = CausalMonitor(), CausalMonitor()
    for i in range(450):
        values = {
            s: sample(10 + i % 7 if i < 350 else 1000) for s in MonitorConfig().sensors
        }
        assert a.step(i, values) == b.step(
            i, {**values, "class": 109, "state": 0, "onset": 350}
        )
