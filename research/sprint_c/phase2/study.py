"""Versioned phase preparation and read-only verification of preserved history."""
import fcntl,getpass,json,os,sqlite3,subprocess
from pathlib import Path
from petromind.audit import canonical
from petromind.eval_protocol import digest
from research.sprint_c.accounting import validate_receipt,receipt_cost
from research.sprint_c.recovery import durability
from research.sprint_c.recovery.reconcile import verify_package,propose,sha
from research.sprint_c.recovery.handoff import extract
from research.sprint_c.recovery.workflow import plan as old_plan
from research.sprint_c.recovery.storage import verify_certificate
from research.synthetic_challenge.integration.verify_readiness import verify
from .journal import Journal,PHASE_CAP,owner_approval,verify_owner_approval

REPO=Path(__file__).resolve().parents[3]
RELEASE=REPO/'research/synthetic_challenge'
EXPORT_SHA='98698f31e519da8d2265f5089741b4798dfc960be3a70e2ddea74722312314cf'
AUTHORIZATION='Proposed maximum additional estimated usage: $30. Requires an explicit versioned owner-local authorize --additional-usd 30 record before activation or HTTP. No historical liability is released.'


def read(p):return json.loads(Path(p).read_text())
def write(p,value):durability.durable_text(p,json.dumps(value,indent=2)+'\n')
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines()] if Path(p).exists() else []
def code_digest():return digest({str(p.relative_to(REPO)):sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))})


def legacy_evidence(root,package):
    root=Path(root);manifest=verify_package(root)
    if {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}!=set(manifest)|{'FILE_MANIFEST.json'}:raise ValueError('legacy_file_set_changed')
    proposal=read(root/'proposal.json');review=read(root/'owner-review.json');activation=read(root/'money.activation.json')
    if propose(package)!=proposal or digest({k:v for k,v in review.items() if k!='review_id'})!=review['review_id']:raise ValueError('legacy_proposal_or_review_changed')
    if activation!={'proposal_id':proposal['proposal_id'],'review_id':review['review_id'],'database':review['continuation_database']}:raise ValueError('legacy_activation_changed')
    c=sqlite3.connect('file:'+str((root/'money').resolve())+'?mode=ro&immutable=1',uri=True)
    try:
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('legacy_database_corrupt')
        events=c.execute('SELECT sequence,body,digest FROM events ORDER BY sequence').fetchall()
    finally:c.close()
    previous='0'*64;reservations={};settled={};unknown=set();provider=set()
    for index,(seq,raw,h) in enumerate(events,1):
        row=json.loads(raw);d=row['data'];kind=row['kind']
        if seq!=index or row['sequence']!=index or row['previous_hash']!=previous or digest(row)!=h:raise ValueError('legacy_chain_corrupt')
        if read(root/'money.anchors'/f'{seq:06d}-{h}.json')!={'sequence':seq,'digest':h}:raise ValueError('legacy_anchor_corrupt')
        if index==1:
            if kind!='conservative_carry_forward' or d!={'proposal_id':proposal['proposal_id'],'review_id':review['review_id'],'historical_held_nusd':proposal['historical_held_nusd'],'carried_sprint_c_liability_nusd':proposal['sprint_c_carried_liability_nusd']}:raise ValueError('legacy_genesis_changed')
        elif kind=='reservation':
            rid=d['reservation_id']
            if rid in reservations or any(k not in settled for k in reservations) or d['reserved_nusd']!=d['input_token_bound']*1250+d['output_token_cap']*4250:raise ValueError('legacy_reservation_invalid')
            reservations[rid]=d
        elif kind=='settlement':
            rid=d['reservation_id']
            if rid not in reservations or rid in settled:raise ValueError('legacy_settlement_invalid')
            validate_receipt(d['receipt'],reservations[rid]);pid=d['receipt']['provider_response_id']
            if pid in provider or digest(pid) in proposal['historical_provider_id_hashes'] or d['settled_nusd']!=receipt_cost(d['receipt']):raise ValueError('legacy_receipt_invalid')
            settled[rid]=d;provider.add(pid)
        elif kind=='unverified_response':
            rid=d['reservation_id']
            if rid not in reservations or rid in settled or rid in unknown:raise ValueError('legacy_unverified_invalid')
            unknown.add(rid)
        else:raise ValueError('legacy_event_invalid')
        previous=h
    if len(list((root/'money.anchors').iterdir()))!=len(events):raise ValueError('legacy_anchor_count')
    charge=proposal['sprint_c_carried_liability_nusd']+sum(s['settled_nusd'] for s in settled.values())+sum(r['reserved_nusd'] for k,r in reservations.items() if k not in settled)
    if (len(events),len(reservations),len(settled),len(unknown),charge,previous)!=(99,49,48,1,5357073350,'11a954c241b45b2ee75e55eba256ecc940413fa06851262a742f4538283186cf'):raise ValueError('different_legacy_incident')
    attempts=rows(root/'run/suite/attempts.jsonl');results=rows(root/'run/suite/results.jsonl')
    if attempts!=old_plan(package)['cells'][:8] or len(results)!=8:raise ValueError('legacy_attempts_changed')
    for task,row in zip(attempts,results):
        if any(row[k]!=v for k,v in task.items()):raise ValueError('legacy_result_identity')
        cell=root/'run/suite'/f"{row['task_id']}-{row['variant']}"
        if read(cell/'result.json')!=row:raise ValueError('legacy_result_changed')
        if sum(all(r['task'][k]==v for k,v in task.items()) for r in reservations.values())!=row['requests']:raise ValueError('legacy_request_count')
        host=read(cell/'host-audit.private.json');prev='0'*64
        for e in host:
            if e['previous']!=prev or digest({k:v for k,v in e.items() if k!='digest'})!=e['digest']:raise ValueError('legacy_host_chain')
            prev=e['digest']
        if prev!=row['host_final_digest'] or len(row['charged_sensors'])>5:raise ValueError('legacy_host_or_budget')
    return {'proposal':proposal,'review':review,'carried_nusd':charge,'last_digest':previous,
            'database_sha256':sha(root/'money'),'manifest_digest':digest(manifest),
            'historical_provider_id_hashes':sorted(set(proposal['historical_provider_id_hashes'])|{digest(x) for x in provider})}


