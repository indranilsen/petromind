"""The active_sensors.py Gaussian fixed/adaptive policies, without NaN warnings.

Algorithm preserved: three summary features, train-only robust scaling, clipped
diagonal Gaussian likelihoods, variance floor .25, Laplace priors and posterior-
weighted separation. Only finite-column handling differs from the prototype.
All target features are obtained through charged DiagnosticSession queries.
"""
from __future__ import annotations

import numpy as np

from .measurements import MAX_ABS_RAW, summarize

FEATURES = ("median", "std", "change")


def feature_vector(summary):
    values = np.array([getattr(summary, f) if getattr(summary, f) is not None else np.nan
                       for f in FEATURES], dtype=float)
    values[~np.isfinite(values) | (np.abs(values) > MAX_ABS_RAW)] = np.nan
    return values


def posterior(score):
    values = np.exp(score - np.max(score))
    return values / values.sum()


class GaussianEvidence:
    def __init__(self, training, sensors):
        self.sensors = tuple(sensors)
        self.classes = np.array(sorted({r.event for r in training}), dtype=int)
        labels = np.array([r.event for r in training])
        counts = np.array([(labels == c).sum() for c in self.classes], dtype=float)
        self.prior = np.log((counts + 1) / (counts.sum() + len(counts)))
        self.params = {}
        for sensor in self.sensors:
            x = np.array([feature_vector(summarize(r.measurements[sensor]))
                          if sensor in r.measurements else np.full(3, np.nan) for r in training])
            center, scale = np.zeros(3), np.ones(3)
            for j in range(3):
                finite = x[:, j][np.isfinite(x[:, j])]
                if len(finite):
                    center[j] = np.median(finite)
                    candidate = (np.percentile(finite, 75) - np.percentile(finite, 25)) / 1.349
                    scale[j] = candidate if candidate > 1e-8 else 1.
            x = np.clip((x - center) / scale, -10, 10)
            gmean = np.array([np.mean(col[np.isfinite(col)]) if np.isfinite(col).any() else 0.
                              for col in x.T])
            means, variances = [], []
            for event in self.classes:
                part = x[labels == event]
                n = np.isfinite(part).sum(axis=0)
                mean = np.divide(np.nansum(part, axis=0), n, out=gmean.copy(), where=n > 0)
                centered = np.where(np.isfinite(part), part - mean, 0.)
                var = np.divide((centered ** 2).sum(axis=0), n, out=np.ones(3), where=n > 1)
                means.append(mean)
                variances.append(np.maximum(var, .25))
            self.params[sensor] = (center, scale, np.array(means), np.array(variances))
        self.ranking = tuple(sorted(self.sensors, key=lambda s: (-self.separation(s, np.exp(self.prior)), s)))

    def separation(self, sensor, probs):
        _, _, mu, var = self.params[sensor]
        weighted = (mu * probs[:, None]).sum(axis=0)
        between = (probs[:, None] * (mu - weighted) ** 2).sum(axis=0)
        within = (probs[:, None] * var).sum(axis=0)
        return float(np.mean(between / (within + .25)))

    def evidence(self, sensor, summary):
        center, scale, means, variances = self.params[sensor]
        z = np.clip((feature_vector(summary) - center) / scale, -10, 10)
        valid = np.isfinite(z)
        if not valid.any():
            return np.zeros(len(self.classes))
        z, mu, var = z[valid], means[:, valid], variances[:, valid]
        return -.5 * (np.log(2 * np.pi * var) + ((z - mu) ** 2) / var).sum(axis=1)

    def run(self, session, policy):
        if policy not in {"fixed", "adaptive"}:
            raise ValueError("Unknown baseline policy")
        score = self.prior.copy()
        remaining = set(self.sensors)
        prefix_predictions = []
        while session.remaining_budget and remaining:
            if policy == "fixed":
                sensor = next(s for s in self.ranking if s in remaining)
            else:
                sensor = max(sorted(remaining), key=lambda s: self.separation(s, posterior(score)))
            remaining.remove(sensor)
            session.dispatch("get_sensor_history", {"sensor_name": sensor})
            score += self.evidence(sensor, session.observations[sensor])
            prefix_predictions.append(int(self.classes[np.argmax(score)]))
        probs = posterior(score)
        evidence = [s for s, obs in session.observations.items() if obs.available]
        final = session.dispatch("submit_diagnosis", {"predicted_fault_type": int(self.classes[np.argmax(score)]),
                                 "confidence": float(np.max(probs)), "evidence": evidence})
        return {"status": "completed" if session.diagnosis else "failed",
                "reason": "diagnosis_submitted" if session.diagnosis else "no_available_evidence",
                "prefix_predictions": prefix_predictions, "diagnosis": final}
