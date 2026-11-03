"""SOFTWARE FIXTURES ONLY: no real AI/human semantic grades, no paid requests."""

import copy
import json

import pytest

from research.ai_semantic_review import contract as c
from research.ai_semantic_review import protocol as p
from research.ai_semantic_review import runner as r
from research.semantic_review.workflow import row_template


def config():
    def model(provider, name):
        return {
            "provider": provider,
            "model": name,
            "max_output_tokens": 512,
            "temperature": None,
            "reasoning_effort": None,
            "input_ceiling_usd_per_million": "0.1",
            "output_ceiling_usd_per_million": "0.2",
            "rate_source": "https://openai.com/api/pricing/"
            if provider == "openai"
            else "https://platform.claude.com/docs/en/about-claude/pricing",
            "rate_checked_at": "2026-11-02",
        }

    return {
        "reviewer_a": model("openai", "gpt-software-fixture"),
        "reviewer_b": model("anthropic", "claude-software-fixture"),
        "adjudicator": model("openai", "gpt-judge-fixture"),
        "same_family_reason": "",
        "execution_mode": "live_external",
        "pricing_confirmation": "OWNER_VERIFIED_PRICE_CEILINGS",
    }


@pytest.fixture
def prepared(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    packets = []
    for i in range(70):
        atom = {
            "id": "fixture-a",
            "scope": "measured_observation",
            "statement": "SOFTWARE FIXTURE NOT A BENCHMARK ANSWER",
        }
        final = (
            {
                "verdict": "SUPPORTED",
                "findings": [
                    {
                        "statement": atom["statement"],
                        "verdict": "SUPPORTED",
                        "citations": ["model:M1"],
                    }
                ],
                "numeric_observations": [],
            }
            if i != 69
            else None
        )
        packets.append(
            {
                "review_id": format(i, "024x"),
                "initial": {
                    "atomic_claims": [atom],
                    "model": {
                        "id": "model:M1",
                        "assumptions": ["SOFTWARE FIXTURE ONLY"],
                    },
                    "initial_measurements": {
                        "P": {
                            "id": "measurement:P",
                            "samples": [{"t_s": 0, "value": 2.5}],
                        }
                    },
                    "sensor_catalog": {"unobserved": {"id": "measurement:UNSEEN"}},
                },
                "events": [
                    {
                        "sequence": 1,
                        "tool": "read_document",
                        "arguments": {"id": "doc:fixture"},
                        "result": {
                            "id": "doc:fixture",
                            "summary": "SOFTWARE FIXTURE ONLY",
                        },
                    }
                ],
                "submission": final,
                "projection_notice": "SOFTWARE FIXTURE ONLY",
            }
        )
    c.write(source / "packets.json", packets)
    form = {
        "version": "sprint-c-human-semantic-review-v2",
        "bundle_id": "fixture-only",
        "reviewer_code": "R-A",
        "attestation": {
            "qualified_independent_human": False,
            "no_key_or_variant_access": False,
            "no_other_review_access": False,
            "not_ai_generated": False,
        },
        "reviews": [row_template(x) for x in packets],
    }
    c.write(source / "review-form.json", form)
    cf = tmp_path / "config.json"
    c.write(cf, config())
    out = tmp_path / "ai"
    digest = c.sha((source / "packets.json").read_bytes())
    p.prepare(source, digest, cf, out)
    return source, out, cf, packets


def review(packet, verdict="SUPPORTED"):
    missing = packet["submission"] is None
    ref = "initial:/model/assumptions/0"
    return {
        "label": c.LABEL,
        "review_id": packet["review_id"],
        "summary": "SOFTWARE FIXTURE ONLY, not actual model review.",
        "atoms": [
            {
                "label": c.LABEL,
                "atom_id": a["id"],
                "interpretation": "SOFTWARE FIXTURE scope",
                "recommended_verdict": "NO_FINAL_SUBMISSION" if missing else verdict,
                "submitted_verdict_validity": "UNASSESSED" if missing else "VALID",
                "justification": "SOFTWARE FIXTURE ONLY",
                "evidence_refs": [ref],
                "citation_checks": []
                if missing
                else [
                    {
                        "cited_id": "model:M1",
                        "received": True,
                        "entailment": "ENTAILS",
                        "evidence_refs": [ref],
                        "explanation": "SOFTWARE FIXTURE ONLY",
                    }
                ],
                "checks": {
                    k: {
                        "judgment": "UNASSESSABLE" if missing else "NOT_APPLICABLE",
                        "evidence_refs": [ref],
                        "explanation": "SOFTWARE FIXTURE ONLY",
                    }
                    for k in c.CHECKS
                },
                "numeric_claims": [
                    {
                        "reference": "initial:/initial_measurements/P/samples/0/value",
                        "value": 2.5,
                    }
                ],
                "uncertainty": "SOFTWARE FIXTURE ONLY",
            }
            for a in packet["initial"]["atomic_claims"]
        ],
    }


def transport(verdict="SUPPORTED", calls=None, usage=None):
    def send(cfg, payload):
        if calls is not None:
            calls.append(copy.deepcopy(payload))
        text = (
            payload["input"][0]["content"]
            if cfg["provider"] == "openai"
            else payload["messages"][0]["content"]
        )
        packet = json.loads(text)["packet"]
        answer = review(packet, verdict)
        if cfg["provider"] == "openai":
            body = {
                "model": cfg["model"] + "-resolved",
                "id": "fixture",
                "status": "completed",
                "error": None,
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": c.canonical(answer)}
                        ],
                    }
                ],
                "usage": usage or {"input_tokens": 100, "output_tokens": 50},
            }
        else:
            body = {
                "model": cfg["model"] + "-resolved",
                "id": "fixture",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": c.canonical(answer)}],
                "usage": usage or {"input_tokens": 100, "output_tokens": 50},
            }
        return c.canonical(body).encode()

    return send


