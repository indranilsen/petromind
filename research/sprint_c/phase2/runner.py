"""Research-only phase driver: fresh cells, bounded runs, resumable closed holds."""
import argparse,json,os,sqlite3,subprocess,time
from dataclasses import asdict
from pathlib import Path
from petromind.agent import AgentConfig,run_tool_agent
from petromind.audit import canonical
from petromind.eval_protocol import digest
from petromind.meta_api import MetaAPIError
from research.muse_integration.bridge import Bridge
from research.sprint_c.runner import decode
from research.sprint_c.recovery import durability
from research.sprint_c.recovery.reconcile import sha,verify_package
from . import study
from .client import ResearchClient


def emit(value):print(canonical(value),flush=True)
def cell_path(root,cell):return Path(root)/'phase2/cells'/cell['group']/f"{cell['task_id']}-{cell['variant']}"


def host_digest(path):
    if not Path(path).exists():return None
    events=study.read(path);previous='0'*64
    for e in events:
        if e['previous']!=previous or digest({k:v for k,v in e.items() if k!='digest'})!=e['digest']:raise ValueError('host_chain_changed')
        previous=e['digest']
    return previous


def failure_category(status,reason):
    if status=='completed':return None
    if reason.startswith('receipt:'):return 'receipt'
    if reason.startswith('api:'):return 'api'
    if reason.startswith(('local','trusted_host')):return 'local_infrastructure'
    if reason.startswith('phase_'):return 'spending_or_request_cap'
    if reason in ('missing_encrypted_reasoning','invalid_assistant_message','model_refused_or_invalid_content'):return 'response_continuation'
    if reason in ('invalid_function_call','tool_call_limit','tool_limit','session_closed'):return 'tool'
    return 'model_or_protocol'


def finish_capture(j,root,cell,status,reason,assessment=None,latency=0,sensors=None):
    path=cell_path(root,cell);path.mkdir(mode=0o700,parents=True,exist_ok=True)
    state=j.state();res={k:r for k,r in state['reservations'].items() if r['cell_id']==cell['cell_id']}
    settlements=[s for k,s in state['settlements'].items() if k in res]
    host=path/'host-audit.private.json'
    try:host_final=host_digest(host);host_valid=host_final is not None
    except (ValueError,OSError):
        if status=='completed':raise
        host_final=None;host_valid=False
    value={**cell,'execution_plan_id':j.plan['plan_id'],'frozen_protocol_id':j.plan['frozen_protocol_id'],
           'status':status,'reason':reason,'failure_category':failure_category(status,reason),'assessment':assessment,'requests':len(res),
           'known_usage_estimate_usd':sum(s['settled_nusd'] for s in settlements)/1e9,
           'unresolved_request_holds_usd':sum(r['reserved_nusd'] for k,r in res.items() if k not in state['settlements'])/1e9,
           'latency_seconds':latency,'charged_sensors':sorted(sensors or []),'charged_sensors_complete':sensors is not None,
           'host_final_digest':host_final,'host_capture_valid':host_valid,
           'captured_files_sha256':{str(p.relative_to(path)):sha(p) for p in sorted(path.rglob('*')) if p.is_file() and p.name!='result.json'}}
    study.write(path/'result.json',value);j.finish(cell,status,sha(path/'result.json'));return value


def verify_capture_files(path,value):
    expected=value['captured_files_sha256']
    actual={str(p.relative_to(path)):sha(p) for p in sorted(path.rglob('*')) if p.is_file() and p.name!='result.json'}
    if actual!=expected:raise ValueError('phase_capture_files_changed')
    if value['host_capture_valid'] and value['host_final_digest']!=host_digest(path/'host-audit.private.json'):raise ValueError('phase_host_capture_changed')


def recover(j,root):
    # Owning the flock means the preceding synchronous runner no longer owns I/O.
    # Closed-but-unsettled requests retain 100% of their monetary reservation.
    j.recover_transports();state=j.state()
    for cid,cell in state['started'].items():
        if cid in state['finished']:continue
        path=cell_path(root,cell)
        if (path/'result.json').exists():
            value=study.read(path/'result.json')
            if any(value[k]!=v for k,v in cell.items()) or value['execution_plan_id']!=j.plan['plan_id']:raise ValueError('interrupted_result_identity_changed')
            verify_capture_files(path,value)
            j.finish(cell,value['status'],sha(path/'result.json'))
        else:finish_capture(j,root,cell,'interrupted','local_process_ended_no_replay')
        emit({'event':'recovered_interruption','cell_id':cid,'replayed':False})


