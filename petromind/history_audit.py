"""OFFLINE REVIEW ONLY: full development histories, never model or browser input.

No detector is selected, fitted or run here. Labels are used to describe and
score annotation boundaries only. Numeric outputs never include fault codes,
well identifiers, source paths or calendar timestamps.
"""

from __future__ import annotations

import hashlib
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

from .audit import canonical
from .claim_review import demo_cases, load_capture
from .data import read_incident
from .incident_replay import _resolve_verified_path, raw_payload, sample, sensor_group
from .knowledge import SENSORS, SOURCES
from .measurements import summarize

VERSION = "history-audit-v1"
TRANSIENT_CODES = (101, 102, 105, 106, 107, 108, 109)  # Authors Table 4; no 103/104.
STATE_NAMES = {
    0: "open",
    1: "shut_in",
    2: "flushing_diesel",
    3: "flushing_gas",
    4: "bullheading",
    5: "closed_with_diesel",
    6: "closed_with_gas",
    7: "restart",
    8: "depressurization",
}


DATA_LICENSE = {
    "license": "CC BY 4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "declaration": "https://github.com/petrobras/3W/blob/main/dataset/README.md",
    "attribution": "Petrobras and the 3W Dataset contributors; Vaz Vargas et al., 3W Dataset 2.0.0, arXiv:2507.01048v1",
    "source": "https://github.com/petrobras/3W",
    "scope": "Upstream declaration for dataset files, not a certificate that local files or derived telemetry are anonymous.",
}


def annotation_category(value):
    if pd.isna(value):
        return "unknown"
    if value == 0:
        return "annotated_normal_operation"
    if value in TRANSIENT_CODES:
        return "annotated_transient_condition"
    if value in range(1, 10):
        return "annotated_steady_undesirable_event"
    return "undocumented_code"


def _counts(values):
    return {
        str(k): int(v)
        for k, v in pd.Series(values, dtype="object").value_counts(dropna=False).items()
    }


def timing(index):
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("Datetime index required")
    valid = ~index.isna()
    seconds = np.full(len(index), np.nan)
    first = int(np.flatnonzero(valid)[0]) if valid.any() else None
    if first is not None:
        seconds[valid] = (index[valid] - index[first]).total_seconds()
    delta = np.diff(seconds)
    finite = np.isfinite(delta)
    positive = delta[finite & (delta > 0)]
    modal = float(pd.Series(positive).mode().iloc[0]) if len(positive) else None
    problems = np.flatnonzero(finite & (delta != 1))
    ordered = bool(valid.all() and index.is_unique and index.is_monotonic_increasing)
    return {
        "timestamp_count": int(valid.sum()),
        "missing_timestamps": int((~valid).sum()),
        "ordered_unique_timestamps": ordered,
        "recording_duration_seconds": float(seconds[-1])
        if ordered and len(index)
        else None,
        "modal_positive_interval_seconds": modal,
        "positive_interval_min_seconds": float(positive.min())
        if len(positive)
        else None,
        "positive_interval_max_seconds": float(positive.max())
        if len(positive)
        else None,
        "unknown_neighbor_intervals": int((~finite).sum()),
        "duplicate_neighbor_pairs": int((finite & (delta == 0)).sum()),
        "backward_neighbor_pairs": int((finite & (delta < 0)).sum()),
        "pairs_not_at_frozen_one_second_cadence": len(problems),
        "discontinuity_examples": [
            {"preceding_row": int(i), "interval_seconds": float(delta[i])}
            for i in problems[:25]
        ],
        "discontinuity_examples_truncated": bool(len(problems) > 25),
        "basis": "Observed timestamp differences; the existing diagnostic protocol expects 1 Hz. No resampling.",
    }, seconds


def _longest(valid):
    longest = current = 0
    for v in valid:
        current = current + 1 if v else 0
        longest = max(current, longest)
    return longest


