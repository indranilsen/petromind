"""Operator regression coverage with explicit synthetic saved-run inputs."""

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from test_saved_investigation import capture as capture_fixture
from test_saved_investigation import saved as saved_fixture

from petromind.claim_demo import DemoApp, make_server
from petromind.saved_investigation import import_saved


@pytest.fixture
def capture(tmp_path, monkeypatch):
    return capture_fixture.__wrapped__(tmp_path, monkeypatch)


@pytest.fixture
def saved(capture, tmp_path, monkeypatch):
    return saved_fixture.__wrapped__(capture, tmp_path, monkeypatch)


def test_operator_conclusion_and_evidence_resolution_preserve_source():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for presentation checks")
    script = r"""
const assert=require('node:assert/strict'),p=require('./petromind/web/investigation.js');
const publicRun=require('./tests/fixtures/live006-public-assessment.json');
const initial={kind:'evidence_received',hypothesis:9,observations:publicRun.observations};
const fact={kind:'tool_result',tool:'lookup_knowledge',facts:[{id:'fault:9:mechanism',citation_id:'knowledge:fault:9:mechanism',subject:'fault:9',relation:'described_as',object:'hydrate_obstruction',status:'documented'}]};
const assessment=structuredClone(publicRun.recorded_assessment);
const submitted={kind:'tool_result',tool:'submit_audit',assessment},done={kind:'completion',status:'completed'};
const all=[initial,fact,submitted,done],before=JSON.stringify(all);
const s=p.operatorConclusion(all);
assert.equal(s.rootVerdict,'NOT ESTABLISHED');assert(s.suspected.includes('obstruction'));
assert.equal(assessment.verdict,'PARTIALLY_SUPPORTED');
assert(s.nextPlan.requirements.length);assert(s.nextPlan.question);
assert.deepEqual(s.nextPlan.requirements,[assessment.findings[3].missing_premise]);
assert(!s.nextPlan.requirements.includes(assessment.findings[3].next_evidence.purpose));
assert.equal(s.nextPlan.requirementSources[0].source,'recorded missing premise');
assert.deepEqual(s.nextPlan.requirementSources[0].citations,assessment.findings[3].citations);
assert.equal(s.nextPlan.requirementSources[0].findingIndex,3);
assert.equal(s.nextPlan.requirementSources[0].premise,assessment.findings[3].missing_premise);
assert(s.nextPlan.limitation.includes('did not identify a verified test'));
assert.equal(JSON.stringify(all),before);
assert.equal(p.operatorConclusion(all.slice(0,-1)),null);
const f=p.findingEvidence(all,0);assert(f.available&&f.citations.includes('measurement:P-PDG'));
assert.equal(p.findingEvidence(all,999).available,false);
assessment.findings.push({statement:'No source or gap',citations:['unknown:source'],verdict:'NOT_ESTABLISHED'});
assert.equal(p.findingEvidence(all,assessment.findings.length-1).available,false);
assert.deepEqual(p.findingEvidence(all,assessment.findings.length-1).unresolved,['unknown:source']);
assessment.findings.at(-1).missing_premise='Missing criterion';
assert(p.findingEvidence(all,assessment.findings.length-1).gap);
// An overall verdict cannot establish a cause with an unestablished causal finding.
assessment.verdict='SUPPORTED';assert.equal(p.operatorConclusion(all).rootVerdict,'NOT ESTABLISHED');
"""
    subprocess.run(
        [node, "-e", script], cwd=Path(__file__).resolve().parents[1], check=True
    )


