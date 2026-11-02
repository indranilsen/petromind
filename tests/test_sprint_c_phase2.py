"""Mock-only regression coverage; no real owner activation or API calls."""
import json,shutil,time,uuid
from pathlib import Path
import httpx,pytest
from petromind.eval_protocol import digest
from petromind.meta_api import MetaAPIError
from research.sprint_c.phase2.client import ProviderError,ResearchClient,receipt,envelope_diagnostic
from research.sprint_c.phase2.journal import Journal,PHASE_CAP,owner_approval
from research.sprint_c.phase2 import runner,study
from test_muse_integration import private,abstain


def plan(cells=2):
    p={'frozen_protocol_id':'fixture','cells':[{'cell_id':f'confirmatory-v1/case{i}/V0','group':'confirmatory-v1','task_id':f'case{i}','variant':'V0'} for i in range(cells)],'default_groups':['confirmatory-v1']};p['plan_id']=digest(p);return p


def policy(path,p):
    value={'version':'sprint-c-additional-30-v1','phase_cap_nusd':PHASE_CAP,'cumulative_c_cap_nusd':40_000_000_000,'legacy_carried_nusd':5357073350,'max_requests':560,'max_output_tokens':4096,'database':str(path.resolve()),'plan_id':p['plan_id'],'historical_provider_id_hashes':[digest('old-response')]};value['policy_id']=digest(value)
    path.parent.mkdir(parents=True,exist_ok=True)
    (path.parent/'owner-authorization.json').write_text(json.dumps(owner_approval(value,'OFFLINE MOCK OWNER')))
    return value


@pytest.fixture
def journal(tmp_path):
    p=plan();j=Journal(tmp_path/'money.sqlite',policy(tmp_path/'money.sqlite',p),p,True)
    yield j
    j.close()