def _quality(values):
    s = summarize(values).to_dict()
    return {
        k: s[k]
        for k in (
            "available",
            "count",
            "total",
            "missing_count",
            "nonnumeric_count",
            "nonfinite_count",
            "extreme_count",
            "zero_count",
            "is_constant",
            "constant_value",
            "quality_status",
            "median",
            "std",
            "first",
            "last",
            "delta",
        )
    }


def analyze_frame(frame, *, before_seconds=1800, after_seconds=1200):
    """Trusted offline analysis. Return sanitized report and private row boundaries."""
    if not frame.columns.is_unique or "class" not in frame or not len(frame):
        raise ValueError("Full incident requires unique columns and annotations")
    if (
        type(before_seconds) is not int
        or type(after_seconds) is not int
        or not 1 <= before_seconds <= 7200
        or not 600 <= after_seconds <= 7200
    ):
        raise ValueError(
            "Bound review clip to 1..7200 seconds before and 600..7200 after"
        )
    labels = pd.to_numeric(frame["class"], errors="coerce")
    positions = np.flatnonzero(labels.isin(TRANSIENT_CODES).to_numpy())
    if not len(positions):
        raise ValueError("No documented transient condition")
    start = int(positions[0])
    end = start
    while end < len(frame) and labels.iloc[end] == labels.iloc[start]:
        end += 1
    time, seconds = timing(frame.index)
    categories = [annotation_category(v) for v in labels]
    sections = {
        "whole_record": slice(None),
        "before_first_transient": slice(0, start),
        "initial_transient_run": slice(start, end),
        "after_initial_transient": slice(end, None),
    }
    state = (
        pd.to_numeric(frame["state"], errors="coerce")
        if "state" in frame
        else pd.Series([np.nan] * len(frame))
    )
    status = [STATE_NAMES.get(v, "unknown_or_undocumented") for v in state]
    region_reports = {}
    for name, sl in sections.items():
        region_reports[name] = {
            "samples": len(frame.iloc[sl]),
            "class_annotation_categories": _counts(categories[sl]),
            "operational_annotation_categories": _counts(status[sl]),
        }
    channels = []
    for sensor in SENSORS:
        present = sensor in frame
        values = frame[sensor] if present else pd.Series([None] * len(frame))
        states = np.array([sample(v)["quality"] for v in values])
        regions = {name: _quality(values.iloc[sl]) for name, sl in sections.items()}
        reference = values.iloc[:start]
        ref = summarize(reference)
        trailing_normal = 0
        for category in reversed(categories[:start]):
            if category != "annotated_normal_operation":
                break
            trailing_normal += 1
        channels.append(
            {
                "sensor": sensor,
                "group": sensor_group(sensor),
                "documented_unit": SENSORS[sensor]["unit"],
                "present": present,
                "quality_by_region": regions,
                "quality_transition_count": int((states[1:] != states[:-1]).sum()),
                "availability_transition_count": int(
                    ((states[1:] == "valid") != (states[:-1] == "valid")).sum()
                ),
                "availability_transition_examples": [
                    {
                        "row": int(i),
                        "elapsed_seconds": float(seconds[i])
                        if np.isfinite(seconds[i])
                        else None,
                        "from_quality": str(states[i - 1]),
                        "to_quality": str(states[i]),
                    }
                    for i in (
                        np.flatnonzero(
                            (states[1:] == "valid") != (states[:-1] == "valid")
                        )
                        + 1
                    )[:10]
                ],
                "longest_pre_transient_consecutive_valid_rows": _longest(
                    states[:start] == "valid"
                ),
                "trailing_annotated_normal_samples": trailing_normal,
                "pre_transient_mad": float(
                    np.median(
                        np.abs(
                            np.array(
                                [
                                    sample(v)["value"]
                                    for v in reference
                                    if sample(v)["quality"] == "valid"
                                ]
                            )
                            - ref.median
                        )
                    )
                )
                if ref.available
                else None,
                "reference_status": "candidate earlier measurements; stationarity and suitability NOT established",
            }
        )
    # Clip in actual elapsed time, never a synthetic grid. Fail export rather than sort/fill.
    clip_start, clip_end = 0, len(frame)
    if time["ordered_unique_timestamps"]:
        clip_start = int(
            np.searchsorted(seconds, seconds[start] - before_seconds, side="left")
        )
        clip_end = int(
            np.searchsorted(seconds, seconds[start] + after_seconds, side="right")
        )
    report = {
        "samples_total": len(frame),
        "timing": time,
        "samples_before_first_transient": start,
        "samples_in_initial_transient_run": end - start,
        "samples_in_all_transient_conditions": len(positions),
        "samples_after_initial_transient_run": len(frame) - end,
        "offline_annotation_reference": {
            "first_transient_row": start,
            "first_transient_elapsed_seconds": float(seconds[start])
            if np.isfinite(seconds[start])
            else None,
            "scope": "Expert annotation, not independent detection time. OFFLINE ONLY.",
        },
        "regions": region_reports,
        "sensors": channels,
        "baseline_feasibility": {
            "status": "requires_review_not_automatically_approved",
            "earlier_samples_exist": start > 0,
            "pre_annotation_scope": "Only explicitly annotated normal samples are described as normal; this does not certify stationarity or open production.",
            "caution": "Operational-state changes can occur under nominal normality. Do not calibrate a detector using the annotation boundary.",
        },
        "detector": {
            "status": "not_run_pending_data_review",
            "configuration": None,
            "first_alert": None,
            "timing_relative_to_annotation": "not_evaluated_not_a_miss",
        },
        "classifier_boundary": {
            "original_window_samples": 600,
            "original_window_start_row_offline": start,
            "first_eligible_original_prediction_row_offline": start + 599,
            "scope": "The original fixed diagnostic window, not an alert-relative sliding classifier. Do not show its result before this row.",
        },
        "review_clip": {
            "start_row_offline": clip_start,
            "end_row_exclusive_offline": clip_end,
            "before_seconds_requested": before_seconds,
            "after_seconds_requested": after_seconds,
        },
    }
    return report, (start, end, clip_start, clip_end), seconds


