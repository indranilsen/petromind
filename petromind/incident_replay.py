"""Trusted viewer-only replay adapter. Never register it as an agent tool."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .claim_evaluation import checked_protocol
from .data import read_incident, well_id
from .knowledge import SENSORS, PhysicalKnowledge
from .measurements import MAX_ABS_RAW, summarize

FRIENDLY = {
    "P-PDG": (
        "Downhole pressure",
        "Pressure measured by the permanent downhole gauge.",
    ),
    "P-TPT": ("Tree pressure", "Pressure measured at the subsea tree transducer."),
    "ABER-CKGL": (
        "Gas-lift choke opening",
        "Reported opening of the choke used for gas lift; not a DHSV valve-state reading.",
    ),
    "T-PDG": ("Downhole temperature", "Temperature at the permanent downhole gauge."),
    "T-TPT": ("Tree temperature", "Temperature at the subsea tree transducer."),
    "QGL": ("Gas-lift flow", "Flow rate of gas used for gas lift."),
    "ESTADO-DHSV": (
        "Safety-valve state",
        "Encoded downhole safety-valve state; no actual state was supplied to these audits.",
    ),
}
# Public catalog names describe generic documented associations, never an exact
# installed layout. Only the allowlisted measurement columns can reach a viewer.
_EXTRA_NAMES = {
    "ABER-CKP": "Production-choke opening",
    "P-ANULAR": "Annulus pressure",
    "P-JUS-BS": "Service-pump outlet pressure",
    "P-JUS-CKGL": "Gas-lift choke outlet pressure",
    "P-JUS-CKP": "Production-choke outlet pressure",
    "P-MON-CKGL": "Gas-lift choke inlet pressure",
    "P-MON-CKP": "Production-choke inlet pressure",
    "P-MON-SDV-P": "Production shutdown-valve inlet pressure",
    "PT-P": "Production wing-valve outlet pressure",
    "QBS": "Service-pump flow",
    "T-JUS-CKP": "Production-choke outlet temperature",
    "T-MON-CKP": "Production-choke inlet temperature",
}
for _sensor, _info in SENSORS.items():
    if _sensor not in FRIENDLY:
        _name = _EXTRA_NAMES.get(
            _sensor, _info["equipment"].replace("_", " ").capitalize() + " state"
        )
        FRIENDLY[_sensor] = (
            _name,
            _info["quantity_relation"].replace("_", " ").capitalize()
            + " "
            + _info["equipment"].replace("_", " ")
            + ".",
        )
DISPLAY_SENSORS = tuple(FRIENDLY)


def sensor_group(sensor):
    if SENSORS[sensor]["quantity_relation"].startswith("pressure"):
        return "Pressure"
    if sensor.startswith("T-"):
        return "Temperature"
    if sensor.startswith("ESTADO-"):
        return "Valve / equipment state"
    return "Flow / opening / other"


def inventory(case, window=None):
    """Column presence is unknown without raw data; an all-missing column is
    distinct from an absent column and from a channel not given to Muse."""
    result = []
    for sensor in SENSORS:
        captured = case["observations"].get(sensor)
        summary = (
            summarize(window[sensor]).to_dict()
            if window is not None and sensor in window
            else captured
        )
        present = (
            sensor in window
            if window is not None
            else (True if captured and captured["available"] else None)
        )
        result.append(
            {
                "sensor": sensor,
                "group": sensor_group(sensor),
                "present_in_incident": bool(present) if present is not None else None,
                "observed_by_muse": captured is not None,
                "availability": "not_present"
                if present is False
                else "unknown"
                if summary is None
                else "available"
                if summary["available"]
                else "no_valid_measurements",
                "valid_count": None if summary is None else summary["count"],
                "missing_count": None
                if summary is None
                else summary.get("missing_count"),
                "invalid_count": None if summary is None else summary["invalid_count"],
            }
        )
    return result


def definitions():
    graph = PhysicalKnowledge()
    return {
        s: {
            "id": s,
            "name": name,
            "description": description,
            **SENSORS[s],
            "location_fact": graph.fact("location:" + s),
            "unit_fact": graph.fact("unit:" + s),
            "valve_encodings": [graph.fact("valve:" + str(v)) for v in (0, 1, 0.5)]
            if s == "ESTADO-DHSV"
            else [],
            "scope": "Documented generic sensor association. Illustration coordinates and well layout are not verified for this well.",
        }
        for s, (name, description) in FRIENDLY.items()
    }


def sample(value):
    """JSON-safe quality, preserving missingness and legitimate zeros."""
    if pd.isna(value):
        return {"value": None, "quality": "missing", "reason": "missing_sample"}
    try:
        number = float(value)
    except (TypeError, ValueError):
        return {"value": None, "quality": "invalid", "reason": "nonnumeric"}
    if not math.isfinite(number):
        return {"value": None, "quality": "invalid", "reason": "nonfinite"}
    if abs(number) > MAX_ABS_RAW:
        return {
            "value": None,
            "quality": "invalid",
            "reason": "numeric_guardrail_not_physical_limit",
        }
    return {"value": number, "quality": "valid", "reason": None}


def endpoints(case, reason="raw_dataset_unavailable"):
    series = {}
    for s, summary in case["observations"].items():
        if not summary["available"]:
            quality = (
                "invalid"
                if summary.get("missing_count", 0) == 0 and summary["invalid_count"] > 0
                else "missing"
            )
            values = [
                {
                    "value": None,
                    "quality": quality,
                    "reason": "no_valid_samples_in_capture; endpoint timestamps unavailable",
                }
                for _ in range(2)
            ]
        else:
            values = [sample(summary[k]) for k in ("first", "last")]
        series[s] = {
            "samples": values,
            "summary": summary,
            "agent_received": "summary_only",
            "reference": summary["first"],
            "reference_kind": "first valid captured value, not verified normal",
        }
    return {
        "mode": "endpoints",
        "inventory": inventory(case),
        "viewer_series": {},
        "availability": reason,
        "timestamps": None,
        "elapsed_seconds": None,
        "sample_labels": ["First valid captured value", "Last valid captured value"],
        "series": series,
        "can_play": False,
        "interpolation": "none",
        "downsampling": "none",
        "timing": "No raw timestamps. First/last valid values may occur at different instants for different sensors.",
        "visibility": "Captured summary evidence; no new observations charged or sent to Muse.",
        "reference_note": "Change from each sensor's first valid observation; not a safe/normal pressure threshold.",
    }


def raw_payload(window, case):
    """Keep captured evidence separate from allowlisted post-hoc viewer telemetry.

    This public viewer projection must never be supplied to an agent.
    """
    if (
        len(window) != 600
        or not isinstance(window.index, pd.DatetimeIndex)
        or window.index.hasnans
        or not window.index.is_unique
        or not window.index.is_monotonic_increasing
        or not (np.diff(window.index.as_unit("ns").asi8) == 1_000_000_000).all()
    ):
        raise ValueError("Expected the original 600 ordered one-second observations")
    series = {}
    for sensor, expected in case["observations"].items():
        values = window[sensor] if sensor in window else pd.Series([None] * 600)
        actual = summarize(values).to_dict()
        # JSON tuples/list quality flags are semantically equivalent.
        if {**actual, "quality_flags": list(actual["quality_flags"])} != expected:
            raise ValueError("Raw telemetry differs from the charged captured summary")
        samples = [sample(v) for v in values]
        first = next(
            (i for i, v in enumerate(samples) if v["quality"] == "valid"), None
        )
        series[sensor] = {
            "samples": samples,
            "summary": expected,
            "agent_received": "summary_only",
            "reference": None if first is None else samples[first]["value"],
            "reference_index": first,
            "reference_kind": "first valid diagnostic-window sample, not verified normal",
        }
    # Explicitly separate post-hoc viewer channels from the immutable audit
    # evidence. Never put these values in case.packet or an agent tool response.
    viewer_series = {}
    for sensor in SENSORS:
        if sensor in case["observations"]:
            continue
        values = window[sensor] if sensor in window else pd.Series([None] * 600)
        samples = [sample(v) for v in values]
        first = next(
            (i for i, v in enumerate(samples) if v["quality"] == "valid"), None
        )
        viewer_series[sensor] = {
            "samples": samples,
            "agent_received": "not_observed_in_audit",
            "reference": None if first is None else samples[first]["value"],
            "reference_kind": "first valid viewer-window sample, not verified normal",
        }
    return {
        "mode": "raw",
        "inventory": inventory(case, window),
        "viewer_series": viewer_series,
        "availability": "verified_raw_window",
        "can_play": True,
        "timestamps": [t.isoformat() for t in window.index],
        "elapsed_seconds": list(range(600)),
        "sample_labels": None,
        "series": series,
        "timing": "600 observations at 1 Hz; 599 seconds from first to last. Original timestamps retained; timezone as encoded (may be unspecified).",
        "interpolation": "none",
        "downsampling": "none",
        "visibility": "Viewer-only raw samples, including additional allowlisted channels. Muse received only the original fixed captured summaries; viewer channels and slider position never enter agent input.",
        "reference_note": "Change from each sensor's first valid observation; not a safe/normal pressure threshold.",
    }


def attach_replay(case, claim_protocol, *, dataset=None, science_protocol=None):
    """Resolve by protocol locator hash, never by guessing event filenames/classes."""
    if dataset is None or not Path(dataset).is_dir():
        return endpoints(case)
    if science_protocol is None:
        return endpoints(case, "private_source_protocol_required")
    checked_protocol(science_protocol)
    parent = science_protocol["parent"]
    checked_protocol(parent)
    if science_protocol["protocol_id"] != claim_protocol["source_protocol_id"]:
        raise ValueError("Unrelated private source protocol")
    task = next(t for t in claim_protocol["tasks"] if t["task_id"] == case["id"])
    cid = task["source_case_id"]
    if cid not in science_protocol["case_ids"]:
        raise ValueError("Unknown source case")
    records = [r for r in parent["records"] if r["case_id"] == cid]
    if len(records) != 1 or records[0]["role"] != "development_pool":
        raise ValueError("Replay requires a development case")
    record = records[0]
    hash_well = lambda w: hashlib.sha256(w.encode()).hexdigest()
    dev = {hash_well(w) for w in parent["development_wells"]}
    forbidden = {
        hash_well(w)
        for w in parent["original_split"]["test_wells"]
        + parent["retrieval_split"]["train_wells"]
    }
    if record["well_group"] not in dev or record["well_group"] in forbidden:
        raise ValueError("Development isolation violated")
    root = Path(dataset).resolve()
    matches = [
        p
        for p in root.rglob("*.parquet")
        if hashlib.sha256(p.relative_to(root).as_posix().encode()).hexdigest()
        == record["locator_hash"]
    ]
    if len(matches) != 1:
        raise ValueError("Private locator did not resolve uniquely")
    path = matches[0]
    if (
        not path.resolve().is_relative_to(root)
        or hash_well(well_id(path)) != record["well_group"]
    ):
        raise ValueError("Private locator well mismatch")
    if hashlib.sha256(path.read_bytes()).hexdigest() != record["file_hash"]:
        raise ValueError("Frozen incident changed")
    # Existing trusted loader validates onset/labels/cadence. Labels stay private.
    read_incident(path, 600)
    raw = pd.read_parquet(path)
    positions = np.flatnonzero(
        pd.to_numeric(raw["class"], errors="coerce").isin(range(101, 110)).to_numpy()
    )
    window = raw.iloc[int(positions[0]) : int(positions[0]) + 600]
    return raw_payload(window, case)