def response(**changes):
    r={'id':'resp_'+uuid.uuid4().hex,'model':'muse-spark-1.3','status':'completed','error':None,
       'usage':{'input_tokens':100,'output_tokens':50,'total_tokens':150,'input_tokens_details':{'cached_tokens':0},'output_tokens_details':{'reasoning_tokens':30}},
       'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'PRIVATE_TEXT_CANARY'}]}]}
    r.update(changes);return r


def reserve(j,input_bound=10000):
    cell=j.plan['cells'][0]
    if cell['cell_id'] not in j.state()['started']:j.start(cell)
    return j.reserve(cell,input_bound,4096,'a'*64)


@pytest.mark.parametrize('status',['completed','incomplete','failed','cancelled'])
def test_terminal_variants_settle_without_model_success(journal,status):
    r=reserve(journal);data=response(status=status);v=receipt(data,r);journal.settle(r['reservation_id'],v);journal.end_transport(r['reservation_id'],'synchronous_stream_scope_exited')
    assert journal.summary()['phase_unresolved_holds_usd']==0
    assert journal.summary()['legacy_carried_usd']==5.35707335


@pytest.mark.parametrize('change,field',[
 ({'usage':None},'usage'),({'model':'other'},'model'),({'id':None},'id'),({'status':'queued'},'status'),({'status':{}},'status'),
 ({'usage':{'input_tokens':True,'output_tokens':0,'total_tokens':1}},'usage.input_tokens'),
 ({'usage':{'input_tokens':100,'output_tokens':10,'total_tokens':111}},'usage.total_tokens'),
 ({'usage':{'input_tokens':100,'output_tokens':4097,'total_tokens':4197}},'usage.output_tokens'),
 ({'usage':{'input_tokens':100,'output_tokens':1,'total_tokens':101,'input_tokens_details':{'cached_tokens':101}}},'usage.cached_tokens')])
def test_field_specific_errors_do_not_settle(journal,change,field):
    r=reserve(journal)
    with pytest.raises(ProviderError) as error:receipt(response(**change),r)
    assert error.value.field==field and journal.summary()['phase_unresolved_holds_usd']>0


def test_redacted_diagnostics_ignore_arbitrary_provider_strings():
    r=response(error={'code':'API_KEY_CANARY','type':'API_KEY_CANARY','message':'PRIVATE_REASONING_CANARY'},incomplete_details={'reason':'API_KEY_CANARY'},instructions='PRIVATE_KEY_CANARY',output=[{'type':'reasoning','encrypted_content':'ENCRYPTED_CANARY','summary':['PRIVATE_REASONING_CANARY']}])
    d=json.dumps(envelope_diagnostic(r,'f'*64,200))
    assert not any(x in d for x in ('API_KEY_CANARY','PRIVATE','ENCRYPTED'))


def test_ended_unknown_hold_allows_unrelated_cell_without_release(journal):
    r=reserve(journal)
    with pytest.raises(MetaAPIError):journal.reserve(journal.plan['cells'][0],1000,4096,'b'*64)
    journal.end_transport(r['reservation_id'],'synchronous_stream_scope_exited');journal.finish(journal.plan['cells'][0],'failed','a'*64)
    cell=journal.plan['cells'][1];journal.start(cell);second=journal.reserve(cell,1000,4096,'b'*64)
    assert journal.summary()['phase_unresolved_holds_usd']==(r['reserved_nusd']+second['reserved_nusd'])/1e9


def test_cap_before_http_and_cumulative_carry(journal):
    cell=journal.plan['cells'][0];journal.start(cell)
    for _ in range(22):
        r=journal.reserve(cell,1032192,4096,'a'*64)
        u={'input_tokens':1032192,'output_tokens':4096,'total_tokens':1036288}
        journal.settle(r['reservation_id'],receipt(response(usage=u),r));journal.end_transport(r['reservation_id'],'synchronous_stream_scope_exited')
    before=journal.summary()
    with pytest.raises(MetaAPIError,match='phase_spending_cap'):journal.reserve(cell,1032192,4096,'a'*64)
    assert journal.summary()==before and before['sprint_c_cumulative_accounted_usd']<40


def test_restart_closes_only_local_transport_retains_full_hold(journal):
    r=reserve(journal);path=journal.path;p=journal.policy;plan=journal.plan;journal.close();j=Journal(path,p,plan)
    try:
        runner.recover(j,path.parent)
        assert r['reservation_id'] in j.state()['closed'] and j.summary()['phase_unresolved_holds_usd']==r['reserved_nusd']/1e9
        assert j.state()['finished'][plan['cells'][0]['cell_id']]['status']=='interrupted'
        with pytest.raises(ValueError):j.start(plan['cells'][0])
    finally:j.close()


def test_torn_capture_is_preserved_and_interrupted_cell_not_replayed(journal,tmp_path):
    cell=journal.plan['cells'][0];journal.start(cell);path=runner.cell_path(tmp_path,cell);path.mkdir(parents=True);(path/'host-audit.private.json').write_text('[partial')
    runner.recover(journal,tmp_path)
    audited=runner.audit(journal,tmp_path)
    assert audited[0]['status']=='interrupted' and not audited[0]['host_capture_valid']
    assert (path/'host-audit.private.json').read_text()=='[partial'


def test_valid_db_prefix_rollback_detected(journal,tmp_path):
    backup=tmp_path/'backup';shutil.copy2(journal.path,backup);reserve(journal);path=journal.path;p=journal.policy;plan=journal.plan;journal.close();shutil.copy2(backup,path)
    with pytest.raises(ValueError,match='anchor_set'):Journal(path,p,plan)


def test_committed_tail_anchor_can_recover_without_refunding(journal):
    r=reserve(journal);last=sorted(journal.anchors.iterdir())[-1];last.unlink();path=journal.path;p=journal.policy;plan=journal.plan;journal.close();j=Journal(path,p,plan)
    try:assert j.summary()['phase_unresolved_holds_usd']==r['reserved_nusd']/1e9 and last.exists()
    finally:j.close()


def test_owner_exclusion_and_no_duplicate_response(journal):
    with pytest.raises(BlockingIOError):Journal(journal.path,journal.policy,journal.plan)
    r=reserve(journal)
    with pytest.raises(ValueError,match='duplicate_provider'):journal.settle(r['reservation_id'],receipt(response(id='old-response'),r))


@pytest.mark.parametrize('kind',['incomplete','failed','cancelled','nonterminal','malformed_output','missing_usage','http_html','timeout','invalid_json','duplicate_json'])
def test_client_failure_classification_and_durable_evidence(journal,monkeypatch,kind):
    monkeypatch.setenv('MODEL_API_KEY','TEST_KEY_CANARY');cell=journal.plan['cells'][0];journal.start(cell)
    def handler(request):
        assert journal.summary()['phase_unresolved_holds_usd']>0
        if kind=='timeout':raise httpx.ReadTimeout('SECRET_EXCEPTION_CANARY')
        if kind=='http_html':return httpx.Response(503,text='SECRET_BODY_CANARY')
        if kind=='invalid_json':return httpx.Response(200,text='SECRET_BODY_CANARY')
        if kind=='duplicate_json':return httpx.Response(200,text='{"id":"one","id":"two"}')
        if kind=='incomplete':data=response(status='incomplete',incomplete_details={'reason':'max_output_tokens'})
        elif kind in ('failed','cancelled'):data=response(status=kind,error={'code':'server_error','message':'SECRET_MESSAGE_CANARY'},output=[])
        elif kind=='nonterminal':data=response(status='in_progress')
        elif kind=='malformed_output':data=response(output=None)
        else:data=response(usage=None)
        return httpx.Response(200,json=data)
    c=ResearchClient({'agent_config':{'max_turns':8,'max_output_tokens':4096}},journal,cell,transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ProviderError) as e:c.create({'model':'muse-spark-1.3','store':False,'max_output_tokens':4096},deadline=time.monotonic()+60)
        assert e.value.category==('model' if kind in ('incomplete','failed','cancelled','malformed_output') else 'receipt' if kind in ('missing_usage','nonterminal') else 'api')
    finally:c.close()
    s=journal.state();assert len(s['closed'])==1 and bool(s['settlements'])==(kind in ('incomplete','failed','cancelled','malformed_output'))
    assert any(json.loads(r[1])['kind']=='diagnostic' for r in s['rows'])
    raw=''.join(r[1] for r in s['rows']);assert not any(x in raw for x in ('SECRET','PRIVATE','CANARY'))


def test_no_local_gate_no_model_client(tmp_path,monkeypatch):
    called=[];monkeypatch.setattr(runner,'ResearchClient',lambda *a:called.append(True))
    with pytest.raises(FileNotFoundError):runner.run(tmp_path)
    assert called==[]


def test_mock_end_to_end_frozen_host_resume_and_blinding(tmp_path,private,monkeypatch):
    root=tmp_path;frozen=study.read(study.REPO/'research/sprint_c/results/protocol-v2.public.json')
    package=root/'preserved/PetroMind-Sprint-C-PRIVATE/sprint-c-v2';package.mkdir(parents=True);study.write(package/'protocol.json',frozen)
    p=plan(0);p['frozen_protocol_id']=frozen['protocol_id'];p['cells']=[{'cell_id':f'confirmatory-v1/c-13df/{v}','group':'confirmatory-v1','task_id':'c-13df','variant':v} for v in ('V0','V1','V2','V3')];p['plan_id']=digest({k:v for k,v in p.items() if k!='plan_id'})
    path=root/'phase2/journal.sqlite';path.parent.mkdir();policyvalue=policy(path,p);j=Journal(path,policyvalue,p,True);j.close()
    monkeypatch.setattr(study,'open_study',lambda root:Journal(path,policyvalue,p))
    monkeypatch.setenv('MODEL_API_KEY','TEST_KEY_CANARY');calls=[];turns={}
    def create(protocol,journal,cell):
        def handler(request):
            body=json.loads(request.content);calls.append(cell['cell_id']);packet=json.loads(body['input'][0]['content'][0]['text'])
            assert body['instructions']==frozen['prompts'][cell['variant']]
            assert str(private) not in str(body) and 'TEST_KEY_CANARY' not in str(body) and 'DO_NOT_RELEASE' not in str(body)
            turn=turns.get(cell['cell_id'],0);turns[cell['cell_id']]=turn+1
            if turn==0:
                assert len(body['input'])==1
                output=[{'type':'reasoning','encrypted_content':'OPAQUE_REASONING_CANARY','summary':[]},
                        {'type':'function_call','call_id':'cached','name':'query_sensor','arguments':json.dumps({'sensor':packet['initial_sensors'][0]})}]
                return httpx.Response(200,json=response(output=output))
            assert any(x.get('encrypted_content')=='OPAQUE_REASONING_CANARY' for x in body['input'])
            assert any(x.get('type')=='function_call_output' and x.get('call_id')=='cached' for x in body['input'])
            output=[{'type':'function_call','call_id':'submit','name':'submit_audit','arguments':json.dumps(abstain(packet))}]
            return httpx.Response(200,json=response(output=output))
        return ResearchClient(protocol,journal,cell,transport=httpx.MockTransport(handler))
    monkeypatch.setattr(runner,'ResearchClient',create)
    original_bridge=runner.Bridge
    monkeypatch.setattr(runner,'Bridge',lambda release,unused,*a:original_bridge(release,private,*a))
    assert runner.run(root)['status']=='GROUPS_ATTEMPTED';assert len(calls)==8
    assert runner.run(root)['status']=='GROUPS_ATTEMPTED' and len(calls)==8
    j=Journal(path,policyvalue,p)
    try:
        rows=runner.audit(j,root);assert len(rows)==4 and all(r['status']=='completed' for r in rows)
        assert 'OPAQUE_REASONING_CANARY' not in ''.join((runner.cell_path(root,c)/'events.jsonl').read_text() for c in p['cells'])
        result=runner.cell_path(root,p['cells'][0])/'events.jsonl';result.write_text(result.read_text()+'tampered')
        with pytest.raises(ValueError,match='capture_files_changed'):runner.audit(j,root)
    finally:j.close()


def test_prepare_cutover_is_idempotent_and_cannot_clone_account(tmp_path,monkeypatch):
    """Native/dataset evidence is mocked here; exercise actual cutover and DB writes."""
    root=tmp_path/'owner';root.mkdir();(root/'continuation').mkdir();old=root/'continuation/old.sqlite';old.write_bytes(b'FIXTURE_LEGACY_BYTES')
    archive=root/'final-export.tar.gz';archive.write_bytes(b'FIXTURE_ARCHIVE');(root/'phase2/historical').mkdir(parents=True)
    package=root/'preserved/PetroMind-Sprint-C-PRIVATE/sprint-c-v2';package.mkdir(parents=True)
    frozen=study.read(study.REPO/'research/sprint_c/results/protocol-v2.public.json');study.write(package/'protocol.json',frozen)
    registry=tmp_path/'registry.json';study.write(registry,{'review_id':'fixture-review','database':str(old)})
    p=plan();evidence={'carried_nusd':5357073350,'last_digest':'fixture-history-digest','database_sha256':study.sha(old),
         'review':{'review_id':'fixture-review','continuation_database':str(old)},'proposal':{'proposal_id':'fixture-proposal','original_policy_id':'fixture-policy'},'historical_provider_id_hashes':[]}
    monkeypatch.setattr(study,'EXPORT_SHA',study.sha(archive));monkeypatch.setattr(study,'legacy_evidence',lambda *args:evidence)
    monkeypatch.setattr(study,'make_plan',lambda *args:p);monkeypatch.setattr(study,'verify',lambda *args:None)
    monkeypatch.setattr(study,'verify_certificate',lambda *args:{'certificate_id':'fixture-storage','owner_directory':str(root)})
    monkeypatch.setattr(study.durability,'local_surface',lambda *args:{'local_macos_approved':True})
    monkeypatch.setattr(study,'registry_path',lambda *args:registry)
    first=study.prepare(root);second=study.prepare(root)
    assert first==second and first['no_authorization_created']
    assert not (root/'phase2/owner-authorization.json').exists()
    assert not (root/'phase2/journal.sqlite').exists()
    assert study.read(registry)=={'review_id':'fixture-review','database':str(old)}
    with pytest.raises(FileNotFoundError):study.open_study(root)
    funded=study.authorize(root,30);assert funded==study.authorize(root,30)
    assert funded['accounting']['phase_http_requests']==0
    assert old.read_bytes()==b'FIXTURE_LEGACY_BYTES'
    assert study.read(registry)['version']=='sprint-c-phase2-registry-v1'
    active=study.open_study(root)
    try:assert active.summary()['additional_authorization_usd']==30
    finally:active.close()
    # The returned owner above must be closed before a second command.
    # Separate output paths cannot make the same authorization spend twice.
    other=tmp_path/'other';shutil.copytree(root,other)
    with pytest.raises(ValueError,match='another_phase_is_registered'):study.prepare(other)


def test_repeat_requires_explicit_execution_flag(tmp_path,monkeypatch):
    p=plan();p['cells'].append({'cell_id':'confirmatory-repeat-v2/case0/V0','group':'confirmatory-repeat-v2','task_id':'case0','variant':'V0'})
    p['plan_id']=digest({k:v for k,v in p.items() if k!='plan_id'});path=tmp_path/'journal.sqlite';v=policy(path,p);j=Journal(path,v,p,True);j.close()
    monkeypatch.setattr(study,'open_study',lambda root:Journal(path,v,p))
    with pytest.raises(ValueError,match='explicit_authorize_repeat_required'):runner.run(tmp_path,'confirmatory-repeat-v2')


def test_cli_never_prints_unexpected_exception_contents(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr('sys.argv',['phase2','prepare','--root',str(tmp_path)])
    def fail(*args):raise RuntimeError('UNRESTRICTED_RESPONSE_SECRET_CANARY')
    monkeypatch.setattr(study,'prepare',fail)
    with pytest.raises(SystemExit) as error:runner.main()
    assert error.value.code==1
    output=capsys.readouterr();assert 'SECRET_CANARY' not in output.out+output.err
    assert json.loads(output.out)['error_class']=='RuntimeError'


def test_missing_owner_authorization_cannot_activate_or_spend(tmp_path):
    p=plan();path=tmp_path/'journal.sqlite';v=policy(path,p)
    (tmp_path/'owner-authorization.json').unlink()
    with pytest.raises(FileNotFoundError):Journal(path,v,p,True)
    assert not path.exists() and not (tmp_path/'activation.json').exists()


@pytest.mark.parametrize('amount',[None,29,31,True])
def test_authorization_requires_explicit_exact_amount(tmp_path,amount):
    with pytest.raises(ValueError,match='explicit_additional_30_required'):study.authorize(tmp_path,amount)
    assert not (tmp_path/'phase2').exists()