@pytest.mark.skipif(
    os.getenv("PETROMIND_BROWSER_CHECK") != "1", reason="Opt-in browser regression"
)
def test_operator_summary_and_each_finding_control_after_repeated_tab_switches(saved):
    from playwright.sync_api import sync_playwright

    sys.path.insert(0, str(Path("scripts").resolve()))
    from verify_operator_experience import verify

    capture_dir, run, _row, bundle = saved
    import_saved(capture_dir, run, bundle)
    app = DemoApp(capture_dir, saved_directory=bundle)
    # Layout-only received-record fixture, not a scientific benchmark or saved run.
    # Seven independent context records exercise a graph larger than 48 entities.
    events = app.cases[0]["saved_investigation"]["events"]
    events.insert(
        -2,
        {
            "kind": "tool_result",
            "tool": "lookup_knowledge",
            "facts": [
                {
                    "citation_id": f"ui-layout:{i}",
                    "subject": f"layout_context_{i}",
                    "relation": "documents",
                    "object": f"layout_quantity_{i}",
                    "scope": "SYNTHETIC UI LAYOUT ONLY",
                }
                for i in range(7)
            ],
        },
    )
    server = make_server(app, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    screenshots = Path(
        os.getenv("PETROMIND_SCREENSHOTS", str(bundle.parent / "operator-screenshots"))
    )
    screenshots.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=os.getenv("PETROMIND_CHROMIUM"),
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            try:
                report = verify(
                    browser,
                    app,
                    f"http://127.0.0.1:{server.server_port}",
                    screenshots,
                    fixture=True,
                )
                assert report["case_viewport_journeys"] == 6
                assert max(report["full_graph_entities"]) >= 48
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize(
    "premise,evidence_request",
    [
        (
            "No additional specificity evidence is needed; the gap concerns calibration.",
            None,
        ),
        (
            "If topology is verified, a necessity rule may be relevant; otherwise assess calibration.",
            None,
        ),
        ("The hydraulic impedance criterion has not been supplied.", None),
        ("", None),
        (
            "",
            {
                "kind": "no_verified_discriminating_test",
                "target": "fault:9",
                "purpose": "No verified discriminating test was supplied.",
            },
        ),
        (
            "   ",
            {
                "kind": "no_verified_discriminating_test",
                "target": "fault:9",
                "purpose": "No verified discriminating test was supplied.",
            },
        ),
        (
            "A specific test is not required; calibration evidence is missing.",
            {
                "kind": "no_verified_discriminating_test",
                "target": "fault:9",
                "purpose": "No verified discriminating test was supplied.",
            },
        ),
        (
            "If the pressure context applies, a causal criterion is missing.",
            {
                "kind": "no_verified_discriminating_test",
                "target": "fault:9",
                "purpose": "No verified discriminating test was supplied.",
            },
        ),
        (
            "",
            {
                "kind": "no_verified_discriminating_test",
                "target": "fault:9",
                "purpose": "",
            },
        ),
        (
            "A criterion is missing.",
            {
                "kind": "documented_rule",
                "target": "fault:9",
                "purpose": "Provide a documented criterion separating these causes.",
            },
        ),
        (
            "A discriminating criterion is missing.",
            {
                "kind": "no_verified_discriminating_test",
                "target": "fault:9",
                "purpose": "No verified discriminating test is supplied.",
            },
        ),
    ],
)
def test_next_evidence_preserves_negation_conditions_and_source(
    premise, evidence_request
):
    import json

    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for presentation checks")
    script = r"""
const assert=require('node:assert/strict'),p=require('./petromind/web/investigation.js');
const [premise,request]=JSON.parse(process.argv[1]);
const f={statement:'Causal claim',scope:'diagnostic_conclusion',basis:'hypothesis',verdict:'NOT_ESTABLISHED',missing_premise:premise,citations:['measurement:P-PDG'],next_evidence:request||{kind:'none',purpose:'',target:''}};
const events=[{kind:'evidence_received',hypothesis:9,observations:{}},{kind:'tool_result',tool:'submit_audit',assessment:{verdict:'PARTIALLY_SUPPORTED',findings:[f]}},{kind:'completion',status:'completed'}];
const before=JSON.stringify(events),plan=p.operatorConclusion(events).nextPlan;
const noTest=request?.kind==='no_verified_discriminating_test';
const expected=(!noTest&&request?.purpose)||premise.trim();
assert.deepEqual(plan.requirements,expected?[expected]:[]);
assert.equal(plan.noTest,request?.kind==='no_verified_discriminating_test');
if(noTest){assert(plan.limitation.includes('did not identify a verified test'));assert(!plan.requirements.includes(request.purpose));}
if(expected){assert.equal(plan.requirementSources[0].source,!noTest&&request?.purpose?'recorded evidence request':'recorded missing premise');assert.equal(plan.requirementSources[0].findingIndex,0);assert.equal(plan.requirementSources[0].premise,premise);assert.deepEqual(plan.requirementSources[0].citations,f.citations);}
assert.equal(JSON.stringify(events),before);
assert(!plan.question.includes('necessarily'));
"""
    subprocess.run(
        [node, "-e", script, json.dumps([premise, evidence_request])],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )
