"""Private, training-well-only development protocol. Never pass it to Muse."""
from __future__ import annotations

import hashlib
import math
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from .agent import AgentConfig
from .baselines import GaussianEvidence
from .challenger import INSTRUCTIONS, PROMPT_VERSION, observe_adaptively
from .data import load_incidents
from .eval_protocol import DEFAULT_PRICES, digest, inventory, runtime_versions, source_digest
from .session import DiagnosticSession
from .splits import WellSplit

METHODS = ("baseline", "challenger", "challenger_graph", "challenger_graphrag")
VARIANTS = {"challenger": "sensor_only", "challenger_graph": "topology", "challenger_graphrag": "graphrag"}
# Engineering feasibility criteria chosen before any M4 live results, not safety certification.
GATE = {"min_wrong_cases": 4, "min_correct_cases": 4, "completion_rate": .95,
        "challenge_recall": .60, "false_challenge_rate_max": .20, "challenge_precision": .75,
        "mechanical_citation_rate": .95, "expert_claim_coverage": 1.,
        "expert_challenge_precision": .80, "expert_useful_case_rate": .80,
        "unsupported_physical_claims_max": 0}


def _pick_stratified(pool, count, seed):
    """Deliberately enrich initial-hypothesis errors; class round robin within strata."""
    buckets = {}
    for row in pool:
        key = (row["baseline_correct"], row.get("five_query_correct", row["baseline_correct"]), row["true_event"])
        buckets.setdefault(key, []).append(row)
    for values in buckets.values():
        values.sort(key=lambda r: digest([seed, r["locator_hash"]]))
    selected = []
    # Alternating wrong/correct, then classes, before filling exhausted strata.
    while len(selected) < count and any(buckets.values()):
        for correct in (False, True):
            for key in sorted(buckets):
                if key[0] == correct and buckets[key] and len(selected) < count:
                    selected.append(buckets[key].pop(0))
    return selected


def freeze_development(dataset, split_path, *, n_cases=16, pilot_cases=2, seconds=600,
                       seed=104, initial_queries=2, config=None):
    if (type(n_cases) is not int or not 12 <= n_cases <= 20 or type(pilot_cases) is not int
            or not 1 <= pilot_cases <= n_cases or type(initial_queries) is not int or initial_queries != 2
            or type(seed) is not int):
        raise ValueError("Use 12–20 requested cases, valid pilot size and the predeclared two initial queries")
    original = WellSplit.load(Path(split_path))
    incidents = load_incidents(Path(dataset), seconds)
    original.validate_universe({r.well for r in incidents})
    if len(original.train_wells) < 4:
        raise ValueError("At least four original training wells are required")
    # Membership is label blind. Never retry splits to improve coverage or performance.
    ordered = sorted(original.train_wells, key=lambda w: digest([seed, w]))
    n_dev = min(len(ordered) - 2, max(2, math.ceil(len(ordered) / 3)))
    dev_wells = tuple(sorted(ordered[:n_dev]))
    fit_wells = tuple(sorted(ordered[n_dev:]))
    excluded = tuple(sorted(set(original.test_wells) | set(dev_wells)))
    retrieval_split = WellSplit(fit_wells, excluded, seed)
    fit = [r for r in incidents if r.well in fit_wells]
    names = tuple(sorted({s for r in fit for s in r.measurements}))
    if len(names) < 5:
        raise ValueError("Five public sensor candidates required")
    model = GaussianEvidence(fit, names)
    rows = inventory(dataset, incidents, original)
    by_locator = {hashlib.sha256(r.path.relative_to(Path(dataset).resolve()).as_posix().encode()).hexdigest(): r
                  for r in incidents}
    pool = []
    for locator, row in rows.items():
        record = by_locator[locator]
        row["case_id"] = uuid4().hex
        row["role"] = ("fit" if record.well in fit_wells else
                       "development_pool" if record.well in dev_wells else "excluded_test")
        if row["role"] == "development_pool":
            session = DiagnosticSession(record.measurements, names, 5, variant="sensor_only")
            hypothesis = observe_adaptively(model, session, initial_queries)
            initial_sequence = list(session.queries)
            final = observe_adaptively(model, session, session.remaining_budget)
            pool.append({"case_id": row["case_id"], "locator_hash": locator,
                         "true_event": record.event, "baseline_prediction": hypothesis["prediction"],
                         "baseline_correct": hypothesis["prediction"] == record.event,
                         "initial_hypothesis": hypothesis, "initial_sensor_sequence": initial_sequence,
                         "five_query_prediction": final["prediction"],
                         "five_query_correct": final["prediction"] == record.event})
    selected = _pick_stratified(pool, min(n_cases, len(pool)), seed)
    if not selected:
        raise ValueError("No eligible development cases")
    # Pilot includes both strata if available; selection never depends on Muse output.
    pilot = []
    for correct in (False, True):
        candidate = next((r for r in selected if r["baseline_correct"] == correct), None)
        if candidate is not None and len(pilot) < pilot_cases:
            pilot.append(candidate["case_id"])
    pilot.extend(r["case_id"] for r in selected if r["case_id"] not in pilot)
    config = config or AgentConfig(max_output_tokens=4096)
    protocol = {"version": 1, "study": "hypothesis-challenger-development-v1",
        "source_digest": source_digest(), "runtime": runtime_versions(),
        "original_split": asdict(original), "retrieval_split": asdict(retrieval_split),
        "development_wells": list(dev_wells), "records": list(rows.values()),
        "selected": selected, "pilot_case_ids": pilot[:pilot_cases], "seed": seed,
        "seconds": seconds, "budget": 5, "initial_queries": initial_queries,
        "methods": list(METHODS), "agent_config": asdict(config),
        "prompt_version": PROMPT_VERSION, "prompt_digest": digest(INSTRUCTIONS),
        "prices": dict(DEFAULT_PRICES), "gate": dict(GATE),
        "fit_classes": [int(c) for c in model.classes], "requested_cases": n_cases,
        "selection": {"policy": "Label-blind hash well split, then joint initial/five-query correctness and class round-robin",
                      "pool_cases": len(pool), "pool_wrong": sum(not r["baseline_correct"] for r in pool),
                      "selected_wrong": sum(not r["baseline_correct"] for r in selected),
                      "pool_five_query_wrong": sum(not r["five_query_correct"] for r in pool),
                      "selected_five_query_wrong": sum(not r["five_query_correct"] for r in selected),
                      "class_counts": {str(c): sum(r["true_event"] == c for r in selected)
                                       for c in sorted({r["true_event"] for r in selected})},
                      "enriched": True, "population_accuracy_claim_allowed": False},
        "per_run_transport": {"max_requests": config.max_turns + 4,
            "max_output_budget": config.max_turns * config.max_output_tokens, "max_retries": 2, "timeout": 60}}
    protocol["protocol_id"] = digest(protocol)
    return protocol


