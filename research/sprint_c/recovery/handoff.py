"""API-free archive preparation, overlapping probe, final audit and private export."""
import hashlib,json,shutil,subprocess,sys,tarfile,time
from pathlib import Path
from petromind.eval_protocol import digest
from . import durability
from .reconcile import sha,verify_package,propose
from .ledger import LocalLedger
from .storage import validate,certify,verify_certificate

ARCHIVE_SHA='f8df9fb71ded437ea6ac47f5d0ae0a820395c55b1b7fcbe3cd262049936ff7bb'
ORIGINAL_SHA='329633ea62644929c0511d1e7495e97f8a0f14bdf7aa4408f5221d1f8066eff4'
EVALUATOR_SHA='10f06578af1255e92bad13d1f4c8735c24c1f3d4f2e1947ad5cde3d45b5e5294'


def extract(archive,destination,expected):
    if sha(archive)!=expected:raise ValueError('archive_sha256_mismatch')
    destination=Path(destination);destination.mkdir(mode=0o700)
    with tarfile.open(archive) as t:
        members=t.getmembers()
        for m in members:
            p=Path(m.name)
            if p.is_absolute() or '..' in p.parts or not (m.isdir() or m.isfile()):raise ValueError('unsafe_archive_member')
        # Only regular files/directories; this also works with Python 3.10/3.11.
        t.extractall(destination,members=members)


def prepare(archive,root):
    from .workflow import write,plan,RELEASE,REPO,verify
    root=Path(root).resolve();root.mkdir(mode=0o700)
    if not durability.local_surface(root)['local_macos_approved']:raise ValueError('trusted_local_mac_required')
    extract(archive,root/'recovery',ARCHIVE_SHA)
    bundle=root/'recovery/PetroMind-Sprint-C-Recovery-LOCAL-PRIVATE';outer=verify_package(bundle)
    extract(bundle/'PetroMind-Sprint-C-PRIVATE.tar.gz',root/'preserved',ORIGINAL_SHA)
    package=root/'preserved/PetroMind-Sprint-C-PRIVATE';inner=verify_package(package)
    if len(inner)!=136:raise ValueError('original_manifest_count_changed')
    extract(package/'PetroMind-Sprint-B-PRIVATE-Evaluator.tar.gz',root/'evaluator',EVALUATOR_SHA)
    verify(RELEASE,root/'evaluator/private_sprint_b',REPO)
    p=propose(package);remaining=plan(package)
    if p!=json.loads((bundle/'OWNER_REVIEW_PROPOSAL.json').read_text()) or remaining!=json.loads((bundle/'PERMITTED_REMAINING_CELLS.json').read_text()):raise ValueError('preserved_proposal_or_plan_changed')
    write(root/'proposal.json',p);write(root/'remaining-cells.json',remaining)
    (root/'continuation').mkdir(mode=0o700)
    return {'prepared':True,'outer_commitments':len(outer),'original_commitments':len(inner),'remaining_cells':len(remaining['cells']),'proposal_id':p['proposal_id'],'no_owner_approval_created':True}


def storage_check(root,owner_local):
    from .workflow import REPO
    report=validate(root,'trusted_local_owner' if owner_local else 'hosted_disposable')
    if not report['passed']:raise ValueError('storage_validation_failed')
    command=[sys.executable,str(REPO/'scripts/recover_sprint_c.py')]
    root=Path(root).resolve()
    with (root/'writer.stdout').open('x') as stdout, (root/'writer.stderr').open('x') as stderr:
        writer=subprocess.Popen(command+['storage-writer','--directory',str(root)],stdout=stdout,stderr=stderr)
        try:
            deadline=time.monotonic()+15
            while not (root/'cross-start').exists():
                if writer.poll() is not None or time.monotonic()>deadline:raise ValueError('storage_writer_not_ready')
                time.sleep(.01)
            reader=subprocess.run(command+['storage-reader','--directory',str(root)],capture_output=True,text=True,timeout=60)
            if reader.returncode!=0 or writer.wait(timeout=60)!=0:raise ValueError('overlap_probe_failed')
        finally:
            if writer.poll() is None:writer.kill();writer.wait()
    return certify(root)


