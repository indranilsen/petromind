"""Prefix-only feasibility detector. No fault taxonomy, labels or metadata inputs.

The reference is earlier observed telemetry, NOT certified normal operation.
Constants/zero are valid readings but cannot supply a nonzero MAD reference.
"""

import math
from dataclasses import asdict, dataclass

import numpy as np

from .incident_replay import sample

VERSION = "causal-pressure-deviation-v1"


@dataclass(frozen=True)
class MonitorConfig:
    sensors: tuple[str, ...] = ("P-PDG", "P-TPT")
    warmup_seconds: int = 300
    minimum_reference_samples: int = 240
    z_min: float = 6.0
    persistence_seconds: int = 30
    maximum_gap_seconds: float = 1.5

    def public(self):
        return {
            "version": VERSION,
            **asdict(self),
            "sensors": list(self.sensors),
            "scale": "1.4826 * MAD",
            "reference": "Earlier measured prefix; normality unverified",
            "meaning": "Sustained two-pressure deviation, not a fault or historical alarm",
        }


class CausalMonitor:
    """Consume exactly one timestamp and its allowlisted samples per step."""

    def __init__(self):
        self.config = MonitorConfig()  # Fixed v1 policy; no case-specific tuning.
        self._start = self._last = None
        self._values = {s: [] for s in self.config.sensors}
        self._reference = None
        self._pending = None
        self._alerted = False

    def step(self, elapsed_seconds, measurements):
        t = float(elapsed_seconds)
        if (
            not math.isfinite(t)
            or t < 0
            or (self._last is not None and t <= self._last)
        ):
            raise ValueError(
                "Monitor requires finite strictly increasing relative times"
            )
        cfg = self.config
        if self._start is None:
            self._start = t
        gap = self._last is not None and t - self._last > cfg.maximum_gap_seconds
        self._last = t
        # Numeric and supplied quality must both agree. Unknown metadata is ignored.
        clean = {}
        for s in cfg.sensors:
            supplied = measurements.get(s, {})
            checked = sample(supplied.get("value"))
            clean[s] = (
                checked
                if supplied.get("quality") == "valid"
                else {"quality": "missing"}
            )
        if t - self._start < cfg.warmup_seconds:
            for s, v in clean.items():
                if v["quality"] == "valid":
                    self._values[s].append(v["value"])
            return {
                "state": "warmup",
                "alerted": False,
                "new_alert": False,
                "scores": {},
            }
        if self._reference is None:
            self._reference = {}
            for s, values in self._values.items():
                median = float(np.median(values)) if values else None
                scale = (
                    float(1.4826 * np.median(np.abs(np.asarray(values) - median)))
                    if values
                    else 0
                )
                if len(values) >= cfg.minimum_reference_samples and scale > 0:
                    self._reference[s] = (median, scale)
            self._values.clear()
        scores = {}
        for s, reference in self._reference.items():
            if clean[s]["quality"] == "valid":
                scores[s] = (clean[s]["value"] - reference[0]) / reference[1]
        usable = len(self._reference) == len(cfg.sensors)
        observed = len(scores) == len(cfg.sensors)
        deviating = (
            usable and observed and all(abs(z) >= cfg.z_min for z in scores.values())
        )
        if gap or not deviating:
            self._pending = None
        if deviating and self._pending is None:
            self._pending = t
        sustained = deviating and t - self._pending >= cfg.persistence_seconds
        new_alert = bool(sustained and not self._alerted)
        self._alerted = self._alerted or bool(sustained)
        state = (
            "alert"
            if self._alerted
            else "reference_unavailable"
            if not usable
            else "measurement_unavailable"
            if not observed
            else "pending"
            if deviating
            else "monitoring"
        )
        return {
            "state": state,
            "alerted": self._alerted,
            "new_alert": new_alert,
            "scores": scores,
            "data_available": observed,
            "gap_reset": gap,
        }


def monitor_trace(elapsed_seconds, series):
    monitor = CausalMonitor()
    return [
        monitor.step(t, {s: series[s]["samples"][i] for s in monitor.config.sensors})
        for i, t in enumerate(elapsed_seconds)
    ]