def validate_development(protocol, dataset):
    if digest({k: v for k, v in protocol.items() if k != "protocol_id"}) != protocol["protocol_id"]:
        raise ValueError("Protocol was modified")
    if protocol["source_digest"] != source_digest() or protocol["runtime"] != runtime_versions():
        raise ValueError("Frozen code/runtime changed")
    raw = protocol["original_split"]
    original = WellSplit(tuple(raw["train_wells"]), tuple(raw["test_wells"]), raw["seed"], raw["version"])
    raw = protocol["retrieval_split"]
    split = WellSplit(tuple(raw["train_wells"]), tuple(raw["test_wells"]), raw["seed"], raw["version"])
    if (not set(split.train_wells) < set(original.train_wells)
            or set(protocol["development_wells"]) & set(original.test_wells)
            or set(protocol["development_wells"]) & set(split.train_wells)
            or not set(original.test_wells) <= set(split.test_wells)):
        raise ValueError("Development well isolation violated")
    incidents = load_incidents(Path(dataset), protocol["seconds"])
    original.validate_universe({r.well for r in incidents})
    expected = {r["locator_hash"]: {k: v for k, v in r.items() if k not in {"case_id", "role"}}
                for r in protocol["records"]}
    if inventory(dataset, incidents, original) != expected:
        raise ValueError("Frozen dataset changed")
    by_locator = {hashlib.sha256(r.path.relative_to(Path(dataset).resolve()).as_posix().encode()).hexdigest(): r
                  for r in incidents}
    by_id = {row["case_id"]: by_locator[row["locator_hash"]] for row in protocol["records"]}
    if len(by_id) != len(incidents):
        raise ValueError("Duplicate case identifiers")
    for row in protocol["records"]:
        well = by_id[row["case_id"]].well
        role = "fit" if well in split.train_wells else "development_pool" if well in protocol["development_wells"] else "excluded_test"
        if row["role"] != role:
            raise ValueError("Invalid split membership")
    selected = [r["case_id"] for r in protocol["selected"]]
    if (len(set(selected)) != len(selected) or not set(protocol["pilot_case_ids"]) <= set(selected)
            or any(by_id[k].well not in protocol["development_wells"] for k in selected)):
        raise ValueError("Selected cases must be isolated development cases")
    return split, by_id
