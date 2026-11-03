"""Read-only projection, independent human forms, agreement and adjudication.

No API client, scorer, accounting database or unblinding-map access. A seal
attests file/coverage consistency, not reviewer qualifications or physical truth.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
import re
import secrets
from collections import Counter
from pathlib import Path

VERSION = "sprint-c-human-semantic-review-v1"
RUBRIC_BLOB = "39c559ec0686ef00a7c936142485d75b0ee32780"
WEIGHTS = {
    "citation_entailment": 4,
    "document_scope": 8,
    "causal_leaps": 8,
    "missing_premises": 6,
    "historical_analogue": 5,
    "hypothesis_comparison": 6,
    "sensor_acquisition": 8,
    "necessity_sufficiency": 6,
}
PENALTIES = {
    "invented_reading": 15,
    "fabricated_citation": 15,
    "unsupported_causal_certainty": 10,
    "ignoring_supplied_contradiction": 10,
    "generic_topology_transfer": 10,
    "correlation_as_causation": 10,
    "unavailable_frozen_irrelevant_sensor": 2,
}
FLAGS = (
    "assumption_misuse",
    "measurement_cause_conflation",
    "calibration_overreach",
    "unjustified_contradiction",
    "missing_premise_vague",
    "next_evidence_not_feasible",
    "unsupported_causal_certainty",
    "excessive_abstention",
)
LABELS = ("SUPPORTED", "NOT_ESTABLISHED", "CONTRADICTED", "UNDETERMINABLE")
TARGETS = ("proposition_truth", "evidence_sufficiency", "ambiguous_wording")
PUBLIC_KEYS = {
    "atomic_claims",
    "budget_policy",
    "case_id",
    "claim",
    "classifier",
    "diagnostic_claim_id",
    "endpoint_windows_s",
    "evidence_budget",
    "initial_measurements",
    "initial_sensors",
    "instructions",
    "model",
    "resources",
    "scenario",
    "sensor_catalog",
    "synthetic",
    "time_origin",
    "version",
}
FORBIDDEN = {
    "variant",
    "model_variant",
    "method",
    "execution_group",
    "reference_verdict",
    "expected_verdict",
    "answer_key",
    "unblinding_map",
    "private_cause",
    "semantic_score",
    "api_key",
    "encrypted_content",
    "authorization",
    "protocol_id",
    "reference_answers",
    "expected",
    "private_metadata",
}
ROOT = Path(__file__).parent


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(value):
    return hashlib.sha256(
        value if isinstance(value, bytes) else canonical(value).encode()
    ).hexdigest()


def fail(code):
    raise ValueError(code)


def read(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                fail("duplicate_json_key")
            out[key] = value
        return out

    raw = Path(path).read_bytes()
    if len(raw) > 150_000_000:
        fail("input_too_large")
    return json.loads(
        raw, object_pairs_hook=unique, parse_constant=lambda _: fail("nonfinite_json")
    )


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def scan(value):
    if isinstance(value, dict):
        if FORBIDDEN & set(value):
            fail("possible_key_or_identity_leak")
        for v in value.values():
            scan(v)
    elif isinstance(value, list):
        for v in value:
            scan(v)
    elif isinstance(value, str) and (
        re.search(r"\bV[0-3]\b|confirmatory(?:-repeat)?-v\d|/phase2/cells/", value)
    ):
        fail("possible_unblinding_text_owner_inspection_required")


def project(packet):
    keys = {
        "review_id",
        "public_packet",
        "received_tool_evidence",
        "propositions",
        "submission",
        "semantic_grades",
    }
    if not isinstance(packet, dict) or set(packet) != keys:
        fail("unsupported_packet_contract")
    rid = packet["review_id"]
    if not isinstance(rid, str) or not re.fullmatch("[0-9a-f]{24}", rid):
        fail("invalid_blind_id")
    if packet["semantic_grades"] is not None:
        fail("prior_semantic_grades_present")
    public = packet["public_packet"]
    if not isinstance(public, dict) or set(public) != PUBLIC_KEYS:
        fail("unexpected_public_packet_fields")
    atoms = public["atomic_claims"]
    if (
        not isinstance(atoms, list)
        or not atoms
        or any(set(a) != {"id", "scope", "statement"} for a in atoms)
    ):
        fail("invalid_atoms")
    if len({a["id"] for a in atoms}) != len(atoms):
        fail("duplicate_atoms")
    props = packet["propositions"]
    if len(props) != len(atoms):
        fail("proposition_coverage_mismatch")
    final = packet["submission"]
    if final is not None and (
        not isinstance(final, dict)
        or set(final) != {"verdict", "findings", "numeric_observations"}
    ):
        fail("unexpected_submission_contract")
    fs = [] if final is None else final["findings"]
    if not isinstance(fs, list):
        fail("invalid_findings")
    for atom, prop in zip(atoms, props):
        if set(prop) != {
            "atomic_proposition",
            "submitted_finding",
            "semantic_entailment",
            "missing_premise_quality",
            "next_evidence_usefulness",
        }:
            fail("unexpected_proposition_fields")
        if any(
            prop[k] is not None
            for k in (
                "semantic_entailment",
                "missing_premise_quality",
                "next_evidence_usefulness",
            )
        ):
            fail("prior_semantic_grades_present")
        found = next((f for f in fs if f.get("statement") == atom["statement"]), None)
        if prop["atomic_proposition"] != atom or prop["submitted_finding"] != found:
            fail("proposition_submission_mismatch")
    events = []
    seen = set()
    allowed = {
        "query_sensor": {"sensor"},
        "read_document": {"id"},
        "lookup_graph": {"node", "hops"},
        "search_history": set(),
    }
    for event in packet["received_tool_evidence"]:
        if not isinstance(event, dict) or set(event) != {
            "sequence",
            "tool",
            "arguments",
            "result",
            "previous",
            "digest",
        }:
            fail("unexpected_evidence_event_contract")
        seq = event["sequence"]
        if type(seq) is not int or seq < 1 or seq in seen:
            fail("duplicate_or_invalid_event_sequence")
        seen.add(seq)
        # Preserve all legitimate returned evidence verbatim. Never export rejected args.
        if event["tool"] == "submit_audit":
            result = event["result"]
            if not isinstance(result, dict):
                fail("unexpected_submission_event")
            safe = {
                k: result[k]
                for k in (
                    "error",
                    "field",
                    "correction",
                    "repairs_remaining",
                    "accepted",
                )
                if k in result
            }
            events.append(
                {
                    "sequence": seq,
                    "tool": "submission_validation",
                    "arguments": {},
                    "result": safe,
                }
            )
        elif event["tool"] in allowed:
            args = event["arguments"]
            if not isinstance(args, dict) or set(args) != allowed[event["tool"]]:
                if (
                    not isinstance(event["result"], dict)
                    or "error" not in event["result"]
                ):
                    fail("unexpected_tool_arguments")
                args = {}
            events.append(
                {
                    "sequence": seq,
                    "tool": event["tool"],
                    "arguments": args,
                    "result": event["result"],
                }
            )
        elif isinstance(event["result"], dict) and "error" in event["result"]:
            events.append(
                {
                    "sequence": seq,
                    "tool": "unrecognized_tool",
                    "arguments": {},
                    "result": {"error": event["result"]["error"]},
                }
            )
        else:
            fail("unexpected_tool_requires_owner_review")
    result = {
        "review_id": rid,
        "initial": copy.deepcopy(public),
        "events": copy.deepcopy(events),
        "submission": copy.deepcopy(final),
        "projection_notice": "Derived review copy. Host hashes/execution metadata omitted; rejected submission arguments withheld. Evidence results and final assessment preserved. No new activity.",
    }
    scan(result)
    return result


def atom_template(atom):
    return {
        "atom_id": atom["id"],
        "interpretation_target": None,
        "preferred_verdict": None,
        "scientific_validity": None,
        "citation_entailment": None,
        "flags": {k: None for k in FLAGS},
        "evidence_refs": [],
        "rationale": "",
        "confidence": None,
    }


def row_template(packet):
    return {
        "review_id": packet["review_id"],
        "packet_sha256": sha(packet),
        "status": "NO_FINAL_SUBMISSION"
        if packet["submission"] is None
        else "HAS_SUBMISSION",
        "atoms": [atom_template(a) for a in packet["initial"]["atomic_claims"]],
        "dimensions": {
            k: {"fraction": None, "evidence_refs": [], "justification": ""}
            for k in WEIGHTS
        },
        "penalty_events": [],
        "blinding_concern": {"present": False, "explanation": ""},
    }


def implementation_hash():
    return sha(
        {
            "workflow": sha((ROOT / "workflow.py").read_bytes()),
            "cli": sha((ROOT.parents[1] / "scripts/semantic_review.py").read_bytes()),
        }
    )


def prepare(source, out, expected_hash, *, count=70):
    source, out = Path(source), Path(out)
    if out.exists():
        fail("fresh_output_directory_required")
    if (
        not re.fullmatch("[0-9a-f]{64}", expected_hash)
        or sha(source.read_bytes()) != expected_hash
    ):
        fail("packet_file_commitment_mismatch")
    raw = read(source)
    if not isinstance(raw, list) or len(raw) != count:
        fail("expected_packet_count_mismatch")
    packets = [project(p) for p in raw]
    if len({p["review_id"] for p in packets}) != count:
        fail("duplicate_blind_ids")
    rubric = (ROOT / "FROZEN_RUBRIC.md").read_bytes()
    if (
        hashlib.sha1(b"blob " + str(len(rubric)).encode() + b"\0" + rubric).hexdigest()
        != RUBRIC_BLOB
    ):
        fail("frozen_rubric_changed")
    bundle_id = sha(
        {
            "process": VERSION,
            "implementation_sha256": implementation_hash(),
            "source_sha256": expected_hash,
            "packets": [sha(p) for p in packets],
            "handbook_sha256": sha((ROOT / "REVIEWER_HANDBOOK.md").read_bytes()),
            "rubric_blob": RUBRIC_BLOB,
        }
    )
    out.mkdir(mode=0o700, parents=True)
    private = out / "owner"
    private.mkdir(mode=0o700)
    write(private / "packets.json", packets)
    seed = secrets.token_hex(32)
    manifest = {
        "version": VERSION,
        "implementation_sha256": implementation_hash(),
        "weights": WEIGHTS,
        "penalties": PENALTIES,
        "bundle_id": bundle_id,
        "source_packet_sha256": expected_hash,
        "count": count,
        "rubric_blob": RUBRIC_BLOB,
        "assignment_seed": seed,
        "packet_hashes": {p["review_id"]: sha(p) for p in packets},
        "projection_limit": "Owner must manually inspect for semantic or stylistic identity leakage. Schema scanning is not proof of blinding.",
    }
    for role in ("R-A", "R-B"):
        folder = out / role
        folder.mkdir(mode=0o700)
        ordered = list(packets)
        random.Random(sha(seed + role)).shuffle(ordered)
        write(folder / "packets.json", ordered)
        write(
            folder / "review-form.json",
            {
                "version": VERSION,
                "bundle_id": bundle_id,
                "reviewer_code": role,
                "attestation": {
                    "qualified_independent_human": False,
                    "no_key_or_variant_access": False,
                    "no_other_review_access": False,
                    "not_ai_generated": False,
                },
                "reviews": [row_template(p) for p in ordered],
            },
        )
        for name in ("REVIEWER_HANDBOOK.md", "RUBRIC_MAPPING.md", "FROZEN_RUBRIC.md"):
            (folder / name).write_bytes((ROOT / name).read_bytes())
        # Readable content, not a new investigator UI. JSON blocks avoid untrusted HTML execution.
        for n, p in enumerate(ordered, 1):
            text = f"# Blinded packet {p['review_id']}\n\nRead only this received evidence. Source submission is not authoritative.\n\n"
            body = json.dumps(p, indent=2)
            fence = "`" * max(
                3, max((len(x) for x in re.findall(r"`+", body)), default=0) + 1
            )
            text += fence + "json\n" + body + "\n" + fence + "\n"
            (folder / f"packet-{n:03d}.md").write_text(text)
    # Bind all distributed bytes; completed forms are returned as new files, never overwritten.
    manifest["distributed_sha256"] = {
        str(p.relative_to(out)): sha(p.read_bytes())
        for p in sorted(out.glob("R-*/*"))
        if p.is_file()
    }
    write(private / "manifest.json", manifest)
    return {
        "status": "review_bundles_prepared",
        "packets": count,
        "reviews_expected": count * 2,
        "bundle_id": bundle_id,
        "semantic_grades_created": False,
        "unblinding_map_read": False,
    }


def bundle(root):
    root = Path(root)
    m = read(root / "owner/manifest.json")
    packets = read(root / "owner/packets.json")
    if m["implementation_sha256"] != implementation_hash():
        fail("review_process_code_changed_use_fresh_versioned_bundle")
    if (
        m["version"] != VERSION
        or {p["review_id"]: sha(p) for p in packets} != m["packet_hashes"]
    ):
        fail("bundle_modified")
    for path, expected in m["distributed_sha256"].items():
        if sha((root / path).read_bytes()) != expected:
            fail("distributed_bundle_modified")
    return m, {p["review_id"]: p for p in packets}


def pointer(value, path):
    if path == "":
        return value
    if not path.startswith("/"):
        fail("invalid_evidence_pointer")
    try:
        for token in path[1:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if isinstance(value, list):
                if not re.fullmatch(r"0|[1-9][0-9]*", token):
                    fail("invalid_evidence_array_index")
                value = value[int(token)]
            else:
                value = value[token]
        return value
    except (KeyError, IndexError, ValueError, TypeError):
        fail("evidence_pointer_not_received")


def refs(packet, values):
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(v, str) for v in values)
    ):
        fail("evidence_refs_required")
    for value in values:
        if value.startswith("initial:"):
            pointer(packet["initial"], value[len("initial:") :])
        elif value.startswith("submission:"):
            pointer(packet["submission"], value[len("submission:") :])
        elif value.startswith("event:"):
            try:
                _, seq, path = value.split(":", 2)
                event = next(e for e in packet["events"] if e["sequence"] == int(seq))
            except (ValueError, StopIteration):
                fail("evidence_event_not_received")
            pointer(event, path)
        else:
            fail("invalid_evidence_reference")


def fraction(v):
    return v == "N/A" or type(v) in (int, float) and v in (0, 0.5, 1)


def validate_row(row, packet):
    if set(row) != set(row_template(packet)) or row["packet_sha256"] != sha(packet):
        fail("review_row_contract_or_packet_changed")
    expected = (
        "NO_FINAL_SUBMISSION" if packet["submission"] is None else "HAS_SUBMISSION"
    )
    if row["status"] != expected:
        fail("submission_status_changed")
    if not isinstance(row["atoms"], list) or [
        a.get("atom_id") for a in row["atoms"]
    ] != [a["id"] for a in packet["initial"]["atomic_claims"]]:
        fail("atomic_coverage_changed")
    final = [] if packet["submission"] is None else packet["submission"]["findings"]
    for a, atom in zip(row["atoms"], packet["initial"]["atomic_claims"]):
        if set(a) != set(atom_template(atom)):
            fail("atomic_review_contract")
        if a["interpretation_target"] not in TARGETS or a["confidence"] not in (
            "high",
            "medium",
            "low",
        ):
            fail("independent_interpretation_required")
        present = any(f.get("statement") == atom["statement"] for f in final)
        if a["preferred_verdict"] not in (LABELS if present else ("NO_SUBMISSION",)):
            fail("independent_atomic_verdict_required")
        if not fraction(a["scientific_validity"]) or not fraction(
            a["citation_entailment"]
        ):
            fail("atomic_rating_required")
        if not present and (
            a["scientific_validity"] != "N/A" or a["citation_entailment"] != "N/A"
        ):
            fail("no_submission_is_not_semantic_error_or_abstention")
        if set(a["flags"]) != set(FLAGS) or any(
            v not in ("none", "minor", "material", "N/A") for v in a["flags"].values()
        ):
            fail("diagnostic_flags_required")
        if not isinstance(a["rationale"], str) or not a["rationale"].strip():
            fail("atomic_rationale_required")
        refs(packet, a["evidence_refs"])
    if set(row["dimensions"]) != set(WEIGHTS):
        fail("frozen_dimension_set_changed")
    for value in row["dimensions"].values():
        if (
            set(value) != {"fraction", "evidence_refs", "justification"}
            or not fraction(value["fraction"])
            or not isinstance(value["justification"], str)
            or not value["justification"].strip()
        ):
            fail("dimension_grade_and_rationale_required")
        if expected == "NO_FINAL_SUBMISSION" and value["fraction"] != "N/A":
            fail("missing_final_semantics_are_unassessed")
        refs(packet, value["evidence_refs"])
    if not isinstance(row["penalty_events"], list):
        fail("penalty_events_required")
    seen = set()
    for e in row["penalty_events"]:
        if (
            set(e)
            != {"category", "error_id", "atom_ids", "evidence_refs", "description"}
            or e["category"] not in PENALTIES
            or not isinstance(e["error_id"], str)
            or not e["error_id"]
            or (e["category"], e["error_id"]) in seen
        ):
            fail("invalid_or_duplicate_penalty_event")
        if (
            not e["description"].strip()
            or not e["atom_ids"]
            or not set(e["atom_ids"]) <= {a["atom_id"] for a in row["atoms"]}
        ):
            fail("penalty_proposition_reference_required")
        refs(packet, e["evidence_refs"])
        seen.add((e["category"], e["error_id"]))
    if (
        set(row["blinding_concern"]) != {"present", "explanation"}
        or type(row["blinding_concern"]["present"]) is not bool
        or not isinstance(row["blinding_concern"]["explanation"], str)
    ):
        fail("blinding_attestation_required")
    if (
        row["blinding_concern"]["present"]
        and not row["blinding_concern"]["explanation"].strip()
    ):
        fail("blinding_explanation_required")


def validate_form(value, manifest, packets, role):
    if (
        set(value)
        != {"version", "bundle_id", "reviewer_code", "attestation", "reviews"}
        or value["version"] != VERSION
        or value["bundle_id"] != manifest["bundle_id"]
        or value["reviewer_code"] != role
    ):
        fail("review_identity_or_bundle_mismatch")
    if set(value["attestation"]) != {
        "qualified_independent_human",
        "no_key_or_variant_access",
        "no_other_review_access",
        "not_ai_generated",
    } or any(v is not True for v in value["attestation"].values()):
        fail("independent_human_attestation_required")
    rows = value["reviews"]
    if (
        len(rows) != len(packets)
        or len({r["review_id"] for r in rows}) != len(rows)
        or {r["review_id"] for r in rows} != set(packets)
    ):
        fail("complete_unique_review_coverage_required")
    for row in rows:
        validate_row(row, packets[row["review_id"]])
    return {r["review_id"]: r for r in rows}


def agreement(a, b, *, ordinal=False):
    if len(a) != len(b):
        fail("agreement_pair_count_mismatch")
    usable = [
        (x, y)
        for x, y in zip(a, b)
        if x != "N/A" and y != "N/A" and x != "NO_SUBMISSION" and y != "NO_SUBMISSION"
    ]
    n = len(usable)
    if not n:
        return {
            "n": 0,
            "excluded": len(a),
            "exact_agreement": None,
            "kappa": None,
            "reason": "no_jointly_assessable_pairs",
        }
    ca = Counter(x for x, _ in usable)
    cb = Counter(y for _, y in usable)
    labels = sorted(set(ca) | set(cb), key=str)
    distance = (
        (lambda x, y: abs(float(x) - float(y)))
        if ordinal
        else (lambda x, y: float(x != y))
    )
    observed = sum(distance(x, y) for x, y in usable) / n
    expected = sum(ca[x] * cb[y] * distance(x, y) for x in labels for y in labels) / (
        n * n
    )
    return {
        "n": n,
        "excluded": len(a) - n,
        "exact_agreement": sum(x == y for x, y in usable) / n,
        "kappa": 1 - observed / expected if expected else None,
        "reason": None if expected else "degenerate_marginals",
        "weighting": "linear 0/0.5/1 distance" if ordinal else "nominal",
        "marginals_a": dict(ca),
        "marginals_b": dict(cb),
    }


def grade_fields(row):
    result = {}
    for i, a in enumerate(row["atoms"]):
        for k in (
            "preferred_verdict",
            "scientific_validity",
            "citation_entailment",
            "interpretation_target",
            "flags",
        ):
            result[f"/atoms/{i}/{k}"] = a[k]
    for k, v in row["dimensions"].items():
        result[f"/dimensions/{k}/fraction"] = v["fraction"]
    result["/penalty_events"] = row["penalty_events"]
    return result


def differences(a, b):
    result = []
    for rid in sorted(a):
        left, right = grade_fields(a[rid]), grade_fields(b[rid])
        for path, x in left.items():
            y = right[path]
            # Wording differences in penalty descriptions also receive adjudication,
            # rather than assuming two independently described errors are identical.
            if x != y:
                result.append({"review_id": rid, "field": path, "a": x, "b": y})
    return result


def compare(root, a_path, b_path, out):
    m, packets = bundle(root)
    a = read(a_path)
    b = read(b_path)
    ar = validate_form(a, m, packets, "R-A")
    br = validate_form(b, m, packets, "R-B")
    out = Path(out)
    if out.exists():
        fail("fresh_output_directory_required")
    out.mkdir(mode=0o700, parents=True)
    ds = differences(ar, br)
    atomic = {}
    for field in ("preferred_verdict", "scientific_validity", "citation_entailment"):
        x = [v[field] for rid in sorted(ar) for v in ar[rid]["atoms"]]
        y = [v[field] for rid in sorted(br) for v in br[rid]["atoms"]]
        atomic[field] = agreement(x, y, ordinal=field != "preferred_verdict")
    dimensions = {
        k: agreement(
            [ar[r]["dimensions"][k]["fraction"] for r in sorted(ar)],
            [br[r]["dimensions"][k]["fraction"] for r in sorted(br)],
            ordinal=True,
        )
        for k in WEIGHTS
    }
    report = {
        "version": VERSION,
        "bundle_id": m["bundle_id"],
        "review_a_sha256": sha(Path(a_path).read_bytes()),
        "review_b_sha256": sha(Path(b_path).read_bytes()),
        "packets": len(packets),
        "disagreement_fields": len(ds),
        "disagreement_packets": len({d["review_id"] for d in ds}),
        "atomic_agreement": atomic,
        "dimension_agreement": dimensions,
        "reviewer_credentials": "attested, not software-verified",
        "limitations": [
            "Descriptive agreement only; correlated cases/repeats, no independent-sample confidence intervals or population reliability claim.",
            "Semantic verdicts are independent human judgments, not replacements for the frozen reference key.",
            "No unblinding map or mechanical scorer results are read.",
        ],
    }
    write(out / "agreement.json", report)
    write(out / "disagreements.json", ds)
    write(
        out / "adjudication.template.json",
        {
            "version": VERSION,
            "bundle_id": m["bundle_id"],
            "review_a_sha256": report["review_a_sha256"],
            "review_b_sha256": report["review_b_sha256"],
            "adjudicator_code": "R-C",
            "attestation": {
                "qualified_independent_human": False,
                "remained_variant_and_key_blind": False,
                "not_ai_generated": False,
            },
            "resolutions": [
                {
                    "review_id": d["review_id"],
                    "field": d["field"],
                    "value": None,
                    "evidence_refs": [],
                    "rationale": "",
                }
                for d in ds
            ],
        },
    )
    return report


def finalize(root, a_path, b_path, adjudication_path, out):
    m, packets = bundle(root)
    a_raw = Path(a_path).read_bytes()
    b_raw = Path(b_path).read_bytes()
    a = validate_form(read(a_path), m, packets, "R-A")
    b = validate_form(read(b_path), m, packets, "R-B")
    ad = read(adjudication_path)
    expected_keys = {
        "version",
        "bundle_id",
        "review_a_sha256",
        "review_b_sha256",
        "adjudicator_code",
        "attestation",
        "resolutions",
    }
    if (
        set(ad) != expected_keys
        or ad["version"] != VERSION
        or ad["bundle_id"] != m["bundle_id"]
        or ad["review_a_sha256"] != sha(a_raw)
        or ad["review_b_sha256"] != sha(b_raw)
        or ad["adjudicator_code"] != "R-C"
    ):
        fail("adjudication_identity_or_sealed_review_changed")
    if set(ad["attestation"]) != {
        "qualified_independent_human",
        "remained_variant_and_key_blind",
        "not_ai_generated",
    } or any(v is not True for v in ad["attestation"].values()):
        fail("human_blinded_adjudication_required")
    ds = differences(a, b)
    expected = {(d["review_id"], d["field"]) for d in ds}
    rs = ad["resolutions"]
    if (
        len(rs) != len(expected)
        or {(r["review_id"], r["field"]) for r in rs} != expected
    ):
        fail("complete_unique_adjudication_required")
    merged = copy.deepcopy(a)
    for r in rs:
        if (
            set(r) != {"review_id", "field", "value", "evidence_refs", "rationale"}
            or not r["rationale"].strip()
        ):
            fail("adjudication_rationale_required")
        refs(packets[r["review_id"]], r["evidence_refs"])
        tokens = r["field"][1:].split("/")
        node = merged[r["review_id"]]
        for token in tokens[:-1]:
            node = node[int(token)] if isinstance(node, list) else node[token]
        node[tokens[-1]] = r["value"]
    for rid, row in merged.items():
        validate_row(row, packets[rid])
    out = Path(out)
    if out.exists():
        fail("fresh_output_directory_required")
    out.mkdir(mode=0o700, parents=True)
    totals = []
    export = {}
    counts = Counter()
    for rid, row in sorted(merged.items()):
        dims = {k: v["fraction"] for k, v in row["dimensions"].items()}
        known = sum(WEIGHTS[k] * v for k, v in dims.items() if v != "N/A")
        complete = all(v != "N/A" for v in dims.values())
        deduction = sum(PENALTIES[e["category"]] for e in row["penalty_events"])
        totals.append(
            {
                "review_id": rid,
                "status": row["status"],
                "semantic_points_of_51_before_penalties": known if complete else None,
                "known_semantic_points_not_rescaled": known,
                "unassessed_dimensions": [k for k, v in dims.items() if v == "N/A"],
                "frozen_penalty_deduction_for_later_combination": deduction,
                "combined_frozen_score_of_100": None,
            }
        )
        export[rid] = {"fractions": dims, "penalty_events": row["penalty_events"]}
        for atom in row["atoms"]:
            counts[atom["preferred_verdict"]] += 1
    report = {
        "version": VERSION,
        "bundle_id": m["bundle_id"],
        "packets": len(packets),
        "completed_reviews_with_human_independence_attestation": 2 * len(packets),
        "adjudicated_fields": len(rs),
        "independent_verdict_counts": dict(counts),
        "packet_semantic_scores": totals,
        "semantic_maximum": 51,
        "mechanical_points_of_29": None,
        "frozen_reference_atomic_points_of_20": None,
        "combined_total": None,
        "unblinded": False,
        "ready_for_owner_post_review_join": True,
        "blinding_concerns_requiring_owner_disclosure": sum(
            row["blinding_concern"]["present"]
            for form in (a, b)
            for row in form.values()
        ),
        "limitations": [
            "A process seal is not physical certification or proof of reviewer credentials.",
            "Do not pool primary, secondary or repeat cohorts after joining; preserve completion-aware and matched-case analyses.",
            "Missing assessments are unassessed semantic outputs, not scientific abstentions; frozen missing-submission penalties remain in the existing scorer.",
            "Do not subtract penalties from the 51-point subtotal or change frozen weights. Join with existing scorer only after seal.",
        ],
    }
    for name, raw in [
        ("independent-a.json", a_raw),
        ("independent-b.json", b_raw),
        ("adjudication.json", Path(adjudication_path).read_bytes()),
    ]:
        with (out / name).open("xb") as stream:
            stream.write(raw)
    write(
        out / "adjudicated-reviews.json",
        {
            "narrative_notice": "Resolved grade fields retain R-A narrative for provenance only. Authoritative disagreement rationales/evidence are in adjudication.json; both original forms are preserved.",
            "reviews": list(merged.values()),
        },
    )
    write(out / "review-fractions.json", export)
    write(out / "semantic-report.json", report)
    seal = {
        "version": VERSION,
        "implementation_sha256": m["implementation_sha256"],
        "bundle_id": m["bundle_id"],
        "review_a_sha256": sha(a_raw),
        "review_b_sha256": sha(b_raw),
        "adjudication_sha256": sha(Path(adjudication_path).read_bytes()),
        "packet_source_sha256": m["source_packet_sha256"],
        "files": {
            p.name: sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()
        },
        "unblinding_map_read": False,
        "all_reviews_and_disagreements_complete": True,
    }
    write(out / "seal.json", seal)
    return {
        "status": "blinded_reviews_sealed",
        "packets": len(packets),
        "adjudicated_fields": len(rs),
        "unblinded": False,
        "semantic_truth_certified": False,
    }
