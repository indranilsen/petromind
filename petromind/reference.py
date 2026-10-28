"""Pre-window measurement distributions, never inferred normal-state labels."""
from __future__ import annotations

from types import MappingProxyType

import numpy as np
import pandas as pd

from .measurements import MAX_ABS_RAW, valid_sensor_name

VERSION = "pre-window-reference-v1"


class PreWindowReference:
    def __init__(self, frame, diagnostic_start, sensors, *, seconds=300, min_samples=30):
        if type(seconds) is not int or seconds < 1 or type(min_samples) is not int or min_samples < 1:
            raise ValueError("Positive reference window and sample count required")
        if (not isinstance(frame.index, pd.DatetimeIndex) or frame.index.hasnans
                or not frame.index.is_unique or not frame.index.is_monotonic_increasing
                or not frame.columns.is_unique):
            raise ValueError("Reference needs ordered unique timestamps and columns")
        names = tuple(sensors)
        if not names or not all(valid_sensor_name(s) for s in names):
            raise ValueError("Public sensor names only")
        start = pd.Timestamp(diagnostic_start)
        if pd.isna(start):
            raise ValueError("Explicit diagnostic start required")
        # Strictly earlier: a sample at onset is never part of the reference.
        prior = frame.loc[(frame.index >= start - pd.Timedelta(seconds, unit="s")) & (frame.index < start)]
        summaries = {}
        for sensor in names:
            values = pd.to_numeric(prior[sensor], errors="coerce").to_numpy(dtype=float, na_value=np.nan) if sensor in prior else np.array([])
            good = values[np.isfinite(values) & (np.abs(values) <= MAX_ABS_RAW)]
            usable = len(good) >= min_samples
            summaries[sensor] = {"available": usable, "count": len(good), "total": len(prior),
                "median": float(np.median(good)) if usable else None,
                "q25": float(np.percentile(good, 25)) if usable else None,
                "q75": float(np.percentile(good, 75)) if usable else None,
                "is_constant": bool(usable and np.all(good == good[0])),
                "window_seconds": seconds, "min_samples": min_samples,
                "normality": "unverified_pre_window", "physical_threshold": False,
                "version": VERSION}
        self._summaries = MappingProxyType(summaries)

    def for_observed(self, sensor, observed):
        if sensor not in observed:
            raise ValueError("Reference access requires a charged sensor observation")
        return dict(self._summaries[sensor]) if sensor in self._summaries else None
