"""Agent capability boundary: expose ONLY the five registered serialized tools.

This is a tool API boundary, not a Python sandbox. Never give agents arbitrary
Python/filesystem execution, a session repr, or evaluator/loader objects.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from numbers import Real
from threading import RLock
from types import MappingProxyType
from uuid import uuid4

import pandas as pd

from .audit import AuditEntry, canonical
from .equipment import EquipmentGraph
from .measurements import summarize, valid_sensor_name
from .variants import VARIANT_TOOLS


@dataclass(frozen=True)
class Diagnosis:
    case_id: str
    predicted_fault_type: int
    confidence: float
    evidence: tuple[str, ...]


class DiagnosticSession:
    def __init__(self, measurements: pd.DataFrame, sensor_names, budget: int = 5,
                 retriever=None, *, variant="graphrag"):
        if type(budget) is not int or not 1 <= budget <= 5:
            raise ValueError("budget must be an integer from 1 to 5")
        if variant not in VARIANT_TOOLS:
            raise ValueError("Unknown investigation variant")
        self._variant = variant
        names = tuple(sorted(sensor_names))
        if not names or len(set(names)) != len(names) or not all(map(valid_sensor_name, names)):
            raise ValueError("Declare a unique public sensor catalog")
        if not measurements.columns.is_unique:
            raise ValueError("Duplicate measurement columns")
        self._case_id = uuid4().hex  # Independent of paths, labels and well identifiers.
        self._sensors = names
        # Whitelist columns, discard metadata and index; take ownership of a deep copy.
        self._measurements = measurements.reindex(columns=names).reset_index(drop=True).copy(deep=True)
        self._measurements.attrs.clear()
        self._measurements.columns.name = None
        self._budget = budget
        self._observed = {}
        self._audit = ()
        self._diagnosis = None
        self._sealed = False
        self._graph = EquipmentGraph()
        self._retriever = retriever
        self._graph_queries = 0
        self._retrieval_queries = 0
        self._lock = RLock()

    @property
    def variant(self):
        return self._variant

    @property
    def case_id(self):
        return self._case_id

    @property
    def budget(self):
        return self._budget

    @property
    def remaining_budget(self):
        with self._lock:
            return self._budget - len(self._observed)

    @property
    def queries(self):
        with self._lock:
            return tuple(self._observed)

    @property
    def observations(self):
        with self._lock:
            return MappingProxyType(dict(self._observed))

    @property
    def audit_trail(self) -> tuple[AuditEntry, ...]:
        with self._lock:
            return self._audit

    @property
    def diagnosis(self) -> Diagnosis | None:
        with self._lock:
            return self._diagnosis

    def _record(self, tool, arguments, result):
        previous = self._audit[-1].digest if self._audit else "0" * 64
        self._audit += (AuditEntry.create(len(self._audit) + 1, tool, arguments, result, previous),)
        # JSON copy: caller mutation cannot change cache/audit/diagnosis.
        return json.loads(canonical(result))

    def _error(self, tool, args, code):
        return self._record(tool, args, {"error": code, "remaining_budget": self.remaining_budget})

    def list_sensors(self):
        with self._lock:
            if self._sealed or self._diagnosis:
                return self._error("list_sensors", {}, "investigation_closed")
            return self._record("list_sensors", {}, list(self._sensors))

    def _sensor_args(self, name):
        # Never echo arbitrary names: a malformed request could contain a hidden path.
        return {"sensor_name": name if isinstance(name, str) and name in self._sensors else "<invalid>"}

    def get_sensor_history(self, sensor_name):
        with self._lock:
            tool, args = "get_sensor_history", self._sensor_args(sensor_name)
            if self._sealed or self._diagnosis:
                return self._error(tool, args, "investigation_closed")
            if args["sensor_name"] == "<invalid>":
                return self._error(tool, args, "unknown_sensor")
            cached = sensor_name in self._observed
            if not cached and self.remaining_budget == 0:
                return self._error(tool, args, "sensor_budget_exhausted")
            if not cached:
                self._observed[sensor_name] = summarize(self._measurements[sensor_name])
            return self._record(tool, args, {"sensor": sensor_name,
                "summary": self._observed[sensor_name].to_dict(),
                "remaining_budget": self.remaining_budget, "cached": cached})

    def get_equipment_neighbors(self, sensor_name):
        with self._lock:
            tool, args = "get_equipment_neighbors", self._sensor_args(sensor_name)
            if tool not in VARIANT_TOOLS[self._variant]:
                return self._error(tool, args, "tool_not_available")
            if self._sealed or self._diagnosis:
                return self._error(tool, args, "investigation_closed")
            if args["sensor_name"] == "<invalid>":
                return self._error(tool, args, "unknown_sensor")
            if self._graph_queries >= 20:
                return self._error(tool, args, "graph_budget_exhausted")
            self._graph_queries += 1
            result = self._graph.neighbors(sensor_name, self._sensors)
            result.update(graph_queries=self._graph_queries, remaining_budget=self.remaining_budget)
            return self._record(tool, args, result)

    def search_similar_incidents(self, top_k=3):
        with self._lock:
            tool = "search_similar_incidents"
            args = {"top_k": top_k if type(top_k) is int and 1 <= top_k <= 10 else "<invalid>"}
            if tool not in VARIANT_TOOLS[self._variant]:
                return self._error(tool, args, "tool_not_available")
            if self._sealed or self._diagnosis:
                return self._error(tool, args, "investigation_closed")
            if type(top_k) is not int or not 1 <= top_k <= 10:
                return self._error(tool, args, "invalid_top_k")
            if self._retrieval_queries >= 10:
                return self._error(tool, args, "retrieval_budget_exhausted")
            self._retrieval_queries += 1
            matches = self._retriever.search(self.observations, top_k) if self._retriever else []
            return self._record(tool, args, {"matches": matches,
                "observed_sensors": list(self._observed), "retrieval_queries": self._retrieval_queries,
                "remaining_budget": self.remaining_budget})

    def submit_diagnosis(self, predicted_fault_type, confidence, evidence):
        with self._lock:
            tool = "submit_diagnosis"
            # Invalid submissions are logged without reflecting arbitrary untrusted payloads.
            valid = (type(predicted_fault_type) is int and 1 <= predicted_fault_type <= 9
                     and isinstance(confidence, Real) and not isinstance(confidence, bool)
                     and 0 <= confidence <= 1 and math.isfinite(confidence)
                     and isinstance(evidence, (list, tuple)) and 0 < len(evidence) <= 5
                     and all(isinstance(s, str) and s in self._observed
                             and self._observed[s].available for s in evidence))
            valid = valid and len(set(evidence)) == len(evidence)
            if self._sealed or self._diagnosis:
                return self._error(tool, {}, "investigation_closed")
            if not valid:
                return self._error(tool, {}, "invalid_diagnosis")
            self._diagnosis = Diagnosis(self.case_id, predicted_fault_type, float(confidence), tuple(evidence))
            result = asdict(self._diagnosis)
            result["supporting_observations"] = {s: self._observed[s].to_dict() for s in evidence}
            result["remaining_budget"] = self.remaining_budget
            return self._record(tool, asdict(self._diagnosis), result)

    def dispatch(self, tool: str, arguments: dict):
        """The ONLY entry point a future model executor should register.

        No getattr on model input and no evaluate/read-file/debug capability.
        """
        handlers = {"list_sensors": (self.list_sensors, set(), set()),
                    "get_sensor_history": (self.get_sensor_history, {"sensor_name"}, {"sensor_name"}),
                    "get_equipment_neighbors": (self.get_equipment_neighbors, {"sensor_name"}, {"sensor_name"}),
                    "search_similar_incidents": (self.search_similar_incidents, {"top_k"}, set()),
                    "submit_diagnosis": (self.submit_diagnosis,
                                         {"predicted_fault_type", "confidence", "evidence"},
                                         {"predicted_fault_type", "confidence", "evidence"})}
        with self._lock:
            if not isinstance(tool, str) or tool not in handlers:
                return self._error("dispatch", {}, "unknown_tool")
            handler, allowed, required = handlers[tool]
            if not isinstance(arguments, dict) or not required <= arguments.keys() <= allowed:
                return self._error(tool, {}, "invalid_arguments")
            return handler(**arguments)