def audit_locked(package,out,ledger):
    from .workflow import read,read_jsonl,plan,REPO
    package=Path(package).resolve();out=Path(out).resolve()
    if propose(package)!=ledger.proposal:raise ValueError('proposal_evidence_changed')
    if str(out)!=ledger.review['continuation_output']:raise ValueError('reviewed_output_directory_changed')
    expected=plan(package);identity=read(out/'continuation.json')
    code=digest({str(p.relative_to(REPO)):sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))})
    if any(identity[k]!=v for k,v in {'plan_id':expected['plan_id'],'scientific_protocol_id':expected['scientific_protocol_id'],
        'proposal_id':ledger.proposal['proposal_id'],'review_id':ledger.review['review_id'],'recovery_code_digest':code}.items()):raise ValueError('continuation_identity_changed')
    rows,res,settled,unknown,charged=ledger.state()
    attempts=read_jsonl(out/'suite/attempts.jsonl');results=read_jsonl(out/'suite/results.jsonl')
    keys=lambda xs:[(x['task_id'],x['variant']) for x in xs]
    attempted=keys(attempts);resultkeys=keys(results);allowed=keys(expected['cells'])
    if len(set(attempted))!=len(attempted) or resultkeys!=attempted or attempted!=[k for k in allowed if k in attempted]:raise ValueError('missing_capture_replay_or_plan_order_changed')
    if any((r['task']['task_id'],r['task']['variant']) not in attempted for r in res.values()):raise ValueError('uncaptured_monetary_request')
    for row in results:
        cell=out/'suite'/f"{row['task_id']}-{row['variant']}"
        if read(cell/'result.json')!=row:raise ValueError('capture_result_changed')
        requests=sum((r['task']['task_id'],r['task']['variant'])==(row['task_id'],row['variant']) for r in res.values())
        if requests!=row['requests']:raise ValueError('request_capture_accounting_disagrees')
        if row['host_final_digest'] is not None:
            events=read(cell/'host-audit.private.json');previous='0'*64
            for event in events:
                if event['previous']!=previous or digest({k:v for k,v in event.items() if k!='digest'})!=event['digest']:raise ValueError('host_capture_chain_changed')
                previous=event['digest']
            if previous!=row['host_final_digest']:raise ValueError('host_capture_changed')
        elif row['status']=='completed':raise ValueError('completed_cell_missing_host_capture')
    return {'version':'local-final-audit-v1','accounting':ledger.summary(),'attempted_cells':len(attempted),
            'completed_cells':sum(r['status']=='completed' for r in results),'planned_cells':len(allowed),
            'unresolved_requests':len(res)-len(settled),'semantic_grades':None,'source_commit':identity['source_commit'],
            'status':'VALIDATED_WITH_UNRESOLVED_HOLDS' if len(res)!=len(settled) else 'VALIDATED',
            'original_manifest_digest':digest(verify_package(package))}


def audit_or_export(package,out,database,proposal_path,review_path,certificate_path,destination=None):
    from .workflow import read,write
    certificate=verify_certificate(certificate_path)
    ledger=LocalLedger(database,read(proposal_path),read(review_path))
    try:
        registry=durability.authorization_registry(ledger.proposal)
        if read(registry)!={'review_id':ledger.review['review_id'],'database':str(ledger.path)}:raise ValueError('authorization_registry_changed')
        report=audit_locked(package,out,ledger)
        if not destination:return report
        destination=Path(destination).resolve();destination.mkdir(mode=0o700)
        # Copy only while the single owner lock is held, including private scores.
        sources={'run':Path(out),'money':ledger.path,'money.anchors':ledger.anchors,
                 'money.activation.json':ledger.path.with_name(ledger.path.name+'.activation.json'),
                 'authorization-registry.json':registry,'proposal.json':Path(proposal_path),
                 'owner-review.json':Path(review_path),'storage-witnesses':Path(certificate_path).parent}
        scoring=Path(out).parent.parent/'final-comparison'
        if scoring.exists():sources['final-comparison']=scoring
        for name,source in sources.items():
            if source.is_dir():shutil.copytree(source,destination/name)
            else:shutil.copy2(source,destination/name)
        write(destination/'FINAL_AUDIT.json',report)
        write(destination/'FILE_MANIFEST.json',{str(p.relative_to(destination)):sha(p) for p in sorted(destination.rglob('*')) if p.is_file()})
        archive=destination.with_suffix('.tar.gz')
        with archive.open('xb') as f:
            with tarfile.open(fileobj=f,mode='w:gz') as t:t.add(destination,arcname=destination.name)
            f.flush();durability.sync_file(f.fileno())
        durability.sync_dir(archive.parent)
        return {'private_archive':str(archive),'sha256':sha(archive),'audit':report,'scoring_included':scoring.exists()}
    finally:ledger.close()
