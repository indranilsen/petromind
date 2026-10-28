"""Trusted offline loader. Never register these functions as agent tools."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .measurements import valid_sensor_name


class IneligibleIncident(ValueError):
    """No complete, contiguous transient window at the declared 1 Hz cadence."""


@dataclass(frozen=True)
class Incident:
    # Evaluation-side metadata: never serialize this object into an agent prompt.
    path: Path
    well: str
    event: int
    measurements: pd.DataFrame


def well_id(path: Path) -> str:
    match = re.fullmatch(r"(WELL-\d+)_[^/]+\.parquet", Path(path).name)
    if match is None:
        raise ValueError("Expected real WELL incident filename")
    return match.group(1)


def read_incident(path: Path, seconds: int = 600) -> Incident:
    if type(seconds) is not int or seconds < 1:
        raise ValueError("seconds must be a positive integer")
    frame = pd.read_parquet(path)
    if "class" not in frame or not frame.columns.is_unique:
        raise ValueError("Missing labels or duplicate columns")
    labels = pd.to_numeric(frame["class"], errors="coerce")
    transient = labels.isin(range(101, 110)).to_numpy()
    positions = np.flatnonzero(transient)
    if not len(positions):
        raise IneligibleIncident("No transient stage")
    start = int(positions[0])
    label = int(labels.iloc[start])
    window = frame.iloc[start:start + seconds]
    if len(window) != seconds or not labels.iloc[start:start + seconds].eq(label).all():
        raise IneligibleIncident("Insufficient contiguous transient samples")
    if (not isinstance(window.index, pd.DatetimeIndex) or window.index.hasnans
            or not window.index.is_unique or not window.index.is_monotonic_increasing
            or (len(window) > 1 and not
                (np.diff(window.index.as_unit("ns").asi8) == 1_000_000_000).all())):
        raise IneligibleIncident("Expected ordered 1 Hz timestamps")
    names = sorted(c for c in frame.columns if valid_sensor_name(c))
    if not names:
        raise IneligibleIncident("No valid measurement columns")
    # Drop labels/state, time index, paths and all arbitrary metadata before session creation.
    measurements = window[names].reset_index(drop=True).copy(deep=True)
    measurements.attrs.clear()
    measurements.columns.name = None
    return Incident(Path(path).resolve(), well_id(Path(path)), label - 100, measurements)


def load_incidents(root: Path, seconds: int = 600) -> tuple[Incident, ...]:
    root = Path(root)
    if not root.is_dir():
        raise ValueError("Dataset directory not found")
    incidents = []
    for path in sorted(root.rglob("WELL-*.parquet")):
        if not path.parent.name.isdigit() or not 1 <= int(path.parent.name) <= 9:
            continue
        try:
            incidents.append(read_incident(path, seconds))
        except IneligibleIncident:
            continue
    if not incidents:
        raise ValueError("No eligible real transient incidents")
    return tuple(incidents)
