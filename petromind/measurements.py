"""Deterministic numeric summaries; no labels, filenames or timestamps."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np
import pandas as pd

# Numerical guardrail inherited from the prototype, NOT an engineering limit.
MAX_ABS_RAW = 1e12
QUALITY_VERSION = "numeric-quality-v2"


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
    change: float | None = None
    missing_count: int = 0
    nonnumeric_count: int = 0
    nonfinite_count: int = 0
    extreme_count: int = 0
    zero_count: int = 0
    is_constant: bool = False
    constant_value: float | None = None
    quality_status: str = "missing"
    quality_flags: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


def summarize(values: Iterable) -> SensorSummary:
    raw = pd.Series(values, copy=True)
    numeric = pd.to_numeric(raw, errors="coerce").to_numpy(dtype=float, na_value=np.nan)
    valid = np.isfinite(numeric) & (np.abs(numeric) <= MAX_ABS_RAW)
    missing = raw.isna().to_numpy()
    nonnumeric = ~missing & np.isnan(numeric)
    nonfinite = np.isinf(numeric)
    extreme = np.isfinite(numeric) & (np.abs(numeric) > MAX_ABS_RAW)
    arr = numeric[valid]
    constant = bool(len(arr) >= 2 and np.min(arr) == np.max(arr))
    rejected = int(nonnumeric.sum() + nonfinite.sum() + extreme.sum())
    flags = []
    if missing.any():
        flags.append("missing_samples")
    if rejected:
        flags.append("potentially_invalid_readings")
    if constant:
        flags.append("constant_measurement_requires_context")
        if arr[0] == 0:
            flags.append("constant_zero_not_automatically_missing")
    if len(arr) == 1:
        flags.append("insufficient_samples_for_variation")
    cleaned = np.where(valid, numeric, np.nan)
    midpoint = len(cleaned) // 2
    first_half, last_half = cleaned[:midpoint], cleaned[midpoint:]
    first_half, last_half = first_half[np.isfinite(first_half)], last_half[np.isfinite(last_half)]
    change = float(np.median(last_half) - np.median(first_half)) if len(first_half) and len(last_half) else None
    common = dict(available=bool(len(arr)), count=int(len(arr)), total=len(raw),
                  invalid_count=int((~valid).sum()), change=change,
                  missing_count=int(missing.sum()), nonnumeric_count=int(nonnumeric.sum()),
                  nonfinite_count=int(nonfinite.sum()), extreme_count=int(extreme.sum()),
                  zero_count=int((arr == 0).sum()), is_constant=constant,
                  constant_value=float(arr[0]) if constant else None,
                  quality_status=("constant" if constant else "single_valid" if len(arr) == 1 else "variable") if len(arr)
                                 else ("invalid" if rejected else "missing"),
                  quality_flags=tuple(flags))
    if not len(arr):
        return SensorSummary(**common)
    scale = float(np.max(np.abs(arr)))
    return SensorSummary(**common, median=float(np.median(arr)),
                         std=float(np.std(arr / scale) * scale) if scale else 0., first=float(arr[0]),
                         last=float(arr[-1]), delta=float(arr[-1] - arr[0]))