def run_both(out):
    r.run(out, "reviewer_a", authorize=True, transport=transport())
    r.run(out, "reviewer_b", authorize=True, transport=transport("NOT_ESTABLISHED"))


def test_intake_preserves_original_bytes_and_blank_human_fields(prepared):
    source, out, _, packets = prepared
    assert (source / "packets.json").read_bytes() == (out / "packets.json").read_bytes()
    assert (source / "review-form.json").read_bytes() == (
        out / "source-human-form.UNMODIFIED.json"
    ).read_bytes()
    protocol, frozen = p.load(out)
    assert len(frozen) == 70
    assert protocol["human_semantic_fields"] == "UNGRADED"
    assert all(
        a["scientific_validity"] is None
        for row in c.read(source / "review-form.json")["reviews"]
        for a in row["atoms"]
    )
    assert len(packets) == 70


def test_budgets_and_schema_do_not_impersonate_human(prepared):
    _, out, _, _ = prepared
    protocol, _ = p.load(out)
    assert protocol["max_cost_nano_usd"] == 20_000_000_000
    assert c.LABEL in c.canonical(c.SCHEMA)
    assert "qualified_independent_human" not in c.canonical(c.SCHEMA)
    assert c.sha(c.PROMPTS["reviewer_a"].encode()) != c.sha(
        c.PROMPTS["reviewer_b"].encode()
    )


@pytest.mark.parametrize(
    "change", ["count", "duplicates", "grade", "attestation", "unknown", "identity"]
)
def test_bad_source_refused(prepared, tmp_path, change):
    source, _, cf, packets = prepared
    form = c.read(source / "review-form.json")
    if change == "count":
        packets.pop()
    if change == "duplicates":
        packets[0] = packets[1]
    if change == "grade":
        form["reviews"][0]["atoms"][0]["scientific_validity"] = 1
    if change == "attestation":
        form["attestation"]["qualified_independent_human"] = True
    if change == "unknown":
        packets[0]["private_metadata"] = {}
    if change == "identity":
        packets[0]["initial"]["variant"] = "V1"
    (source / "packets.json").write_text(c.canonical(packets))
    (source / "review-form.json").write_text(c.canonical(form))
    with pytest.raises(ValueError):
        p.prepare(
            source, c.sha((source / "packets.json").read_bytes()), cf, tmp_path / "bad"
        )


