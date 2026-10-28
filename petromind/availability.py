"""Label-blind, well-balanced availability estimates fitted on fitting wells only."""
from __future__ import annotations

from collections import defaultdict
from types import MappingProxyType

import numpy as np

from .baselines import posterior
from .measurements import summarize

VERSION = "availability-well-balanced-v1"


class AvailabilityPolicy:
    def __init__(self, training, split, sensors):
        records = tuple(training)
        if not records or any(r.well not in split.train_wells or r.well in split.test_wells for r in records):
            raise ValueError("Availability fitting accepts fitting wells only")
        rates, informative = {}, []
        for sensor in sorted(sensors):
            wells = defaultdict(list)
            medians = []
            for record in records:
                obs = summarize(record.measurements[sensor]) if sensor in record.measurements else None
                available = obs is not None and obs.available
                wells[record.well].append(float(available))
                if available:
                    medians.append(obs.median)
            rates[sensor] = float(np.mean([np.mean(v) for v in wells.values()]))
            # Across-incident median variation, not a physical informativeness rule.
            # Legitimate zero/constant target readings are never discarded here.
            if medians and max(medians) > min(medians):
                informative.append(sensor)
        self.rates = MappingProxyType(rates)
        self.informative_sensors = frozenset(informative)
        self.fit_well_count = len({r.well for r in records})

    def context(self):
        return {"version": VERSION, "epistemic_status": "empirical_correlation",
                "fit_well_count": self.fit_well_count, "availability_rates": dict(self.rates),
                "meaning": "Well-balanced fitting-incident availability, not target sensor availability or reliability. Constant and zero measurements count as available."}

    def select(self, model, remaining, probabilities):
        # Same separation objective, multiplied by a train-only probability of
        # obtaining a usable observation. No target-quality lookup or label use.
        return max(sorted(remaining), key=lambda s: (model.separation(s, probabilities) * self.rates[s], self.rates[s]))


def observe_with_policy(model, session, steps, policy=None):
    score = model.prior.copy()
    for sensor, obs in session.observations.items():
        score += model.evidence(sensor, obs)
    for _ in range(steps):
        remaining = set(model.sensors) - set(session.queries)
        if not remaining or not session.remaining_budget:
            break
        probs = posterior(score)
        sensor = (policy.select(model, remaining, probs) if policy else
                  max(sorted(remaining), key=lambda s: model.separation(s, probs)))
        result = session.dispatch("get_sensor_history", {"sensor_name": sensor})
        if "error" in result:
            raise ValueError("Charged baseline query failed")
        score += model.evidence(sensor, session.observations[sensor])
    return int(model.classes[np.argmax(score)])
