"""Paired descriptive analysis; failures count as incorrect, never disappear."""
from __future__ import annotations

from collections import Counter
from itertools import combinations

import numpy as np

from .variants import METHODS


def macro_f1(rows):
    labels = sorted({r["true_event"] for r in rows})
    scores = []
    for label in labels:
        tp = sum(r["prediction"] == label and r["true_event"] == label for r in rows)
        fp = sum(r["prediction"] == label and r["true_event"] != label for r in rows)
        fn = sum(r["prediction"] != label and r["true_event"] == label for r in rows)
        scores.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.)
    return float(np.mean(scores)) if scores else None


def paired_comparison(left, right, seed=42, bootstrap_samples=2000):
    a = {r["case_id"]: r for r in left}
    b = {r["case_id"]: r for r in right}
    shared = sorted(a.keys() & b.keys())
    wins = [c for c in shared if not a[c]["correct"] and b[c]["correct"]]
    losses = [c for c in shared if a[c]["correct"] and not b[c]["correct"]]
    differences = {c: int(b[c]["correct"]) - int(a[c]["correct"]) for c in shared}
    groups = {}
    for c in shared:
        if a[c]["true_event"] != b[c]["true_event"] or a[c]["well_group"] != b[c]["well_group"]:
            raise ValueError("Paired rows refer to different ground truth")
        groups.setdefault(a[c]["well_group"], []).append(differences[c])
    ci = None
    if len(groups) >= 2:
        rng = np.random.RandomState(seed)
        totals = np.array([(sum(values), len(values)) for _, values in sorted(groups.items())])
        draws = rng.randint(0, len(totals), size=(bootstrap_samples, len(totals)))
        sums = totals[draws].sum(axis=1)
        estimates = sums[:, 0] / sums[:, 1]
        ci = [float(x) for x in np.percentile(estimates, [2.5, 97.5])]
    selection = []
    for case in shared:
        x, y = a[case]["sensor_sequence"], b[case]["sensor_sequence"]
        union = set(x) | set(y)
        divergent = next((i + 1 for i in range(max(len(x), len(y)))
                          if (x[i] if i < len(x) else None) != (y[i] if i < len(y) else None)), None)
        selection.append({"case_id": case, "sequence_changed": x != y,
                          "sensor_set_changed": set(x) != set(y), "first_divergence_query": divergent,
                          "jaccard": len(set(x) & set(y)) / len(union) if union else 1.,
                          "left_sequence": x, "right_sequence": y,
                          "left_correct": a[case]["correct"], "right_correct": b[case]["correct"]})
    return {"n_pairs": len(shared), "n_wells": len(groups), "right_only_correct": wins,
            "left_only_correct": losses,
            "accuracy_delta_right_minus_left": (len(wins) - len(losses)) / len(shared) if shared else None,
            "well_cluster_bootstrap_95_percentile_interval": ci,
            "bootstrap_seed": seed, "bootstrap_samples": bootstrap_samples,
            "sequence_changed_cases": sum(s["sequence_changed"] for s in selection),
            "sensor_set_changed_cases": sum(s["sensor_set_changed"] for s in selection),
            "selection_changes": selection}


def build_report(protocol, rows, case_ids):
    keys = [(r["case_id"], r["method"], r["budget"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate evaluation tasks cannot be analyzed")
    if any(r.get("protocol_id", protocol["protocol_id"]) != protocol["protocol_id"] for r in rows):
        raise ValueError("Cannot combine different evaluation protocols")
    selected = set(case_ids)
    blocks = [r for r in rows if r["case_id"] in selected]
    summary, comparisons = [], []
    for budget in protocol["budgets"]:
        for method in METHODS:
            block = [r for r in blocks if r["budget"] == budget and r["method"] == method]
            complete = len(block) == len(selected)
            correct = sum(r["correct"] for r in block)
            n = len(block)
            confusion = Counter((r["true_event"], r["prediction"]) for r in block)
            summary.append({"method": method, "budget": budget, "n_expected": len(selected),
                "n_attempted": n, "complete": complete,
                "n_failed": sum(r["status"] != "completed" for r in block),
                "accuracy": correct / n if n and complete else None,
                "accuracy_on_attempted": correct / n if n else None,
                "supported_class_macro_f1": macro_f1(block) if complete else None,
                "supported_classes": sorted({r["true_event"] for r in block}),
                "test_class_coverage_in_train": len({r["true_event"] for r in block} & set(protocol["training_classes"]))
                    / len({r["true_event"] for r in block}) if n else None,
                "mean_sensor_queries": float(np.mean([len(r["sensor_sequence"]) for r in block])) if n else None,
                "mean_latency_seconds": float(np.mean([r["latency_seconds"] for r in block])) if n else None,
                "estimated_known_usage_cost_usd": sum(r["estimated_cost_usd"] for r in block),
                "cost_complete": complete and all(r["cost_complete"] for r in block),
                "confusion": [{"true": a, "predicted": b, "count": count}
                              for (a, b), count in sorted(confusion.items(), key=lambda x: str(x[0]))],
                "per_class": [{"event": label, "support": sum(r["true_event"] == label for r in block),
                    "accuracy": sum(r["correct"] for r in block if r["true_event"] == label)
                                / sum(r["true_event"] == label for r in block)}
                              for label in sorted({r["true_event"] for r in block})],
                "errors": [{k: r[k] for k in ("case_id", "true_event", "prediction", "status", "reason", "confidence",
                                               "sensor_sequence", "sensor_quality", "graph_calls", "retrieval_calls")}
                           for r in block if not r["correct"]]})
        for a, b in combinations(METHODS, 2):
            comparison = paired_comparison([r for r in blocks if r["method"] == a and r["budget"] == budget],
                                           [r for r in blocks if r["method"] == b and r["budget"] == budget], protocol["seed"])
            comparisons.append({"left": a, "right": b, "budget": budget,
                                "complete": comparison["n_pairs"] == len(selected), **comparison})
    return {"protocol_id": protocol["protocol_id"], "n_cases": len(selected),
            "summary": summary, "paired_comparisons": comparisons,
            "limitations": ["Failures are incorrect; unattempted tasks make primary accuracy null.",
                "Bootstrap resamples wells, preserving within-well pairing; few wells imply uncertain intervals.",
                "One stochastic model draw per condition; selection differences do not prove graph causality.",
                "Illustrative graph, known labeled onset, small class counts and possible well/missingness shortcuts.",
                "Pilot/smoke labels may already be seen; do not tune prompts on this cohort.",
                "API estimates exclude unreported charges, taxes and account-specific credits; not invoices."]}
