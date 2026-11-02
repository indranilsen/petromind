#!/usr/bin/env python3
"""Post-session owner-only ablation analysis; never imported by model runner."""
import argparse,json,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from petromind.eval_runner import read_jsonl
from research.sprint_c.interventions import VARIANTS
from research.sprint_c.accounting import SettlementLedger


def analyze(root,private,public_path):
    protocol=json.loads((root/'protocol.json').read_text());rows=read_jsonl(root/'suite/results.jsonl')
    refs=json.loads((private/'build/private/answer_key.json').read_text())['cases']
    scores={v:json.loads((root/f'suite/{v}-score.private.json').read_text()) for v in VARIANTS}
    completed={(r['task_id'],r['variant']) for r in rows if r['status']=='completed'}
    paired=[cid for cid in protocol['cases'] if all((cid,v) in completed for v in VARIANTS)]
    by_task={(r['task_id'],r['variant']):r for r in rows}
    methods={};details=[];projection=[]
    for variant in VARIANTS:
        cells=[r for r in rows if r['variant']==variant]
        counts={v:[0,0] for v in ('SUPPORTED','NOT_ESTABLISHED','CONTRADICTED')}
        confusion=Counter();literal_failures=[];correct=0;raw_correct=0;total=0;unsupported=0;incorrect_contra=0;abstention_errors=0;blanket=0
        tool_counts=Counter();retrieval_bytes=0;wasted=0;new_sensors=0;cache=0;repairs=0;case_results=[]
        for cid in protocol['cases']:
            row=by_task.get((cid,variant));scored=scores[variant]['cases'][cid]['atoms']
            if row:
                events=json.loads((root/f'suite/{cid}-{variant}/host-audit.private.json').read_text())
                packet=events[0]['result'];submission=row['assessment'];seen=set(packet['initial_sensors']);received={'model:M1'}|{x['id'] for x in packet['initial_measurements'].values()}
                for e in events[1:]:
                    name=e['tool'];result=e['result'];tool_counts[name]+=1
                    if name=='query_sensor' and 'sensor' in result:
                        if result['sensor'] in seen:cache+=1
                        else:
                            seen.add(result['sensor']);new_sensors+=1
                            wasted+=all(x['value'] is None for x in result['samples']) or any('FROZEN' in x['quality'] for x in result['samples'])
                        received.add(result['id'])
                    if name=='lookup_graph':received.update(x['id'] for x in result.get('edges',[]))
                    if name=='read_document' and 'id' in result:received.add(result['id'])
                    if name in ('lookup_graph','read_document'):retrieval_bytes+=len(json.dumps(result,sort_keys=True,separators=(',',':')).encode())
                    if name=='submit_audit' and 'error' in result:repairs+=1
                    projection.append({'case_id':cid,'variant':variant,'sequence':e['sequence'],'tool':name,
                        'request':e['arguments'] if name!='submit_audit' else {'submission':'owner-only'},
                        'returned_edge_ids':[x['id'] for x in result.get('edges',[])],
                        'document_id':result.get('id') if name=='read_document' else None,
                        'accepted':result.get('accepted',False),'error':result.get('error'),
                        'result_bytes':len(json.dumps(result,separators=(',',':')).encode()),'host_event_digest':e['digest']})
            else:
                packet=json.loads((Path(__file__).resolve().parents[1]/f'research/synthetic_challenge/public/cases/{cid}.json').read_text())
                submission=None;received=set()
            findings={f['statement']:f for f in (submission or {}).get('findings',[])}
            if findings and all(f['verdict']=='NOT_ESTABLISHED' for f in findings.values()):blanket+=1
            case_correct=0;case_raw=0
            for atom in packet['atomic_claims']:
                aid=atom['id'];s=scored[aid];expected=s['expected'];submitted=s['submitted'];f=findings.get(atom['statement'])
                counts[expected][1]+=1;counts[expected][0]+=s['correct_with_evidence']
                total+=1;correct+=s['correct_with_evidence'];raw_correct+=expected==submitted
                case_correct+=s['correct_with_evidence'];case_raw+=expected==submitted
                confusion[(expected,submitted or 'MISSING')]+=1
                unsupported+=atom['scope']=='diagnostic_conclusion' and submitted=='SUPPORTED' and expected!='SUPPORTED'
                incorrect_contra+=submitted=='CONTRADICTED' and expected!='CONTRADICTED'
                abstention_errors+=submitted=='NOT_ESTABLISHED' and expected!='NOT_ESTABLISHED'
                if expected==submitted and not s['correct_with_evidence']:
                    required=set(refs[cid]['minimum_evidence'].get(aid,[]))
                    literal_failures.append({'case_id':cid,'atom_id':aid,'missing_literal_citations':sorted(required-set(f['citations'])),
                                            'missing_received_evidence':sorted(required-received)})
            case_results.append({'case_id':cid,'correct':case_correct,'raw_matches':case_raw,'total_atoms':len(packet['atomic_claims']),
                                 'completed':bool(row and row['status']=='completed')})
            details.append({'case_id':cid,'variant':variant,'assessment':submission,'scored_atoms':scored})
        recall={v:a/b if b else None for v,(a,b) in counts.items()}
        paired_cells=[c for c in case_results if c['case_id'] in paired]
        methods[variant]={'completed':sum(r['status']=='completed' for r in cells),'attempted':len(cells),'planned':7,
            'evidence_qualified_correct':correct,'atomic_count':total,'evidence_qualified_accuracy':correct/total,
            'raw_verdict_matches':raw_correct,'raw_verdict_accuracy':raw_correct/total,
            'recall':recall,'macro_recall':sum(x for x in recall.values() if x is not None)/len([x for x in recall.values() if x is not None]),
            'literal_citation_contract_failures':len(literal_failures),'unreceived_citations_in_accepted_submissions':0 if len(cells)==7 else None,
            'incorrect_CONTRADICTED':incorrect_contra,'reference_disagreeing_NOT_ESTABLISHED':abstention_errors,
            'unsupported_causal_SUPPORTED':unsupported,'blanket_abstention_cases':blanket,
            'confusion_matrix':[{ 'reference':a,'submitted':b,'count':n} for (a,b),n in sorted(confusion.items())],
            'mechanical_points_of_29':scores[variant]['mechanical_points_of_29'],'semantic_citation_entailment':None,
            'missing_premise_quality':None,'next_evidence_usefulness':None,'full_100_point_total':None,
            'paired_correct':sum(c['correct'] for c in paired_cells),'paired_atoms':sum(c['total_atoms'] for c in paired_cells),
            'tool_counts':dict(tool_counts),'retrieval_bytes':retrieval_bytes,'new_sensor_count':new_sensors,
            'unavailable_or_frozen_requests':wasted,'cache_hits':cache,'validation_rejections':repairs,
            'http_attempts':sum(r['requests'] for r in cells),
            'input_tokens':sum(r['usage'].get('input_tokens',0) for r in cells),
            'output_tokens':sum(r['usage'].get('output_tokens',0) for r in cells),
            'estimated_usage_cost_usd':sum(r['usage']['estimated_cost_usd'] for r in cells),
            'latency_seconds':sum(r['latency_seconds'] for r in cells),
            'private_literal_failure_details':literal_failures,'case_metrics':case_results}
    comparisons={}
    for v in ('V1','V2','V3'):
        def pair_errors(method):
            return sum(a['submitted']=='CONTRADICTED' and a['expected']!='CONTRADICTED'
                       for d in details if d['variant']==method and d['case_id'] in paired
                       for a in d['scored_atoms'].values())
        def pair_literals(method):
            return sum(d['case_id'] in paired for d in methods[method]['private_literal_failure_details'])
        comparisons[v]={'complete_matched_cases_only':len(paired),
            'additional_correct_vs_V0':methods[v]['paired_correct']-methods['V0']['paired_correct'],
            'fewer_incorrect_contradictions':pair_errors('V0')-pair_errors(v),
            'fewer_literal_failures':pair_literals('V0')-pair_literals(v),
            'interpretation':'Incomplete suite; descriptive matched subset only, no generalization claim.'}
    all_rows=read_jsonl(root/'pilot/results.jsonl')+rows
    try:accounting=SettlementLedger(protocol['ledger_directory']).summary()
    except (ValueError,OSError):
        accounting=json.loads((root/'ACCOUNTING_BLOCKED.json').read_text())
    report={'protocol_id':protocol['protocol_id'],'complete_four_way_cases':paired,'complete_four_way_count':len(paired),
        'methods':methods,'comparisons':comparisons,'details':details,'trace_projection':projection,
        'accounting':accounting,
        'total_http_attempts':sum(r['requests'] for r in all_rows),
        'usage_estimated_cost_all_stages_usd':sum(r['usage']['estimated_cost_usd'] for r in all_rows),
        'semantic_review_status':'UNGRADED: qualified independent review unavailable',
        'interpretation_limit':'Development reuse of seven correlated cases from one synthetic incident; one sample per cell. No population or independent generalization claim.'}
    (root/'analysis.private.json').write_text(json.dumps(report,indent=2)+'\n')
    public={k:v for k,v in report.items() if k not in ('methods','details')}
    public['methods']={v:{k:x for k,x in m.items() if k not in ('private_literal_failure_details','case_metrics')} for v,m in methods.items()}
    Path(public_path).write_text(json.dumps(public,indent=2)+'\n')
    print(json.dumps({'complete_four_way_cases':paired,'comparisons':comparisons,'accounting':report['accounting']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--private-root',required=True);p.add_argument('--public-report',required=True);a=p.parse_args()
    analyze(Path(a.out).resolve(),Path(a.private_root).resolve(),a.public_report)
