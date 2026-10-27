"""PetroMind hackathon scaffold: bounded sensor tools + conservative graph + retrieval.
Python >=3.9. Requires pandas, numpy, pyarrow, networkx.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List
import numpy as np
import pandas as pd
import networkx as nx

# This is an illustrative, curated sensor-to-equipment association graph.
# Verify every relationship against the 3W documentation before asserting it is real.
EQUIPMENT = {
    "downhole": ["P-PDG", "T-PDG"],
    "tubing": ["P-TPT", "T-TPT"],
    "production_choke": ["P-MON-CKP", "P-JUS-CKP", "T-MON-CKP", "T-JUS-CKP", "ABER-CKP"],
    "gas_lift": ["P-JUS-CKGL", "P-MON-CKGL", "ABER-CKGL", "QGL", "P-ANULAR"],
}


def make_graph():
    g = nx.Graph()
    for equipment, sensors in EQUIPMENT.items():
        g.add_node(equipment, kind="equipment")
        for sensor in sensors:
            g.add_node(sensor, kind="sensor")
            g.add_edge(equipment, sensor, relation="monitored_or_associated")
    return g


def well_id(path: Path) -> str:
    m = re.match(r"(WELL-\d+)_", path.name)
    if not m:
        raise ValueError("Expected WELL-*.parquet name")
    return m.group(1)


def clean(x: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(x, errors="coerce").astype(float)
    numeric = numeric.replace([np.inf, -np.inf], np.nan)
    return numeric.mask(numeric.abs() > 1e12)


def summarize(x: pd.Series) -> Dict:
    arr = clean(x).dropna()
    if len(arr) == 0:
        return {"available": False, "count": 0}
    return {"available": True, "count": int(len(arr)),
            "median": float(arr.median()), "std": float(arr.std(ddof=0)),
            "first": float(arr.iloc[0]), "last": float(arr.iloc[-1]),
            "delta": float(arr.iloc[-1] - arr.iloc[0])}


class Investigation:
    """Label-blinded query interface. Internal labels used only for offline evaluation."""
    def __init__(self, incident: Path, budget: int = 5, seconds: int = 600):
        if budget < 1: raise ValueError("budget must be >= 1")
        self.incident = Path(incident)
        self._df = pd.read_parquet(self.incident)
        self._labels = self._df["class"].copy()
        transient = self._labels.dropna().astype(int)
        onset = transient.index[transient.ge(100) & transient.lt(200)]
        if len(onset) == 0:
            raise ValueError("Incident does not have a labeled transient stage")
        self._window = self._df.loc[onset[0]:].iloc[:seconds].copy()
        if len(self._window) < seconds:
            raise ValueError("Insufficient samples from transient onset")
        self.sensors = sorted(c for c in self._df.columns if c not in ("class", "state"))
        self.budget = budget
        self.queries: List[str] = []
        self.graph = make_graph()

    def list_sensors(self) -> List[str]:
        return self.sensors.copy()  # No availability information until queried.

    def get_sensor_history(self, sensor: str) -> Dict:
        if sensor not in self.sensors:
            return {"error": "unknown sensor"}
        if sensor in self.queries:
            return {"sensor": sensor, "summary": summarize(self._window[sensor]),
                    "remaining_budget": self.budget - len(self.queries), "cached": True}
        if len(self.queries) >= self.budget:
            return {"error": "sensor query budget exhausted", "remaining_budget": 0}
        self.queries.append(sensor)  # Missing sensor still costs one query.
        return {"sensor": sensor, "summary": summarize(self._window[sensor]),
                "remaining_budget": self.budget - len(self.queries), "cached": False}

    def get_equipment_neighbors(self, sensor: str) -> Dict:
        if sensor not in self.graph:
            return {"sensor": sensor, "neighbors": [], "note": "Not mapped"}
        equipment = list(self.graph.neighbors(sensor))
        neighbors = sorted(set(n for e in equipment for n in self.graph.neighbors(e) if n != sensor))
        return {"sensor": sensor, "equipment": equipment, "neighbor_sensors": neighbors,
                "note": "Curated illustrative associations; not verified per-well topology"}

    def evaluate(self, prediction: int) -> Dict:
        labels = self._window["class"].dropna().astype(int)
        true_type = int(labels.iloc[0]) % 100
        return {"predicted": prediction, "true_event": true_type,
                "correct": int(prediction) == true_type, "sensor_queries": len(self.queries),
                "trace": self.queries.copy()}


class IncidentRetriever:
    """Retrieval from disjoint training wells using ONLY queried sensor summaries.
    Training incidents have labeled classes; target class is never used for retrieval.
    Distances are uncalibrated and useful only as an initial smoke test.
    """
    def __init__(self, root: Path, held_out_wells: set, seconds=600, max_train=500):
        self.records = []
        for p in sorted(Path(root).rglob("WELL-*.parquet")):
            if well_id(p) in held_out_wells or p.parent.name == "0":
                continue
            if len(self.records) >= max_train: break
            df = pd.read_parquet(p)
            lab = df["class"].dropna().astype(int)
            onset = lab.index[(lab >= 100) & (lab < 200)]
            if len(onset) == 0: continue
            w = df.loc[onset[0]:].iloc[:seconds]
            if len(w) < seconds: continue
            event = int(lab.loc[onset[0]]) % 100
            self.records.append((event, {c: summarize(w[c]) for c in w.columns if c not in ("class", "state")}))

    def search(self, investigation: Investigation, top_k=3):
        # Strictly refuse retrieval before an agent requests evidence.
        queried = investigation.queries
        if not queried: return []
        query = {s: summarize(investigation._window[s]) for s in queried}
        scored = []
        for event, sensor_stats in self.records:
            diffs = []
            for s in queried:
                a, b = query[s], sensor_stats.get(s, {})
                if a.get("available") and b.get("available"):
                    # Scale-invariant bounded comparison; exploratory only.
                    a_med, b_med = a["median"], b["median"]
                    denom = max(1.0, abs(a_med), abs(b_med))
                    diffs.append(min(1.0, abs(a_med - b_med) / denom))
            if diffs: scored.append((float(np.mean(diffs)), event, len(diffs)))
        scored.sort(key=lambda x: x[0])
        # No filenames, well IDs, or test ground truth returned.
        return [{"training_event": e, "distance": round(d, 4), "shared_sensors": n}
                for d, e, n in scored[:top_k]]
