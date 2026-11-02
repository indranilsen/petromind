#!/usr/bin/env python3
"""Offline scoring/reviewer export even when billing integrity blocks execution.

Does not load or alter the spending ledger and never instantiates or calls an HTTP client.
"""
import argparse,json,secrets,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from petromind.eval_protocol import digest
from research.synthetic_challenge.integration.verify_readiness import verify


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--private-root',required=True);a=p.parse_args()
    root=Path(a.out).resolve();private=Path(a.private_root).resolve();repo=Path(__file__).resolve().parents[1];release=repo/'research/synthetic_challenge'
    verify(release,private,repo)
    protocol=json.loads((root/'protocol.json').read_text())
    assert digest({k:v for k,v in protocol.items() if k!='protocol_id'})==protocol['protocol_id']
    for stage in ('pilot','suite'):
        folder=root/stage
        rows=[json.loads(x) for x in (folder/'results.jsonl').read_text().splitlines()]
        packets=[];unblind={}
        for variant in ('V0','V1','V2','V3'):
            audits={}
            for row in rows:
                if row['variant']!=variant:continue
                cid=row['task_id'];events=json.loads((folder/f'{cid}-{variant}/host-audit.private.json').read_text())
                assert events[-1]['digest']==row['host_final_digest']
                assert events[0]['result']==json.loads((release/f'public/cases/{cid}.json').read_text())
                assert cid not in audits;audits[cid]=events
                rid=secrets.token_hex(12);unblind[rid]={'case_id':cid,'variant':variant,'stage':stage}
                packets.append({'review_id':rid,'public_packet':events[0]['result'],'tool_events':events[1:],
                    'submission':row['assessment'],'reviewer':None,
                    'review':{k:None for k in ('scientific_support','citation_entailment','affirmative_contradiction_vs_missing_support',
                        'model_applicability','calibration_limits','missing_premises','next_evidence_usefulness','unjustified_abstention')}})
            audit_path=folder/f'{variant}-audits.private.json';score_path=folder/f'{variant}-score.private.json'
            with audit_path.open('x') as f:f.write(json.dumps(audits)+'\n')
            with score_path.open('x') as f:
                subprocess.run([sys.executable,str(private/'evaluate.py'),'--public',str(release/'public'),
                    '--key',str(private/'build/private/answer_key.json'),'--audits',str(audit_path)],stdout=f,check=True)
        packets.sort(key=lambda x:x['review_id'])
        for name,value in [('human-review-packets.private.json',packets),('reviewer-unblinding.private.json',unblind)]:
            with (folder/name).open('x') as f:f.write(json.dumps(value,indent=2)+'\n')
        print(stage, 'offline scored;',len(packets),'blinded review packets; semantic grades null')
if __name__=='__main__':main()
