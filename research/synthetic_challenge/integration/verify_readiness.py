"""Owner-only, read-only release verification; prints no keys or hidden values."""
import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path


def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def verify(release,private,repo):
    release=Path(release).resolve();private=Path(private).resolve();repo=Path(repo).resolve()
    frozen=json.loads((release/'FREEZE.json').read_text())
    core=json.loads((private/'PRIVATE_CORE_MANIFEST.json').read_text())
    original=json.loads((private/'PRIVATE_FREEZE.json').read_text())
    addendum=json.loads((release/'FREEZE_ADDENDUM.json').read_text())
    assert digest(frozen['public_files'])==frozen['public_root_digest']
    assert digest(original['files'])==original['root_digest']==frozen['private_package_commitment']
    assert digest(core['files'])==core['root_digest']==addendum['private_core_digest']
    for root,items in [(release,frozen['public_files']),(private,core['files'])]:
        for path,expected in items.items():
            assert hashlib.sha256((root/path).read_bytes()).hexdigest()==expected,path
    assert all(original['files'][path]==sha for path,sha in core['files'].items())
    banned={'atomic_verdicts','expected_verdict','expected_verdicts','reference_verdicts','generating_cause',
            'raw_simulation','parameters','required_acquisition','minimum_evidence','variant','answer_key','seed'}
    def inspect(obj):
        if isinstance(obj,dict):
            assert not (set(obj)&banned)
            for v in obj.values():inspect(v)
        elif isinstance(obj,list):
            for v in obj:inspect(v)
    public=release/'public';ids=json.loads((public/'index.json').read_text())['case_ids']
    packets={cid:json.loads((public/'cases'/f'{cid}.json').read_text()) for cid in ids}
    for path in public.rglob('*.json'):inspect(json.loads(path.read_text()))
    for cid,packet in packets.items():
        initial=set(packet['initial_sensors'])
        assert set(packet['initial_measurements'])==initial
        seen=[]
        def measurements(obj):
            if isinstance(obj,dict):
                if 'samples' in obj:
                    assert obj['sensor'] in initial
                    seen.append(obj['sensor'])
                for v in obj.values():measurements(v)
            elif isinstance(obj,list):
                for v in obj:measurements(v)
        measurements(packet);assert set(seen)==initial and len(seen)==len(initial)
        for payload in packet['initial_measurements'].values():
            assert set(payload)=={'id','sensor','unit','absolute_error_bound','samples'}
            assert all(set(s)=={'t_s','value','quality'} for s in payload['samples'])
    graph=json.loads((public/'graph.json').read_text())
    assert all('samples' not in e and all(k in e for k in ('subject','predicate','object','provenance','epistemic_status','applicable_assumptions','scope_limitations')) for e in graph['edges'])
    # Quantify a boundary hazard, not an invalid within-case payload: variants share traces.
    overlapping=[]
    for cid,packet in packets.items():
        hidden={s['id'] for s in packet['sensor_catalog']}-set(packet['initial_sensors'])
        if any(hidden & set(other['initial_sensors']) for ocid,other in packets.items() if ocid!=cid):
            overlapping.append(cid)
    # No production imports in this release. V5 original source bytes remain exact.
    for path in [release/'adapter.py',*(release/'integration').glob('*.py')]:
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):assert all(not n.name.startswith('petromind') for n in node.names)
            elif isinstance(node,ast.ImportFrom):assert not (node.module or '').startswith('petromind')
    base=frozen['base_commit']
    production=['petromind/atomic_auditor.py','petromind/reliable_auditor.py','petromind/scope_auditor.py','petromind/claim_auditor.py']
    for path in production:
        before=subprocess.check_output(['git','show',f'{base}:{path}'],cwd=repo)
        assert before==(repo/path).read_bytes(),path
    assert 'verified_causal_rule_unavailable' in (repo/'petromind/atomic_auditor.py').read_text()
    return {'status':'passed','public_freeze_entries':len(frozen['public_files']),
        'private_core_freeze_entries':len(core['files']),'public_case_count':len(ids),
        'private_vault_count':len(list((private/'build/private/vault').glob('*.json'))),
        'within_case_payload_leak_checks':'passed; initial sensors only; no private answer fields or generator metadata',
        'cross_case_sensor_overlap':bool(overlapping),'required_boundary':'one packet per fresh model context, tool-mediated access only; never mount the public corpus or private archive',
        'production_modules_unchanged':production,'synthetic_imports_production':False,
        'scenarios_verdicts_weights_changed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--release-root',required=True);p.add_argument('--private-root',required=True);p.add_argument('--repo-root',required=True);a=p.parse_args()
    print(json.dumps(verify(a.release_root,a.private_root,a.repo_root),indent=2))
