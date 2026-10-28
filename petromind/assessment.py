"""Deterministic submission contract. Provenance and consistency are not physics."""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from numbers import Real

ASSESSMENT_VERSION = "assessment-contract-v2"
MAX_REPAIRS = 2
FIELDS = ("available", "median", "std", "first", "last", "delta", "change", "count",
          "total", "missing_count", "nonfinite_count", "nonnumeric_count", "extreme_count",
          "zero_count", "is_constant", "constant_value", "quality_status")
CATEGORIES = ("supporting", "contradictory", "unavailable", "uncertainty")
DECISIONS = ("SUPPORT", "CHALLENGE", "INSUFFICIENT_EVIDENCE")
RELATIONSHIPS = {"supporting": "supports", "contradictory": "contradicts",
                 "unavailable": "inconclusive", "uncertainty": "inconclusive"}
NUMERIC_FIELDS = {"median", "std", "first", "last", "delta", "change", "constant_value"}
# A narrow generic-text guard, NOT a semantic classifier or expert judgment.
GENERIC_WORDS = frozenset("a an the this that it is be being for of to and or with in "
    "expert review needed need requires require required further more assessment "
    "interpretation interpret observation observations evidence contradictory contradiction "
    "support supporting supports uncertain uncertainty inconclusive consult specialist "
    "please should must seek get physical diagnosis diagnostic evaluate evaluation context".split())


def substantive(text):
    if not isinstance(text, str) or not 1 <= len(text) <= 1000:
        return False
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return len(tokens) >= 4 and bool(set(tokens) - GENERIC_WORDS)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    field: str
    correction: str


@dataclass(frozen=True)
class RejectedSubmission:
    issue: ValidationIssue
    fingerprint: str


def decode_submission(raw):
    """Retain only an issue and memory-only fingerprint for malformed arguments."""
    fingerprint = hashlib.sha256(raw.encode()).hexdigest()
    if len(raw) > 8192:
        return RejectedSubmission(ValidationIssue("assessment_arguments_too_large", "$",
            "Keep the JSON under 8192 characters; use fewer, concise claims."), fingerprint)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result
    def finite(_):
        raise ValueError("nonfinite")
    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("nonfinite")
        return parsed
    try:
        parsed = json.loads(raw, object_pairs_hook=unique, parse_constant=finite, parse_float=finite_float)
    except (ValueError, RecursionError):
        return RejectedSubmission(ValidationIssue("invalid_assessment_json", "$",
            "Use strict JSON with unique keys and finite numbers; do not include commentary outside the object."), fingerprint)
    if not isinstance(parsed, dict):
        return RejectedSubmission(ValidationIssue("assessment_object_required", "$",
            "Return a JSON object matching submit_assessment, not an array, string or null."), fingerprint)
    return parsed


