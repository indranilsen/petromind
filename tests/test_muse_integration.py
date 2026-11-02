"""Security and budget regressions; mock HTTP only, no paid model calls."""
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import httpx
import pytest

from petromind.agent import AgentConfig, run_tool_agent
from petromind.audit import canonical
from petromind.meta_api import MetaAPIError, MetaResponsesClient
from research.muse_integration.bridge import Bridge, tools
from research.muse_integration.budget import IntegrationLedger
from research.muse_integration.runner import INSTRUCTIONS, RELEASE, decode
from research.sprint_a.experiment import ResearchClient, SessionLedger

# Real frozen vault optional on a public checkout. All boundary tests use local
# generated sensor responses with a private canary that the host must strip.
@pytest.fixture
def private(tmp_path):
    root=tmp_path/'owner';vault=root/'build/private/vault';vault.mkdir(parents=True)
    ids=json.loads((RELEASE/'public/index.json').read_text())['case_ids']
    for cid in ids:
        packet=json.loads((RELEASE/'public/cases'/f'{cid}.json').read_text())
        values={s['id']:{'id':'measurement:'+s['id'],'sensor':s['id'],'unit':s['unit'],
            'absolute_error_bound':s['absolute_error_bound'],
            'samples':[{'t_s':0,'value':None if s['availability']=='unavailable' else .1,
                        'quality':'MISSING' if s['availability']=='unavailable' else 'GOOD',
                        'private_sample':'DO_NOT_RELEASE'}], 'reference_answer':'DO_NOT_RELEASE'} for s in packet['sensor_catalog']}
        (vault/f'{cid}.json').write_text(json.dumps(values))
    (root/'answer_key.json').write_text('PRIVATE_KEY_CANARY')
    return root

@pytest.fixture
def ledger(tmp_path):
    path=tmp_path/'original-ledger'
    SessionLedger(path)
    return path


def protocol(cap=10):
    return {'protocol_id':'test', 'prices':{'input_per_million_usd':1.25,'output_per_million_usd':4.25},
            'max_estimated_usd':cap,'agent_config':{'max_turns':8,'max_output_tokens':4096}}


def task():return {'task_id':'test','variant':'B'}


def abstain(packet):
    return {'verdict':'NOT_ESTABLISHED','numeric_observations':[], 'findings':[
        {'statement':c['statement'],'scope':c['scope'],'premises':['Transport-only test'],
         'basis':'unsupported','verdict':'NOT_ESTABLISHED','citations':['model:M1'],
         'missing_premise':'Not graded in a transport test',
         'next_evidence':{'kind':'descriptive_test','target':'test','purpose':'test'},
         'justification':'Mock response, no efficacy claim'} for c in packet['atomic_claims']]}


def test_budget_preserves_original_rows_and_config(ledger):
    before=(ledger/'session.json').read_bytes()
    old=SessionLedger(ledger)
    old.reserve(protocol(5),task(),4096,1000)
    row=(ledger/'reservations.jsonl').read_bytes()
    new=IntegrationLedger(ledger)
    new.reserve(protocol(),task(),4096,1000)
    assert (ledger/'session.json').read_bytes()==before
    assert (ledger/'reservations.jsonl').read_bytes().startswith(row)
    assert len(IntegrationLedger(ledger).rows())==2
    assert json.loads((ledger/'authorization-v2.json').read_text())['prior_reservations']==1


def test_budget_exhaustion_no_release_or_restart_reset(ledger):
    budget=IntegrationLedger(ledger)
    budget.reserve(protocol(),task(),4096,7_900_000)
    with pytest.raises(MetaAPIError):budget.reserve(protocol(),task(),4096,200_000)
    assert len(IntegrationLedger(ledger).rows())==1
    assert budget.summary()['remaining_conservative_session_usd']<.11


def test_atomic_concurrent_reservation(ledger):
    IntegrationLedger(ledger)
    def reserve(_):
        try:IntegrationLedger(ledger).reserve(protocol(),task(),4096,4_000_000);return True
        except MetaAPIError:return False
    with ThreadPoolExecutor(max_workers=4) as pool:assert sum(pool.map(reserve,range(4)))==1
    assert len(IntegrationLedger(ledger).rows())==1


def test_fail_closed_unknown_or_tampered_ledger(tmp_path,ledger):
    with pytest.raises(FileNotFoundError):IntegrationLedger(tmp_path/'no-ledger')
    budget=IntegrationLedger(ledger);budget.reserve(protocol(),task(),4096,1000)
    rows=budget.rows();rows[0]['estimated_usd_reserved']=.001
    (ledger/'reservations.jsonl').write_text(canonical(rows[0])+'\n')
    with pytest.raises(ValueError):IntegrationLedger(ledger)


