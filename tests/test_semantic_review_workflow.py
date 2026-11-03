"""SOFTWARE FIXTURES ONLY: no real Sprint C packet or human semantic grade."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.semantic_review import workflow as w


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.json"
        packets = []
        for i in range(70):
            atom = {
                "id": "a1",
                "scope": "measured_observation",
                "statement": "SOFTWARE FIXTURE proposition, not a benchmark answer.",
            }
            public = {k: None for k in w.PUBLIC_KEYS}
            public.update(
                atomic_claims=[atom],
                model={"id": "model:M1", "assumptions": ["SOFTWARE FIXTURE only"]},
                synthetic=True,
                scenario="SOFTWARE FIXTURE NOT REAL DATA",
            )
            final = {
                "verdict": "SUPPORTED",
                "numeric_observations": [],
                "findings": [
                    {
                        "statement": atom["statement"],
                        "verdict": "SUPPORTED",
                        "citations": ["model:M1"],
                    }
                ],
            }
            if i == 69:
                final = None
            packets.append(
                {
                    "review_id": format(i, "024x"),
                    "public_packet": public,
                    "received_tool_evidence": [
                        {
                            "sequence": 1,
                            "tool": "lookup_graph",
                            "arguments": {"node": "model:M1", "hops": 1},
                            "result": {"edges": []},
                            "previous": "a" * 64,
                            "digest": "b" * 64,
                        },
                        {
                            "sequence": 2,
                            "tool": "submit_audit",
                            "arguments": {
                                "rejected_secret": "DO_NOT_DISTRIBUTE_REJECTED_BODY"
                            },
                            "result": {
                                "error": "fixture_shape_error",
                                "correction": "Correct schema",
                            },
                            "previous": "b" * 64,
                            "digest": "c" * 64,
                        },
                    ],
                    "propositions": [
                        {
                            "atomic_proposition": atom,
                            "submitted_finding": None
                            if final is None
                            else final["findings"][0],
                            "semantic_entailment": None,
                            "missing_premise_quality": None,
                            "next_evidence_usefulness": None,
                        }
                    ],
                    "submission": final,
                    "semantic_grades": None,
                }
            )
        self.packets = packets
        self.save(self.source, packets)
        self.before = self.source.read_bytes()
        self.bundle = self.root / "bundle"

    def tearDown(self):
        self.temp.cleanup()

    def save(self, path, value):
        path.write_text(json.dumps(value))

    def prep(self):
        return w.prepare(
            self.source,
            self.bundle,
            hashlib.sha256(self.source.read_bytes()).hexdigest(),
        )

    def completed(self, role):
        value = w.read(self.bundle / role / "review-form.json")
        value["attestation"] = {k: True for k in value["attestation"]}
        for row in value["reviews"]:
            missing = row["status"] == "NO_FINAL_SUBMISSION"
            for a in row["atoms"]:
                a.update(
                    interpretation_target="proposition_truth",
                    preferred_verdict="NO_SUBMISSION" if missing else "SUPPORTED",
                    scientific_validity="N/A" if missing else 1,
                    citation_entailment="N/A" if missing else 1,
                    flags={k: "N/A" if missing else "none" for k in w.FLAGS},
                    evidence_refs=["initial:/model/assumptions/0"],
                    rationale="SOFTWARE FIXTURE ONLY; not a human review.",
                    confidence="medium",
                )
            for d in row["dimensions"].values():
                d.update(
                    fraction="N/A" if missing else 1,
                    evidence_refs=["initial:/model/assumptions/0"],
                    justification="SOFTWARE FIXTURE ONLY",
                )
        return value

    def forms(self):
        self.prep()
        a = self.completed("R-A")
        b = self.completed("R-B")
        pa = self.root / "a.json"
        pb = self.root / "b.json"
        self.save(pa, a)
        self.save(pb, b)
        return a, b, pa, pb

    def test_prepare_70_without_key_or_map_and_preserves_source(self):
        result = self.prep()
        self.assertEqual(result["reviews_expected"], 140)
        self.assertEqual(self.before, self.source.read_bytes())
        _m, packets = w.bundle(self.bundle)
        self.assertEqual(len(packets), 70)
        for role in ("R-A", "R-B"):
            text = (self.bundle / role / "packets.json").read_text()
            self.assertNotIn("DO_NOT_DISTRIBUTE_REJECTED_BODY", text)
            self.assertNotIn("previous", text)
            self.assertNotIn("digest", text)
            self.assertEqual(len(list((self.bundle / role).glob("packet-*.md"))), 70)
        self.assertNotEqual(
            [p["review_id"] for p in w.read(self.bundle / "R-A/packets.json")],
            [p["review_id"] for p in w.read(self.bundle / "R-B/packets.json")],
        )
        self.assertEqual(w.WEIGHTS["citation_entailment"], 4)
        self.assertEqual(sum(w.WEIGHTS.values()), 51)

    def test_wrong_commitment_and_packet_count_refused(self):
        with self.assertRaisesRegex(ValueError, "commitment"):
            w.prepare(self.source, self.bundle, "0" * 64)
        self.save(self.source, self.packets[:2])
        with self.assertRaisesRegex(ValueError, "packet_count"):
            self.prep()

    def test_duplicate_packets_and_unknown_source_fields_refused(self):
        self.packets[1]["review_id"] = self.packets[0]["review_id"]
        self.save(self.source, self.packets)
        with self.assertRaisesRegex(ValueError, "duplicate_blind"):
            self.prep()
        self.packets[1]["review_id"] = "f" * 24
        self.packets[0]["answer_key"] = {}
        self.save(self.source, self.packets)
        with self.assertRaisesRegex(ValueError, "packet_contract"):
            self.prep()

    def test_variant_reference_and_unblinding_leak_refused(self):
        for key, value in [("variant", "V1"), ("reference_verdict", "SUPPORTED")]:
            packet = copy.deepcopy(self.packets[0])
            packet["public_packet"]["model"][key] = value
            with self.assertRaisesRegex(ValueError, "identity_leak"):
                w.project(packet)
        packet = copy.deepcopy(self.packets[0])
        packet["submission"]["findings"][0]["statement"] = "V2 result"
        packet["propositions"][0]["submitted_finding"] = None
        with self.assertRaisesRegex(ValueError, "unblinding"):
            w.project(packet)

    def test_prior_semantic_grades_refused(self):
        p = copy.deepcopy(self.packets[0])
        p["propositions"][0]["semantic_entailment"] = 1
        with self.assertRaisesRegex(ValueError, "prior_semantic"):
            w.project(p)

    def test_blank_template_and_false_human_attestation_refused(self):
        self.prep()
        m, packets = w.bundle(self.bundle)
        with self.assertRaisesRegex(ValueError, "human_attestation"):
            w.validate_form(
                w.read(self.bundle / "R-A/review-form.json"), m, packets, "R-A"
            )
        form = self.completed("R-A")
        form["reviews"][0]["dimensions"]["causal_leaps"]["fraction"] = None
        with self.assertRaisesRegex(ValueError, "dimension_grade"):
            w.validate_form(form, m, packets, "R-A")

    def test_boolean_grades_and_half_fabricated_ratings_refused(self):
        self.prep()
        m, p = w.bundle(self.bundle)
        form = self.completed("R-A")
        for bad in (True, 0.25, 2):
            form["reviews"][0]["atoms"][0]["scientific_validity"] = bad
            with self.assertRaisesRegex(ValueError, "atomic_rating"):
                w.validate_form(form, m, p, "R-A")

    def test_missing_rows_duplicates_and_wrong_reviewer_refused(self):
        self.prep()
        m, p = w.bundle(self.bundle)
        f = self.completed("R-A")
        with self.assertRaisesRegex(ValueError, "identity"):
            w.validate_form(f, m, p, "R-B")
        f["reviews"][-1] = f["reviews"][0]
        with self.assertRaisesRegex(ValueError, "coverage"):
            w.validate_form(f, m, p, "R-A")

    def test_unknown_unqueried_evidence_and_negative_indices_refused(self):
        self.prep()
        packet = w.read(self.bundle / "R-A/packets.json")[0]
        for ref in [
            "event:900:/result",
            "initial:/hidden_sensor",
            "initial:/atomic_claims/-1",
            "private:/answer",
        ]:
            with self.assertRaises(ValueError):
                w.refs(packet, [ref])
        w.refs(packet, ["event:1:/result/edges", "initial:/model/id"])

    def test_na_is_not_full_credit_or_false_semantic_failure(self):
        a, _b, _pa, _pb = self.forms()
        m, p = w.bundle(self.bundle)
        missing = next(
            row for row in a["reviews"] if row["status"] == "NO_FINAL_SUBMISSION"
        )
        self.assertEqual(missing["atoms"][0]["preferred_verdict"], "NO_SUBMISSION")
        missing["dimensions"]["causal_leaps"]["fraction"] = 0
        with self.assertRaisesRegex(ValueError, "missing_final"):
            w.validate_form(a, m, p, "R-A")

    def test_native_bundle_tampering_refused(self):
        self.prep()
        (self.bundle / "R-A/REVIEWER_HANDBOOK.md").write_text("changed")
        with self.assertRaisesRegex(ValueError, "distributed_bundle_modified"):
            w.bundle(self.bundle)

    def test_kappa_and_degenerate_missing_cases(self):
        v = w.agreement(["a", "a", "b", "b"], ["a", "b", "a", "b"])
        self.assertEqual(v["kappa"], 0)
        self.assertEqual(v["exact_agreement"], 0.5)
        self.assertEqual(
            w.agreement([0, 0.5, 1], [0, 0.5, 1], ordinal=True)["kappa"], 1
        )
        self.assertIsNone(w.agreement([1, 1], [1, 1], ordinal=True)["kappa"])
        self.assertEqual(
            w.agreement(["N/A", "NO_SUBMISSION"], ["N/A", "NO_SUBMISSION"])["n"], 0
        )
        with self.assertRaisesRegex(ValueError, "pair_count"):
            w.agreement([0], [])

    def test_two_reviews_adjudication_and_seal_never_unblind(self):
        a, b, pa, pb = self.forms()
        rid = a["reviews"][0]["review_id"]
        row = next(r for r in b["reviews"] if r["review_id"] == rid)
        if row["status"] == "NO_FINAL_SUBMISSION":
            rid = a["reviews"][1]["review_id"]
            row = next(r for r in b["reviews"] if r["review_id"] == rid)
        row["dimensions"]["citation_entailment"]["fraction"] = 0.5
        self.save(pb, b)
        cmp = self.root / "comparison"
        report = w.compare(self.bundle, pa, pb, cmp)
        self.assertEqual(report["disagreement_fields"], 1)
        ad = w.read(cmp / "adjudication.template.json")
        with self.assertRaisesRegex(ValueError, "adjudication_required"):
            w.finalize(
                self.bundle,
                pa,
                pb,
                cmp / "adjudication.template.json",
                self.root / "not-final",
            )
        ad["attestation"] = {k: True for k in ad["attestation"]}
        ad["resolutions"][0].update(
            value=0.5,
            evidence_refs=["initial:/model/id"],
            rationale="SOFTWARE FIXTURE ADJUDICATION",
        )
        pad = self.root / "adjudication.json"
        self.save(pad, ad)
        result = w.finalize(self.bundle, pa, pb, pad, self.root / "final")
        self.assertFalse(result["unblinded"])
        self.assertFalse(result["semantic_truth_certified"])
        scores = w.read(self.root / "final/semantic-report.json")[
            "packet_semantic_scores"
        ]
        self.assertEqual(
            next(s for s in scores if s["review_id"] == rid)[
                "semantic_points_of_51_before_penalties"
            ],
            49,
        )
        self.assertIsNone(
            next(s for s in scores if s["status"] == "NO_FINAL_SUBMISSION")[
                "semantic_points_of_51_before_penalties"
            ]
        )
        self.assertIsNone(
            w.read(self.root / "final/semantic-report.json")["combined_total"]
        )
        for name, expected in w.read(self.root / "final/seal.json")["files"].items():
            self.assertEqual(w.sha((self.root / "final" / name).read_bytes()), expected)
        self.assertEqual(self.source.read_bytes(), self.before)
        self.assertEqual(
            (self.root / "final/independent-a.json").read_bytes(), pa.read_bytes()
        )
        self.assertEqual(
            (self.root / "final/independent-b.json").read_bytes(), pb.read_bytes()
        )
        self.assertEqual(
            (self.root / "final/adjudication.json").read_bytes(), pad.read_bytes()
        )

    def test_changed_review_after_compare_refused(self):
        a, _b, pa, pb = self.forms()
        cmp = self.root / "comparison"
        w.compare(self.bundle, pa, pb, cmp)
        ad = w.read(cmp / "adjudication.template.json")
        ad["attestation"] = {k: True for k in ad["attestation"]}
        self.save(cmp / "adjudication.json", ad)
        a["reviews"][0]["atoms"][0]["rationale"] += " changed"
        self.save(pa, a)
        with self.assertRaisesRegex(ValueError, "sealed_review_changed"):
            w.finalize(
                self.bundle, pa, pb, cmp / "adjudication.json", self.root / "final"
            )

    def test_duplicate_penalty_events_not_counted_twice(self):
        self.prep()
        m, p = w.bundle(self.bundle)
        f = self.completed("R-A")
        r = next(r for r in f["reviews"] if r["status"] == "HAS_SUBMISSION")
        e = {
            "category": "invented_reading",
            "error_id": "e1",
            "atom_ids": ["a1"],
            "evidence_refs": ["initial:/model/id"],
            "description": "SOFTWARE FIXTURE not real misconduct",
        }
        r["penalty_events"] = [e, copy.deepcopy(e)]
        with self.assertRaisesRegex(ValueError, "duplicate_penalty"):
            w.validate_form(f, m, p, "R-A")

    def test_changed_process_code_refused(self):
        self.prep()
        with (
            patch.object(w, "implementation_hash", return_value="0" * 64),
            self.assertRaisesRegex(ValueError, "process_code_changed"),
        ):
            w.bundle(self.bundle)

    def test_markdown_fence_cannot_be_closed_by_received_content(self):
        self.packets[0]["public_packet"]["instructions"] = (
            "```\n<h1>untrusted</h1>\n```"
        )
        self.save(self.source, self.packets)
        self.prep()
        packet = next(
            p
            for p in (self.bundle / "R-A").glob("packet-*.md")
            if "000000000000000000000000" in p.read_text()
        )
        body = packet.read_text()
        self.assertIn("````json", body)
        self.assertTrue(body.endswith("````\n"))

    def test_missing_adjudication_resolution_refused(self):
        _a, b, pa, pb = self.forms()
        row = next(r for r in b["reviews"] if r["status"] == "HAS_SUBMISSION")
        row["dimensions"]["document_scope"]["fraction"] = 0.5
        self.save(pb, b)
        cmp = self.root / "comparison"
        w.compare(self.bundle, pa, pb, cmp)
        ad = w.read(cmp / "adjudication.template.json")
        ad["attestation"] = {k: True for k in ad["attestation"]}
        ad["resolutions"] = []
        target = cmp / "incomplete.json"
        self.save(target, ad)
        with self.assertRaisesRegex(ValueError, "complete_unique_adjudication"):
            w.finalize(self.bundle, pa, pb, target, self.root / "final")

    def test_duplicate_json_keys_fail_closed(self):
        x = self.root / "bad.json"
        x.write_text('{"a":1,"a":2}')
        with self.assertRaisesRegex(ValueError, "duplicate_json"):
            w.read(x)


if __name__ == "__main__":
    unittest.main()
