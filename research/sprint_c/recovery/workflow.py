"""Local-only workflow. No hosted paid execution, no failed/completed-cell replay."""
import argparse,json,os,shutil,subprocess,sys,time,secrets,fcntl
from dataclasses import asdict
from pathlib import Path
from petromind.agent import AgentConfig,run_tool_agent
from petromind.audit import canonical
from petromind.eval_protocol import digest,source_digest
from petromind.eval_runner import read_jsonl,append_json,usage_and_cost
from research.muse_integration.bridge import Bridge
from research.sprint_c.client import SettlingClient
from research.sprint_c.runner import decode
from research.synthetic_challenge.integration.verify_readiness import verify
from .reconcile import propose,verify_proposal,verify_package
from .ledger import LocalLedger,approval,verify_review
from .storage import validate,cross,certify,verify_certificate
from . import durability

REPO=Path(__file__).resolve().parents[3]
RELEASE=REPO/'research/synthetic_challenge'


def read(path):return json.loads(Path(path).read_text())
def write(path,value):
    durability.durable_text(path,json.dumps(value,indent=2)+'\n')

def append_json(path,value):
    durability.durable_text(path,canonical(value)+'\n',exclusive=False)


def plan(package):
    package=Path(package).resolve();verify_package(package)
    p=read(package/'sprint-c-v2/protocol.json')
    if p['production_digest']!=source_digest():raise ValueError('frozen_production_source_changed')
    pilot=read_jsonl(package/'sprint-c-v2/pilot/results.jsonl')
    if len(pilot)!=4 or any(r['status']!='completed' for r in pilot):raise ValueError('frozen_pilot_incomplete')
    attempted={(r['task_id'],r['variant']) for r in read_jsonl(package/'sprint-c-v2/suite/attempts.jsonl')}
    cells=[{'task_id':c,'variant':v} for c in p['cases'] for v in p['order'][c] if (c,v) not in attempted]
    value={'version':'local-remaining-frozen-cells-v1','scientific_protocol_id':p['protocol_id'],
           'cells':cells,'excluded_original_attempts':[list(x) for x in sorted(attempted)],
           'scientific_inputs_digest':digest({k:p[k] for k in ('prompts','tools','agent_config','cases','order','retrieval','public_root_digest')}),
           'same_cell_retries':0}
    value['plan_id']=digest(value);return value


def gates(package,proposal_path,review_path,certificate_path,db_path,owner_local):
    if not owner_local:raise ValueError('explicit_trusted_local_owner_required')
    package=Path(package).resolve();p=read(proposal_path);review=read(review_path)
    if propose(package)!=p:raise ValueError('proposal_does_not_match_preserved_evidence')
    verify_review(p,review);c=verify_certificate(certificate_path)
    parent=Path(db_path).resolve().parent
    if not parent.is_dir() or parent.stat().st_dev!=Path(c['owner_directory']).stat().st_dev:raise ValueError('database_not_on_validated_filesystem')
    registry=durability.authorization_registry(p).resolve()
    for location in (parent,registry.parent):
        existing=location
        while not existing.exists():existing=existing.parent
        facts=durability.local_surface(existing)
        if not facts['local_macos_approved'] or existing.stat().st_dev!=parent.stat().st_dev:raise ValueError('state_and_registry_require_certified_local_volume')
    if registry.exists():
        if read(registry)!={'review_id':review['review_id'],'database':str(Path(db_path).resolve())}:raise ValueError('reconciliation_already_activated_elsewhere')
    elif Path(db_path).exists():raise ValueError('unregistered_continuation_database')
    return p,review,c


