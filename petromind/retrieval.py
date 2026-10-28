"""Training-only analogues using exactly the observations passed by the session."""
from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping
from uuid import uuid4

from .measurements import SensorSummary, summarize
from .splits import WellSplit


@dataclass(frozen=True)
class TrainingRecord:
    case_id: str
    well: str
    event: int
    summaries: Mapping[str, SensorSummary]


class IncidentRetriever:
    def __init__(self, incidents, split: WellSplit, *, case_ids=None):
        records = []
        # Fail closed if a caller accidentally supplies ANY non-training incident.
        for incident in incidents:
            if incident.well not in split.train_wells or incident.well in split.test_wells:
                raise ValueError("Retrieval accepts training wells only")
            summaries = MappingProxyType({s: summarize(incident.measurements[s])
                                          for s in incident.measurements})
            case_id = case_ids[incident.path] if case_ids is not None else uuid4().hex
            if not isinstance(case_id, str) or len(case_id) != 32 or any(c not in "0123456789abcdef" for c in case_id):
                raise ValueError("Retrieval identifiers must be opaque UUID hex values")
            records.append(TrainingRecord(case_id, incident.well, incident.event, summaries))
        self._records = tuple(records)
        self._train_wells = frozenset(split.train_wells)
        self._test_wells = frozenset(split.test_wells)

    @property
    def index_wells(self) -> frozenset[str]:
        return frozenset(r.well for r in self._records)

    @property
    def test_wells(self) -> frozenset[str]:
        return self._test_wells

    @property
    def size(self) -> int:
        return len(self._records)

    def search(self, observed: Mapping[str, SensorSummary], top_k: int = 3) -> list[dict]:
        if type(top_k) is not int or not 1 <= top_k <= 10:
            raise ValueError("top_k must be an integer from 1 to 10")
        scored = []
        for order, record in enumerate(self._records):
            shared = []
            distances = []
            for sensor, a in sorted(observed.items()):
                b = record.summaries.get(sensor)
                if a.available and b is not None and b.available:
                    # Preserve prototype distance. This is NOT a probability or causal metric.
                    denominator = max(1.0, abs(a.median), abs(b.median))
                    distances.append(min(1.0, abs(a.median - b.median) / denominator))
                    shared.append(sensor)
            if distances:
                scored.append((math.fsum(distances) / len(distances), order, record, shared))
        scored.sort(key=lambda item: (item[0], item[1]))
        # NO unqueried historical sensor values, well IDs or filenames in results.
        return [dict(case_id=r.case_id, training_event=r.event, distance=round(distance, 6),
                     shared_sensors=len(shared), matched_sensors=shared)
                for distance, _, r, shared in scored[:top_k]]