def run(root,group=None,authorize_repeat=False):
    root=Path(root).resolve();j=study.open_study(root)
    try:
        recover(j,root)
        groups=[group] if group else j.plan['default_groups']
        if any(g not in {c['group'] for c in j.plan['cells']} for g in groups):raise ValueError('unknown_group')
        if 'confirmatory-repeat-v2' in groups and not authorize_repeat:raise ValueError('explicit_additional_30_required','explicit_phase_authorization_required','phase_authorization_record_changed','explicit_authorize_repeat_required')
        key=os.environ.get('MODEL_API_KEY','').strip()
        if not key or not key.isascii() or any(c.isspace() for c in key):raise MetaAPIError('missing_or_invalid_api_key')
        del key
        frozen=study.read(root/'preserved/PetroMind-Sprint-C-PRIVATE/sprint-c-v2/protocol.json')
        cells=[c for g in groups for c in j.plan['cells'] if c['group']==g]
        for index,cell in enumerate(cells,1):
            if cell['cell_id'] in j.state()['started']:continue
            j.start(cell);path=cell_path(root,cell);path.mkdir(mode=0o700,parents=True,exist_ok=True);durability.sync_dir(path.parent)
            emit({'event':'cell_started','position':index,'of':len(cells),'cell_id':cell['cell_id'],'accounting':j.summary()})
            bridge=None;client=None;started=time.monotonic();status='failed';reason='local_setup_failed';fatal=False
            try:
                bridge=Bridge(study.RELEASE,root/'evaluator/private_sprint_b',cell['task_id'],path/'host-audit.private.json','B')
                client=ResearchClient(frozen,j,cell)
                result=run_tool_agent(bridge,client,AgentConfig(**frozen['agent_config']),
                    instructions=frozen['prompts'][cell['variant']],tools=frozen['tools'],
                    initial_history=[{'role':'user','content':[{'type':'input_text','text':canonical(bridge.packet)}]}],
                    prompt_version='sprint-c-citation-verdict-v2',submission_reason='synthetic_assessment_submitted',
                    is_complete=lambda:bridge.result is not None,stop_reason=lambda:bridge.stop,decode_arguments=decode,
                    on_event=lambda event:durability.durable_text(path/'events.jsonl',canonical(asdict(event))+'\n',exclusive=False))
                status,reason=result.status,result.reason
                fatal=(reason.startswith(('local:','protocol:','phase_')) or reason.startswith('api:'))
            except Exception as error:
                # Never serialize exception messages, repr, frames or response bodies.
                safe_host={'trusted_host_timeout','trusted_host_start_failed','invalid_host_envelope'}
                reason='local_infrastructure_'+(str(error) if str(error) in safe_host else type(error).__name__);fatal=True
            finally:
                if client:client.close()
                if bridge:bridge.close()
            capture=path/'host-audit.private.json'
            if capture.exists():
                with capture.open('r+') as f:durability.sync_file(f.fileno())
            value=finish_capture(j,root,cell,status,reason,bridge.result if bridge and status=='completed' else None,time.monotonic()-started,bridge.observed if bridge else [])
            emit({'event':'cell_finished','cell_id':cell['cell_id'],'status':status,'reason':reason,'accounting':j.summary()})
            if fatal:return {'status':'STOPPED_ACTION_REQUIRED','failed_cell':cell['cell_id'],'reason':reason,'accounting':j.summary()}
        return {'status':'GROUPS_ATTEMPTED','groups':groups,'accounting':j.summary(),'failed_cells_are_not_replayed':True}
    finally:j.close()


def audit(j,root):
    root=Path(root);s=j.state();results=[]
    for cid,end in s['finished'].items():
        cell=s['started'][cid];path=cell_path(root,cell);value=study.read(path/'result.json')
        if sha(path/'result.json')!=end['result_sha256'] or value['status']!=end['status'] or any(value[k]!=v for k,v in cell.items()) or value['execution_plan_id']!=j.plan['plan_id']:raise ValueError('phase_result_changed')
        verify_capture_files(path,value)
        requests=sum(r['cell_id']==cid for r in s['reservations'].values())
        if value['requests']!=requests or len(value['charged_sensors'])>5:raise ValueError('capture_request_or_sensor_count')
        if value['status']=='completed' and (value['assessment']is None or not value['host_capture_valid'] or value['host_final_digest']is None):raise ValueError('completed_capture_missing')
        results.append(value)
    if set(s['started'])!=set(s['finished']):raise ValueError('unfinished_cell_run_resume_first')
    return results