def run(package,proposal_path,review_path,certificate_path,db_path,plan_path,out,private,owner_local):
    package=Path(package).resolve();out=Path(out).resolve();private=Path(private).resolve()
    p,review,c=gates(package,proposal_path,review_path,certificate_path,db_path,owner_local)
    if str(out)!=review.get('continuation_output'):raise ValueError('reviewed_output_directory_changed')
    frozen=read(package/'sprint-c-v2/protocol.json');expected=plan(package)
    if read(plan_path)!=expected:raise ValueError('remaining_cell_plan_modified')
    verify(RELEASE,private,REPO)
    if not os.environ.get('MODEL_API_KEY'):raise ValueError('MODEL_API_KEY_missing')
    ledger=LocalLedger(db_path,p,review)
    try:
        if not out.exists():out.mkdir(mode=0o700,parents=True);durability.sync_dir(out.parent)
        identity={'version':'local-accounting-continuation-v1','scientific_protocol_id':frozen['protocol_id'],
                  'proposal_id':p['proposal_id'],'review_id':review['review_id'],'plan_id':expected['plan_id'],
                  'storage_certificate_id':c['certificate_id'],'recovery_code_digest':digest({str(p.relative_to(REPO)):__import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob('*.py'))}),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()}
        if (out/'continuation.json').exists():
            if read(out/'continuation.json')!=identity:raise ValueError('continuation_identity_changed')
        else:write(out/'continuation.json',identity)
        cells=out/'suite';cells.mkdir(exist_ok=True);durability.sync_dir(out)
        attempted={(r['task_id'],r['variant']) for r in read_jsonl(cells/'attempts.jsonl')}
        prior_monetary_tasks={(r['task']['task_id'],r['task']['variant']) for r in ledger.state()[1].values()}
        if not prior_monetary_tasks<=attempted:raise ValueError('missing_continuation_capture_records')
        protocol={**frozen,'platform_proxy':False}
        for task in expected['cells']:
            key=(task['task_id'],task['variant'])
            if key in attempted:continue
            append_json(cells/'attempts.jsonl',task)
            cell=cells/f'{key[0]}-{key[1]}';cell.mkdir(mode=0o700);durability.sync_dir(cells)
            bridge=None;client=None;start=time.monotonic()
            try:
                bridge=Bridge(RELEASE,private,key[0],cell/'host-audit.private.json','B')
                client=SettlingClient(protocol,ledger,{**task,'stage':'local_continuation'})
                result=run_tool_agent(bridge,client,AgentConfig(**frozen['agent_config']),instructions=frozen['prompts'][key[1]],
                    tools=frozen['tools'],initial_history=[{'role':'user','content':[{'type':'input_text','text':canonical(bridge.packet)}]}],
                    prompt_version='sprint-c-citation-verdict-v2',submission_reason='synthetic_assessment_submitted',
                    is_complete=lambda:bridge.result is not None,stop_reason=lambda:bridge.stop,decode_arguments=decode,
                    on_event=lambda e:append_json(cell/'events.jsonl',asdict(e)))
                row={**task,'protocol_id':frozen['protocol_id'],'stage':'local_continuation','status':result.status,'reason':result.reason,
                     'requests':result.requests,'usage':usage_and_cost(result.events,result.requests,frozen['prices']),
                     'assessment':bridge.result,'latency_seconds':time.monotonic()-start,'charged_sensors':sorted(bridge.observed)}
            except Exception as error:
                # Exception messages can include transport data: record only the class.
                _,reservations,settlements,_,_=ledger.state()
                cell_reservations={rid for rid,r in reservations.items() if (r['task']['task_id'],r['task']['variant'])==key}
                requests=len(cell_reservations)
                verified=[s for rid,s in settlements.items() if rid in cell_reservations]
                row={**task,'protocol_id':frozen['protocol_id'],'stage':'local_continuation','status':'failed',
                     'reason':'local_exception_'+type(error).__name__,'requests':requests,
                     'usage':{'responses_with_usage':len(verified),'estimated_cost_usd':sum(s['settled_nusd'] for s in verified)/1e9},'assessment':None,
                     'latency_seconds':time.monotonic()-start,'charged_sensors':sorted(bridge.observed) if bridge else []}
            finally:
                if client:client.close()
                if bridge:bridge.close()
            row['host_final_digest']=None
            if (cell/'host-audit.private.json').exists():
                with (cell/'host-audit.private.json').open('r+') as capture:durability.sync_file(capture.fileno())
                row['host_final_digest']=read(cell/'host-audit.private.json')[-1]['digest']
            write(cell/'result.json',row);append_json(cells/'results.jsonl',row)
            print(canonical({**task,'status':row['status'],'reason':row['reason'],'accounting':ledger.summary()}),flush=True)
            if row['status']!='completed':return {'status':'STOPPED_NO_RETRY','reason':row['reason'],'accounting':ledger.summary()}
        return {'status':'PERMITTED_CELLS_FINISHED','accounting':ledger.summary()}
    finally:ledger.close()


def _score_unlocked(package,out,private,destination):
    package=Path(package).resolve();out=Path(out).resolve();private=Path(private).resolve();destination=Path(destination).resolve()
    verify_package(package);verify(RELEASE,private,REPO)
    expected=plan(package)
    identity=read(out/'continuation.json')
    if identity['plan_id']!=expected['plan_id'] or identity['scientific_protocol_id']!=expected['scientific_protocol_id']:raise ValueError('continuation_scientific_identity_changed')
    allowed={(t['task_id'],t['variant']) for t in expected['cells']}
    old=package/'sprint-c-v2/suite';new=out/'suite'
    oldrows=read_jsonl(old/'results.jsonl');newrows=read_jsonl(new/'results.jsonl')
    if any((x['task_id'],x['variant']) not in allowed for x in newrows) or len({(x['task_id'],x['variant']) for x in newrows})!=len(newrows):raise ValueError('cell_replay_or_unknown_cell')
    destination.mkdir(mode=0o700);suite=destination/'suite';suite.mkdir()
    # Copies are analysis artifacts, never edits to original host or money logs.
    for source,rows in ((old,oldrows),(new,newrows)):
        for row in rows:shutil.copytree(source/f"{row['task_id']}-{row['variant']}",suite/f"{row['task_id']}-{row['variant']}")
    write(suite/'all-cells.private.json',oldrows+newrows)
    packets=[];mapping={}
    for v in ('V0','V1','V2','V3'):
        audits={}
        for row in oldrows+newrows:
            if row['variant']!=v:continue
            if row['host_final_digest'] is None:
                if row['status']=='completed':raise ValueError('completed_cell_missing_host_capture')
                continue
            events=read(suite/f"{row['task_id']}-{v}/host-audit.private.json")
            if events[-1]['digest']!=row['host_final_digest']:raise ValueError('host_digest_changed')
            audits[row['task_id']]=events;rid=secrets.token_hex(12);mapping[rid]={'case_id':row['task_id'],'variant':v}
            packets.append({'review_id':rid,'public_packet':events[0]['result'],'tool_events':events[1:],'submission':row['assessment'],
                            'semantic_review':None,'citation_entailment':None})
        audit=suite/f'{v}-audits.private.json';write(audit,audits)
        with (suite/f'{v}-score.private.json').open('x') as f:
            subprocess.run([sys.executable,str(private/'evaluate.py'),'--public',str(RELEASE/'public'),'--key',str(private/'build/private/answer_key.json'),'--audits',str(audit)],stdout=f,check=True)
    write(suite/'blinded-review-packets.private.json',sorted(packets,key=lambda p:p['review_id']))
    write(suite/'reviewer-unblinding.private.json',mapping)
    completed={(r['task_id'],r['variant']) for r in oldrows+newrows if r['status']=='completed'}
    frozen=read(package/'sprint-c-v2/protocol.json');paired=[c for c in frozen['cases'] if all((c,v) in completed for v in ('V0','V1','V2','V3'))]
    summary={'matched_cases':paired,'scientific_protocol_id':frozen['protocol_id'],'semantic_scores':None,
        'preserved_failed_cells':[(r['task_id'],r['variant']) for r in oldrows if r['status']!='completed'],
        'note':'No failed/completed cell replay. Full frozen scorer totals include missing/failed cells; matched-case reporting must use common completed cases.'}
    metrics={}
    for v in ('V0','V1','V2','V3'):
        scored=read(suite/f'{v}-score.private.json');counts={k:[0,0] for k in ('SUPPORTED','NOT_ESTABLISHED','CONTRADICTED')}
        raw=0;literal=0;incorrect_contra=0;extra_abstain=0;unsupported=0
        for cid in paired:
            packet=read(RELEASE/f'public/cases/{cid}.json');scopes={x['id']:x['scope'] for x in packet['atomic_claims']}
            for aid,a in scored['cases'][cid]['atoms'].items():
                counts[a['expected']][1]+=1;counts[a['expected']][0]+=a['correct_with_evidence'];raw+=a['expected']==a['submitted']
                literal+=a['expected']==a['submitted'] and not a['correct_with_evidence']
                incorrect_contra+=a['submitted']=='CONTRADICTED' and a['expected']!='CONTRADICTED'
                extra_abstain+=a['submitted']=='NOT_ESTABLISHED' and a['expected']!='NOT_ESTABLISHED'
                unsupported+=scopes[aid]=='diagnostic_conclusion' and a['submitted']=='SUPPORTED' and a['expected']!='SUPPORTED'
        selected=[r for r in oldrows+newrows if r['variant']==v]
        metrics[v]={'matched_correct':sum(n[0] for n in counts.values()),'matched_atoms':sum(n[1] for n in counts.values()),
            'matched_recall':{k:a/b if b else None for k,(a,b) in counts.items()},'raw_matches':raw,'literal_citation_contract_failures':literal,
            'incorrect_contradictions':incorrect_contra,'reference_disagreeing_abstentions':extra_abstain,'unsupported_causal_support':unsupported,
            'all_planned_mechanical_points_of_29':scored['mechanical_points_of_29'],
            'http_requests_including_preserved_v2_cells':sum(r['requests'] for r in selected),
            'completed_cells':sum(r['status']=='completed' for r in selected),'attempted_cells':len(selected),
            'charged_sensor_uses':sum(len(r.get('charged_sensors',[])) for r in selected),
            'known_usage_estimate_usd':sum(r['usage']['estimated_cost_usd'] for r in selected),
            'latency_seconds':sum(r['latency_seconds'] for r in selected),'citation_entailment':None,'missing_premise_quality':None,
            'next_evidence_usefulness':None,'semantic_score':None}
    summary['metrics']=metrics
    summary['interpretation']='Continuation of identical frozen v2 scientific inputs; different execution batches. Seven correlated development tasks, no independent semantic grades or population inference.'
    write(suite/'coverage.json',summary);return summary