def test_prior_sha_required_and_outputs_fresh(prepared, tmp_path):
    source, out, cf, _ = prepared
    with pytest.raises(ValueError, match="commitment"):
        p.prepare(source, "0" * 64, cf, tmp_path / "bad")
    with pytest.raises(ValueError, match="fresh"):
        p.prepare(source, "0" * 64, cf, out)


@pytest.mark.parametrize(
    "change", ["cap", "family", "muse", "credential", "date", "price"]
)
def test_invalid_configuration_refused(prepared, tmp_path, change):
    source, _, cf, _ = prepared
    cfg = config()
    cap = "20"
    if change == "cap":
        cap = "21"
    if change == "family":
        cfg["reviewer_b"] = copy.deepcopy(cfg["reviewer_a"])
    if change == "muse":
        cfg["reviewer_a"]["model"] = "muse-spark-1.3"
    if change == "credential":
        cfg["reviewer_a"]["rate_source"] = "https://openai.com/?api_key=SENTINEL"
    if change == "date":
        cfg["reviewer_a"]["rate_checked_at"] = "2026-99-99"
    if change == "price":
        cfg["reviewer_a"]["input_ceiling_usd_per_million"] = "NaN"
    cf.write_text(c.canonical(cfg))
    with pytest.raises(ValueError):
        p.prepare(
            source,
            c.sha((source / "packets.json").read_bytes()),
            cf,
            tmp_path / "bad",
            cap,
        )


def test_immutable_input_and_prompts(prepared):
    _, out, _, _ = prepared
    (out / "prompts.json").write_text("{}")
    with pytest.raises(ValueError, match="prompt"):
        p.load(out)


def test_packet_byte_tamper_refused(prepared):
    _, out, _, _ = prepared
    with (out / "packets.json").open("a") as f:
        f.write(" ")
    with pytest.raises(ValueError, match="source_bytes"):
        p.load(out)


def test_human_copy_tamper_refused(prepared):
    _, out, _, _ = prepared
    with (out / "source-human-form.UNMODIFIED.json").open("a") as f:
        f.write(" ")
    with pytest.raises(ValueError, match="source_bytes"):
        p.load(out)


def test_authorization_and_credentials_before_spend(prepared, monkeypatch):
    _, out, _, _ = prepared
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="authorization"):
        r.run(out, "reviewer_a")
    with pytest.raises(ValueError, match="credential"):
        r.run(out, "reviewer_a", authorize=True)
    assert r.call_rows(out) == []


def test_fresh_contexts_have_no_peer_conclusions(prepared):
    _, out, _, _ = prepared
    a = []
    b = []
    r.run(out, "reviewer_a", authorize=True, limit=1, transport=transport(calls=a))
    r.run(out, "reviewer_b", authorize=True, limit=1, transport=transport(calls=b))
    assert set(json.loads(a[0]["input"][0]["content"])) == {"packet"}
    assert set(json.loads(b[0]["messages"][0]["content"])) == {"packet"}
    assert a[0]["store"] is False
    assert "previous_response_id" not in a[0]
    assert len(b[0]["messages"]) == 1
    cfg = config()["reviewer_b"]
    with pytest.raises(ValueError, match="peer_context"):
        r.request_payload(cfg, "reviewer_b", {}, context={})


def test_no_retries_or_duplicate_calls(prepared):
    _, out, _, _ = prepared
    calls = []
    r.run(out, "reviewer_a", authorize=True, transport=transport(calls=calls))
    result = r.run(out, "reviewer_a", authorize=True, transport=transport(calls=calls))
    assert len(calls) == 70 and result["new_requests"] == 0
    assert len(r.call_rows(out)) == 70


