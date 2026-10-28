"""Small source-scoped diagnostic experiment registry and numeric computations."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .knowledge import PhysicalKnowledge
from .measurements import MAX_ABS_RAW

VERSION = "diagnostic-tests-v1"


@dataclass(frozen=True)
class TestTemplate:
    id: str
    sensors: tuple[str, ...]
    computation: str
    primary: str
    measures: str
    fact_ids: tuple[str, ...]
    limitations: str
    requires_reference: bool = False

    def public(self, physical=True):
        result = {
            k: v
            for k, v in asdict(self).items()
            if k not in {"fact_ids", "limitations"}
        }
        result["limitations"] = (
            self.limitations
            if physical
            else "Numeric computation alone does not establish a fault; physical interpretation needs review."
        )
        if physical:
            result["verification_status"] = (
                "documented_generic_locations; example_signatures_not_fault_rules"
            )
            result["physical_basis"] = [
                PhysicalKnowledge().fact(i) for i in self.fact_ids
            ]
        return result


REGISTRY = {
    t.id: t
    for t in (
        TestTemplate(
            "tree_trend",
            ("P-TPT",),
            "last valid value minus first valid value",
            "delta",
            "Signed pressure change in Pa within the diagnostic window",
            ("location:P-TPT", "example:2:P-TPT", "example:8:P-TPT"),
            "Figures 3/5 illustrate different tree-pressure directions. Examples are not necessary/sufficient fault rules; no normality or threshold is inferred.",
        ),
        TestTemplate(
            "paired_pressure_trends",
            ("P-PDG", "P-TPT"),
            "Compute both last-minus-first deltas and their product",
            "delta_product",
            "Same/opposite downhole and tree pressure trend signs; product in Pa squared",
            (
                "location:P-PDG",
                "location:P-TPT",
                "example:2:P-PDG",
                "example:2:P-TPT",
                "example:8:P-PDG",
                "example:8:P-TPT",
            ),
            "Published examples involve these locations; neither exact-well topology nor a necessary closure/hydrate signature is established. A product sign loses which sensor increased; inspect both deltas. It does not establish fault causality.",
        ),
        TestTemplate(
            "choke_pressure_difference",
            ("P-MON-CKP", "P-JUS-CKP"),
            "Median of pointwise upstream minus downstream pressure on jointly valid samples",
            "median_difference",
            "Signed pressure difference across the named production choke in Pa",
            ("location:P-MON-CKP", "location:P-JUS-CKP"),
            "Documented generic measurement positions, not validated per-well tags. No flow direction, choke loss coefficient, hydrate threshold or fault cause follows.",
        ),
        TestTemplate(
            "tree_oscillation",
            ("P-TPT",),
            "Detrend longest contiguous valid segment by least squares; FFT peak power / total non-DC power; minimum 32 samples",
            "peak_power_fraction",
            "Spectral concentration, peak period and detrended amplitude of tree pressure",
            ("location:P-TPT", "example:3:P-TPT"),
            "Figure 6 is an oscillatory example, not an established spectral threshold. Trends, noise and interpolation can confound periodicity; concentration alone cannot diagnose slugging.",
        ),
        TestTemplate(
            "tree_reference_change",
            ("P-TPT",),
            "Diagnostic median minus prior-window median; 300 seconds strictly before onset, minimum 30 valid samples",
            "median_shift",
            "Measured pressure shift relative to a pre-window distribution in Pa",
            ("location:P-TPT",),
            "Prior period is not independently verified normal. No label-derived normal mask, future samples or physically established threshold is used.",
            True,
        ),
    )
}


def clean(values):
    import pandas as pd

    a = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float, na_value=np.nan)
    return np.where(np.isfinite(a) & (np.abs(a) <= MAX_ABS_RAW), a, np.nan)


def compute(template, signals, reference=None):
    """Only called after session queries have charged every required sensor."""
    arrays = {s: clean(signals[s]) for s in template.sensors}
    output = {
        "primary_metric": template.primary,
        "primary_value": None,
        "values": {},
        "quality": {},
    }
    for s, a in arrays.items():
        good = a[np.isfinite(a)]
        output["quality"][s] = {
            "valid_count": len(good),
            "total": len(a),
            "constant": bool(len(good) and np.all(good == good[0])),
        }
    if template.id in {"tree_trend", "paired_pressure_trends"}:
        for s, a in arrays.items():
            valid = a[np.isfinite(a)]
            output["values"][s + "_delta"] = (
                float(valid[-1] - valid[0]) if len(valid) >= 2 else None
            )
        deltas = output["values"]
        output["primary_value"] = (
            deltas["P-TPT_delta"]
            if template.id == "tree_trend"
            else deltas["P-PDG_delta"] * deltas["P-TPT_delta"]
            if all(v is not None for v in deltas.values())
            else None
        )
    elif template.id == "choke_pressure_difference":
        a, b = (arrays[s] for s in template.sensors)
        mask = np.isfinite(a) & np.isfinite(b)
        output["quality"]["joint_valid_count"] = int(mask.sum())
        output["primary_value"] = (
            float(np.median(a[mask] - b[mask])) if mask.any() else None
        )
    elif template.id == "tree_reference_change":
        observed = arrays["P-TPT"]
        valid = observed[np.isfinite(observed)]
        ref = reference.for_observed("P-TPT", {"P-TPT"}) if reference else None
        output["values"]["reference"] = ref
        if len(valid) and ref and ref["available"]:
            output["primary_value"] = float(np.median(valid) - ref["median"])
    else:
        a = arrays["P-TPT"]
        mask = np.isfinite(a)
        # Do not interpolate missing observations or join noncontiguous intervals.
        edges = np.diff(np.r_[False, mask, False].astype(int))
        runs = list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))
        lo, hi = max(runs, key=lambda r: r[1] - r[0]) if runs else (0, 0)
        output["quality"]["contiguous_samples"] = int(hi - lo)
        if hi - lo >= 32:
            y = a[lo:hi]
            x = np.arange(len(y), dtype=float)
            residual = (
                y
                - np.column_stack((x, np.ones(len(x))))
                @ np.linalg.lstsq(np.column_stack((x, np.ones(len(x)))), y, rcond=None)[
                    0
                ]
            )
            numerical_floor = (
                8 * np.finfo(float).eps * len(y) * max(1.0, float(np.max(np.abs(y))))
            )
            output["quality"]["numerical_residual_floor_applied"] = bool(
                np.max(np.abs(residual)) <= numerical_floor
            )
            if output["quality"]["numerical_residual_floor_applied"]:
                residual = np.zeros(len(y))
            power = np.abs(np.fft.rfft(residual)) ** 2
            power[0] = 0.0
            total = float(power.sum())
            peak = int(np.argmax(power))
            output["primary_value"] = float(power[peak] / total) if total > 0 else 0.0
            output["values"].update(
                peak_period_seconds=float(len(y) / peak)
                if peak and total > 0
                else None,
                detrended_peak_to_peak=float(np.ptp(residual)),
            )
    output["quality"]["available"] = output["primary_value"] is not None
    return output