def trajectory_svg(frame, seconds, boundaries):
    """Standard offline Matplotlib plot; every usable recorded sample retained."""
    import matplotlib
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    start, _end, lo, hi = boundaries
    t = seconds[lo:hi]
    with matplotlib.rc_context(
        {"svg.fonttype": "none", "svg.hashsalt": VERSION, "path.simplify": False}
    ):
        figure = Figure(figsize=(12, 8), layout="constrained")
        FigureCanvasAgg(figure)
        axes = figure.subplots(4, 1, sharex=True)
        figure.suptitle("OFFLINE REVIEW: annotated transition is not a detector alert")
        for axis, sensor in zip(axes, ["P-PDG", "P-TPT", "T-TPT", "QGL"], strict=True):
            vals = frame[sensor].iloc[lo:hi] if sensor in frame else [None] * (hi - lo)
            xs, ys = [], []
            previous = None
            for x, value in zip(t, vals, strict=True):
                point = sample(value)
                if not np.isfinite(x) or point["quality"] != "valid":
                    xs.append(np.nan)
                    ys.append(np.nan)
                    previous = None
                    continue
                if previous is not None and x - previous != 1:
                    xs.append(np.nan)
                    ys.append(np.nan)
                xs.append(x)
                ys.append(point["value"])
                previous = x
            if any(np.isfinite(ys)):
                axis.plot(
                    xs, ys, color="#216e9b", linewidth=1, marker=".", markersize=1.5
                )
            else:
                axis.text(0.02, 0.5, "No usable measurements", transform=axis.transAxes)
            if np.isfinite(seconds[start]):
                axis.axvline(
                    seconds[start],
                    color="#8c6134",
                    linestyle="--",
                    label="Offline annotation",
                )
            axis.set_ylabel(SENSORS[sensor]["unit"])
            axis.set_title(
                sensor + " — generic documented units", loc="left", fontsize=10
            )
            axis.grid(alpha=0.2)
        axes[-1].set_xlabel(
            "Elapsed seconds from first valid timestamp; no imputation/resampling; gaps break lines"
        )
        buffer = StringIO()
        figure.savefig(
            buffer,
            format="svg",
            metadata={"Date": None, "Creator": "PetroMind offline history audit"},
        )
        return buffer.getvalue()


