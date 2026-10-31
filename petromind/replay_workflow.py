"""Viewer-only retrospective checkpoint. Not a detector or historical alarm."""

import pandas as pd

VERSION = "complete-evidence-checkpoint-v1"


def replay_workflow(replay):
    mode = replay["mode"]
    if mode == "raw":
        timestamps = pd.DatetimeIndex(replay["timestamps"])
        if (
            len(timestamps) < 2
            or timestamps.hasnans
            or not timestamps.is_unique
            or not timestamps.is_monotonic_increasing
        ):
            raise ValueError("Expected ordered replay timestamps")
        count = len(timestamps)
        elapsed = ((timestamps - timestamps[0]).total_seconds()).tolist()
        timestamp = timestamps[-1].isoformat()
        counter = "recorded samples"
    elif mode == "endpoints":
        count = len(replay["sample_labels"])
        if count != 2 or replay["timestamps"] is not None or replay["can_play"]:
            raise ValueError("Endpoint fallback must not imply a continuous replay")
        elapsed, timestamp, counter = None, None, "captured endpoints"
    else:
        raise ValueError("Unknown replay mode")
    if any(
        len(s["samples"]) != count
        for s in {**replay["series"], **replay.get("viewer_series", {})}.values()
    ):
        raise ValueError("Replay channels must share the timeline")
    return {
        "version": VERSION,
        "positions": count,
        "counter_unit": counter,
        "elapsed_seconds": elapsed,
        "checkpoint": {
            "kind": "demo_investigation_checkpoint",
            "label": "Demo investigation checkpoint",
            "index": count - 1,
            "timestamp": timestamp,
            "rule": "Reveal the frozen diagnosis only at the final position of the loaded window or endpoint comparison; the prediction uses complete-window summaries.",
            "historical_operational_alarm": False,
            "retrospective": True,
            "explanation": "The saved statistical prediction uses complete-window summaries; it is not an early-warning prediction. No operational alarm threshold is supplied.",
        },
    }
