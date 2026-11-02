"""Recovery fixtures authorize only mock/local tests; no real review or HTTP."""
import json,sqlite3,uuid
from pathlib import Path
import pytest
from test_muse_integration import private
from petromind.eval_protocol import digest
from petromind.meta_api import MetaAPIError
from research.sprint_c.accounting import provider_receipt,NANO
from research.sprint_c.recovery.reconcile import MAX_REQUEST_NUSD,verify_proposal
from research.sprint_c.recovery.ledger import LocalLedger,approval
from research.sprint_c.recovery.storage import validate,verify_certificate,certify


@pytest.fixture
def proposal():
    p={'version':'sprint-c-conservative-loss-proposal-v1','approval_required':True,
       'maximum_request_nusd':MAX_REQUEST_NUSD,'uncertain_attempt_count':3,'historical_held_nusd':9884069500,
       'verified_settled_estimate_nusd':809010850,'sprint_c_carried_liability_nusd':4731954850,
       'sprint_c_safe_capacity_after_owner_review_nusd':5268045150,'sprint_c_ceiling_nusd':10*NANO,
       'archived_http_attempt_count':122,'historical_reserved_output_token_bound':499712,'historical_provider_id_hashes':[digest('old-provider-response')]}
    p['proposal_id']=digest(p);return p

@pytest.fixture
def local(tmp_path,proposal):
    l=LocalLedger.initialize(tmp_path/'continuation.sqlite',proposal,approval(proposal,'TEST FIXTURE OWNER',tmp_path/'continuation.sqlite'))
    yield l
    l.close()


def reserve(l,i=10000):return l.reserve('frozen',{'task_id':'case','variant':'V0'},i,4096,'a'*64)


def receipt(r,identifier=None,i=1000,o=100):
    response={'id':identifier or 'resp_'+uuid.uuid4().hex,'model':'muse-spark-1.3','status':'completed',
              'usage':{'input_tokens':i,'output_tokens':o,'total_tokens':i+o},'output':[{'type':'message'}]}
    return provider_receipt(response,r)


def test_approval_required_and_bound_not_reset(tmp_path,proposal):
    with pytest.raises((ValueError,KeyError)):LocalLedger.initialize(tmp_path/'no.sqlite',proposal,{})
    assert not (tmp_path/'no.sqlite').exists()
    verify_proposal(proposal)
    assert proposal['sprint_c_carried_liability_nusd']==809010850+3*MAX_REQUEST_NUSD


def test_carry_forward_settlement_restart_and_no_reset(local,proposal):
    assert local.summary()['sprint_c_accounted_usd']==4.73195485
    r=reserve(local);local.settle(r['reservation_id'],receipt(r))
    old=local.summary();path=local.path;review=local.review;local.close()
    l=LocalLedger(path,proposal,review)
    try:assert l.summary()==old
    finally:l.close()
    with pytest.raises(FileExistsError):LocalLedger.initialize(path,proposal,review)


def test_unknown_or_interrupted_request_stays_held(local,proposal):
    r=reserve(local);path=local.path;review=local.review;local.close();l=LocalLedger(path,proposal,review)
    try:
        assert l.summary()['new_unsettled_holds_usd']==r['reserved_nusd']/NANO
        with pytest.raises(MetaAPIError):reserve(l)
    finally:l.close()


def test_duplicate_settlement_and_historical_provider_id_refused(local):
    r=reserve(local)
    with pytest.raises(ValueError):local.settle(r['reservation_id'],receipt(r,'old-provider-response'))
    good=receipt(r);local.settle(r['reservation_id'],good)
    with pytest.raises(ValueError):local.settle(r['reservation_id'],good)


def test_single_owner_excludes_concurrent_process_owner(local,proposal):
    with pytest.raises(ValueError):LocalLedger(local.path,proposal,local.review)


def test_budget_cap_includes_entire_conservative_carry(local):
    for _ in range(4):
        r=reserve(local,1_000_000);local.settle(r['reservation_id'],receipt(r,i=1_000_000,o=4000))
    with pytest.raises(MetaAPIError):reserve(local,1_000_000)
    assert local.summary()['sprint_c_accounted_usd']<=10


def test_append_only_and_corruption_detection(local,proposal):
    with pytest.raises(sqlite3.IntegrityError):local.db.execute('DELETE FROM events')
    r=reserve(local);local.settle(r['reservation_id'],receipt(r))
    local.db.execute('DROP TRIGGER no_update');local.db.execute("UPDATE events SET digest=? WHERE sequence=2",('f'*64,))
    with pytest.raises(ValueError):local.state()


def test_wrong_price_or_proposal_tamper_rejected(proposal):
    proposal['maximum_request_nusd']=1;proposal['proposal_id']=digest({k:v for k,v in proposal.items() if k!='proposal_id'})
    with pytest.raises(ValueError):verify_proposal(proposal)


def test_unverified_usage_keeps_hold(local):
    r=reserve(local);local.unverified(r['reservation_id'])
    assert local.summary()['new_unsettled_holds_usd']>0
    with pytest.raises(ValueError):local.settle(r['reservation_id'],receipt(r))
    with pytest.raises(MetaAPIError):reserve(local)