def test_ambiguous_failure_holds_entire_reservation(prepared):
    _, out, _, _ = prepared
    calls = []

    def failure(cfg, payload):
        calls.append(payload)
        raise RuntimeError("PRIVATE_PROVIDER_BODY")

    r.run(out, "reviewer_a", authorize=True, limit=1, transport=failure)
    row = r.call_rows(out)[0]
    assert row["charged"] == row["reservation"] and row["state"] == "usage_unknown"
    record = c.read(r.record_path(out, "reviewer_a", row["rid"]))
    assert "PRIVATE_PROVIDER_BODY" not in c.canonical(record)
    r.run(out, "reviewer_a", authorize=True, limit=1, transport=failure)
    assert len(calls) == 2 and len({x["rid"] for x in r.call_rows(out)}) == 2


def test_cap_reserves_before_any_provider_request(prepared, tmp_path):
    source, _, cf, _ = prepared
    out = tmp_path / "tiny"
    p.prepare(
        source, c.sha((source / "packets.json").read_bytes()), cf, out, "0.000001"
    )
    calls = []
    result = r.run(out, "reviewer_a", authorize=True, transport=transport(calls=calls))
    assert (
        result["stopped_reason"] == "ai_spending_cap"
        and not calls
        and not r.call_rows(out)
    )


def test_usage_anomaly_blocks_following_requests(prepared):
    _, out, _, _ = prepared
    r.run(
        out,
        "reviewer_a",
        authorize=True,
        transport=transport(usage={"input_tokens": 99999999, "output_tokens": 50}),
    )
    assert len(r.call_rows(out)) == 1
    with pytest.raises(ValueError, match="anomaly"):
        r.run(out, "reviewer_b", authorize=True, transport=transport())


def test_numeric_provenance_and_self_citation_rejected(prepared):
    _, _, _, packets = prepared
    q = review(packets[0])
    c.validate_review(q, packets[0])
    q["atoms"][0]["numeric_claims"][0]["value"] = 100
    with pytest.raises(ValueError, match="numeric"):
        c.validate_review(q, packets[0])
    for ref in [
        "initial:/sensor_catalog/unobserved",
        "submission:/findings/0",
        "event:999:/result",
    ]:
        q = review(packets[0])
        q["atoms"][0]["evidence_refs"] = [ref]
        with pytest.raises(ValueError):
            c.validate_review(q, packets[0])


def test_missing_citations_and_physical_checks_fail(prepared):
    _, _, _, packets = prepared
    q = review(packets[0])
    q["atoms"][0]["citation_checks"] = []
    with pytest.raises(ValueError, match="citation"):
        c.validate_review(q, packets[0])
    q = review(packets[0])
    del q["atoms"][0]["checks"]["calibration"]
    with pytest.raises(ValueError, match="contract"):
        c.validate_review(q, packets[0])


def test_noncompletion_is_not_abstention_or_graded_prose(prepared):
    _, _, _, packets = prepared
    q = review(packets[-1])
    c.validate_review(q, packets[-1])
    q["atoms"][0]["recommended_verdict"] = "NOT_ESTABLISHED"
    with pytest.raises(ValueError, match="no_final"):
        c.validate_review(q, packets[-1])


def test_premature_freeze_and_adjudication_make_no_calls(prepared):
    _, out, _, _ = prepared
    calls = []
    with pytest.raises(ValueError, match="both_full"):
        r.freeze_reviews(out)
    with pytest.raises(OSError):
        r.run(out, "adjudicator", authorize=True, transport=transport(calls=calls))
    assert not calls


