"""Frozen development claims and a strict public/private independent-case adapter."""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import fields
from urllib.parse import urlparse

from petromind.claim_evaluation import load_captured
from petromind.claim_review import load_capture
from petromind.eval_protocol import digest
from petromind.knowledge import SENSORS, PhysicalKnowledge
from petromind.measurements import SensorSummary

EXCHANGE_VERSION = "sprint-a-exchange-v1"
PREDICATES = {
    "metric_equal": {"kind", "sensor", "metric", "value"},
    "cross_sensor_constraint": {
        "kind",
        "left_sensor",
        "right_sensor",
        "metric",
        "operator",
    },
    "direction_equal": {"kind", "sensor", "value"},
    "fact": {"kind", "subject", "relation", "object", "scope"},
    "example_comparison": {"kind", "fault_type", "sensors"},
    "causal_inference": {"kind", "fault_type", "quantifier", "sensors"},
    "history_implication": {"kind", "sensors"},
    "expert_claim": {"kind"},
}
SUMMARY_FIELDS = {f.name for f in fields(SensorSummary)}


def validate_summary(summary):
    if not isinstance(summary, dict) or set(summary) - SUMMARY_FIELDS:
        raise ValueError("summary_fields_not_public")
    if type(summary.get("available")) is not bool:
        raise ValueError("invalid_availability")
    for key in ("count", "total", "invalid_count"):
        if type(summary.get(key)) is not int or summary[key] < 0:
            raise ValueError("invalid_summary_counts")
    if summary["count"] + summary["invalid_count"] != summary["total"]:
        raise ValueError("invalid_summary_counts")
    for key, value in summary.items():
        if type(value) in (float, int) and not math.isfinite(value):
            raise ValueError("nonfinite_summary")
    for key in ("median", "std", "first", "last", "delta"):
        value = summary.get(key)
        if summary["available"] and (
            type(value) not in (int, float) or not math.isfinite(value)
        ):
            raise ValueError("invalid_available_readings")
        if not summary["available"] and value is not None:
            raise ValueError("unavailable_reading_exposed")
    if summary["available"] != (summary["count"] > 0):
        raise ValueError("inconsistent_summary_availability")


