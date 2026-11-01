"""Explicit, local-only projection of reviewed history into a viewer replay.

No detector input includes annotation bounds. Private bounds are used only to
verify the unchanged 600-sample capture and separately score alert timing.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .audit import canonical
from .causal_monitor import MonitorConfig, monitor_trace
from .claim_review import CAPTURE_PROTOCOL, demo_cases
from .eval_protocol import digest
from .incident_replay import inventory, sample
from .knowledge import SENSORS
from .measurements import summarize

VERSION = "monitoring-replay-v1"


def read_fixture(directory, entry):
    directory = Path(directory)
    name = entry["file"]
    if name not in ("case-1.parquet", "case-2.parquet"):
        raise ValueError("Unexpected fixture filename")
    path = directory / name
    if path.is_symlink() or path.resolve().parent != directory.resolve():
        raise ValueError("Unsafe fixture path")
    if path.stat().st_size > 20_000_000:
        raise ValueError("Fixture too large")
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise ValueError("Fixture checksum mismatch")
    frame = pd.read_parquet(path)
    expected = {"elapsed_seconds"} | {
        s + suffix for s in SENSORS for suffix in ("", "__quality", "__reason")
    }
    if (
        set(frame.columns) != expected
        or len(frame) != entry["samples"]
        or not 601 <= len(frame) <= 10000
    ):
        raise ValueError("Unexpected fixture schema or length")
    times = frame.elapsed_seconds.to_numpy(dtype=float)
    if not np.isfinite(times).all() or times[0] != 0 or not (np.diff(times) > 0).all():
        raise ValueError("Invalid fixture times")
    if not set(entry["present_sensor_ids"]).issubset(SENSORS):
        raise ValueError("Unknown sensor metadata")
    return frame


def project(frame, entry, case, window_start):
    """Allowlist every public field. Never serialize the private audit report."""
    window = frame.iloc[window_start : window_start + 600]
    if len(window) != 600 or not (np.diff(window.elapsed_seconds) == 1).all():
        raise ValueError("Original diagnostic window unavailable")
    for sensor, expected in case["observations"].items():
        actual = summarize(window[sensor]).to_dict()
        if {**actual, "quality_flags": list(actual["quality_flags"])} != expected:
            raise ValueError("Fixture differs from captured 600-sample evidence")
    series = {}
    for sensor in SENSORS:
        if (
            sensor not in entry["present_sensor_ids"]
            and not (frame[sensor + "__quality"] == "missing").all()
        ):
            raise ValueError("Absent sensor has supplied measurements")
        samples = []
        for value, quality, reason in zip(
            frame[sensor],
            frame[sensor + "__quality"],
            frame[sensor + "__reason"],
            strict=True,
        ):
            checked = sample(value)
            if quality == "valid":
                if checked["quality"] != "valid" or reason is not None:
                    raise ValueError("Inconsistent valid sample")
                samples.append(checked)
            elif quality in ("missing", "invalid") and pd.isna(value):
                # Reasons are enums, never arbitrary source strings in a browser.
                allowed = {
                    "missing_sample",
                    "nonfinite",
                    "nonnumeric",
                    "numeric_guardrail_not_physical_limit",
                }
                if reason not in allowed:
                    raise ValueError("Unexpected quality reason")
                samples.append({"value": None, "quality": quality, "reason": reason})
            else:
                raise ValueError("Inconsistent sample quality")
        series[sensor] = {
            "samples": samples,
            "reference": next(
                (p["value"] for p in samples if p["quality"] == "valid"), None
            ),
            "reference_kind": "First valid recorded value, normality unverified",
            "agent_received": "original_600_sample_summary_only"
            if sensor in case["observations"]
            else "not_observed",
        }
    # Inventory describes the whole viewer clip, never new agent observations.
    catalog = inventory(case, frame[list(entry["present_sensor_ids"])])
    for row in catalog:
        qualities = frame[row["sensor"] + "__quality"]
        row.update(
            valid_count=int((qualities == "valid").sum()),
            missing_count=int((qualities == "missing").sum()),
            invalid_count=int((qualities == "invalid").sum()),
        )
    elapsed = frame.elapsed_seconds.tolist()
    trace = monitor_trace(elapsed, series)
    replay = {
        "mode": "history",
        "can_play": True,
        "timestamps": None,
        "elapsed_seconds": elapsed,
        "sample_labels": None,
        "series": {s: series[s] for s in case["observations"]},
        "viewer_series": {
            s: v for s, v in series.items() if s not in case["observations"]
        },
        "inventory": catalog,
        "interpolation": "none",
        "downsampling": "none",
        "availability": "supplied_local_recorded_clip",
        "timing": "Actual relative recording times; calendar times withheld. Annotation-centered selection is retrospective, not a blinded detector trial.",
        "visibility": "Viewer-only history. Muse retains its original 600-sample summaries and five-query accounting.",
        "reference_note": "Earlier measured prefix, normality unverified; not a physical safety threshold.",
        "workflow": {
            "version": VERSION,
            "positions": len(frame),
            "counter_unit": "recorded samples",
            "elapsed_seconds": elapsed,
            "checkpoint": {
                "index": window_start + 599,
                "kind": "original_evidence_complete",
                "retrospective": True,
                "historical_operational_alarm": False,
            },
            "monitor": {"config": MonitorConfig().public(), "trace": trace},
        },
    }
    return replay


def prepare_monitoring(capture, fixture, history_report, out):
    """Offline only. Match private offsets to unchanged charged evidence."""
    out = Path(out)
    if out.exists():
        raise ValueError("Use a fresh output directory")
    manifest = json.loads((Path(fixture) / "manifest.json").read_text())
    report = json.loads(Path(history_report).read_text())
    cases = demo_cases(capture)
    if (
        manifest["version"] != "local-telemetry-review-v1"
        or report["version"] != "history-audit-v1"
        or report["status"] != "actual_local_files_audited"
        or len(manifest["cases"]) != len(cases)
        or len(report["cases"]) != len(cases)
    ):
        raise ValueError("Reviewed fixture and matching history report required")
    views, scores = {}, []
    for i, (case, entry, private) in enumerate(
        zip(cases, manifest["cases"], report["cases"], strict=True), 1
    ):
        if (
            entry["file"] != f"case-{i}.parquet"
            or private["case_alias"] != f"case-{i}"
            or private["task_id"] != case["id"]
        ):
            raise ValueError("Case mapping mismatch")
        frame = read_fixture(fixture, entry)
        start = (
            private["classifier_boundary"]["original_window_start_row_offline"]
            - private["review_clip"]["start_row_offline"]
        )
        if not isinstance(start, int) or start < 300:
            raise ValueError("Insufficient earlier context")
        replay = project(frame, entry, case, start)
        trace = replay["workflow"]["monitor"]["trace"]
        first = next((i for i, row in enumerate(trace) if row["new_alert"]), None)
        # Offline annotation only: deliberately excluded from replay and detector.
        onset = (
            private["offline_annotation_reference"]["first_transient_row"]
            - private["review_clip"]["start_row_offline"]
        )
        scores.append(
            {
                "case_alias": f"case-{i}",
                "samples": len(frame),
                "first_alert_index": first,
                "first_alert_elapsed_seconds": None
                if first is None
                else replay["elapsed_seconds"][first],
                "annotation_index_OFFLINE_ONLY": onset,
                "alert_minus_annotation_seconds_OFFLINE_ONLY": None
                if first is None
                else replay["elapsed_seconds"][first]
                - replay["elapsed_seconds"][onset],
                "diagnosis_ready_index": start + 599,
                "source_sha256": entry["sha256"],
                "packet_unchanged": True,
            }
        )
        views[case["id"]] = {"packet_digest": digest(case["packet"]), "replay": replay}
    payload = {
        "version": VERSION,
        "capture_protocol": CAPTURE_PROTOCOL,
        "cases": views,
        "attribution": manifest["dataset_license"],
        "limitations": [
            "User-supplied recorded projection; original full dataset unavailable here.",
            "Checksum verifies upload integrity, not independent dataset authenticity.",
            "Two annotation-centered development clips; no prospective or population performance claim.",
        ],
    }
    out.mkdir(parents=True)
    (out / "viewer.json").write_text(canonical(payload) + "\n")
    evaluation = {
        "version": VERSION,
        "api_requests": 0,
        "config": MonitorConfig().public(),
        "cases": scores,
        "limitations": payload["limitations"],
        "audience": "offline_review_only_never_agent_or_browser",
    }
    (out / "offline-report.json").write_text(canonical(evaluation) + "\n")
    return evaluation


def load_monitoring(directory, cases):
    payload = json.loads((Path(directory) / "viewer.json").read_text())
    if (
        payload["version"] != VERSION
        or payload["capture_protocol"] != CAPTURE_PROTOCOL
        or set(payload["cases"]) != {c["id"] for c in cases}
    ):
        raise ValueError("Wrong monitoring bundle")
    for case in cases:
        row = payload["cases"][case["id"]]
        if row["packet_digest"] != digest(case["packet"]):
            raise ValueError("Changed agent packet")
    from .history_audit import DATA_LICENSE

    sanitized = {}
    for case in cases:
        raw = payload["cases"][case["id"]]["replay"]
        streams = {**raw["series"], **raw["viewer_series"]}
        times = raw["elapsed_seconds"]
        if set(streams) != set(SENSORS) or not 601 <= len(times) <= 10000:
            raise ValueError("Invalid monitoring streams")
        if (
            not np.isfinite(times).all()
            or times[0] != 0
            or not (np.diff(times) > 0).all()
        ):
            raise ValueError("Invalid monitoring times")
        columns = {"elapsed_seconds": times}
        for sensor, stream in streams.items():
            samples = stream["samples"]
            if len(samples) != len(times):
                raise ValueError("Inconsistent monitoring stream")
            for suffix, key in (
                ("", "value"),
                ("__quality", "quality"),
                ("__reason", "reason"),
            ):
                columns[sensor + suffix] = [sample[key] for sample in samples]
        present = [
            r["sensor"] for r in raw["inventory"] if r["present_in_incident"] is True
        ]
        if not set(present).issubset(SENSORS):
            raise ValueError("Invalid monitoring inventory")
        start = raw["workflow"]["checkpoint"]["index"] - 599
        if not isinstance(start, int) or start < 300:
            raise ValueError("Invalid original window boundary")
        # Recompute trace; never accept injected alert states, metadata or rule changes.
        replay = project(
            pd.DataFrame(columns), {"present_sensor_ids": present}, case, start
        )
        sanitized[case["id"]] = {"replay": replay}
    return {"cases": sanitized, "attribution": DATA_LICENSE}
