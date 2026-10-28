"""Compatibility imports for the hardened investigation framework.

Use DiagnosticSession with a label-free frame and public sensor catalog for new
code. The legacy path constructor uses the SAME frozen split as the CLI.
Evaluation is deliberately no longer a method on the investigation object.
"""
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from petromind.data import well_id
from petromind.equipment import EQUIPMENT, EquipmentGraph
from petromind.measurements import MAX_ABS_RAW, summarize as _summarize
from petromind.pipeline import prepare_investigation
from petromind.retrieval import IncidentRetriever
from petromind.session import DiagnosticSession


def clean(x: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(x, errors="coerce").astype(float)
    return numeric.mask(~np.isfinite(numeric) | (numeric.abs() > MAX_ABS_RAW))


def summarize(x: pd.Series) -> dict:
    return _summarize(x).to_dict()


def make_graph():
    graph = nx.Graph()
    for edge in EquipmentGraph().relationships:
        graph.add_node(edge.sensor.name, kind=edge.sensor.kind.value)
        graph.add_node(edge.equipment.name, kind=edge.equipment.kind.value)
        graph.add_edge(edge.sensor.name, edge.equipment.name, relation=edge.kind.value,
                       verification=edge.verification.value, provenance=edge.provenance)
    return graph


def Investigation(incident: Path, budget: int = 5, seconds: int = 600):
    """Legacy factory; target must belong to the shared test partition.

    For explicit split/seed control use prepare_investigation. The old
    held_out_wells-only retriever constructor is intentionally unsupported.
    """
    return prepare_investigation(Path(incident).parent.parent, budget, seconds,
                                 split_path=Path(".petromind/split.json"),
                                 incident_path=incident).session
