#!/usr/bin/env python3
"""Owner-only post-run analysis. Never imported by the model orchestrator.

Uses the frozen scorer's output; does not fabricate semantic grades. Run only
when model execution is over. Public projection omits samples and reference keys.
"""
import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from petromind.eval_runner import read_jsonl
from research.muse_integration.budget import IntegrationLedger


def summarize(root,private):
    protocol=json.loads((root/'protocol.json').read_text())
    rows=read_jsonl(root/'suite/results.jsonl')
    refs=json.loads((private/'build/private/answer_key.json').read_text())['cases']
    scores={v:json.loads((root/f'suite/{v}-score.private.json').read_text()) for v in ('B','E')}
    complete={(r['task_id'],r['variant']) for r in rows if r['status']=='completed'}
    paired=[c for c in protocol['cases'] if {(c,'B'),(c,'E')}<=complete]
    methods={};case_metrics=[];trace_projection=[]
    for variant in ('B','E'):
        selected=[r for r in rows if r['variant']==variant]
        counter=Counter();errors=[];retrieval=[]
        for r in selected:
            cid=r['task_id'];events=json.loads((root/f'suite/{cid}-{variant}/host-audit.private.json').read_text())
            initial=set(events[0]['result']['initial_sensors']);seen=set(initial)
            received={'model:M1'}|{m['id'] for m in events[0]['result']['initial_measurements'].values()}
            atom_scopes={a['id']:a['scope'] for a in events[0]['result']['atomic_claims']}
            evidence={};context_size=0;edges=set();docs=set();sensor_order=[];wasted=[];cache=0
            for e in events[1:]:
                tool=e['tool'];result=e['result'];counter['tool_calls']+=1;counter[tool]+=1
                if tool=='query_sensor' and 'sensor' in result:
                    s=result['sensor'];sensor_order.append(s)
                    if s in seen:cache+=1
                    else:
                        seen.add(s)
                        if all(x['value'] is None for x in result['samples']) or any('FROZEN' in x['quality'] for x in result['samples']):wasted.append(s)
                    received.add(result['id'])
                if tool=='read_document' and 'id' in result:docs.add(result['id']);received.add(result['id'])
                if tool=='lookup_graph':
                    edges.update(x['id'] for x in result.get('edges',[]));received.update(x['id'] for x in result.get('edges',[]))
                if tool in ('lookup_graph','read_document'):
                    context_size+=len(json.dumps(result,sort_keys=True,separators=(',',':')).encode())
                if tool=='submit_audit' and 'error' in result:counter['validation_rejections']+=1
                trace_projection.append({'case_id':cid,'variant':variant,'sequence':e['sequence'],
                    'tool':tool,'request':e['arguments'] if tool in ('query_sensor','lookup_graph','read_document') else {'submission_arguments':'owner-only'},
                    'returned_edge_ids':[x['id'] for x in result.get('edges',[])],
                    'document_id':result.get('id') if tool=='read_document' else None,
                    'accepted':result.get('accepted',False),'error':result.get('error'),
                    'result_bytes':len(json.dumps(result,separators=(',',':')).encode()),'host_event_digest':e['digest']})
            scored=scores[variant]['cases'][cid]['atoms'];required={x for aid in scored for x in refs[cid]['minimum_evidence'].get(aid,[])}
            required_knowledge={x for x in required if x.startswith(('doc:','edge:','history:'))}
            missing_acquired=sorted(required-received)
            for aid,a in scored.items():
                if not a['correct_with_evidence']:
                    # Observable classification only. Not a claim about private reasoning.
                    errors.append({'case_id':cid,'atom_id':aid,'expected':a['expected'],'submitted':a['submitted'],
                        'category':'incomplete_submission' if a['submitted'] is None else
                         'required_evidence_or_citation_missing' if a['submitted']==a['expected'] else
                         'unsupported_causal_support' if a['submitted']=='SUPPORTED' and atom_scopes[aid]=='diagnostic_conclusion' else 'verdict_disagreement',
                        'missing_required_receipts':sorted(set(refs[cid]['minimum_evidence'].get(aid,[]))-received),
                        'missing_required_citations':sorted(set(refs[cid]['minimum_evidence'].get(aid,[]))-set(next((f['citations'] for f in (r['assessment'] or {}).get('findings',[]) if f['statement']==next(x['statement'] for x in events[0]['result']['atomic_claims'] if x['id']==aid)),[])))})
            data={'case_id':cid,'variant':variant,'status':r['status'],'reason':r['reason'],
                'correct_atoms':sum(a['correct_with_evidence'] for a in scored.values()),'atoms':len(scored),
                'required_evidence_not_received':missing_acquired,'required_knowledge_receipt_recall':len(required_knowledge&received)/len(required_knowledge) if required_knowledge else None,
                'context_bytes':context_size,'unique_graph_edges':len(edges),'documents':sorted(docs),
                'sensor_choices':sensor_order,'cache_hits':cache,'wasted_unavailable_or_frozen':wasted,
                'charged_sensors':sorted(seen),'semantic_relevance_precision':None,
                'independent_citation_entailment':None,'missing_premise_quality':None,
                'tool_counts':dict(Counter(e['tool'] for e in events[1:])),
                'assessment':r['assessment'],'scored_atoms':scored,'requests':r['requests'],
                'latency_seconds':r['latency_seconds'],'usage':r['usage']}
            case_metrics.append(data);retrieval.append(data)
        def metric(cases):
            counts={v:[0,0] for v in ('SUPPORTED','NOT_ESTABLISHED','CONTRADICTED')}
            causal_errors=0;rejected=0;total_correct=0;total=0;raw_matches=0
            for cid in cases:
                packet=json.loads((Path(__file__).resolve().parents[1]/f'research/synthetic_challenge/public/cases/{cid}.json').read_text())
                scopes={a['id']:a['scope'] for a in packet['atomic_claims']}
                for aid,a in scores[variant]['cases'][cid]['atoms'].items():
                    counts[a['expected']][1]+=1;counts[a['expected']][0]+=a['correct_with_evidence']
                    total+=1;total_correct+=a['correct_with_evidence'];raw_matches+=a['submitted']==a['expected']
                    causal_errors+=scopes[aid]=='diagnostic_conclusion' and a['submitted']=='SUPPORTED' and a['expected']!='SUPPORTED'
                    rejected+=a['expected']=='NOT_ESTABLISHED' and a['correct_with_evidence']
            return {'correct_atoms':total_correct,'total_atoms':total,'accuracy':total_correct/total if total else None,'raw_verdict_matches':raw_matches,'raw_verdict_accuracy':raw_matches/total if total else None,
                'recall':{k:a/b if b else None for k,(a,b) in counts.items()},
                'incorrectly_supported_causal_claims':causal_errors,'correctly_rejected_unestablished':rejected}
        methods[variant]={'attempted':len(selected),'completed':sum(r['status']=='completed' for r in selected),
            'planned_cases':7,'planned_case_metrics':metric(protocol['cases']), 'paired_completed_metrics':metric(paired),
            'mechanical_points_of_29':scores[variant]['mechanical_points_of_29'],'semantic_points':None,'total_of_100':None,
            'unsupported_matches_count':len(scores[variant]['unsupported_matches']),
            'tool_counts':dict(counter),'requests':sum(r['requests'] for r in selected),
            'input_tokens':sum(r['usage'].get('input_tokens',0) for r in selected),
            'output_tokens':sum(r['usage'].get('output_tokens',0) for r in selected),
            'known_usage_cost_usd':sum(r['usage']['estimated_cost_usd'] for r in selected),
            'latency_seconds':sum(r['latency_seconds'] for r in selected),
            'retrieved_context_bytes':sum(x['context_bytes'] for x in retrieval),
            'mean_context_bytes':statistics.mean(x['context_bytes'] for x in retrieval) if retrieval else None,
            'observed_error_categories':dict(Counter(e['category'] for e in errors)),
            'private_errors':errors}
    all_rows=read_jsonl(root/'pilot/results.jsonl')+rows
    ledger=IntegrationLedger(protocol['ledger_directory'])
    report={'protocol_id':protocol['protocol_id'],'paired_complete_cases':paired,'paired_complete_count':len(paired),
        'suite_planned_case_count':7,'methods':methods,'case_details':case_metrics,
        'spending':ledger.summary(),'total_model_requests':sum(r['requests'] for r in all_rows),
        'total_known_usage_cost_usd':sum(r['usage']['estimated_cost_usd'] for r in all_rows),
        'total_input_tokens':sum(r['usage'].get('input_tokens',0) for r in all_rows),
        'total_output_tokens':sum(r['usage'].get('output_tokens',0) for r in all_rows),
        'responses_with_usage':sum(r['usage'].get('responses_with_usage',0) for r in all_rows),
        'total_cached_input_tokens':sum(r['usage'].get('cached_tokens',0) for r in all_rows),
        'unknown_usage_http_attempts':sum(r['usage'].get('http_attempts_without_usage',0) for r in all_rows),
        'total_latency_seconds':sum(r['latency_seconds'] for r in all_rows),
        'semantic_review_required':True,'retrieval_precision_and_completeness_semantics_ungraded':True,
        'verdict':'INCONCLUSIVE: incomplete paired suite and semantic review pending' if len(paired)<7 else 'Exploratory mechanical result; human semantic review pending',
        'scope':'Seven correlated synthetic tasks, one sample per variant/cell; pilot duplication not independent.'}
    (root/'analysis.private.json').write_text(json.dumps(report,indent=2)+'\n')
    public={k:v for k,v in report.items() if k not in ('case_details','methods')}
    public['methods']={v:{k:x for k,x in m.items() if k!='private_errors'} for v,m in methods.items()}
    public['trace_projection']=trace_projection
    return report,public

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--private-root',required=True);p.add_argument('--public-report',required=True);a=p.parse_args()
    report,public=summarize(Path(a.out).resolve(),Path(a.private_root).resolve())
    Path(a.public_report).write_text(json.dumps(public,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('case_details','methods')},indent=2))