def validate_exchange(data):
    if (
        set(data)
        != {"exchange_version", "author", "frozen", "isolation", "facts", "cases"}
        or data["exchange_version"] != EXCHANGE_VERSION
        or data["frozen"] is not True
    ):
        raise ValueError("invalid_exchange_contract")
    if not isinstance(data["author"], str) or not data["author"]:
        raise ValueError("reference_author_required")
    isolation = data["isolation"]
    if set(isolation) != {
        "fit_groups",
        "development_groups",
        "excluded_test_groups",
        "history_provenance",
    }:
        raise ValueError("isolation_attestation_required")
    groups = [
        set(isolation[k])
        for k in ("fit_groups", "development_groups", "excluded_test_groups")
    ]
    if not all(groups) or any(
        groups[i] & groups[j] for i in range(3) for j in range(i)
    ):
        raise ValueError("well_partitions_overlap_or_empty")
    if any(
        not isinstance(x, str)
        or len(x) != 64
        or any(c not in "0123456789abcdef" for c in x)
        for group in groups
        for x in group
    ):
        raise ValueError("hashed_groups_required")
    if (
        not isinstance(isolation["history_provenance"], str)
        or not isolation["history_provenance"]
    ):
        raise ValueError("history_provenance_required")
    facts = data["facts"]
    if not isinstance(facts, list) or len(facts) > 200:
        raise ValueError("bounded_fact_collection_required")
    fact_ids = set()
    fact_keys = {
        "id",
        "subject",
        "relation",
        "object",
        "source",
        "locator",
        "status",
        "scope",
        "provenance",
    }
    for f in facts:
        if (
            not isinstance(f, dict)
            or set(f) != fact_keys
            or not all(
                isinstance(f[k], str) and 0 < len(f[k]) <= 1000
                for k in fact_keys - {"provenance"}
            )
        ):
            raise ValueError("fact_provenance_required")
        if f["id"] in fact_ids or f["status"] not in {
            "documented",
            "engineering_hypothesis",
            "empirical_correlation",
        }:
            raise ValueError("invalid_fact_status_or_id")
        fact_ids.add(f["id"])
        provenance = f["provenance"]
        if (
            not isinstance(provenance, dict)
            or not provenance.get("version")
            or not provenance.get("url")
        ):
            raise ValueError("fact_provenance_required")
        url = urlparse(provenance["url"])
        if (
            url.scheme != "https"
            or not url.netloc
            or url.username
            or url.password
            or url.query
        ):
            raise ValueError("public_source_url_required")
        if set(provenance) - {
            "url",
            "immutable_url",
            "git_blob",
            "version",
            "authors",
            "license",
        }:
            raise ValueError("private_provenance_field")
    if not isinstance(data["cases"], list) or not 1 <= len(data["cases"]) <= 20:
        raise ValueError("bounded_cohort_required")
    identifiers = set()
    for case in data["cases"]:
        if set(case) != {
            "public",
            "reference",
            "source",
            "history",
            "optional_summaries",
        }:
            raise ValueError("case_contract_mismatch")
        public = case["public"]
        if set(public) != {
            "task_id",
            "constructed_evaluation_claim",
            "observations",
            "baseline",
            "candidate_faults",
            "claims",
            "scope",
        }:
            raise ValueError("public_packet_has_private_or_unknown_fields")
        if public["constructed_evaluation_claim"] is not True or not isinstance(
            public["scope"], str
        ):
            raise ValueError("constructed_claim_and_scope_required")
        if (
            not isinstance(public["task_id"], str)
            or len(public["task_id"]) != 32
            or any(c not in "0123456789abcdef" for c in public["task_id"])
            or public["task_id"] in identifiers
        ):
            raise ValueError("opaque_unique_task_ids_required")
        identifiers.add(public["task_id"])
        if (
            set(public["baseline"]) != {"prediction"}
            or type(public["baseline"]["prediction"]) is not int
            or not 1 <= public["baseline"]["prediction"] <= 9
        ):
            raise ValueError("public_hypothesis_required")
        if (
            not isinstance(public["candidate_faults"], list)
            or not 1 <= len(public["candidate_faults"]) <= 3
            or any(
                type(c) is not int or not 1 <= c <= 9
                for c in public["candidate_faults"]
            )
        ):
            raise ValueError("invalid_public_candidates")
        if (
            not isinstance(public["observations"], dict)
            or not 1 <= len(public["observations"]) <= 5
        ):
            raise ValueError("initial_sensor_budget_invalid")
        for collection in (public["observations"], case["optional_summaries"]):
            if not isinstance(collection, dict) or not set(collection) <= set(SENSORS):
                raise ValueError("invalid_sensor_catalog")
            for summary in collection.values():
                validate_summary(summary)
        # Either no active access, or a complete backend catalog including genuinely missing summaries.
        if case["optional_summaries"] and set(case["optional_summaries"]) != set(
            SENSORS
        ):
            raise ValueError(
                "optional_provider_must_cover_catalog_without_availability_oracle"
            )
        if (
            not isinstance(public["claims"], list)
            or not 1 <= len(public["claims"]) <= 6
        ):
            raise ValueError("bounded_claims_required")
        claim_ids = set()
        for claim in public["claims"]:
            if (
                set(claim) != {"claim_id", "statement", "predicate"}
                or not isinstance(claim["claim_id"], str)
                or not 1 <= len(claim["claim_id"]) <= 32
                or claim["claim_id"] in claim_ids
                or not isinstance(claim["statement"], str)
                or not 1 <= len(claim["statement"]) <= 1500
            ):
                raise ValueError("invalid_atomic_claim")
            claim_ids.add(claim["claim_id"])
            p = claim["predicate"]
            if (
                not isinstance(p, dict)
                or p.get("kind") not in PREDICATES
                or set(p) != PREDICATES[p["kind"]]
            ):
                raise ValueError("unknown_formal_proposition")
            if p["kind"] == "cross_sensor_constraint" and (
                p["left_sensor"] not in SENSORS
                or p["right_sensor"] not in SENSORS
                or p["operator"] not in {"lt", "le", "eq", "ge", "gt"}
            ):
                raise ValueError("invalid_cross_sensor_constraint")
            if p["kind"] == "fact" and any(
                not isinstance(p[key], str)
                for key in ("subject", "relation", "object", "scope")
            ):
                raise ValueError("invalid_fact_proposition")
            if "fault_type" in p and (
                type(p["fault_type"]) is not int or not 1 <= p["fault_type"] <= 9
            ):
                raise ValueError("invalid_claimed_fault_type")
            if "sensor" in p and p["sensor"] not in SENSORS:
                raise ValueError("invalid_predicate_sensor")
            if "sensors" in p and (
                not isinstance(p["sensors"], list)
                or not p["sensors"]
                or not set(p["sensors"]) <= set(SENSORS)
            ):
                raise ValueError("invalid_predicate_sensors")
            if "value" in p and (
                type(p["value"]) not in (int, float) or not math.isfinite(p["value"])
            ):
                raise ValueError("invalid_predicate_value")
            if "metric" in p and p["metric"] not in {
                "median",
                "std",
                "first",
                "last",
                "delta",
                "change",
            }:
                raise ValueError("invalid_predicate_metric")
            if p["kind"] == "direction_equal" and p["value"] not in (-1, 0, 1):
                raise ValueError("invalid_predicate_direction")
            if p["kind"] == "causal_inference" and p["quantifier"] not in {
                "necessity",
                "sufficiency",
            }:
                raise ValueError("unknown_quantifier")
        reference = case["reference"]
        if set(reference) != {
            "name",
            "judgments",
            "review_status",
            "reference_basis",
        } or reference["review_status"] not in {
            "mechanical_source_scope",
            "independent_review_pending",
            "external_review_attested",
        }:
            raise ValueError("private_reference_contract")
        if set(reference["judgments"]) != claim_ids or any(
            v not in {"SUPPORTED", "NOT_ESTABLISHED", "CONTRADICTED", "UNASSESSED"}
            for v in reference["judgments"].values()
        ):
            raise ValueError("reference_claim_mismatch")
        if not reference["reference_basis"]:
            raise ValueError("reference_basis_required")
        if (
            set(case["source"]) != {"group", "partition", "evidence_digest"}
            or case["source"]["partition"] != "development"
            or case["source"]["group"] not in groups[1]
        ):
            raise ValueError("case_outside_development_groups")
        if not isinstance(case["history"], list) or len(case["history"]) > 10:
            raise ValueError("bounded_historical_snapshot_required")
        for row in case["history"]:
            if (
                not isinstance(row, dict)
                or set(row)
                != {
                    "case_id",
                    "training_event",
                    "distance",
                    "shared_sensors",
                    "matched_sensors",
                }
                or not isinstance(row["case_id"], str)
                or len(row["case_id"]) != 32
                or any(c not in "0123456789abcdef" for c in row["case_id"])
                or type(row["training_event"]) is not int
                or not 1 <= row["training_event"] <= 9
                or not isinstance(row["matched_sensors"], list)
                or len(set(row["matched_sensors"])) != len(row["matched_sensors"])
                or not set(row["matched_sensors"]) <= set(public["observations"])
                or row["shared_sensors"] != len(row["matched_sensors"])
                or type(row["distance"]) not in (int, float)
                or not math.isfinite(row["distance"])
                or row["distance"] < 0
            ):
                raise ValueError("historical_snapshot_isolation")
    return deepcopy(data)