def make_plan(package):
    frozen=read(Path(package)/'sprint-c-v2/protocol.json')
    cells=[]
    for task in old_plan(package)['cells'][8:]:cells.append({'cell_id':'remaining-v1/'+task['task_id']+'/'+task['variant'],'group':'remaining-v1',**task})
    for group in ('confirmatory-v1','confirmatory-repeat-v2'):
        for case in frozen['cases']:
            for variant in frozen['order'][case]:cells.append({'cell_id':group+'/'+case+'/'+variant,'group':group,'task_id':case,'variant':variant})
    p={'version':'sprint-c-phase2-execution-plan-v1','frozen_protocol_id':frozen['protocol_id'],
       'scientific_inputs_digest':old_plan(package)['scientific_inputs_digest'],'cells':cells,
       'default_groups':['confirmatory-v1','remaining-v1'],
       'repeat_rule':'confirmatory-repeat-v2 requires explicit --authorize-repeat. All 28 cells are fresh; no selective replacement of primary outcomes.'}
    p['plan_id']=digest(p);return p


def registry_path(policy):return durability.authorization_registry({'proposal_id':policy['legacy_proposal_id'],'original_policy_id':policy['original_policy_id']}).resolve()

def registry_record(policy):return {'version':'sprint-c-phase2-registry-v1','policy_id':policy['policy_id'],'database':policy['database'],'legacy_database':policy['legacy_database'],'legacy_final_digest':policy['legacy_final_digest']}


def atomic_registry(path,value):
    temporary=path.with_name(path.name+'.phase2-transition')
    durability.durable_text(temporary,canonical(value)+'\n');os.replace(temporary,path);durability.sync_dir(path.parent)
    with path.open('r+') as f:durability.sync_file(f.fileno())


def prepare(root):
    root=Path(root).resolve();phase=root/'phase2';package=root/'preserved/PetroMind-Sprint-C-PRIVATE'
    certificate=verify_certificate(root/'storage-check/certificate.json')
    if not durability.local_surface(root)['local_macos_approved']:raise ValueError('local_mac_required')
    if root.stat().st_dev!=Path(certificate['owner_directory']).stat().st_dev:raise ValueError('validated_volume_required')
    phase.mkdir(mode=0o700,exist_ok=True)
    # Idempotent verification of the same immutable source archive, never overwrite.
    archive=root/'final-export.tar.gz'
    if sha(archive)!=EXPORT_SHA:raise ValueError('wrong_legacy_export_sha256')
    imported=phase/'historical'
    if not imported.exists():extract(archive,imported,EXPORT_SHA)
    evidence=legacy_evidence(imported/'final-export',package)
    frozen=read(package/'sprint-c-v2/protocol.json');plan=make_plan(package)
    verify(RELEASE,root/'evaluator/private_sprint_b',REPO)
    p={'version':'sprint-c-additional-30-v1','authorization':AUTHORIZATION,'phase_cap_nusd':PHASE_CAP,
       'cumulative_c_cap_nusd':40_000_000_000,'legacy_carried_nusd':evidence['carried_nusd'],
       'legacy_transport_end_basis':'Previously exited synchronous owner process; exported under owner lock; cutover reacquires exclusive legacy owner lock; full hold retained',
       'legacy_unresolved_hold_nusd':178845500,'legacy_final_digest':evidence['last_digest'],
       'legacy_database_sha256':evidence['database_sha256'],'legacy_export_sha256':EXPORT_SHA,
       'legacy_database':evidence['review']['continuation_database'],'legacy_review_id':evidence['review']['review_id'],
       'legacy_proposal_id':evidence['proposal']['proposal_id'],'original_policy_id':evidence['proposal']['original_policy_id'],
       'historical_provider_id_hashes':evidence['historical_provider_id_hashes'],
       'database':str(phase/'journal.sqlite'),'plan_id':plan['plan_id'],'code_digest':code_digest(),
       'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
       'max_requests':560,'max_output_tokens':4096,'scientific_protocol_id':frozen['protocol_id'],
       'storage_certificate_id':certificate['certificate_id']}
    p['policy_id']=digest(p)
    registry=registry_path(p)
    if not durability.local_surface(registry.parent)['local_macos_approved'] or registry.parent.stat().st_dev!=root.stat().st_dev:raise ValueError('registry_local_volume_required')
    # Same old owner lock, acquired before cutover. It excludes an active old run.
    with (Path(p['legacy_database']).parent/'owner.lock').open('a') as owner:
        fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old={'review_id':p['legacy_review_id'],'database':p['legacy_database']};current=read(registry)
        if current not in (old,registry_record(p)):raise ValueError('another_phase_is_registered')
        if sha(p['legacy_database'])!=p['legacy_database_sha256']:raise ValueError('live_legacy_money_changed_since_export')
        for name,value in (('policy.json',p),('plan.json',plan)):
            target=phase/name
            if target.exists():
                if read(target)!=value:raise ValueError('prepared_phase_identity_changed')
            else:write(target,value)
    approved=(phase/'owner-authorization.json').exists()
    if approved:verify_owner_approval(p,read(phase/'owner-authorization.json'))
    return {'status':'PREPARED_AUTHORIZED' if approved else 'PREPARED_AWAITING_AUTHORIZATION','proposed_maximum_additional_usd':30,
            'no_paid_calls':True,'no_authorization_created':True,'policy_id':p['policy_id'],'groups':plan['default_groups']}