def validate_assessment(args, baseline, observations, sources, returned_relationships):
    """Return only static errors and bounded field paths; never echo rejected data."""
    def fail(code, field, instruction):
        return ValidationIssue(code, field, instruction)
    required = ("decision", "confidence", "alternative_fault_type", "claims", "relationships", "uncertainty")
    if not isinstance(args, dict):
        return fail("invalid_submission_fields", "$", "Use a JSON object with exactly the fields in submit_assessment's schema.")
    missing = next((k for k in required if k not in args), None)
    if missing is not None:
        return fail("missing_submission_field", missing, "Include all required submission fields: decision, confidence, alternative_fault_type, claims, relationships, uncertainty.")
    if set(args) != set(required):
        return fail("invalid_submission_fields", "$", "Use exactly the fields in submit_assessment's schema; omit all other keys.")
    decision, confidence, alt = args["decision"], args["confidence"], args["alternative_fault_type"]
    if decision not in DECISIONS:
        return fail("invalid_decision", "decision", "Choose SUPPORT, CHALLENGE, or INSUFFICIENT_EVIDENCE.")
    if (not isinstance(confidence, Real) or isinstance(confidence, bool)
            or not math.isfinite(confidence) or not 0 <= confidence <= 1):
        return fail("invalid_confidence", "confidence", "Use a finite number from 0 to 1, not a boolean.")
    if not isinstance(args["uncertainty"], str) or not 1 <= len(args["uncertainty"]) <= 1000:
        return fail("invalid_uncertainty", "uncertainty", "Describe uncertainty in 1–1000 characters.")
    if alt is not None and (decision != "CHALLENGE" or type(alt) is not int or not 1 <= alt <= 9 or alt == baseline):
        return fail("invalid_alternative", "alternative_fault_type", "Use null unless challenging; an alternative must be an integer 1–9 different from the baseline.")
    claims = args["claims"]
    if not isinstance(claims, list) or not 1 <= len(claims) <= 12:
        return fail("invalid_claim_count", "claims", "Provide 1–12 sourced claims; uncertainty can cite unavailable queried evidence.")
    directions, facts = {}, {}
    for index, claim in enumerate(claims):
        path = f"claims[{index}]"
        keys = ("source_id", "hypothesis_fault_type", "category", "sensor_name", "field", "value",
                "interpretation", "expected_if_hypothesis_true")
        if not isinstance(claim, dict):
            return fail("invalid_claim_fields", path, "Use a claim object containing every required field in the schema.")
        missing = next((k for k in keys if k not in claim), None)
        if missing is not None:
            return fail("missing_claim_field", path + "." + missing,
                "Include every claim field: source_id, hypothesis_fault_type, category, sensor_name, field, value, interpretation, expected_if_hypothesis_true.")
        if set(claim) != set(keys):
            return fail("invalid_claim_fields", path, "Use exactly the allowed claim fields; remove all other keys.")
        fault = claim["hypothesis_fault_type"]
        if type(fault) is not int or not 1 <= fault <= 9:
            return fail("invalid_claim_hypothesis", path + ".hypothesis_fault_type", "Identify the evaluated fault with an integer 1–9.")
        category = claim["category"]
        if category not in CATEGORIES:
            return fail("invalid_claim_category", path + ".category", "Use supporting, contradictory, unavailable, or uncertainty.")
        source_id = claim["source_id"]
        if not isinstance(source_id, str) or source_id not in sources:
            return fail("source_not_observed", path + ".source_id", "Use a source_id returned with queried evidence; unqueried readings and illustrative graph edges cannot be proof.")
        source = sources[source_id]
        interpretation = claim["interpretation"]
        if not isinstance(interpretation, str) or not 1 <= len(interpretation) <= 1000:
            return fail("invalid_interpretation", path + ".interpretation", "Provide a brief interpretation of the cited fact, within 1000 characters.")
        if category in {"supporting", "contradictory"} and not substantive(interpretation):
            return fail("generic_evidence_claim", path + ".interpretation", "Explain how the cited fact bears on the identified hypothesis; a review recommendation is not evidence.")
        expected = claim["expected_if_hypothesis_true"]
        if expected is not None and (not isinstance(expected, str) or not 1 <= len(expected) <= 1000):
            return fail("invalid_expectation", path + ".expected_if_hypothesis_true", "Use null or a concise statement of the expected observation.")
        if category == "contradictory" and not substantive(expected):
            return fail("contradiction_requires_expectation", path + ".expected_if_hypothesis_true", "State the expected observation under this hypothesis, separately from the actual cited reading; do not substitute a review request.")
        if source["kind"] == "measurement":
            sensor = claim["sensor_name"]
            if not isinstance(sensor, str) or sensor != source["sensor_name"] or sensor not in observations:
                return fail("sensor_not_observed", path + ".sensor_name", "Cite the observed sensor identified by this source_id.")
            field = claim["field"]
            if field not in FIELDS:
                return fail("invalid_citation_field", path + ".field", "Choose an allowed sensor summary field from the schema.")
            obs = observations[sensor]
            actual, quoted = obs[field], claim["value"]
            if type(actual) is not type(quoted) and (isinstance(actual, bool) or isinstance(quoted, bool)
                    or not isinstance(actual, Real) or not isinstance(quoted, Real)):
                return fail("citation_type_mismatch", path + ".value", "Quote the returned field with its original JSON scalar type; boolean and number differ.")
            if isinstance(quoted, Real) and not math.isfinite(quoted):
                return fail("nonfinite_citation", path + ".value", "Quote a finite returned value or its exact null; do not use NaN or infinity.")
            if quoted != actual:
                return fail("citation_value_mismatch", path + ".value", "Quote the exact value from the queried summary without rounding or replacing it.")
            if category in {"supporting", "contradictory"}:
                if not obs["available"]:
                    return fail("unavailable_reading_cannot_support_or_contradict", path + ".category", "Categorize unavailable measurements as unavailable or uncertainty, not diagnostic support or contradiction.")
                if field not in NUMERIC_FIELDS or actual is None:
                    return fail("numeric_reading_required", path + ".field", "Use an available numeric reading field for diagnostic support or contradiction.")
            if category == "unavailable" and obs["available"]:
                return fail("available_reading_cannot_be_unavailable", path + ".category", "The cited reading is available; use an appropriate evidence category.")
            fact = ("measurement", source["sensor_name"], field, fault)
        elif source["kind"] == "graph_relationship":
            if source["relationship"].get("verification") != "verified_generic":
                return fail("graph_source_not_verified", path + ".source_id", "Only an actually returned, verified graph relationship may be a graph evidence source.")
            if any(claim[k] is not None for k in ("sensor_name", "field", "value")):
                return fail("graph_claim_has_measurement", path, "For graph evidence use null sensor_name, field and value; the source_id identifies the returned relationship.")
            if category == "unavailable":
                return fail("invalid_graph_category", path + ".category", "A returned graph source cannot be unavailable; use uncertainty for limited interpretation.")
            relation = source["relationship"]
            fact = ("graph", relation["sensor"], relation["equipment"], relation["relation"],
                    relation["verification"], fault)
        else:
            return fail("invalid_source_kind", path + ".source_id", "Use an observed measurement or verified graph evidence source.")
        direction = RELATIONSHIPS[category]
        previous = facts.setdefault(fact, set())
        previous.add(direction)
        if {"supports", "contradicts"} <= previous:
            return fail("conflicting_evidence_relationships", path + ".category", "The same cited fact cannot both support and contradict the same hypothesis; resolve it or mark uncertainty.")
        directions.setdefault(fault, set()).add(direction)
    baseline_directions = directions.get(baseline, set())
    if decision == "CHALLENGE" and "contradicts" not in baseline_directions:
        return fail("challenge_requires_baseline_contradiction", "claims", "CHALLENGE must cite a contradiction of the baseline hypothesis itself, not just an alternative.")
    if decision == "SUPPORT" and "supports" not in baseline_directions:
        return fail("support_requires_baseline_support", "claims", "SUPPORT must cite evidence supporting the baseline hypothesis itself.")
    if decision == "SUPPORT" and "contradicts" in baseline_directions:
        return fail("support_conflicts_with_contradiction", "decision", "Resolve the baseline contradiction or use INSUFFICIENT_EVIDENCE; do not finalize it as SUPPORT.")
    if alt is not None:
        if "contradicts" in directions.get(alt, set()):
            return fail("alternative_conflicts_with_evidence", "alternative_fault_type", "Do not propose an alternative contradicted by your own claims; resolve it or leave the alternative null.")
        if "supports" not in directions.get(alt, set()):
            return fail("alternative_requires_support", "claims", "Cite supporting evidence for the proposed alternative, or leave alternative_fault_type null.")
    relations = args["relationships"]
    if not isinstance(relations, list) or len(relations) > 8:
        return fail("invalid_relationships", "relationships", "Use at most eight graph-context relationships, or an empty list.")
    if any(not isinstance(r, dict) or r not in returned_relationships for r in relations):
        return fail("relationship_not_returned", "relationships", "Copy only relationships actually returned by graph tools, retaining their verification status.")
    return None
