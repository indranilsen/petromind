"""Frozen private mechanical scorer; separate groups and blinded human packets."""
import json,secrets,subprocess,sys,tempfile
from pathlib import Path
from petromind.eval_protocol import digest
from . import study

VARIANTS=('V0','V1','V2','V3')
VERDICTS=('SUPPORTED','NOT_ESTABLISHED','CONTRADICTED')


def metrics(scored,matched,rows,public):
    confusion={e:{s:0 for s in (*VERDICTS,'MISSING')} for e in VERDICTS};counts={e:[0,0] for e in VERDICTS}
    raw=0;qualified=0;literal_fail=0;false_contra=0;abstain=0;unsupported=0;percase={}
    for cid in matched:
        scopes={a['id']:a['scope'] for a in study.read(public/'cases'/f'{cid}.json')['atomic_claims']};correct=0
        for aid,a in scored['cases'][cid]['atoms'].items():
            expected,submitted=a['expected'],a['submitted'];hit=bool(a['correct_with_evidence']);same=expected==submitted
            confusion[expected][submitted if submitted in VERDICTS else 'MISSING']+=1
            counts[expected][1]+=1;counts[expected][0]+=hit;qualified+=hit;correct+=hit;raw+=same;literal_fail+=same and not hit
            false_contra+=submitted=='CONTRADICTED' and expected!='CONTRADICTED'
            abstain+=submitted=='NOT_ESTABLISHED' and expected!='NOT_ESTABLISHED'
            unsupported+=scopes[aid]=='diagnostic_conclusion' and submitted=='SUPPORTED' and expected!='SUPPORTED'
        percase[cid]=correct
    return {'matched_cases':len(matched),'matched_atoms':sum(n[1] for n in counts.values()),'evidence_qualified_correct':qualified,
            'raw_verdict_matches':raw,'recall':{k:a/b if b else None for k,(a,b) in counts.items()},'confusion':confusion,
            'incorrect_contradictions':false_contra,'reference_disagreeing_abstentions':abstain,'unsupported_causal_support':unsupported,
            'literal_citation_failures_among_raw_matches':literal_fail,'per_case_evidence_qualified_correct':percase,
            'attempted_cells':len(rows),'completed_cells':sum(r['status']=='completed' for r in rows),
            'http_requests':sum(r['requests'] for r in rows),'known_usage_estimate_usd':sum(r['known_usage_estimate_usd'] for r in rows),
            'held_usd':sum(r['unresolved_request_holds_usd'] for r in rows),'latency_seconds':sum(r['latency_seconds'] for r in rows),
            'charged_sensor_uses_known':sum(len(r['charged_sensors']) for r in rows),'cells_with_unknown_sensor_count':sum(not r['charged_sensors_complete'] for r in rows),'semantic_entailment':None,
            'correct_abstention_semantic_review':None,'missing_premise_quality':None,'next_evidence_usefulness':None}


def score_locked(j,root,results):
    phase=root/'phase2';inputs=digest({'plan_id':j.plan['plan_id'],'results':results});scores=phase/'scores';scores.mkdir(mode=0o700,exist_ok=True)
    index=scores/f'index-{inputs}.json'
    if index.exists():
        target=scores/study.read(index)['directory'];study.verify_package(target);return study.read(target/'coverage.json')
    output=Path(tempfile.mkdtemp(prefix='score-',dir=scores));private=root/'evaluator/private_sprint_b';public=study.RELEASE/'public'
    frozen=study.read(root/'preserved/PetroMind-Sprint-C-PRIVATE/sprint-c-v2/protocol.json')
    coverage={'version':'sprint-c-phase2-independent-groups-v1','input_digest':inputs,'frozen_protocol_id':frozen['protocol_id'],
              'execution_plan_id':j.plan['plan_id'],'groups':{},'semantic_grades':None,
              'limitations':['Seven correlated, previously inspected synthetic development cases; confirmatory means a fresh fixed execution, not unseen benchmark generalization.',
                             'No pooling historical/remaining/confirmatory/repeat protocols. Repeated attempts are not independent samples. All failed attempts remain visible.',
                             'No population significance or semantic grades without qualified independent review.']}
    packets=[];mapping={}
    for group in dict.fromkeys(r['group'] for r in results):
        selected=[r for r in results if r['group']==group];target=output/group;target.mkdir(mode=0o700)
        completed={(r['task_id'],r['variant']) for r in selected if r['status']=='completed'}
        matched=[c for c in frozen['cases'] if all((c,v) in completed for v in VARIANTS)]
        group_metrics={};mechanical={}
        for variant in VARIANTS:
            audits={};vrows=[r for r in selected if r['variant']==variant]
            for row in vrows:
                source=phase/'cells'/group/f"{row['task_id']}-{variant}";host=source/'host-audit.private.json'
                if not host.exists() or not row['host_capture_valid']:continue
                events=study.read(host);audits[row['task_id']]=events
                packet=study.read(public/'cases'/f"{row['task_id']}.json");assessment=row['assessment'] or {};findings=assessment.get('findings',[])
                identifier=secrets.token_hex(12);mapping[identifier]={'group':group,'case_id':row['task_id'],'variant':variant,'status':row['status']}
                propositions=[]
                for atom in packet['atomic_claims']:
                    finding=next((f for f in findings if f.get('statement')==atom['statement']),None)
                    propositions.append({'atomic_proposition':atom,'submitted_finding':finding,
                                         'semantic_entailment':None,'missing_premise_quality':None,'next_evidence_usefulness':None})
                packets.append({'review_id':identifier,'public_packet':events[0]['result'],'received_tool_evidence':events[1:],
                                'propositions':propositions,'submission':row['assessment'],'semantic_grades':None})
            audit_path=target/f'{variant}-audits.private.json';study.write(audit_path,audits)
            result=subprocess.check_output([sys.executable,str(private/'evaluate.py'),'--public',str(public),
                    '--key',str(private/'build/private/answer_key.json'),'--audits',str(audit_path)],text=True,stderr=subprocess.PIPE)
            scored=json.loads(result);study.write(target/f'{variant}-score.private.json',scored)
            group_metrics[variant]=metrics(scored,matched,vrows,public)
            mechanical[variant]=scored['mechanical_points_of_29']
        coverage['groups'][group]={'matched_case_ids':matched,'complete_seven_case_coverage':len(matched)==7,
              'metrics':group_metrics,'full_plan_mechanical_totals_not_paired_effects':mechanical,
              'failed_attempts':[{'case':r['task_id'],'variant':r['variant'],'reason':r['reason']} for r in selected if r['status']!='completed']}
    study.write(output/'blinded-review-packets.private.json',sorted(packets,key=lambda p:p['review_id']))
    study.write(output/'reviewer-unblinding.private.json',mapping);study.write(output/'coverage.json',coverage)
    study.write(output/'FILE_MANIFEST.json',{str(p.relative_to(output)):study.sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    study.write(index,{'directory':output.name,'input_digest':inputs})
    return coverage
