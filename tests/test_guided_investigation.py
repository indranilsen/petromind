"""Public presentation contracts; no model calls or physical self-certification."""

import shutil
import subprocess
from pathlib import Path

import pytest

from petromind.investigation_events import request_event


@pytest.mark.parametrize(
    "arguments",
    [
        None,
        [],
        "private reasoning",
        {"topic": "PRIVATE_SENTINEL"},
        {"findings": "PRIVATE_SENTINEL"},
    ],
)
def test_request_projection_never_exports_submission_text_or_unknown_topics(arguments):
    result = request_event(
        {"tool": "submit_audit", "audit_sequence": 2, "arguments": arguments}
    )
    assert result == {
        "kind": "tool_request",
        "mode": "live",
        "tool": "submit_audit",
        "sequence": 2,
        "title": "Actual tool request; awaiting Python result",
    }
    result = request_event(
        {"tool": "lookup_knowledge", "audit_sequence": 2, "arguments": arguments}
    )
    assert "PRIVATE_SENTINEL" not in str(result) and "private reasoning" not in str(
        result
    )


def test_known_graph_query_topic_is_public_but_free_text_purpose_is_not():
    r = request_event(
        {
            "tool": "lookup_knowledge",
            "audit_sequence": 0,
            "arguments": {"topic": "fault:9", "purpose": "PRIVATE_SENTINEL"},
        }
    )
    assert r["topic"] == "fault:9"
    assert "PRIVATE_SENTINEL" not in str(r)
    r = request_event({"tool": "PRIVATE_SENTINEL", "audit_sequence": 0})
    assert r["tool"] == "unrecognized_tool"


def test_public_graph_projection_and_cursor_have_no_future_or_invented_edges():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for frontend contract checks")
    script = r"""
const assert=require('node:assert/strict');
const p=require('./petromind/web/investigation.js');
const received={kind:'evidence_received',hypothesis:9,claim:'constructed claim',observations:{'P-TPT':{available:true,first:1,last:2}}};
const f={citation_id:'knowledge:location:P-TPT',subject:'P-TPT',relation:'pressure_at',object:'subsea_tree_transducer',status:'documented',scope:'generic_not_well_specific',provenance:{url:'https://github.com/petrobras/3W'},locator:'dataset.ini'};
const lookup={kind:'tool_result',sequence:0,tool:'lookup_knowledge',facts:[f]};
const h={citation_id:'analogue:0',shared_sensors:1,matched_sensors:['P-TPT']};
const history={kind:'tool_result',sequence:1,tool:'search_history',matches:[h]};
const final={kind:'tool_result',tool:'submit_audit',assessment:{verdict:'PARTIALLY_SUPPORTED',findings:[{statement:'No supplied specificity premise',citations:[f.citation_id],missing_premise:'Need discriminating criteria',next_evidence:{target:'Validated procedure'}}]}};
const all=[received,lookup,history,final];
assert.equal(p.result(p.visible(all,1)),null);
assert.equal(p.graph(p.visible(all,1)).nodes.length,3);
assert(!JSON.stringify(p.graph(p.visible(all,1))).includes('subsea_tree_transducer'));
const g=p.graph(p.visible(all,2));
assert(g.edges.some(e=>e.from==='entity:P-TPT'&&e.to==='entity:subsea_tree_transducer'&&e.label===f.relation&&e.provenance.locator===f.locator));
assert(!g.nodes.some(n=>n.kind==='finding'||n.kind==='history'));
const done=p.graph(all);
for(const e of done.edges) {assert(done.nodes.some(n=>n.id===e.from));assert(done.nodes.some(n=>n.id===e.to));assert(e.provenance);}
assert(done.edges.some(e=>e.kind==='empirical'));
assert(done.edges.some(e=>e.kind==='citation'&&e.label.includes('not entailment')));
assert(!done.edges.some(e=>e.label.includes('causes')));
assert.equal(done.nodes.filter(n=>n.kind==='fact').length,1);
assert.equal(p.result(all).verdict,'PARTIALLY_SUPPORTED');
assert.equal(p.visible(all,-3).length,0);assert.equal(p.visible(all,999).length,4);
const pending=p.graph([received,{kind:'tool_request',sequence:0,tool:'lookup_knowledge',topic:'fault:9'}]);
assert(pending.nodes.some(n=>n.kind==='request'));assert(!pending.nodes.some(n=>n.kind==='fact'));
assert(!p.graph([received,{kind:'tool_request',sequence:0,tool:'lookup_knowledge'},lookup]).nodes.some(n=>n.kind==='request'));
"""
    result = subprocess.run(
        [node, "-e", script],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_manual_next_buttons_are_removed_and_public_module_is_packaged():
    html = Path("petromind/web/index.html").read_text()
    assert 'id="nextRecord"' not in html and 'id="graphAdvance"' not in html
    assert 'id="capturePause"' in html and 'id="captureSkip"' in html
    assert 'src="/investigation.js"' in html
    assert "STATISTICAL MACHINE-LEARNING CLASSIFIER" in html


def test_scope_groups_preserve_actual_public_v4_result_without_regrading():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for frontend contract checks")
    script = r"""
const assert=require('node:assert/strict');
const p=require('./petromind/web/investigation.js');
const f=require('./tests/fixtures/live006-public-assessment.json');
const result=f.recorded_assessment, before=JSON.stringify(result);
const groups=p.assessmentSections(result);
assert.equal(groups.measured.length,2); assert.equal(groups.documented.length,1);
assert.equal(groups.causal.length,1); assert.equal(groups.other.length,0);
assert.equal(groups.causal[0].verdict,'PARTIALLY_SUPPORTED');
assert.equal(groups.causal[0],result.findings[3]);
assert.equal(JSON.stringify(result),before);
const legacy={findings:[{basis:'unsupported',verdict:'NOT_ESTABLISHED',statement:'legacy scope unspecified'}]};
assert.equal(p.assessmentSections(legacy).other.length,1);
assert.equal(p.assessmentSections(legacy).causal.length,0);
"""
    subprocess.run(
        [node, "-e", script], cwd=Path(__file__).resolve().parents[1], check=True
    )