def test_all_disposable_storage_checks_and_missing_witness_blocks(tmp_path):
    p=tmp_path/'surface';report=validate(p)
    assert report['passed'] and all(report['checks'].values())
    with pytest.raises(FileNotFoundError):certify(p)
    # No locally approved certificate can be inferred from a passing hosted test.
    fake={'version':'local-storage-certificate-v1','surface':'hosted_disposable','passed':True}
    fake['certificate_id']=digest(fake);(p/'certificate.json').write_text(json.dumps(fake))
    with pytest.raises(ValueError):verify_certificate(p/'certificate.json')


def test_missing_review_storage_or_owner_ack_blocks_workflow_before_http(tmp_path,monkeypatch):
    from research.sprint_c.recovery.workflow import gates,run
    called=[]
    monkeypatch.setattr('research.sprint_c.recovery.workflow.SettlingClient',lambda *a,**k:called.append(True))
    with pytest.raises(ValueError):gates(tmp_path,'missing','missing','missing',tmp_path/'db',False)
    with pytest.raises(ValueError):run(tmp_path,'missing','missing','missing',tmp_path/'db','missing',tmp_path/'out',tmp_path,False)
    assert called==[]


def test_valid_database_prefix_rollback_detected_by_immutable_anchors(local,proposal,tmp_path):
    import shutil
    backup=tmp_path/'before.sqlite';shutil.copy2(local.path,backup)
    r=reserve(local);local.settle(r['reservation_id'],receipt(r))
    path=local.path;review=local.review;local.close();shutil.copy2(backup,path)
    with pytest.raises(ValueError):LocalLedger(path,proposal,review)


def test_interrupted_anchor_persistence_fails_closed_before_http(local,monkeypatch):
    def fail():raise OSError('simulated interrupted anchor')
    monkeypatch.setattr(local,'checkpoint',fail)
    with pytest.raises(OSError):reserve(local)
    with pytest.raises(ValueError):local.state()


@pytest.mark.parametrize('provider_usage_valid',[True,False])
def test_mocked_local_continuation_uses_frozen_prompt_and_settles(tmp_path,proposal,private,monkeypatch,provider_usage_valid):
    import httpx
    from test_muse_integration import abstain
    from petromind.meta_api import MetaResponsesClient
    from research.sprint_c.client import SettlingClient
    from research.sprint_c.recovery import workflow as wf
    package=tmp_path/'package';(package/'sprint-c-v2').mkdir(parents=True)
    frozen=json.loads((Path(__file__).resolve().parents[1]/'research/sprint_c/results/protocol-v2.public.json').read_text())
    (package/'sprint-c-v2/protocol.json').write_text(json.dumps(frozen))
    db=tmp_path/'money.sqlite';review=approval(proposal,'TEST FIXTURE OWNER',db)
    l=LocalLedger.initialize(db,proposal,review);l.close()
    expected={'plan_id':'fixture','scientific_protocol_id':frozen['protocol_id'],'cells':[{'task_id':'c-13df','variant':'V3'}]}
    planfile=tmp_path/'plan.json';planfile.write_text(json.dumps(expected))
    monkeypatch.setattr(wf,'gates',lambda *args:(proposal,review,{'certificate_id':'fixture'}))
    monkeypatch.setattr(wf,'plan',lambda *args:expected)
    monkeypatch.setattr(wf,'verify',lambda *args:None)
    monkeypatch.setenv('MODEL_API_KEY','test-placeholder')
    calls=[]
    def create(protocol,ledger,task):
        def handler(request):
            payload=json.loads(request.content);calls.append(payload)
            assert payload['instructions']==frozen['prompts']['V3']
            assert str(private) not in json.dumps(payload) and 'test-placeholder' not in json.dumps(payload)
            assert ledger.summary()['new_unsettled_holds_usd']>0
            packet=json.loads(payload['input'][0]['content'][0]['text'])
            return httpx.Response(200,json={'id':'resp_'+uuid.uuid4().hex,'model':'muse-spark-1.3','status':'completed',
                'usage':{'input_tokens':100 if provider_usage_valid else -1,'output_tokens':100,'total_tokens':200},
                'output':[{'type':'function_call','call_id':'submit','name':'submit_audit','arguments':json.dumps(abstain(packet))}]})
        factory=lambda **kw:MetaResponsesClient(transport=httpx.MockTransport(handler),**kw)
        return SettlingClient(protocol,ledger,task,factory=factory)
    monkeypatch.setattr(wf,'SettlingClient',create)
    result=wf.run(package,'fixture','fixture','fixture',db,planfile,tmp_path/'run',private,True)
    assert result['status']==('PERMITTED_CELLS_FINISHED' if provider_usage_valid else 'STOPPED_NO_RETRY') and len(calls)==1
    assert (result['accounting']['new_unsettled_holds_usd']==0)==provider_usage_valid
    from research.sprint_c.recovery import handoff
    monkeypatch.setattr(handoff,'propose',lambda *args:proposal)
    monkeypatch.setattr(handoff,'verify_package',lambda *args:{})
    l=LocalLedger(db,proposal,review)
    try:
        audited=handoff.audit_locked(package,tmp_path/'run',l)
        assert audited['completed_cells']==int(provider_usage_valid) and audited['unresolved_requests']==int(not provider_usage_valid)
        capture=tmp_path/'run/suite/c-13df-V3/result.json'
        changed=json.loads(capture.read_text());changed['requests']=99;capture.write_text(json.dumps(changed))
        with pytest.raises(ValueError,match='capture_result_changed'):handoff.audit_locked(package,tmp_path/'run',l)
    finally:l.close()


