"""Deterministic numeric summaries; no labels, filenames or timestamps."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np
import pandas as pd

# Numerical guardrail inherited from the prototype, NOT an engineering limit.
MAX_ABS_RAW = 1e12


def valid_sensor_name(name: object) -> bool:
    return (isinstance(name, str) and len(name) <= 64
            and re.fullmatch(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*", name) is not None
            and not name.startswith("WELL") and name not in {"CLASS", "STATE"})


@dataclass(frozen=True)
class SensorSummary:
    available: bool
    count: int
    total: int
    invalid_count: int
    median: float | None = None
    std: float | None = None
    first: float | None = None
    last: float | None = None
    delta: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def summarize(values: Iterable) -> SensorSummary:
    raw = pd.Series(values, copy=True)
    numeric = pd.to_numeric(raw, errors="coerce").to_numpy(dtype=float, na_value=np.nan)
    valid = np.isfinite(numeric) & (np.abs(numeric) <= MAX_ABS_RAW)
    # Missing and rejected values are charged alike; expose cleaning impact.
    arr = numeric[valid]
    common = dict(available=bool(len(arr)), count=int(len(arr)), total=len(raw),
                  invalid_count=int((~valid).sum()))
    if not len(arr):
        return SensorSummary(**common)
    return SensorSummary(**common, median=float(np.median(arr)),
                         std=float(np.std(arr)), first=float(arr[0]),
                         last=float(arr[-1]), delta=float(arr[-1] - arr[0]))