def score(root):
    from .scoring import score_locked
    j=study.open_study(root)
    try:return score_locked(j,Path(root).resolve(),audit(j,root))
    finally:j.close()


def report(root,export=False):
    import tarfile
    j=study.open_study(root)
    try:
        results=audit(j,root);root=Path(root).resolve();phase=root/'phase2'
        summary={'version':'phase2-report-v1','accounting':j.summary(),'execution_plan_id':j.plan['plan_id'],
                 'groups':{g:{'attempted':sum(r['group']==g for r in results),'completed':sum(r['group']==g and r['status']=='completed' for r in results),'planned':sum(c['group']==g for c in j.plan['cells'])} for g in {c['group'] for c in j.plan['cells']}},
                 'source_commit':j.policy.get('source_commit','OFFLINE_FIXTURE'),
                 'code_digest':study.code_digest(),'semantic_grades':None,'historical_results_preserved':True}
        if not export:return summary
        # Every export is a new snapshot, never replaces a previous report.
        destination=phase/'exports'/f"snapshot-{len(j.state()['rows']):06d}-{time.time_ns()}"
        destination.mkdir(mode=0o700,parents=True)
        import shutil
        for name in ('journal.sqlite','journal.sqlite.anchors','activation.json','owner-authorization.json','policy.json','plan.json','cells','scores','historical'):
            source=phase/name
            if source.is_dir():shutil.copytree(source,destination/name)
            elif source.exists():shutil.copy2(source,destination/name)
        study.write(destination/'REPORT.json',summary)
        study.write(destination/'registry.json',study.read(study.registry_path(j.policy)))
        shutil.copytree(root/'storage-check',destination/'storage-witnesses')
        study.write(destination/'FILE_MANIFEST.json',{str(p.relative_to(destination)):sha(p) for p in sorted(destination.rglob('*')) if p.is_file()})
        archive=destination.with_suffix('.tar.gz')
        with archive.open('xb') as f:
            with tarfile.open(fileobj=f,mode='w:gz') as t:t.add(destination,arcname=destination.name)
            f.flush();durability.sync_file(f.fileno())
        durability.sync_dir(archive.parent)
        return {'private_archive':str(archive),'sha256':sha(archive),'report':summary}
    finally:j.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','authorize','validate','run','resume','score','report'])
    parser.add_argument('--root',default=str(Path.home()/'Personal/PetroMindSprintC'))
    parser.add_argument('--group',choices=['confirmatory-v1','remaining-v1','confirmatory-repeat-v2'])
    parser.add_argument('--additional-usd',type=int)
    parser.add_argument('--authorize-repeat',action='store_true');parser.add_argument('--export',action='store_true')
    args=parser.parse_args();os.umask(0o077)
    try:
        if args.action=='prepare':result=study.prepare(args.root)
        elif args.action=='authorize':result=study.authorize(args.root,args.additional_usd)
        elif args.action in ('run','resume'):result=run(args.root,args.group,args.authorize_repeat)
        elif args.action=='score':result=score(args.root)
        else:result=report(args.root,args.export)
        emit(result)
    except Exception as error:
        # Stable class only: lower layers' safe diagnostics live in the journal.
        safe={'missing_or_invalid_api_key','phase_source_commit_changed','phase_code_plan_or_storage_changed','wrong_legacy_export_sha256','phase_prepare_required','phase_capture_files_changed','phase_result_changed','phase_not_registered','another_phase_is_registered','live_legacy_money_changed_since_export','explicit_additional_30_required','explicit_phase_authorization_required','phase_authorization_record_changed','explicit_authorize_repeat_required','phase_anchor_set_mismatch','phase_sqlite_corrupt','phase_chain_corrupt','unfinished_cell_run_resume_first','prepared_phase_identity_changed','hosted_execution_forbidden','local_mac_required','local_validated_volume_required'}
        code=str(error) if str(error) in safe else 'required_artifact_missing' if isinstance(error,FileNotFoundError) else 'local_file_permissions' if isinstance(error,PermissionError) else 'see_error_class'
        known_files={'policy.json','plan.json','journal.sqlite','final-export.tar.gz','certificate.json','protocol.json','owner-review.json','proposal.json','FILE_MANIFEST.json','activation.json','owner-authorization.json'}
        name=Path(error.filename).name if isinstance(error,OSError) and error.filename else None
        artifact=name if name in known_files else None
        emit({'status':'STOPPED_ACTION_REQUIRED','category':'local_or_gate','code':code,'artifact':artifact,'action':args.action,'error_class':type(error).__name__,'instruction':'Preserve state and return the error; do not reset accounting.'})
        raise SystemExit(1) from None
