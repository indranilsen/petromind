"""Owner-only integration smoke. No API client, credentials, reference-guided agent.

The intentionally generic all-NOT_ESTABLISHED assessment is a transport fixture,
not a reference answer or efficacy result. Detailed score/transcript stay private.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--release-root',required=True)
    p.add_argument('--private-root',required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    release=Path(a.release_root).resolve();private=Path(a.private_root).resolve()
    out=Path(a.out).resolve();out.mkdir(mode=0o700) # must be fresh
    case_id='c-13df'
    audit_path=out/'host-audit.private.json'
    host=subprocess.Popen([sys.executable,str(release/'integration/trusted_host.py'),
        '--release-root',str(release),'--private-root',str(private),'--case',case_id,
        '--audit-out',str(audit_path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,text=True,env={'PATH':os.defpath,'PYTHONNOUSERSITE':'1'})
    def receive():
        line=host.stdout.readline()
        if not line:raise RuntimeError('host returned no response')
        return json.loads(line)['result']
    def call(name,arguments):
        host.stdin.write(json.dumps({'name':name,'arguments':arguments})+'\n');host.stdin.flush()
        return receive()
    packet=receive()
    assert packet['case_id']==case_id and 'SYN-Q-PROD' not in packet['initial_measurements']
    observed=call('query_sensor',{'sensor':'SYN-Q-PROD'})
    assert observed['sensor']=='SYN-Q-PROD' and len(observed['samples'])==81
    edges=call('lookup_graph',{'node':'P-TPT','hops':2})
    assert edges['edges']
    findings=[]
    for atom in packet['atomic_claims']:
        findings.append({'statement':atom['statement'],'scope':atom['scope'],'premises':['Integration transport fixture only.'],
            'basis':'unsupported','verdict':'NOT_ESTABLISHED','citations':['model:M1'],
            'missing_premise':'This generic smoke fixture performs no physical entailment analysis.',
            'next_evidence':{'kind':'no_verified_discriminating_test','target':'','purpose':'Not a scientific assessment.'},
            'justification':'Exercise structured submission without consulting private reference answers.'})
    assessment={'verdict':'NOT_ESTABLISHED','findings':findings,'numeric_observations':[]}
    accepted=call('submit_audit',assessment)
    assert accepted.get('accepted') is True
    host.stdin.close();host.wait(timeout=10)
    assert host.returncode==0 and not host.stderr.read()
    events=json.loads(audit_path.read_text())
    assert [e['tool'] for e in events]==['initial_packet','query_sensor','lookup_graph','submit_audit']
    audits=out/'suite-audits.private.json';audits.write_text(json.dumps({case_id:events})+'\n')
    score_path=out/'score.private.json'
    # Separate evaluator process reads the answer key AFTER the host has exited.
    with score_path.open('w') as score:
        subprocess.run([sys.executable,str(private/'evaluate.py'),'--public',str(release/'public'),
            '--key',str(private/'build/private/answer_key.json'),'--audits',str(audits)],
            check=True,stdout=score,env={'PATH':os.defpath,'PYTHONNOUSERSITE':'1'})
    result=json.loads(score_path.read_text())
    assert result['cases'][case_id]['accepted']
    assert sum(c['accepted'] for c in result['cases'].values())==1
    assert result['total'] is None and result['semantic_review_required']
    report={'status':'passed','coverage':'one accepted case; other six absent and scored as missing by unchanged suite evaluator',
        'initial_sensor_count':len(packet['initial_sensors']),'new_sensor_requests':1,
        'charged_sensors':len(result['cases'][case_id]['charged_sensors']),
        'graph_edges_returned':len(edges['edges']),'assessment_accepted':True,
        'score_produced':True,'mechanical_suite_points_of_29':result['mechanical_points_of_29'],
        'semantic_total':None,'model_requests':0,'estimated_cost_usd':0,
        'audit_final_digest':events[-1]['digest'],
        'private_score_sha256':hashlib.sha256(score_path.read_bytes()).hexdigest()}
    (out/'smoke-summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