def test_freeze_then_adjudicate_and_report_without_unblinding(prepared, tmp_path):
    _, out, _, _ = prepared
    run_both(out)
    freeze = r.freeze_reviews(out)
    assert freeze["disagreement_packets"] == 69
    calls = []
    r.run(out, "adjudicator", authorize=True, transport=transport(calls=calls))
    assert len(calls) == 69
    for payload in calls:
        data = json.loads(payload["input"][0]["content"])
        assert set(data) == {"packet", "frozen_reviews_and_disagreements"}
        assert "model_identity" not in c.canonical(data)
    rep = r.report(out, tmp_path / "report.ai.json")
    assert (
        rep["human_semantic_fields"] == "UNGRADED"
        and rep["qualified_human_validation"] is False
    )
    assert (
        rep["verdict_agreement"]["n"] == 69
        and rep["verdict_agreement"]["excluded"] == 1
    )
    assert rep["charged_or_held_usd"] <= 20
    assert rep["roles"]["adjudicator"]["valid"] == 69
    assert (
        c.read(out / "source-human-form.UNMODIFIED.json")["attestation"][
            "qualified_independent_human"
        ]
        is False
    )
    with pytest.raises(ValueError, match="frozen"):
        r.run(out, "reviewer_a", authorize=True, transport=transport())


def test_frozen_review_tampering_refused(prepared):
    _, out, _, packets = prepared
    run_both(out)
    r.freeze_reviews(out)
    path = r.record_path(out, "reviewer_a", packets[0]["review_id"])
    with path.open("a") as f:
        f.write(" ")
    with pytest.raises(ValueError, match="commitment"):
        r.run(out, "adjudicator", authorize=True, transport=transport())


def test_partial_report_does_not_claim_complete_review(prepared, tmp_path):
    _, out, _, _ = prepared
    r.run(out, "reviewer_a", authorize=True, limit=1, transport=transport())
    report = r.report(out, tmp_path / "partial.ai.json")
    assert (
        report["roles"]["reviewer_a"]["attempted"] == 1
        and report["roles"]["reviewer_b"]["attempted"] == 0
    )
    assert (
        report["jointly_valid_packets"] == 0
        and report["verdict_agreement"]["kappa"] is None
    )


def test_http_adapters_disable_redirects_proxies_and_retries(monkeypatch):
    import httpx

    real = httpx.Client
    seen = []
    init = []
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key-only")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-key-only")

    def callback(request):
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://untrusted.example/"})

    def client(**kw):
        init.append(kw)
        return real(**kw, transport=httpx.MockTransport(callback))

    monkeypatch.setattr(httpx, "Client", client)
    for role in ("reviewer_a", "reviewer_b"):
        with pytest.raises(ValueError, match="http_failure"):
            r.http_call(config()[role], {"fixture": True})
    assert len(seen) == 2
    assert all(x["follow_redirects"] is False and x["trust_env"] is False for x in init)
    assert str(seen[0].url) == "https://api.openai.com/v1/responses"
    assert str(seen[1].url) == "https://api.anthropic.com/v1/messages"


def test_crash_reservation_is_never_retried(prepared):
    _, out, _, packets = prepared
    protocol, _ = p.load(out)
    cfg = protocol["config"]["reviewer_a"]
    first = packets[0]["review_id"]
    payload = r.request_payload(cfg, "reviewer_a", packets[0])
    r.reserve(out, protocol, "reviewer_a", first, payload, cfg)
    calls = []
    r.run(out, "reviewer_a", authorize=True, limit=1, transport=transport(calls=calls))
    requested = json.loads(calls[0]["input"][0]["content"])["packet"]["review_id"]
    assert requested != first and r.call_rows(out)[0]["state"] == "reserved"


def test_invalid_response_stops_bulk_run_without_repairs(prepared):
    _, out, _, _ = prepared
    calls = []

    def invalid(cfg, payload):
        calls.append(payload)
        return c.canonical(
            {
                "status": "completed",
                "error": None,
                "model": cfg["model"],
                "output": [],
                "usage": {"input_tokens": 100, "output_tokens": 50},
            }
        ).encode()

    result = r.run(out, "reviewer_a", authorize=True, transport=invalid)
    assert len(calls) == 1 and result["stopped_reason"] is not None
    assert r.call_rows(out)[0]["state"] == "settled"