def test_reviewed_path_and_activation_prevent_directory_reset(local,proposal,tmp_path):
    with pytest.raises(ValueError):LocalLedger.initialize(tmp_path/'other.sqlite',proposal,local.review)
    path=local.path;review=local.review;local.close();path.unlink()
    with pytest.raises(FileExistsError):LocalLedger.initialize(path,proposal,review)


def test_scoring_rejects_active_owner_before_loading_private_key(local,tmp_path):
    from research.sprint_c.recovery.workflow import score
    with pytest.raises(ValueError):score(tmp_path,tmp_path,tmp_path,tmp_path/'score',local.path)


def test_macos_sync_requires_and_uses_fullfsync(monkeypatch,tmp_path):
    import fcntl,os
    from research.sprint_c.recovery import durability as d
    monkeypatch.setattr(d,'is_macos',lambda:True)
    monkeypatch.delattr(fcntl,'F_FULLFSYNC',raising=False)
    with (tmp_path/'sync').open('w') as f:
        with pytest.raises(ValueError,match='fullfsync'):d.sync_file(f.fileno())
        called=[];monkeypatch.setattr(fcntl,'F_FULLFSYNC',51,raising=False)
        monkeypatch.setattr(fcntl,'fcntl',lambda *args:called.append(args))
        d.sync_file(f.fileno());assert called==[(f.fileno(),51,0)]


def test_initialization_lock_precedes_activation(tmp_path,proposal):
    import fcntl
    db=tmp_path/'locked.sqlite';review=approval(proposal,'FIXTURE',db)
    with (tmp_path/'owner.lock').open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(ValueError,match='single_owner'):LocalLedger.initialize(db,proposal,review)
    assert not db.exists() and not db.with_name(db.name+'.activation.json').exists()


def test_review_registry_cannot_move_with_package(tmp_path,proposal,monkeypatch):
    from research.sprint_c.recovery import durability as d
    from research.sprint_c.recovery.ledger import verify_review
    monkeypatch.setattr(Path,'home',classmethod(lambda cls:tmp_path))
    review=approval(proposal,'FIXTURE',tmp_path/'money.sqlite')
    assert review['authorization_registry']==str(d.authorization_registry(proposal))
    review['authorization_registry']=str(tmp_path/'copied-package/registry.json')
    review['review_id']=digest({k:v for k,v in review.items() if k!='review_id'})
    with pytest.raises(ValueError):verify_review(proposal,review)


def test_overlap_certificate_rechecks_current_witnesses(tmp_path):
    from research.sprint_c.recovery.handoff import storage_check
    root=tmp_path/'storage';c=storage_check(root,False)
    assert verify_certificate(root/'certificate.json',require_local=False)==c
    (root/'cross-head').write_text('499')
    with pytest.raises(ValueError,match='diverged_after'):verify_certificate(root/'certificate.json',require_local=False)


def test_non_mac_local_certificate_fails_closed(tmp_path):
    import sys
    if sys.platform=='darwin':pytest.skip('Linux gate check')
    with pytest.raises(ValueError,match='trusted_local_mac'):validate(tmp_path/'local','trusted_local_owner')


def test_native_mac_local_surface(tmp_path):
    import sys
    if sys.platform!='darwin':pytest.skip('requires native macOS/APFS')
    report=validate(tmp_path/'mac-native','trusted_local_owner')
    assert report['passed'] and report['filesystem']['local_macos_approved']


def test_sqlite_required_settings(local):
    assert local.db.execute('PRAGMA synchronous').fetchone()[0]==3
    assert local.db.execute('PRAGMA fullfsync').fetchone()[0]==1
    assert local.db.execute('PRAGMA journal_mode').fetchone()[0]=='delete'


def test_activation_tamper_refuses_restart(local,proposal):
    path=local.path;review=local.review;local.close()
    path.with_name(path.name+'.activation.json').write_text('{}')
    with pytest.raises(ValueError,match='activation_changed'):LocalLedger(path,proposal,review)


def test_unsafe_archive_rejected_before_extract(tmp_path):
    import tarfile,io
    from research.sprint_c.recovery.handoff import extract
    from research.sprint_c.recovery.reconcile import sha
    archive=tmp_path/'bad.tar.gz'
    with tarfile.open(archive,'w:gz') as t:
        m=tarfile.TarInfo('../escape');m.size=1;t.addfile(m,io.BytesIO(b'x'))
    with pytest.raises(ValueError,match='unsafe_archive'):extract(archive,tmp_path/'extracted',sha(archive))
    assert not (tmp_path/'escape').exists()
