"""No paid calls. Accounting integrity, migration, races and unknown-cost failures."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

from petromind.audit import canonical
from petromind.eval_protocol import digest
from petromind.meta_api import MetaAPIError,MetaResponsesClient
from research.sprint_a.experiment import SessionLedger
from research.sprint_c.accounting import SettlementLedger,provider_receipt,history,NANO
from research.sprint_c.client import SettlingClient


@pytest.fixture
def historical(tmp_path):
    original=tmp_path/'original';old=SessionLedger(original)
    protocol={'version':'prior'};protocol['protocol_id']=digest(protocol)
    old.reserve({'protocol_id':protocol['protocol_id'],'prices':{'input_per_million_usd':1.25,'output_per_million_usd':4.25},'max_estimated_usd':5},
                {'task_id':'case','variant':'B'},4096,1000)
    run=tmp_path/'prior';(run/'pilot/case-B').mkdir(parents=True);(run/'suite').mkdir()
    (run/'protocol.json').write_text(canonical(protocol))
    usage={'input_tokens':100,'output_tokens':100,'cached_tokens':0,'total_tokens':200}
    (run/'pilot/case-B/events.jsonl').write_text(canonical({'kind':'usage','details_json':canonical(usage)})+'\n')
    row={'protocol_id':protocol['protocol_id'],'task_id':'case','variant':'B','requests':1,
         'usage':{'responses_with_usage':1,'estimated_cost_usd':.00055}}
    (run/'pilot/results.jsonl').write_text(canonical(row)+'\n');(run/'suite/results.jsonl').write_text('')
    return original,run

@pytest.fixture
def ledger(historical):return SettlementLedger.authorize(*historical)


def reserve(l,**kw):return l.reserve('protocol',{'case':'test'},kw.get('input_bound',10000),kw.get('cap',4096),'a'*64)


def response(res,**kw):
    u={'input_tokens':kw.get('input_tokens',1000),'output_tokens':100,'total_tokens':kw.get('input_tokens',1000)+100,
       'input_tokens_details':{'cached_tokens':100}}
    return {'id':kw.get('id','resp_'+uuid.uuid4().hex),'model':'muse-spark-1.3','status':'completed','usage':u,
            'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'test'}]}]}


def settle(l,r,**kw):
    rec=provider_receipt(response(r,**kw),r);l.settle(r['reservation_id'],rec);return rec


def test_verified_settlement_and_restart(ledger):
    r=reserve(ledger);before=ledger.summary();settle(ledger,r)
    summary=SettlementLedger(ledger.original).summary()
    assert summary['verified_new_settlements']==1 and summary['sprint_c_outstanding_reservations_usd']==0
    assert summary['sprint_c_conservatively_accounted_usd']<before['sprint_c_conservatively_accounted_usd']
    assert summary['historical_unresolved_reservations_usd']==summary['historical_reservations_usd']


def test_missing_usage_never_settles(ledger):
    r=reserve(ledger);data=response(r);del data['usage']
    with pytest.raises(ValueError):provider_receipt(data,r)
    ledger.unverified(r['reservation_id'])
    assert ledger.summary()['verified_new_settlements']==0
    with pytest.raises(MetaAPIError):reserve(ledger)


def test_interrupted_request_full_reservation_on_restart(ledger):
    r=reserve(ledger);l=SettlementLedger(ledger.original)
    assert l.summary()['sprint_c_outstanding_reservations_usd']==r['reserved_nusd']/NANO
    with pytest.raises(MetaAPIError):reserve(l)


def test_duplicate_settlement_and_response_ids(ledger):
    r=reserve(ledger);receipt=settle(ledger,r)
    with pytest.raises(ValueError):ledger.settle(r['reservation_id'],receipt)
    second=reserve(ledger)
    bad=provider_receipt(response(second,id=receipt['provider_response_id']),second)
    with pytest.raises(ValueError):ledger.settle(second['reservation_id'],bad)


@pytest.mark.parametrize('change',[{'input_tokens':-1},{'output_tokens':True},{'total_tokens':7},{'input_tokens_details':{'cached_tokens':1000000}}])
def test_tampered_or_inconsistent_provider_usage(ledger,change):
    r=reserve(ledger);data=response(r);data['usage'].update(change)
    with pytest.raises(ValueError):provider_receipt(data,r)
    assert ledger.summary()['verified_new_settlements']==0


def test_request_identifier_mismatch(ledger):
    r=reserve(ledger);rec=provider_receipt(response(r),r);rec['request_digest']='b'*64
    with pytest.raises(ValueError):ledger.settle(r['reservation_id'],rec)


def test_wrong_pricing_fails_closed(ledger):
    p=ledger.policy_path;policy=json.loads(p.read_text());policy['prices']['input_nusd_per_token']=1
    policy['policy_id']=digest({k:v for k,v in policy.items() if k!='policy_id'});p.write_text(canonical(policy))
    with pytest.raises(ValueError):SettlementLedger(ledger.original)


def test_broken_chain_and_corrupted_append(ledger):
    reserve(ledger);raw=ledger.path.read_text();ledger.path.write_text(raw[:-1])
    with pytest.raises(ValueError):SettlementLedger(ledger.original)
    rows=[json.loads(x) for x in raw.splitlines()];rows[0]['data']['reserved_nusd']=1
    ledger.path.write_text(canonical(rows[0])+'\n')
    with pytest.raises(ValueError):SettlementLedger(ledger.original)


def test_valid_prefix_truncation_detected_by_head(ledger):
    r=reserve(ledger);settle(ledger,r)
    ledger.path.write_text(ledger.path.read_text().splitlines()[0]+'\n')
    with pytest.raises(ValueError):SettlementLedger(ledger.original)


def test_budget_exhaustion_and_no_request_sent(ledger):
    r=reserve(ledger,input_bound=7_980_000)
    data=response(r,input_tokens=7_980_000);data['usage']['output_tokens']=4000;data['usage']['total_tokens']=7_984_000
    ledger.settle(r['reservation_id'],provider_receipt(data,r))
    with pytest.raises(MetaAPIError):reserve(ledger,input_bound=10000)
    assert ledger.summary()['sprint_c_conservatively_accounted_usd']<=10


def test_concurrent_reservations_only_one_can_start(ledger):
    def attempt(_):
        try:reserve(SettlementLedger(ledger.original));return True
        except MetaAPIError:return False
    with ThreadPoolExecutor(max_workers=6) as pool:assert sum(pool.map(attempt,range(6)))==1
    assert ledger.summary()['http_reservations']==1


def test_concurrent_settlement_and_reservation(ledger):
    r=reserve(ledger);rec=provider_receipt(response(r),r)
    def attempt():
        try:return reserve(ledger)
        except MetaAPIError:return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(ledger.settle,r['reservation_id'],rec);b=pool.submit(attempt);a.result();b.result()
    assert ledger.summary()['sprint_c_conservatively_accounted_usd']<=10


def test_historical_reconciliation_and_no_record_rewrite(historical):
    original,run=historical;before=(original/'reservations.jsonl').read_bytes();config=(original/'session.json').read_bytes()
    l=SettlementLedger.authorize(original,run)
    assert (original/'reservations.jsonl').read_bytes()==before and (original/'session.json').read_bytes()==config
    assert l.summary()['historical_observed_usage_estimate_usd']==.00055
    assert l.summary()['historical_verified_settlements_usd']==0
    with pytest.raises(FileExistsError):SettlementLedger.authorize(original,run)
    (original/'reservations.jsonl').write_bytes(before+b'\n')
    with pytest.raises(ValueError):SettlementLedger(original)


def test_historical_usage_tampering_refused(historical):
    original,run=historical
    p=run/'pilot/results.jsonl';x=json.loads(p.read_text());x['usage']['estimated_cost_usd']=0;p.write_text(canonical(x)+'\n')
    with pytest.raises(ValueError):history(original,run)


def test_transport_failure_holds_money_and_no_retries(ledger,monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY','test-placeholder')
    observed=[]
    def handler(request):
        assert ledger.summary()['http_reservations']==1
        observed.append(request);return httpx.Response(503)
    factory=lambda **kw:MetaResponsesClient(transport=httpx.MockTransport(handler),**kw)
    client=SettlingClient({'protocol_id':'test','platform_proxy':False,'agent_config':{'max_turns':8,'max_output_tokens':4096}},ledger,{},factory=factory)
    try:
        with pytest.raises(MetaAPIError):client.create({'max_output_tokens':4096},deadline=10**12)
    finally:client.close()
    assert len(observed)==1 and ledger.summary()['sprint_c_outstanding_reservations_usd']>0


def test_transport_settles_http_envelope_not_model_text(ledger,monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY','test-placeholder')
    def handler(request):
        assert ledger.summary()['http_reservations']==1
        data=response(None);data['output'][0]['content'][0]['text']='{"usage":{"input_tokens":0,"output_tokens":0}}'
        return httpx.Response(200,json=data)
    factory=lambda **kw:MetaResponsesClient(transport=httpx.MockTransport(handler),**kw)
    client=SettlingClient({'protocol_id':'test','platform_proxy':False,'agent_config':{'max_turns':8,'max_output_tokens':4096}},ledger,{},factory=factory)
    try:client.create({'max_output_tokens':4096},deadline=10**12)
    finally:client.close()
    assert ledger.summary()['sprint_c_settled_estimate_usd']>0


def test_closed_transport_continues_only_after_versioned_acknowledgment(ledger):
    r=reserve(ledger);original_money=ledger.summary()['sprint_c_outstanding_reservations_usd']
    with pytest.raises(ValueError):ledger.record_closed_transport(r['reservation_id'],'a'*64)
    ledger.enable_closed_transport_policy()
    with pytest.raises(MetaAPIError):reserve(ledger) # unacknowledged request still blocks
    ledger.record_closed_transport(r['reservation_id'],'a'*64)
    second=reserve(ledger)
    assert ledger.summary()['sprint_c_outstanding_reservations_usd']==original_money+second['reserved_nusd']/NANO
    settle(ledger,second)
    state=SettlementLedger(ledger.original).summary()
    assert state['sprint_c_outstanding_reservations_usd']==original_money
    assert state['closed_unsettled_transports']==1
    with pytest.raises(ValueError):ledger.record_closed_transport(r['reservation_id'],'a'*64)