def export_fixture(directory, frame, seconds, boundaries, case_number):
    """Local-only numeric projection. No label/onset/state, date, path or well ID."""
    _start, _end, lo, hi = boundaries
    clip = frame.iloc[lo:hi]
    if (
        not clip.index.is_unique
        or not clip.index.is_monotonic_increasing
        or clip.index.hasnans
    ):
        return {"status": "not_exported_invalid_timestamps"}
    output = {"elapsed_seconds": seconds[lo:hi] - seconds[lo]}
    for sensor in SENSORS:
        vals = clip[sensor] if sensor in clip else [None] * len(clip)
        projected = [sample(v) for v in vals]
        output[sensor] = [p["value"] for p in projected]
        output[sensor + "__quality"] = [p["quality"] for p in projected]
        output[sensor + "__reason"] = [p["reason"] for p in projected]
    directory = Path(directory)
    directory.mkdir(exist_ok=True)
    filename = f"case-{case_number}.parquet"
    pd.DataFrame(output).to_parquet(directory / filename, index=False)
    return {
        "status": "local_only_no_automatic_publication",
        "file": filename,
        "samples": len(clip),
        "present_sensor_ids": [sensor for sensor in SENSORS if sensor in frame],
        "sha256": hashlib.sha256((directory / filename).read_bytes()).hexdigest(),
        "time_basis": "Original relative offsets; calendar timestamps omitted; gaps retained.",
        "schema": "elapsed_seconds plus each of 27 sensor values, __quality and __reason. Invalid values null, not imputed.",
        "warning": "Label stripping is NOT anonymization. Real telemetry remains potentially identifying; preserve attribution, license links and change notices, and check applicable privacy constraints before sharing.",
    }


