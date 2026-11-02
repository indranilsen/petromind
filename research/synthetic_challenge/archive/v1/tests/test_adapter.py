"""Public interface tests only. No reference case labels or hidden measurements."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('synthetic_adapter',ROOT/'adapter.py')
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)

@pytest.fixture
def session():
    def read(tag):
        catalog={s['id']:s for s in json.loads((ROOT/'public/cases/c-7a91.json').read_text())['sensor_catalog']}
        return {'id':'measurement:'+tag,'sensor':tag,'unit':catalog[tag]['unit'],'absolute_error_bound':catalog[tag]['absolute_error_bound'],
                'samples':[{'t_s':0,'value':None,'quality':'MISSING','private_extra':'must drop'}], 'private_extra':'must drop'}
    return adapter.ChallengeSession(ROOT/'public','c-7a91',read)

def assessment(session):
    # A syntactically valid example, not a scientifically graded result.
    fs=[]
    for a in session.packet()['atomic_claims']:
        fs.append(dict(statement=a['statement'],scope=a['scope'],premises=['example premise'],basis='unsupported',
                       verdict='NOT_ESTABLISHED',citations=[],missing_premise='example missing premise',
                       next_evidence={'kind':'no_verified_discriminating_test','target':'','purpose':'example'},justification='Structure example only.'))
    return dict(verdict='NOT_ESTABLISHED',findings=fs,numeric_observations=[])

def test_initial_count_and_budget(session):
    session.call('query_sensor',{'sensor':'QBS'})
    session.call('query_sensor',{'sensor':'QGL'})
    assert session.call('query_sensor',{'sensor':'P-PDG'})['error']=='sensor_budget_exhausted'

def test_cached_request_does_not_charge(session):
    for _ in range(4):session.call('query_sensor',{'sensor':'P-TPT'})
    assert 'error' not in session.call('query_sensor',{'sensor':'SYN-Q-PROD'})
    assert 'error' not in session.call('query_sensor',{'sensor':'SYN-P-SEP'})

def test_recursive_whitelist(session):
    r=session.call('query_sensor',{'sensor':'SYN-Q-PROD'})
    assert 'private_extra' not in json.dumps(r)

def test_graph_connected_and_provenance(session):
    r=session.call('lookup_graph',{'node':'P-TPT','hops':2})
    assert r['edges'] and any(e['object']=='U' for e in r['edges'])
    for e in r['edges']:
        assert all(k in e for k in ['subject','predicate','object','provenance','epistemic_status','applicable_assumptions','scope_limitations'])

def test_receipt_membership_and_repairs(session):
    a=assessment(session);a['findings'][0]['citations']=['doc:example']
    assert session.call('submit_audit',a)['error']=='unreceived_citation'
    session.call('read_document',{'id':'doc:example'})
    assert session.call('submit_audit',a)['accepted']
    assert session.call('query_sensor',{'sensor':'QBS'})['error']=='session_closed'

def test_no_numeric_invention(session):
    a=assessment(session);a['numeric_observations']=[{'sensor':'P-TPT','metric':'t_s:0','value':12345}]
    assert session.call('submit_audit',a)['error']=='invented_numeric_observation'

def test_no_hidden_sensor_numbers(session):
    a=assessment(session);a['numeric_observations']=[{'sensor':'SYN-Q-PROD','metric':'t_s:0','value':0.006}]
    assert session.call('submit_audit',a)['error']=='unobserved_numeric_sensor'

@pytest.mark.parametrize('bad',[{}, {'verdict':[],'findings':None,'numeric_observations':[]},
 {'verdict':'SUPPORTED','findings':[{'statement':[]}],'numeric_observations':[]}, {'x':float('nan')}])
def test_malformed_rejected_without_exception(session,bad):
    assert 'error' in session.call('submit_audit',bad)

def test_repair_limit(session):
    for _ in range(3):assert 'error' in session.call('submit_audit',{})
    assert session.call('submit_audit',assessment(session))['error']=='session_closed'

def test_log_immutable_and_hash_chain(session):
    r=session.call('read_document',{'id':'doc:ini'});r['id']='changed'
    events=session.audit;events[0]['result']['case_id']='changed'
    previous='0'*64
    for event in session.audit:
        data={k:v for k,v in event.items() if k!='digest'}
        assert event['previous']==previous
        assert hashlib.sha256(adapter.canonical(data).encode()).hexdigest()==event['digest']
        previous=event['digest']

def test_citation_paths_not_accepted(session):
    assert session.call('read_document',{'id':'../../private/answer_key.json'})['error']=='unknown_document'

def test_public_is_separate():
    ids=json.loads((ROOT/'public/index.json').read_text())['case_ids']
    assert len(ids)==7 and len(set(ids))==7
    banned={'atomic_verdicts','generating_cause','raw_simulation','parameters','required_acquisition','minimum_evidence','variant'}
    def check(obj):
        if isinstance(obj,dict):
            assert not (set(obj)&banned)
            for v in obj.values():check(v)
        elif isinstance(obj,list):
            for v in obj:check(v)
    for p in (ROOT/'public').rglob('*.json'):check(json.loads(p.read_text()))

def test_atomic_aggregate():
    assert adapter.aggregate(['SUPPORTED','NOT_ESTABLISHED'])=='PARTIALLY_SUPPORTED'
    assert adapter.aggregate(['SUPPORTED','CONTRADICTED'])=='CONTRADICTED'
    with pytest.raises(ValueError):adapter.aggregate(['PARTIALLY_SUPPORTED'])