def score(package,out,private,destination,database,proposal_path=None,review_path=None):
    if not database or not Path(database).is_file():raise ValueError('existing_continuation_database_required')
    from .handoff import audit_locked
    if not proposal_path or not review_path:raise ValueError('proposal_and_owner_review_required_for_scoring')
    ledger=LocalLedger(database,read(proposal_path),read(review_path))
    try:
        audit_locked(package,out,ledger)
        return _score_unlocked(package,out,private,destination)
    finally:ledger.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','propose','plan','review','storage-check','storage-validate','storage-writer','storage-reader','storage-certify','init','run','score','audit','export'])
    for arg in ('archive','package','proposal','review','accept-proposal-id','owner','directory','certificate','db','plan','out','private-root','destination'):p.add_argument('--'+arg)
    p.add_argument('--owner-local',action='store_true');a=p.parse_args();os.umask(0o077)
    if a.action=='prepare':
        from .handoff import prepare
        result=prepare(a.archive,a.directory)
    elif a.action=='storage-check':
        from .handoff import storage_check
        result=storage_check(a.directory,a.owner_local)
    elif a.action in ('audit','export'):
        from .handoff import audit_or_export
        result=audit_or_export(a.package,a.out,a.db,a.proposal,a.review,a.certificate,a.destination if a.action=='export' else None)
    elif a.action=='propose':result=propose(a.package);write(a.out,result)
    elif a.action=='plan':result=plan(a.package);write(a.out,result)
    elif a.action=='review':
        proposal=read(a.proposal)
        if a.accept_proposal_id!=proposal['proposal_id']:raise ValueError('exact_proposal_id_review_required')
        if not a.db:p.error('--db binds owner approval to one canonical continuation database')
        result=approval(proposal,a.owner,a.db);write(a.out,result)
    elif a.action=='storage-validate':result=validate(a.directory,'trusted_local_owner' if a.owner_local else 'hosted_disposable')
    elif a.action in ('storage-writer','storage-reader'):result=cross(a.directory,a.action.split('-')[1])
    elif a.action=='storage-certify':result=certify(a.directory)
    elif a.action=='init':
        proposal,review,_=gates(a.package,a.proposal,a.review,a.certificate,a.db,a.owner_local)
        registry=durability.authorization_registry(proposal).resolve();registry.parent.mkdir(exist_ok=True,parents=True,mode=0o700)
        write(registry,{'review_id':review['review_id'],'database':str(Path(a.db).resolve())})
        ledger=LocalLedger.initialize(a.db,proposal,review)
        try:result=ledger.summary()
        finally:ledger.close()
    elif a.action=='run':result=run(a.package,a.proposal,a.review,a.certificate,a.db,a.plan,a.out,a.private_root,a.owner_local)
    else:result=score(a.package,a.out,a.private_root,a.destination,a.db,a.proposal,a.review)
    if a.action=='propose':result={k:v for k,v in result.items() if k in ('proposal_id','kind','approval_required','hosted_execution_permitted','verified_settled_estimate_nusd','conservative_uncertain_holds_nusd','sprint_c_carried_liability_nusd','sprint_c_safe_capacity_after_owner_review_nusd')}
    print(canonical(result))
if __name__=='__main__':main()
