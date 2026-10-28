"""Scripted tool demonstration: no Muse/LLM and no claimed agent intelligence."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .pipeline import prepare_investigation


def emit(kind, value):
    print(json.dumps({"kind": kind, "result": value}, allow_nan=False, sort_keys=True))


def run_scripted_investigation(session):
    """Exercise the same five-tool dispatcher as the future model.

    Uses nearest-analogue votes; confidence=0 denotes uncalibrated support.
    """
    sensors = session.dispatch("list_sensors", {})
    emit("sensors", sensors)
    candidates = (["P-TPT"] if "P-TPT" in sensors else []) + sensors
    requested = set()
    last_matches = []
    while candidates and session.remaining_budget:
        sensor = candidates.pop(0)
        if sensor in requested:
            continue
        requested.add(sensor)
        observation = session.dispatch("get_sensor_history", {"sensor_name": sensor})
        emit("sensor_query", observation)
        graph = session.dispatch("get_equipment_neighbors", {"sensor_name": sensor})
        emit("graph_query", graph)
        candidates = graph["neighbor_sensors"] + candidates
        search = session.dispatch("search_similar_incidents", {})
        emit("historical_retrieval", search)
        last_matches = search["matches"]
    available = [s for s, summary in session.observations.items() if summary.available]
    if not available or not last_matches:
        raise ValueError("Insufficient observed evidence or historical overlap; no diagnosis fabricated")
    counts = Counter(match["training_event"] for match in last_matches)
    prediction = max(counts, key=lambda event: (counts[event], -event))
    diagnosis = session.dispatch("submit_diagnosis", {"predicted_fault_type": prediction,
                                 "confidence": 0.0, "evidence": available})
    if "error" in diagnosis:
        raise ValueError("Scripted diagnosis rejected")
    emit("final_diagnosis", diagnosis)
    return diagnosis


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--budget", type=int, choices=range(1, 6), default=5)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--split", type=Path, default=Path(".petromind/split.json"))
    parser.add_argument("--incident", type=Path, help="Evaluator-only path; must be held out")
    parser.add_argument("--reveal", action="store_true", help="Separate post-submission evaluator reveal")
    args = parser.parse_args(argv)
    try:
        prepared = prepare_investigation(args.dataset, args.budget, args.seconds, args.seed,
                                          args.split, args.incident)
        emit("protocol", {"scripted_demo": True, "meta_model": False,
             "known_transient_onset": True, "training_incidents": prepared.training_incidents,
             "test_incidents": prepared.test_incidents, "confidence_calibrated": False})
        run_scripted_investigation(prepared.session)
        emit("audit", {"entries": len(prepared.session.audit_trail),
                       "digest": prepared.session.audit_trail[-1].digest})
        if args.reveal:
            emit("evaluation_only", prepared.evaluator.reveal(prepared.session))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Investigation unavailable ({type(exc).__name__}); verify local dataset, "
                       "eligible transient windows, frozen split and evidence coverage.\n")
    return 0