def from_capture(capture, science_run):
    """Verify saved audit chains, development lineage and partition membership.

    Snapshot history cannot be independently reindexed without raw data. Its
    provenance is the pinned training-only constructor, not guessed opaque IDs.
    """
    p, _ = load_capture(capture)
    science, packets, fingerprint = load_captured(science_run)
    if (
        science["protocol_id"] != p["source_protocol_id"]
        or fingerprint != p["capture_digest"]
    ):
        raise ValueError("capture_science_lineage_mismatch")
    parent = science["parent"]
    roles = {r["case_id"]: r for r in parent["records"]}
    fit = sorted({r["well_group"] for r in parent["records"] if r["role"] == "fit"})
    dev = sorted(
        {r["well_group"] for r in parent["records"] if r["role"] == "development_pool"}
    )
    test = sorted(
        {r["well_group"] for r in parent["records"] if r["role"] == "excluded_test"}
    )
    rising = next(
        r
        for r in packets
        if r["observations"]["P-PDG"]["delta"] > 0
        and r["observations"]["P-TPT"]["delta"] > 0
    )
    opposite = next(
        r
        for r in packets
        if r["observations"]["P-PDG"]["delta"] > 0
        and r["observations"]["P-TPT"]["delta"] < 0
    )
    missing = next(
        r for r in packets if not r["observations"]["ABER-CKGL"]["available"]
    )
    cases = []

    def add(name, record, statement, predicate, verdict, basis):
        baseline = record["baseline"]
        alternatives = sorted(
            (v for v in baseline["probabilities"] if v["represented_in_fit"]),
            key=lambda v: -v["probability"],
        )
        candidates = [baseline["prediction"]] + [
            v["fault_type"]
            for v in alternatives
            if v["fault_type"] != baseline["prediction"]
        ][:1]
        public = {
            "task_id": digest([p["protocol_id"], name])[:32],
            "constructed_evaluation_claim": True,
            "observations": deepcopy(record["observations"]),
            "baseline": {"prediction": baseline["prediction"]},
            "candidate_faults": candidates,
            "claims": [
                {"claim_id": "c1", "statement": statement, "predicate": predicate}
            ],
            "scope": "Previously observed development-window summaries only; no raw timeline or unqueried availability. Formal propositions are public to every method.",
        }
        cases.append(
            {
                "public": public,
                "reference": {
                    "name": name,
                    "judgments": {"c1": verdict},
                    "review_status": "mechanical_source_scope",
                    "reference_basis": basis,
                },
                "source": {
                    "group": roles[record["source_case_id"]]["well_group"],
                    "partition": "development",
                    "evidence_digest": digest(record),
                },
                "history": deepcopy(p["histories"].get(record["source_case_id"], [])),
                "optional_summaries": {},
            }
        )

    delta = opposite["observations"]["P-TPT"]["delta"]
    add(
        "exact_observation",
        opposite,
        f"The recorded P-TPT endpoint change equals {delta} Pa.",
        {"kind": "metric_equal", "sensor": "P-TPT", "metric": "delta", "value": delta},
        "SUPPORTED",
        "Exact recorded numeric value; not physical interpretation.",
    )
    add(
        "contrary_direction",
        opposite,
        "P-TPT increased from its first to last valid reading.",
        {"kind": "direction_equal", "sensor": "P-TPT", "value": 1},
        "CONTRADICTED",
        "The actual recorded endpoint change is negative, not absent.",
    )
    add(
        "missing_not_zero",
        missing,
        "An actual ABER-CKGL median opening of zero was measured.",
        {"kind": "metric_equal", "sensor": "ABER-CKGL", "metric": "median", "value": 0},
        "NOT_ESTABLISHED",
        "No valid reading establishes zero or an opposite value.",
    )
    add(
        "generic_sensor_definition",
        rising,
        "The source generically associates P-PDG with a downhole gauge.",
        {
            "kind": "fact",
            "subject": "P-PDG",
            "relation": "pressure_at",
            "object": "downhole_gauge",
            "scope": "generic_documented_definition",
        },
        "SUPPORTED",
        "dataset.ini location:P-PDG; no installed-well inference.",
    )
    add(
        "documented_valve_code",
        opposite,
        "In the cited generic valve-state convention, code 0 means closed.",
        {
            "kind": "fact",
            "subject": "valve_state:0",
            "relation": "means",
            "object": "closed",
            "scope": "generic_documented_definition",
        },
        "SUPPORTED",
        "Published Table 3; not an observed target valve state.",
    )
    add(
        "contrary_valve_code",
        opposite,
        "In the cited generic valve-state convention, code 0 means open.",
        {
            "kind": "fact",
            "subject": "valve_state:0",
            "relation": "means",
            "object": "open",
            "scope": "generic_documented_definition",
        },
        "CONTRADICTED",
        "Same scoped Table 3 convention explicitly says closed.",
    )
    add(
        "encoding_scope_leap",
        opposite,
        "A target equipment-state code of 0 establishes normal operational condition.",
        {
            "kind": "fact",
            "subject": "valve_state:0",
            "relation": "means",
            "object": "normal_operation",
            "scope": "well_specific_operational_annotation",
        },
        "NOT_ESTABLISHED",
        "A generic valve-state convention does not establish target reading or event-annotation mapping.",
    )
    add(
        "narrow_documented_comparison",
        rising,
        "Only the two observed pressure directions are consistent with the corresponding directions in the published fault-8 example; no whole-pattern or root-cause conclusion is asserted.",
        {"kind": "example_comparison", "fault_type": 8, "sensors": ["P-PDG", "P-TPT"]},
        "SUPPORTED",
        "Two source directions in Figure 5 plus two actual measured endpoint signs; no diagnostic inference.",
    )
    add(
        "fault9_necessity",
        rising,
        "The supplied evidence establishes that fault 9 must always cause both observed pressures to rise.",
        {
            "kind": "causal_inference",
            "fault_type": 9,
            "quantifier": "necessity",
            "sensors": ["P-PDG", "P-TPT"],
        },
        "NOT_ESTABLISHED",
        "No universal necessary fault-9 pressure rule in the supplied registry; not proof no such rule exists elsewhere.",
    )
    add(
        "fault9_sufficiency",
        rising,
        "The two pressure increases alone establish fault-9 service-line hydrate as the cause.",
        {
            "kind": "causal_inference",
            "fault_type": 9,
            "quantifier": "sufficiency",
            "sensors": ["P-PDG", "P-TPT"],
        },
        "NOT_ESTABLISHED",
        "No sufficient/discriminating rule in the supplied source collection; compatible fault-8 example is not proof of fault 9.",
    )
    add(
        "analogue_implication",
        rising,
        "A close historical match sharing one observed pressure establishes the same unique physical cause.",
        {"kind": "history_implication", "sensors": ["P-TPT"]},
        "NOT_ESTABLISHED",
        "Conditional constructed inference, not a fabricated retrieved match; unequal overlap is empirical similarity, not causal entailment.",
    )
    add(
        "second_narrow_comparison",
        opposite,
        "Only the two measured pressure directions are consistent with the corresponding directions of the published fault-2 example.",
        {"kind": "example_comparison", "fault_type": 2, "sensors": ["P-PDG", "P-TPT"]},
        "SUPPORTED",
        "Figure 3 directional comparison, not proof of DHSV closure or a complete published signature.",
    )
    exchange = {
        "exchange_version": EXCHANGE_VERSION,
        "author": "Predeclared numeric/source-scope construction; no LLM-generated key or independent engineering certification",
        "frozen": True,
        "isolation": {
            "fit_groups": fit,
            "development_groups": dev,
            "excluded_test_groups": test,
            "history_provenance": "Pinned claim prepare uses load_development_cohort fitting records and IncidentRetriever training-only guard. Opaque IDs are index-order hashes; raw reindexing not available.",
        },
        "facts": [f.public() for f in PhysicalKnowledge().facts],
        "cases": cases,
    }
    return validate_exchange(exchange), {
        "claim_protocol_id": p["protocol_id"],
        "science_protocol_id": science["protocol_id"],
        "capture_digest": p["capture_digest"],
    }
