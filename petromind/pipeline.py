"""Trusted composition for CLI and future evaluation runners; never model-visible."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .data import load_incidents
from .evaluation import Evaluator
from .retrieval import IncidentRetriever
from .session import DiagnosticSession
from .splits import WellSplit, make_well_split


@dataclass(frozen=True)
class PreparedInvestigation:
    session: DiagnosticSession
    evaluator: Evaluator
    split: WellSplit
    training_incidents: int
    test_incidents: int


def prepare_investigation(dataset: Path, budget=5, seconds=600, seed=42,
                          split_path: Path | None = None,
                          incident_path: Path | None = None) -> PreparedInvestigation:
    incidents = load_incidents(dataset, seconds)
    wells = {r.well for r in incidents}
    if split_path is not None and Path(split_path).exists():
        split = WellSplit.load(split_path)
        split.validate_universe(wells)
        if split.seed != seed:
            raise ValueError("Requested seed differs from frozen split")
    else:
        split = make_well_split(wells, seed)
        if split_path is not None:
            Path(split_path).parent.mkdir(parents=True, exist_ok=True)
            split.save(split_path)
    train = tuple(r for r in incidents if r.well in split.train_wells)
    test = tuple(r for r in incidents if r.well in split.test_wells)
    if incident_path is None:
        target = test[0]  # Stable ordering; never selected by success or ground truth.
    else:
        target = next((r for r in test if r.path == Path(incident_path).resolve()), None)
        if target is None:
            raise ValueError("Selected incident must be eligible and in the frozen test partition")
    retriever = IncidentRetriever(train, split)
    sensors = sorted({s for r in train for s in r.measurements.columns})
    session = DiagnosticSession(target.measurements, sensors, budget, retriever)
    return PreparedInvestigation(session, Evaluator(session.case_id, target.event), split,
                                 retriever.size, len(test))