def run_history_audit(
    capture,
    dataset,
    science_protocol,
    out,
    *,
    before_seconds=1800,
    after_seconds=1200,
    export=False,
):
    out = Path(out)
    if out.exists():
        raise ValueError("Use a fresh output directory")
    if not Path(dataset).is_dir():
        raise ValueError("Actual local dataset required")
    protocol, _ = load_capture(capture)
    cases = demo_cases(capture)
    rows = []
    work = []
    for number, case in enumerate(cases, 1):
        path = _resolve_verified_path(case, protocol, dataset, science_protocol)
        read_incident(path, 600)  # Existing eligibility and private-label validation.
        frame = pd.read_parquet(path)
        row, boundaries, seconds = analyze_frame(
            frame, before_seconds=before_seconds, after_seconds=after_seconds
        )
        start = boundaries[0]
        raw_payload(
            frame.iloc[start : start + 600], case
        )  # Captured summary/cadence equality.
        row.update(
            case_alias=f"case-{number}",
            task_id=case["id"],
            frozen_source_file_verified=True,
            muse_observed_sensor_ids=list(case["observations"]),
            muse_packet_changed=False,
        )
        rows.append(row)
        work.append((frame, boundaries, seconds))
    report = {
        "version": VERSION,
        "status": "actual_local_files_audited",
        "audience": "offline_review_only_never_agent_or_browser",
        "api_requests": 0,
        "sources": {
            "stage_semantics": {
                "url": SOURCES["authors"]["url"],
                "locator": "Section 2.4, Tables 4 and 5; Figures 3 and 7",
            },
            "sensor_catalog": SOURCES["ini"],
            "dataset_license": DATA_LICENSE,
        },
        "cases": rows,
        "limitations": [
            "Two selected development examples; no population accuracy or detector validation.",
            "Annotated normality does not guarantee stationary telemetry or normal production mode.",
            "Annotation time is not independently detectable onset. No detector or thresholds selected or tuned.",
            "Plots/report contain OFFLINE annotation information and must not be served to agents or browser.",
            "Upstream dataset files declare CC BY 4.0; exported artifacts retain attribution and change notices. This does not certify local-file authenticity, privacy or anonymization.",
        ],
    }
    out.mkdir(parents=True)
    if export:
        (out / "local-fixture").mkdir()
    for number, (row, (frame, boundaries, seconds)) in enumerate(
        zip(rows, work, strict=True), 1
    ):
        (out / f"case-{number}-trajectories.svg").write_text(
            trajectory_svg(frame, seconds, boundaries)
        )
        if export:
            row["fixture"] = export_fixture(
                out / "local-fixture", frame, seconds, boundaries, number
            )
    if export:
        manifest = {
            "version": "local-telemetry-review-v1",
            "audience": "offline_review_only_not_agent_or_browser",
            "distribution": "Local export only; no automatic publication or anonymization claim.",
            "dataset_license": DATA_LICENSE,
            "changes": [
                "Selected bounded time slice for offline review",
                "Removed class/state labels, calendar timestamps, source path and well identifiers",
                "Converted to relative seconds",
                "Applied existing numeric guardrail: invalid values null with quality/reason tags; no imputation or resampling",
            ],
            "selection_scope": "Clip uses offline annotation bounds; timing may be indirectly inferable. NOT a prospectively blinded or agent/browser-ready packet.",
            "cases": [r["fixture"] for r in rows],
            "sensor_units": {s: v["unit"] for s, v in SENSORS.items()},
        }
        (out / "local-fixture" / "manifest.json").write_text(canonical(manifest) + "\n")
    (out / "ATTRIBUTION.json").write_text(
        canonical(
            {
                "source": DATA_LICENSE,
                "changes": "Offline aggregate statistics and bounded trajectory plots; labels converted to generic categories, calendar timestamps omitted. Optional telemetry projection preserves usable numeric readings and explicit invalid/missing flags.",
            }
        )
        + "\n"
    )
    (out / "report.json").write_text(canonical(report) + "\n")
    lines = [
        "# Offline development history audit",
        "",
        "No detector was run. Annotation is not detection.",
        "",
        "| Case | Samples | Duration (s) | Before first transient | Initial transient | Following |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['case_alias']} | {r['samples_total']} | {r['timing']['recording_duration_seconds']} | {r['samples_before_first_transient']} | {r['samples_in_initial_transient_run']} | {r['samples_after_initial_transient_run']} |"
        )
    lines += [
        "",
        "| Case | Sensor group | Present | Usable | Constant | Missing/invalid/absent |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        for group in sorted({s["group"] for s in r["sensors"]}):
            group_sensors = [s for s in r["sensors"] if s["group"] == group]
            present = sum(s["present"] for s in group_sensors)
            usable = sum(
                s["quality_by_region"]["whole_record"]["available"]
                for s in group_sensors
            )
            constant = sum(
                s["quality_by_region"]["whole_record"]["is_constant"]
                for s in group_sensors
            )
            lines.append(
                f"| {r['case_alias']} | {group} | {present} | {usable} | {constant} | {len(group_sensors) - usable} |"
            )
    lines += [
        "",
        "Use report.json for all 27 sensor quality profiles, operational annotations, cadence and reference diagnostics.",
        "Share report.json for OFFLINE review first. Plots and real telemetry fixtures require separate redistribution/privacy review.",
    ]
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    return {
        "status": report["status"],
        "cases": len(rows),
        "api_requests": 0,
        "detector": "not_run_pending_data_review",
        "next_step": "Return report.json for offline review; do not publish the dataset or fixture.",
    }
