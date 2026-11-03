"""Presentation-only completion/summary checks; captured records stay unchanged."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_conclusion_uses_accepted_evidence_and_waits_for_completion():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for frontend presentation tests")
    script = r"""
const assert=require('node:assert/strict'), p=require('./petromind/web/investigation.js');
const publicRun=require('./tests/fixtures/live006-public-assessment.json');
const input={kind:'evidence_received',hypothesis:9,observations:publicRun.observations};
const submitted={kind:'tool_result',tool:'submit_audit',assessment:publicRun.recorded_assessment};
const done={kind:'completion',status:'completed'};
const before=JSON.stringify([input,submitted]);
assert.equal(p.conclusion([input]),null);
assert.equal(p.conclusion([input,submitted]),null);
assert.equal(p.conclusion([input,submitted,{kind:'completion',status:'failed'}]),null);
assert.equal(p.conclusion([input,done]),null);
const c=p.conclusion([input,submitted,done]);
assert.equal(c.headline,'Pressure increases confirmed.');
assert.equal(c.cause,'Suspected service-line hydrate not verified.');
assert.equal(c.status,'unverified');
assert(c.uncertain.length && c.next.length);
assert(c.caveat.includes('does not mean ruled out'));
assert.equal(publicRun.recorded_assessment.verdict,'PARTIALLY_SUPPORTED');
assert.equal(publicRun.recorded_assessment.findings.at(-1).verdict,'PARTIALLY_SUPPORTED');
assert.equal(JSON.stringify([input,submitted]),before);
// Generic, supported observation alone never turns into a causal conclusion.
const observation={scope:'measured_observation',basis:'measurement',verdict:'SUPPORTED',statement:'Value observed.',citations:['measurement:X'],missing_premise:'',next_evidence:{kind:'none'}};
function summary(findings,verdict='SUPPORTED') {
 return p.conclusion([{kind:'evidence_received',hypothesis:2,observations:{X:{available:true,first:1,last:2,delta:1}}},
 {kind:'tool_result',tool:'submit_audit',assessment:{findings,verdict,numeric_observations:[{sensor:'X',metric:'delta',value:1}]}},done]);
}
const only=summary([observation]);
assert.equal(only.status,'not_recorded');assert(only.fault.includes('safety-valve'));assert(!only.cause.includes('hydrate'));
assert.equal(only.next.length,0);
const causal={scope:'diagnostic_conclusion',verdict:'NOT_ESTABLISHED',statement:'Constructed cause.',missing_premise:'No discriminating rule.',next_evidence:{kind:'no_verified_discriminating_test',purpose:'No verified test is supplied.'}};
assert.equal(summary([observation,causal],'PARTIALLY_SUPPORTED').status,'unverified');
assert.equal(summary([{...causal,verdict:'CONTRADICTED'}],'CONTRADICTED').status,'contradicted');
assert(summary([{...causal,verdict:'CONTRADICTED'}],'CONTRADICTED').caveat.includes('does not by itself exclude'));
assert.equal(summary([{...causal,verdict:'SUPPORTED',missing_premise:'',next_evidence:{kind:'none'}}]).status,'supported');
assert.equal(summary([observation],'CONTRADICTED').status,'claim_contradicted');
// A documented example can be supported while root cause has no separate verdict.
assert.equal(summary([{...observation,scope:'documented_comparison',basis:'documented'}]).status,'not_recorded');
const bad=structuredClone(submitted);bad.assessment.numeric_observations=[];
assert.equal(p.conclusion([input,bad,done]).measured.length,0);
assert.equal(p.completedResult([input,submitted,done,{kind:'completion',status:'incomplete'}]),null);
"""
    subprocess.run(
        [node, "-e", script], cwd=Path(__file__).resolve().parents[1], check=True
    )
