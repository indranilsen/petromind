"""Opt-in development capabilities; existing M3/M4 sessions stay unchanged."""
from __future__ import annotations

import json

from .audit import canonical
from .challenger import ChallengeSession
from .knowledge import DocumentedEquipmentGraph, PhysicalKnowledge, VERSION


class GroundedChallengeSession(ChallengeSession):
    def __init__(self, *args, availability=None, reference=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.budget != 5:
            raise ValueError("Grounded development uses the shared five-sensor budget")
        self._graph = DocumentedEquipmentGraph()
        self._availability = availability
        self._reference = reference
        self._primed_context = None

    def _record(self, tool, arguments, result):
        if tool == "get_sensor_history" and isinstance(result, dict) and "error" not in result and self._reference is not None:
            # Only this already-charged sensor's historical distribution is returned.
            result = {**result, "pre_window_reference": self._reference.for_observed(result["sensor"], self.queries)}
        return super()._record(tool, arguments, result)

    def prepare_investigation_context(self):
        with self._lock:
            if self._hypothesis is None or self._sealed:
                raise ValueError("Bind the initial public hypothesis before priming context")
            if self._primed_context is None:
                if len(self.queries) != 2 or self.remaining_budget != 3:
                    raise ValueError("Prime graph after exactly two initial queries, before additional sensors")
                context = {"knowledge": PhysicalKnowledge().context(),
                           "availability": self._availability.context() if self._availability else None,
                           "initial_graph_context": [], "version": VERSION,
                           "reference_policy": "Only queried sensors; pre-window distributions are not verified normality or engineering thresholds. Assessment citations still quote diagnostic-window fields; reference interpretations need review."}
                if self.variant in {"topology", "graphrag"}:
                    for sensor in self.queries:
                        result = self.get_equipment_neighbors(sensor)
                        if "error" in result:
                            raise ValueError("Initial graph context failed")
                        context["initial_graph_context"].append(result)
                # Snapshot includes only references returned by charged initial queries.
                context["observed_references"] = {sensor: self._reference.for_observed(sensor, self.queries)
                    for sensor in self.queries} if self._reference else {}
                self._primed_context = canonical(context)
            return json.loads(self._primed_context)