def test_reservation_persisted_before_failed_http(ledger,monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY','test-placeholder')
    budget=IntegrationLedger(ledger)
    def transport(request):
        assert len(budget.rows())==1
        assert request.url==MetaResponsesClient.ENDPOINT
        return httpx.Response(503)
    factory=lambda **kw:MetaResponsesClient(transport=httpx.MockTransport(transport),**kw)
    client=ResearchClient(protocol(),budget,task(),factory=factory)
    try:
        with pytest.raises(MetaAPIError):client.create({'max_output_tokens':4096},deadline=10**12)
    finally:client.close()
    assert len(budget.rows())==1 # transport errors retain full reservation; no retries


def test_budget_denial_prevents_http(ledger,monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY','test-placeholder')
    budget=IntegrationLedger(ledger);budget.reserve(protocol(),task(),4096,7_950_000)
    called=[]
    factory=lambda **kw:MetaResponsesClient(transport=httpx.MockTransport(lambda req:called.append(req)),**kw)
    client=ResearchClient(protocol(),budget,task(),factory=factory)
    try:
        with pytest.raises(MetaAPIError):client.create({'max_output_tokens':4096,'input':'x'*10000},deadline=10**12)
    finally:client.close()
    assert called==[]


def test_whitelist_and_no_private_data(private,tmp_path):
    b=Bridge(RELEASE,private,'c-13df',tmp_path/'audit.json','B')
    try:
        packet=canonical(b.packet)
        assert 'SYN-Q-PROD' not in b.packet['initial_measurements']
        assert 'PRIVATE_KEY_CANARY' not in packet and str(private) not in packet
        for name,args in [('read_file',{'path':str(private/'answer_key.json')}),('search_history',{}),
                          ('lookup_graph',{'node':'../../answer_key.json'}),('read_document',{'id':'../../answer_key.json'})]:
            assert 'error' in b.dispatch(name,args)
        result=b.dispatch('query_sensor',{'sensor':'SYN-Q-PROD'})
        assert 'DO_NOT_RELEASE' not in canonical(result)
        assert set(result)=={'id','sensor','unit','absolute_error_bound','samples'}
        before=b.remaining_budget
        assert b.dispatch('query_sensor',{'sensor':'SYN-Q-PROD'})==result
        assert b.remaining_budget==before
        missing=b.dispatch('query_sensor',{'sensor':'P-PDG'})
        assert missing['samples'][0]['value'] is None and b.remaining_budget==0
        assert b.dispatch('query_sensor',{'sensor':'SYN-P-SEP'})['error']=='sensor_budget_exhausted'
    finally:b.close()


def test_retrieval_only_depth_changes_and_scope(private,tmp_path):
    edges={}
    for variant in ('B','E'):
        b=Bridge(RELEASE,private,'c-13df',tmp_path/f'{variant}.json',variant)
        try:
            result=b.dispatch('lookup_graph',{'node':'P-TPT'})
            edges[variant]={e['id'] for e in result['edges']}
            assert all({'provenance','scope_limitations','applicable_assumptions','epistemic_status'}<=set(e) for e in result['edges'])
            assert 'samples' not in canonical(result)
            for _ in range(3):b.dispatch('read_document',{'id':'doc:ini'})
            assert b.dispatch('lookup_graph',{'node':'L'})['error']=='tool_or_scope_not_allowed'
        finally:b.close()
    assert edges['B'] < edges['E']


def test_submission_repairs_and_valid_completion(private,tmp_path):
    b=Bridge(RELEASE,private,'c-13df',tmp_path/'valid.json','E')
    try:
        assert 'error' in b.dispatch('submit_audit',{})
        assert b.dispatch('submit_audit',abstain(b.packet))['accepted']
        assert b.result is not None
    finally:b.close()
    b=Bridge(RELEASE,private,'c-13df',tmp_path/'invalid.json','E')
    try:
        for _ in range(3):assert 'error' in b.dispatch('submit_audit',{})
        assert b.dispatch('submit_audit',abstain(b.packet))['error']=='session_closed'
    finally:b.close()


def test_fresh_model_contexts_and_explicit_tools(private,tmp_path,ledger,monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY','test-placeholder')
    initial=[]
    for i,(cid,variant) in enumerate([('c-13df','B'),('c-42e8','E')]):
        b=Bridge(RELEASE,private,cid,tmp_path/f'{i}.json',variant)
        def handler(request):
            payload=json.loads(request.content);initial.append(payload)
            assert len(payload['input'])==1 and 'previous_response_id' not in payload
            assert json.loads(payload['input'][0]['content'][0]['text'])['case_id']==cid
            assert {t['name'] for t in payload['tools']}=={'query_sensor','lookup_graph','read_document','submit_audit'}
            assert 'PRIVATE_KEY_CANARY' not in canonical(payload) and 'test-placeholder' not in canonical(payload)
            assert str(private) not in canonical(payload)
            return httpx.Response(200,json={'status':'completed','output':[{'type':'function_call','call_id':'submit',
                'name':'submit_audit','arguments':canonical(abstain(b.packet))}],
                'usage':{'input_tokens':100,'output_tokens':100,'total_tokens':200}})
        factory=lambda **kw:MetaResponsesClient(transport=httpx.MockTransport(handler),**kw)
        client=ResearchClient(protocol(),IntegrationLedger(ledger),task(),factory=factory)
        try:
            result=run_tool_agent(b,client,AgentConfig(max_turns=8,max_tool_calls=24,max_output_tokens=4096,variant='sensor_only'),
                instructions=INSTRUCTIONS,tools=tools(),initial_history=[{'role':'user','content':[{'type':'input_text','text':canonical(b.packet)}]}],
                prompt_version='test',submission_reason='submitted',is_complete=lambda:b.result is not None,decode_arguments=decode)
            assert result.status=='completed'
        finally:client.close();b.close()
    assert len(initial)==2


def test_explicit_platform_route_preserves_endpoint_and_tls(monkeypatch):
    from research.muse_integration.transport import factory
    monkeypatch.setenv('HTTPS_PROXY','ftp://unapproved-proxy')
    assert factory(False) is MetaResponsesClient
    with pytest.raises(ValueError):factory(True)
    assert MetaResponsesClient.ENDPOINT=='https://api.meta.ai/v1/responses'


def test_underpricing_and_nonfinite_cost_refused(ledger):
    budget=IntegrationLedger(ledger)
    p=protocol();p['prices']['input_per_million_usd']=float('nan')
    with pytest.raises(ValueError):budget.reserve(p,task(),4096,1000)
    p=protocol();p['prices']['input_per_million_usd']=.01
    with pytest.raises(ValueError):budget.reserve(p,task(),4096,1000)
