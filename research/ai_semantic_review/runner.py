"""One-shot reviewer workers, aggregate reservation ledger and staged adjudication.

Only provider text/usage and response commitments are retained, not hidden reasoning.
No SDK retries, tools, browsing, peer-review inputs before freezing, or human grades.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import sqlite3
import time
from pathlib import Path

from .contract import (
    CHECKS,
    LABEL,
    PROMPTS,
    ROLES,
    SCHEMA,
    agreement,
    canonical,
    disagreements,
    fail,
    read,
    sha,
    validate_review,
    write,
)
from .protocol import cost, load

ENDPOINTS = {
    "openai": ("https://api.openai.com/v1/responses", "OPENAI_API_KEY"),
    "anthropic": ("https://api.anthropic.com/v1/messages", "ANTHROPIC_API_KEY"),
}


def db(root):
    con = sqlite3.connect(Path(root) / "ai-cost-ledger.sqlite", timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA synchronous=FULL")
    return con


def initialize(root):
    with db(root) as con:
        con.execute(
            "CREATE TABLE calls (role TEXT, rid TEXT, state TEXT, reservation INTEGER, charged INTEGER, payload_sha TEXT, output_sha TEXT, PRIMARY KEY(role,rid))"
        )
        con.execute(
            "CREATE TABLE control (id INTEGER PRIMARY KEY CHECK(id=1), blocked INTEGER NOT NULL)"
        )
        con.execute("INSERT INTO control VALUES(1,0)")


@contextlib.contextmanager
def locked(root):
    with (Path(root) / "ai-run.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail("ai_run_already_active")
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def call_rows(root):
    with db(root) as con:
        return [dict(r) for r in con.execute("SELECT * FROM calls ORDER BY role,rid")]


def request_payload(config, role, packet, context=None):
    data = {"packet": packet}
    if role == "adjudicator":
        if context is None:
            fail("ai_adjudication_requires_frozen_reviews")
        data["frozen_reviews_and_disagreements"] = context
    elif context is not None:
        fail("ai_reviewer_must_not_receive_peer_context")
    prompt = PROMPTS[role]
    text = canonical(data)
    if config["provider"] == "openai":
        payload = {
            "model": config["model"],
            "instructions": prompt,
            "input": [{"role": "user", "content": text}],
            "store": False,
            "service_tier": "default",
            "max_output_tokens": config["max_output_tokens"],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "ai_semantic_review_v1",
                    "strict": True,
                    "schema": SCHEMA,
                }
            },
        }
        if config["reasoning_effort"] is not None:
            payload["reasoning"] = {"effort": config["reasoning_effort"]}
    else:
        payload = {
            "model": config["model"],
            "system": prompt,
            "messages": [{"role": "user", "content": text}],
            "max_tokens": config["max_output_tokens"],
            "service_tier": "standard_only",
            "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}},
        }
    if config["temperature"] is not None:
        payload["temperature"] = config["temperature"]
    return payload


def http_call(config, payload):
    import httpx

    endpoint, env = ENDPOINTS[config["provider"]]
    key = os.environ.get(env, "").strip()
    if not key or not key.isascii() or any(c.isspace() for c in key):
        fail("ai_provider_credential_missing_or_malformed")
    headers = (
        {"Authorization": "Bearer " + key}
        if config["provider"] == "openai"
        else {"x-api-key": key, "anthropic-version": "2023-06-01"}
    )
    with httpx.Client(timeout=90, follow_redirects=False, trust_env=False) as client:  # noqa: SIM117
        with client.stream("POST", endpoint, json=payload, headers=headers) as response:
            # Never echo provider error bodies or headers, including on redirects.
            if response.status_code != 200:
                fail("ai_provider_http_failure")
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 2_000_000:
                    fail("ai_provider_response_too_large")
            return bytes(body)


def extract_response(config, raw):
    from research.semantic_review.workflow import parse

    data = parse(raw)
    usage = data.get("usage")
    if not isinstance(usage, dict):
        fail("ai_provider_usage_missing")
    if config["provider"] == "openai":
        inputs = usage.get("input_tokens")
        outputs = usage.get("output_tokens")
        complete = data.get("status") == "completed" and data.get("error") is None
        texts = [
            c["text"]
            for m in data.get("output", [])
            if m.get("type") == "message"
            for c in m.get("content", [])
            if c.get("type") == "output_text"
        ]
    else:
        values = [
            usage.get("input_tokens"),
            usage.get("cache_creation_input_tokens", 0),
            usage.get("cache_read_input_tokens", 0),
        ]
        if any(type(v) is not int or v < 0 for v in values):
            fail("ai_provider_usage_invalid")
        inputs = sum(values)
        outputs = usage.get("output_tokens")
        complete = data.get("stop_reason") == "end_turn"
        texts = [c["text"] for c in data.get("content", []) if c.get("type") == "text"]
    if type(inputs) is not int or type(outputs) is not int or min(inputs, outputs) < 0:
        fail("ai_provider_usage_invalid")
    return {
        "input_tokens": inputs,
        "output_tokens": outputs,
        "provider_usage": usage,
        "complete": complete,
        "text": "\n".join(texts),
        "response_sha256": sha(raw),
        "provider_response_id_sha256": sha(str(data.get("id", "")).encode()),
        "returned_model": data.get("model"),
    }


def reserve(root, p, role, rid, payload, config):
    input_ceiling = len(canonical(payload).encode()) + 4096
    reservation = cost(config, input_ceiling, config["max_output_tokens"])
    with db(root) as con:
        con.execute("BEGIN IMMEDIATE")
        if con.execute("SELECT blocked FROM control").fetchone()[0]:
            fail("ai_accounting_anomaly_blocks_requests")
        if con.execute(
            "SELECT 1 FROM calls WHERE role=? AND rid=?", (role, rid)
        ).fetchone():
            return None
        used, n = con.execute(
            "SELECT COALESCE(SUM(charged),0),COUNT(*) FROM calls"
        ).fetchone()
        if n >= p["max_requests"] or used + reservation > p["max_cost_nano_usd"]:
            fail("ai_spending_cap")
        con.execute(
            "INSERT INTO calls VALUES(?,?,?,?,?,?,?)",
            (role, rid, "reserved", reservation, reservation, sha(payload), None),
        )
    return input_ceiling, reservation


def record_path(root, role, rid):
    return Path(root) / role / (rid + ".ai.json")


def result_for(root, p, role, rid, rows=None):
    row = next(
        (
            r
            for r in (rows if rows is not None else call_rows(root))
            if r["role"] == role and r["rid"] == rid
        ),
        None,
    )
    if row is None:
        return None
    path = record_path(root, role, rid)
    if row["state"] == "reserved":
        return {"status": "interrupted_or_usage_unknown", "review": None}
    if not path.is_file() or sha(path.read_bytes()) != row["output_sha"]:
        fail("ai_record_commitment_mismatch")
    record = read(path)
    if (
        record["label"] != LABEL
        or record["protocol_id"] != p["protocol_id"]
        or record["role"] != role
        or record["review_id"] != rid
    ):
        fail("ai_record_identity_changed")
    return record


def frozen_context(root, p, packets):
    freeze = read(Path(root) / "independent-ai-reviews.frozen.json")
    if (
        freeze.get("protocol_id") != p["protocol_id"]
        or freeze.get("label") != LABEL
        or freeze.get("seal_sha256")
        != sha({k: v for k, v in freeze.items() if k != "seal_sha256"})
    ):
        fail("ai_review_freeze_changed")
    rows = call_rows(root)
    current = {
        role: {
            rid: next(r for r in rows if r["role"] == role and r["rid"] == rid)
            for rid in packets
        }
        for role in ("reviewer_a", "reviewer_b")
    }
    if current != freeze["ledger_rows"]:
        fail("ai_independent_reviews_changed_after_freeze")
    contexts = {}
    for rid in packets:
        a = result_for(root, p, "reviewer_a", rid, rows)
        b = result_for(root, p, "reviewer_b", rid, rows)
        if a and b and a["status"] == "valid" and b["status"] == "valid":
            validate_review(a["review"], packets[rid])
            validate_review(b["review"], packets[rid])
            ds = disagreements(a["review"], b["review"])
            if ds:
                contexts[rid] = {
                    "review_A": a["review"],
                    "review_B": b["review"],
                    "disagreements": ds,
                }
    if {rid: sha(ctx) for rid, ctx in contexts.items()} != freeze[
        "disagreement_contexts"
    ]:
        fail("ai_frozen_disagreements_changed")
    return contexts


def run(root, role, *, authorize=False, limit=None, transport=None, on_result=None):
    if role not in ROLES:
        fail("ai_unknown_role")
    if not authorize:
        fail("explicit_paid_external_ai_authorization_required")
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 70):
        fail("ai_call_limit_invalid")
    with locked(root):
        p, packets = load(root)
        if (
            role != "adjudicator"
            and (Path(root) / "independent-ai-reviews.frozen.json").exists()
        ):
            fail("ai_reviews_already_frozen")
        config = p["config"][role]
        if transport is None and p["config"]["execution_mode"] != "live_external":
            fail("ai_offline_protocol_cannot_make_paid_calls")
        if transport is None:
            key = os.environ.get(ENDPOINTS[config["provider"]][1], "").strip()
            if not key or not key.isascii() or any(c.isspace() for c in key):
                fail("ai_provider_credential_missing_or_malformed")
        contexts = frozen_context(root, p, packets) if role == "adjudicator" else None
        targets = sorted(contexts if contexts is not None else packets)
        made = 0
        stopped = None
        for rid in targets:
            if limit is not None and made >= limit:
                break
            payload = request_payload(
                config,
                role,
                packets[rid],
                contexts[rid] if contexts is not None else None,
            )
            try:
                reservation = reserve(root, p, role, rid, payload, config)
            except ValueError as e:
                if str(e) == "ai_spending_cap":
                    stopped = "ai_spending_cap"
                    break
                raise
            if reservation is None:
                continue
            made += 1
            start = time.monotonic()
            usage = None
            text = ""
            review = None
            reason = None
            raw_commitment = None
            status = "failed"
            charged = reservation[1]
            state = "usage_unknown"
            blocked = False
            try:
                raw = (transport or http_call)(config, payload)
                raw_commitment = sha(raw)
                usage = extract_response(config, raw)
                charged = cost(config, usage["input_tokens"], usage["output_tokens"])
                text = usage["text"]
                if (
                    usage["input_tokens"] > reservation[0]
                    or usage["output_tokens"] > config["max_output_tokens"]
                ):
                    fail("ai_usage_exceeds_reservation")
                charged = cost(config, usage["input_tokens"], usage["output_tokens"])
                state = "settled"
                if not usage["complete"]:
                    fail("ai_model_incomplete")
                from research.semantic_review.workflow import parse

                review = validate_review(parse(text.encode()), packets[rid])
                status = "valid"
            except Exception as e:  # noqa: BLE001 — quarantine provider failures; never retry or echo bodies
                # Hold the full reservation on ambiguous failures. No automatic repair/retry.
                reason = (
                    str(e)
                    if isinstance(e, ValueError) and str(e).startswith("ai_")
                    else "ai_response_or_transport_failed"
                )
                review = None
                if reason == "ai_usage_exceeds_reservation":
                    blocked = True
                    state = "accounting_anomaly"
                    charged = max(charged, reservation[1])
            record = {
                "label": LABEL,
                "version": p["version"],
                "protocol_id": p["protocol_id"],
                "role": role,
                "review_id": rid,
                "status": status,
                "reason": reason,
                "model_identity": {
                    "provider": config["provider"],
                    "requested_model": config["model"],
                },
                "prompt_sha256": p["prompt_sha256"][role],
                "parameters": {
                    k: config[k]
                    for k in ("max_output_tokens", "temperature", "reasoning_effort")
                },
                "ai_execution_attestation": {
                    "label": LABEL,
                    "scope": "HARNESS_INPUT_ISOLATION_ONLY",
                    "fresh_single_packet_context": True,
                    "peer_review_access": role == "adjudicator",
                    "reference_answers_access": False,
                    "not_human_validation": True,
                },
                "payload_sha256": sha(payload),
                "response_sha256": raw_commitment,
                "output_text": text,
                "review": review,
                "usage": usage,
                "elapsed_seconds": time.monotonic() - start,
                "reserved_nano_usd": reservation[1],
                "charged_or_held_nano_usd": charged,
                "accounting_state": state,
            }
            path = record_path(root, role, rid)
            write(path, record)
            with db(root) as con:
                con.execute(
                    "UPDATE calls SET state=?,charged=?,output_sha=? WHERE role=? AND rid=?",
                    (state, charged, sha(path.read_bytes()), role, rid),
                )
                if blocked:
                    con.execute("UPDATE control SET blocked=1")
            if on_result is not None:
                on_result(
                    {
                        "label": LABEL,
                        "role": role,
                        "new_request": made,
                        "status": status,
                        "reason": reason,
                        "charged_or_held_usd": charged / 1e9,
                    }
                )
            if status != "valid":
                stopped = reason
                break
        return {
            "label": LABEL,
            "role": role,
            "new_requests": made,
            "stopped_reason": stopped,
            "human_semantic_fields": "UNGRADED",
        }


def freeze_reviews(root):
    with locked(root):
        p, packets = load(root)
        rows = call_rows(root)
        selected = {
            role: {r["rid"]: r for r in rows if r["role"] == role}
            for role in ("reviewer_a", "reviewer_b")
        }
        if any(set(selected[role]) != set(packets) for role in selected):
            fail("ai_both_full_independent_attempts_required")
        contexts = {}
        for rid in packets:
            a = result_for(root, p, "reviewer_a", rid, rows)
            b = result_for(root, p, "reviewer_b", rid, rows)
            if a and b and a["status"] == "valid" and b["status"] == "valid":
                validate_review(a["review"], packets[rid])
                validate_review(b["review"], packets[rid])
                ds = disagreements(a["review"], b["review"])
                if ds:
                    contexts[rid] = sha(
                        {
                            "review_A": a["review"],
                            "review_B": b["review"],
                            "disagreements": ds,
                        }
                    )
        seal = {
            "label": LABEL,
            "protocol_id": p["protocol_id"],
            "ledger_rows": selected,
            "disagreement_contexts": contexts,
            "limitations": "All attempts frozen, including failures; no completion or scientific validity is implied. Same-grade prose disagreements are not exhaustively detected.",
        }
        seal["seal_sha256"] = sha(seal)
        write(Path(root) / "independent-ai-reviews.frozen.json", seal)
        return {
            "label": LABEL,
            "status": "independent_ai_attempts_frozen",
            "disagreement_packets": len(contexts),
        }


def report(root, out):
    with locked(root):
        p, packets = load(root)
        rows = call_rows(root)
        roles = {}
        valid = {}
        for role in ROLES:
            rr = [r for r in rows if r["role"] == role]
            records = {rid: result_for(root, p, role, rid, rows) for rid in packets}
            valid[role] = {
                rid: r["review"]
                for rid, r in records.items()
                if r and r["status"] == "valid"
            }
            for rid, r in valid[role].items():
                validate_review(r, packets[rid])
            roles[role] = {
                "label": LABEL,
                "attempted": len(rr),
                "valid": len(valid[role]),
                "invalid_or_interrupted": len(rr) - len(valid[role]),
                "charged_or_held_usd": sum(r["charged"] for r in rr) / 1e9,
                "usage_unknown_or_reserved": sum(r["state"] != "settled" for r in rr),
                "known_input_tokens": sum(
                    r["usage"]["input_tokens"]
                    for r in records.values()
                    if r and r.get("usage")
                ),
                "known_output_tokens": sum(
                    r["usage"]["output_tokens"]
                    for r in records.values()
                    if r and r.get("usage")
                ),
                "latency_seconds": sum(
                    r.get("elapsed_seconds", 0) for r in records.values() if r
                ),
                "mechanically_validated_numeric_values": sum(
                    len(a["numeric_claims"])
                    for rev in valid[role].values()
                    for a in rev["atoms"]
                ),
            }
        if (Path(root) / "independent-ai-reviews.frozen.json").exists():
            frozen_context(root, p, packets)
        common = sorted(set(valid["reviewer_a"]) & set(valid["reviewer_b"]))
        differences = {
            rid: disagreements(valid["reviewer_a"][rid], valid["reviewer_b"][rid])
            for rid in common
        }
        a = [
            atom["recommended_verdict"]
            for rid in common
            for atom in valid["reviewer_a"][rid]["atoms"]
        ]
        b = [
            atom["recommended_verdict"]
            for rid in common
            for atom in valid["reviewer_b"][rid]["atoms"]
        ]
        entailment = []
        for role, reviews in valid.items():
            for rid, review in reviews.items():
                for atom in review["atoms"]:
                    entailment.append(
                        {
                            "label": LABEL,
                            "role": role,
                            "review_id": rid,
                            "atom_id": atom["atom_id"],
                            "verdict": atom["recommended_verdict"],
                            "proposition": next(
                                a
                                for a in packets[rid]["initial"]["atomic_claims"]
                                if a["id"] == atom["atom_id"]
                            ),
                            "submitted_verdict_validity": atom[
                                "submitted_verdict_validity"
                            ],
                            "citation_checks": atom["citation_checks"],
                            "checks": atom["checks"],
                            "justification": atom["justification"],
                            "uncertainty": atom["uncertainty"],
                        }
                    )
        check_agreement = {}
        for check in CHECKS:
            left = [
                atom["checks"][check]["judgment"]
                for rid in common
                for atom in valid["reviewer_a"][rid]["atoms"]
            ]
            right = [
                atom["checks"][check]["judgment"]
                for rid in common
                for atom in valid["reviewer_b"][rid]["atoms"]
            ]
            check_agreement[check] = agreement(
                ["N/A" if x == "NOT_APPLICABLE" else x for x in left],
                ["N/A" if x == "NOT_APPLICABLE" else x for x in right],
            )
        citation_a = []
        citation_b = []
        for rid in common:
            for left, right in zip(
                valid["reviewer_a"][rid]["atoms"], valid["reviewer_b"][rid]["atoms"]
            ):
                mapping = {
                    x["cited_id"]: x["entailment"] for x in right["citation_checks"]
                }
                for x in left["citation_checks"]:
                    citation_a.append(x["entailment"])
                    citation_b.append(mapping[x["cited_id"]])
        result = {
            "label": LABEL,
            "protocol_id": p["protocol_id"],
            "packets": 70,
            "check_agreement": check_agreement,
            "citation_entailment_agreement": agreement(citation_a, citation_b),
            "ai_flagged_potential_entailment_gaps_despite_received_ids": {
                role: sum(
                    any(
                        x["received"]
                        and x["entailment"] in ("PARTIAL", "DOES_NOT_ENTAIL")
                        for x in atom["citation_checks"]
                    )
                    for review in reviews.values()
                    for atom in review["atoms"]
                )
                for role, reviews in valid.items()
            },
            "roles": roles,
            "jointly_valid_packets": len(common),
            "verdict_agreement": agreement(
                ["NO_SUBMISSION" if x == "NO_FINAL_SUBMISSION" else x for x in a],
                ["NO_SUBMISSION" if x == "NO_FINAL_SUBMISSION" else x for x in b],
            ),
            "disagreements": differences,
            "detailed_entailment": entailment,
            "models_and_parameters": p["config"],
            "max_cost_usd": p["max_cost_nano_usd"] / 1e9,
            "charged_or_held_usd": sum(r["charged"] for r in rows) / 1e9,
            "human_semantic_fields": "UNGRADED",
            "qualified_human_validation": False,
            "limitations": [
                "AI agreement is not scientific truth or qualified human validation.",
                "Literal pointer/numeric checks are mechanical; entailment and physics remain AI judgments.",
                "No comparison to hidden reference answers or mechanical scores; no efficacy result without separate independent validation.",
                "Failures and unattempted packets remain visible; no automatic retries or favorable substitution.",
                "Shared training and recognizable source style can correlate reviewers.",
                "Disagreement routing compares declared labels, not every semantic difference in equal-grade prose.",
                p["pricing_limitation"],
            ],
        }
        write(out, result)
        return {
            k: v
            for k, v in result.items()
            if k
            not in ("detailed_entailment", "disagreements", "models_and_parameters")
        }