def authorize(root,additional_usd):
    if type(additional_usd)is not int or additional_usd!=30:raise ValueError('explicit_additional_30_required')
    prepare(root)
    root=Path(root).resolve();phase=root/'phase2';p=read(phase/'policy.json');plan=read(phase/'plan.json')
    registry=registry_path(p)
    with (Path(p['legacy_database']).parent/'owner.lock').open('a') as owner:
        fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old={'review_id':p['legacy_review_id'],'database':p['legacy_database']};current=read(registry)
        if current not in (old,registry_record(p)):raise ValueError('another_phase_is_registered')
        if sha(p['legacy_database'])!=p['legacy_database_sha256']:raise ValueError('live_legacy_money_changed_since_export')
        approval=owner_approval(p,getpass.getuser());target=phase/'owner-authorization.json'
        if target.exists():
            if read(target)!=approval:raise ValueError('phase_authorization_record_changed')
        else:write(target,approval)
        if current==old:atomic_registry(registry,registry_record(p))
        # Only this explicit command advances the registry and activates funds.
        initialize=not (phase/'activation.json').exists()
        j=Journal(phase/'journal.sqlite',p,plan,initialize=initialize)
        try:summary=j.summary()
        finally:j.close()
    return {'status':'AUTHORIZED','authorization_id':approval['authorization_id'],'additional_authorization_usd':30,'no_paid_calls':True,'accounting':summary}


def open_study(root):
    root=Path(root).resolve();phase=root/'phase2';p=read(phase/'policy.json');plan=read(phase/'plan.json')
    verify_owner_approval(p,read(phase/'owner-authorization.json'))
    certificate=verify_certificate(root/'storage-check/certificate.json')
    for location in (root,phase,registry_path(p).parent):
        if not durability.local_surface(location)['local_macos_approved'] or location.stat().st_dev!=Path(certificate['owner_directory']).stat().st_dev:raise ValueError('local_validated_volume_required')
    if p['source_commit']!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip():raise ValueError('phase_source_commit_changed')
    if p['storage_certificate_id']!=certificate['certificate_id'] or p['code_digest']!=code_digest() or plan!=make_plan(root/'preserved/PetroMind-Sprint-C-PRIVATE'):raise ValueError('phase_code_plan_or_storage_changed')
    if read(registry_path(p))!=registry_record(p):raise ValueError('phase_not_registered')
    evidence=legacy_evidence(phase/'historical/final-export',root/'preserved/PetroMind-Sprint-C-PRIVATE')
    if evidence['last_digest']!=p['legacy_final_digest'] or sha(p['legacy_database'])!=p['legacy_database_sha256']:raise ValueError('legacy_evidence_changed')
    verify(RELEASE,root/'evaluator/private_sprint_b',REPO)
    owner=(Path(p['legacy_database']).parent/'owner.lock').open('a')
    try:
        fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if sha(p['legacy_database'])!=p['legacy_database_sha256']:raise ValueError('live_legacy_money_changed')
        journal=Journal(phase/'journal.sqlite',p,plan);journal.legacy_owner=owner
        return journal
    except Exception:owner.close();raise