def test_anomaly_reports_all_known_cost_not_only_reservation(prepared, tmp_path):
    _, out, _, _ = prepared
    r.run(
        out,
        "reviewer_a",
        authorize=True,
        transport=transport(usage={"input_tokens": 999999999, "output_tokens": 50}),
    )
    row = r.call_rows(out)[0]
    assert row["charged"] > row["reservation"]
    report = r.report(out, tmp_path / "anomaly.json")
    assert report["charged_or_held_usd"] > 20
    assert report["roles"]["reviewer_a"]["usage_unknown_or_reserved"] == 1


def test_offline_protocol_cannot_use_real_transport(prepared, tmp_path, monkeypatch):
    source, _, cf, _ = prepared
    cfg = config()
    cfg["execution_mode"] = "offline_contract_check"
    cfg["pricing_confirmation"] = "OFFLINE_FIXTURE_NOT_A_QUOTE"
    cf.write_text(c.canonical(cfg))
    out = tmp_path / "offline"
    p.prepare(source, c.sha((source / "packets.json").read_bytes()), cf, out)
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key-only")
    with pytest.raises(ValueError, match="offline_protocol"):
        r.run(out, "reviewer_a", authorize=True)
    assert not r.call_rows(out)


def test_price_confirmation_required(prepared, tmp_path):
    source, _, cf, _ = prepared
    cfg = config()
    cfg["pricing_confirmation"] = "NOT_CHECKED"
    cf.write_text(c.canonical(cfg))
    with pytest.raises(ValueError, match="confirmation"):
        p.prepare(
            source, c.sha((source / "packets.json").read_bytes()), cf, tmp_path / "bad"
        )


def test_citation_pointer_must_anchor_the_named_source(prepared):
    _, _, _, packets = prepared
    q = review(packets[0])
    q["atoms"][0]["citation_checks"][0]["evidence_refs"] = ["event:1:/result/summary"]
    with pytest.raises(ValueError, match="identify_source"):
        c.validate_review(q, packets[0])


def test_self_citation_in_accepted_assessment_is_not_evidence(prepared):
    _, _, _, packets = prepared
    q = copy.deepcopy(packets[0])
    q["events"].append(
        {
            "sequence": 2,
            "tool": "submission_validation",
            "arguments": {},
            "result": {"assessment": q["submission"]},
        }
    )
    with pytest.raises(ValueError, match="self_citation"):
        c.evidence(q, "event:2:/result/assessment")


def test_reviewer_identity_guess_is_not_accepted(prepared):
    _, _, _, packets = prepared
    q = review(packets[0])
    q["summary"] = "This is V2"
    with pytest.raises(ValueError, match="unblinding"):
        c.validate_review(q, packets[0])


def test_next_evidence_can_reference_catalog_as_context_only(prepared):
    _, _, _, packets = prepared
    q = review(packets[0])
    q["atoms"][0]["checks"]["next_evidence"]["evidence_refs"] = [
        "context:/sensor_catalog/unobserved"
    ]
    c.validate_review(q, packets[0])
    q["atoms"][0]["numeric_claims"] = [
        {"reference": "context:/sensor_catalog/unobserved", "value": 1}
    ]
    with pytest.raises(ValueError, match="not_received"):
        c.validate_review(q, packets[0])


def test_physical_checks_cannot_use_catalog_as_measured_support(prepared):
    _, _, _, packets = prepared
    q = review(packets[0])
    q["atoms"][0]["checks"]["physical_assumptions"]["evidence_refs"] = [
        "context:/sensor_catalog/unobserved"
    ]
    with pytest.raises(ValueError, match="not_received"):
        c.validate_review(q, packets[0])
