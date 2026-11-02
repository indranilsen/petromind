"""Append-only reservation/settlement policy, shared ORIGINAL research lock.

Money is integer nanodollars. Only the trusted HTTPS transport supplies receipts;
there is deliberately no model-facing settlement or billing tool. Local hash
chains rely on a trusted owner and externally retained final digest, not signatures.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from petromind.audit import canonical
from petromind.eval_protocol import digest
from petromind.meta_api import MetaAPIError
from research.muse_integration.budget import IntegrationLedger

NANO = 1_000_000_000
PRICES = {'input_nusd_per_token':1250, 'cached_input_nusd_per_token':150,
          'output_nusd_per_token':4250, 'model':'muse-spark-1.3',
          'source':'https://dev.meta.ai/docs/pricing-rate-limits','verified_date':'2026-11-02'}
ZERO = '0'*64


def file_digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dollars(n):return n/NANO


def nanos(value):
    x=Decimal(str(value))*NANO
    if not x.is_finite() or x!=x.to_integral_value() or x<0:raise ValueError('invalid_money')
    return int(x)


def history(ledger_dir, run):
    """Reconcile saved observations, WITHOUT retrospectively releasing old holds."""
    ledger=IntegrationLedger(ledger_dir)
    reservations=ledger.rows()
    run=Path(run);p=json.loads((run/'protocol.json').read_text())
    if digest({k:v for k,v in p.items() if k!='protocol_id'})!=p['protocol_id']:
        raise ValueError('historical_protocol_changed')
    files={};requests=0;usage_rows=0;observed=Decimal(0)
    from collections import Counter
    expected=Counter()
    for stage in ('pilot','suite'):
        result_path=run/stage/'results.jsonl'
        files[str(result_path.relative_to(run))]=file_digest(result_path)
        rows=[json.loads(x) for x in result_path.read_text().splitlines()]
        for r in rows:
            if r['protocol_id']!=p['protocol_id']:raise ValueError('historical_protocol_mismatch')
            cell=run/stage/f"{r['task_id']}-{r['variant']}"
            events_path=cell/'events.jsonl'
            files[str(events_path.relative_to(run))]=file_digest(events_path)
            events=[json.loads(x) for x in events_path.read_text().splitlines()]
            usages=[json.loads(e['details_json']) for e in events if e['kind']=='usage']
            if len(usages)!=r['usage']['responses_with_usage']:raise ValueError('historical_usage_count_mismatch')
            amounts=[]
            for u in usages:
                i,o,c=u['input_tokens'],u['output_tokens'],u.get('cached_tokens',0)
                if any(type(n)is not int or n<0 for n in (i,o,c)) or c>i:raise ValueError('historical_usage_invalid')
                amounts.append(Decimal((i-c)*1250+c*150+o*4250)/NANO)
            amount=sum(amounts,Decimal(0))
            if abs(amount-Decimal(str(r['usage']['estimated_cost_usd'])))>Decimal('0.000000001'):
                raise ValueError('historical_cost_mismatch')
            requests+=r['requests'];usage_rows+=len(usages);observed+=amount
            expected[(r['task_id'],r['variant'])]+=r['requests']
    if len(reservations)!=requests or expected!=Counter((r['task_id'],r['variant']) for r in reservations):
        raise ValueError('historical_reservation_reconciliation_failed')
    if any(r['protocol_id']!=p['protocol_id'] for r in reservations):raise ValueError('unreconciled_historical_protocol')
    return {'historical_reservations_nusd':sum(nanos(r['estimated_usd_reserved']) for r in reservations),
        'historical_reservation_count':len(reservations),'historical_final_digest':reservations[-1]['digest'] if reservations else ZERO,
        'historical_observed_usage_estimate_nusd':int(observed*NANO),
        'historical_usage_rows':usage_rows,'historical_verified_settlements_nusd':0,
        'historical_unresolved_held_nusd':sum(nanos(r['estimated_usd_reserved']) for r in reservations),
        'historical_policy':'Keep ALL old reservations held. Captured usage lacks provider response IDs and request/response commitments required by new settlement policy. Observed estimate is reported separately, never added again or reclaimed.',
        'historical_files':files,'historical_protocol_id':p['protocol_id']}


class SettlementLedger:
    def __init__(self, original_directory):
        self.original=Path(original_directory).resolve()
        self.directory=self.original/'sprint-c-accounting-v1'
        self.policy_path=self.directory/'authorization.json'
        self.path=self.directory/'events.jsonl'
        self.head_path=self.directory/'head.json'
        if not self.policy_path.is_file() or not self.path.is_file():
            raise ValueError('explicit_sprint_c_authorization_required')
        with self.lock():self._state()

    @contextmanager
    def lock(self):
        if not (self.original/'session.json').is_file():raise ValueError('original_ledger_missing')
        with (self.original/'lock').open('a') as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            yield

    @classmethod
    def authorize(cls, original, prior_run):
        """Explicit one-time policy creation. No default/fresh-directory fallback."""
        original=Path(original).resolve()
        receipt=history(original,prior_run)
        value={'version':'sprint-c-reservation-settlement-v1','prices':PRICES,
            'additional_authorization_nusd':10*NANO,'historical_authorized_ceiling_nusd':10*NANO,
            'max_http_attempts':256,'max_reserved_output_tokens':1_048_576,
            'max_inflight_requests':1,'history':receipt,
            'history_config_sha256':file_digest(original/'session.json'),
            'history_authorization_sha256':file_digest(original/'authorization-v2.json'),
            'historical_reservations_sha256':file_digest(original/'reservations.jsonl'),
            'owner_authorization':'Sprint C instructions authorize $10 ADDITIONAL, isolated research only; valid new responses may settle, old rows never modified.'}
        value['policy_id']=digest(value)
        # Recheck old state under its shared lock to avoid a migration race.
        with (original/'lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if file_digest(original/'reservations.jsonl')!=value['historical_reservations_sha256']:
                raise ValueError('historical_ledger_changed_during_migration')
            directory=original/'sprint-c-accounting-v1'
            directory.mkdir(mode=0o700) # exclusive; never reset existing accounting
            for name,data in [('authorization.json',canonical(value)+'\n'),('events.jsonl',''),('head.json',canonical({'policy_id':value['policy_id'],'sequence':0,'digest':ZERO})+'\n')]:
                fd=os.open(directory/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'w') as f:f.write(data);f.flush();os.fsync(f.fileno())
            fd=os.open(directory,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
            fd=os.open(original,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
        return cls(original)

    def _policy(self):
        p=json.loads(self.policy_path.read_text())
        if (digest({k:v for k,v in p.items() if k!='policy_id'})!=p['policy_id']
            or p['version']!='sprint-c-reservation-settlement-v1' or p['prices']!=PRICES
            or p['additional_authorization_nusd']!=10*NANO or p['historical_authorized_ceiling_nusd']!=10*NANO
            or p['max_http_attempts']!=256 or p['max_reserved_output_tokens']!=1_048_576 or p['max_inflight_requests']!=1):
            raise ValueError('accounting_policy_changed')
        for file,key in [('session.json','history_config_sha256'),('authorization-v2.json','history_authorization_sha256'),('reservations.jsonl','historical_reservations_sha256')]:
            if file_digest(self.original/file)!=p[key]:raise ValueError('historical_ledger_changed')
        h=p['history']
        if h['historical_verified_settlements_nusd']!=0 or h['historical_unresolved_held_nusd']!=h['historical_reservations_nusd'] or h['historical_unresolved_held_nusd']>10*NANO:
            raise ValueError('historical_policy_invalid')
        amendment=self.directory/'operational-policy-v2.json'
        if amendment.exists():
            a=json.loads(amendment.read_text())
            if (set(a)!={'version','base_policy_id','rule','amendment_id','max_http_attempts','max_reserved_output_tokens'} or a['version']!='closed-transport-full-hold-v2'
                or a['max_http_attempts']!=320 or a['max_reserved_output_tokens']!=1_310_720
                or a['base_policy_id']!=p['policy_id'] or digest({k:v for k,v in a.items() if k!='amendment_id'})!=a['amendment_id']
                or a['rule']!='Closed local transports retain their full unresolved monetary holds; only live or unacknowledged requests block concurrency. No new authorization or historical release.'):
                raise ValueError('operational_amendment_invalid')
            p={**p,'operational_amendment':a,'max_http_attempts':a['max_http_attempts'],'max_reserved_output_tokens':a['max_reserved_output_tokens']}
        return p

    def _state(self):
        p=self._policy();raw=self.path.read_text()
        if raw and not raw.endswith('\n'):raise ValueError('incomplete_ledger_append')
        rows=[json.loads(x) for x in raw.splitlines()]
        previous=ZERO;reservations={};settled={};provider_ids=set();seen_unverified=set();closed=set()
        for index,row in enumerate(rows,1):
            if (set(row)!={'sequence','previous_hash','policy_id','kind','data','digest'}
                or row['sequence']!=index or row['previous_hash']!=previous or row['policy_id']!=p['policy_id']
                or digest({k:v for k,v in row.items() if k!='digest'})!=row['digest']):
                raise ValueError('accounting_chain_invalid')
            d=row['data'];kind=row['kind'];rid=d.get('reservation_id')
            if kind=='reservation':
                if set(d)!={'reservation_id','protocol_id','task','input_token_bound','output_token_cap','request_digest','reserved_nusd'}:
                    raise ValueError('reservation_schema_invalid')
                if (not isinstance(rid,str) or not rid or rid in reservations
                    or type(d['input_token_bound'])is not int or d['input_token_bound']<=0
                    or type(d['output_token_cap'])is not int or not 16<=d['output_token_cap']<=8192
                    or type(d['reserved_nusd'])is not int
                    or d['reserved_nusd']!=d['input_token_bound']*1250+d['output_token_cap']*4250):
                    raise ValueError('reservation_amount_invalid')
                if any(k not in settled and k not in closed for k in reservations):raise ValueError('concurrent_or_unresolved_reservation_in_chain')
                reservations[rid]=d
            elif kind=='settlement':
                if rid not in reservations or rid in settled or rid in seen_unverified:
                    raise ValueError('unknown_duplicate_or_unverifiable_settlement')
                validate_receipt(d['receipt'],reservations[rid])
                if set(d)!={'reservation_id','receipt','settled_nusd','released_nusd'} or d['receipt']['provider_response_id'] in provider_ids:
                    raise ValueError('settlement_identifier_invalid')
                cost=receipt_cost(d['receipt'])
                if type(d['settled_nusd'])is not int or type(d['released_nusd'])is not int or d['settled_nusd']!=cost or d['released_nusd']!=reservations[rid]['reserved_nusd']-cost:
                    raise ValueError('settlement_amount_invalid')
                settled[rid]=d;provider_ids.add(d['receipt']['provider_response_id'])
            elif kind=='transport_closed_unsettled':
                if ('operational_amendment' not in p or set(d)!={'reservation_id','amendment_id','evidence_digest','reason'}
                    or d['amendment_id']!=p['operational_amendment']['amendment_id'] or rid not in reservations or rid in settled or rid in closed
                    or d['reason']!='owner_verified_local_transport_ended' or not isinstance(d['evidence_digest'],str) or len(d['evidence_digest'])!=64):
                    raise ValueError('closed_transport_evidence_invalid')
                closed.add(rid)
            elif kind=='unverified_response':
                if set(d)!={'reservation_id','reason'} or rid not in reservations or rid in settled or rid in seen_unverified or d['reason']!='provider_receipt_not_verifiable':
                    raise ValueError('unverified_response_invalid')
                seen_unverified.add(rid)
            else:raise ValueError('unknown_accounting_event')
            active=[r for r in reservations if r not in settled]
            charge=sum(r['settled_nusd'] for r in settled.values())+sum(reservations[r]['reserved_nusd'] for r in active)
            if (charge>p['additional_authorization_nusd'] or len(reservations)>p['max_http_attempts']
                or sum(r['output_token_cap'] for r in reservations.values())>p['max_reserved_output_tokens']):
                raise ValueError('ledger_exceeds_authorization')
            previous=row['digest']
        head=json.loads(self.head_path.read_text())
        if head!={'policy_id':p['policy_id'],'sequence':len(rows),'digest':previous}:
            raise ValueError('ledger_head_checkpoint_mismatch')
        self.closed_transports=closed
        return p,rows,reservations,settled,seen_unverified

    def _append(self,p,rows,kind,data):
        row={'sequence':len(rows)+1,'previous_hash':rows[-1]['digest'] if rows else ZERO,
             'policy_id':p['policy_id'],'kind':kind,'data':data}
        row['digest']=digest(row)
        with self.path.open('a') as f:
            f.write(canonical(row)+'\n');f.flush();os.fsync(f.fileno())
        head={'policy_id':p['policy_id'],'sequence':row['sequence'],'digest':row['digest']}
        temporary=self.directory/'head.new'
        with temporary.open('x') as f:
            f.write(canonical(head)+'\n');f.flush();os.fsync(f.fileno())
        os.replace(temporary,self.head_path)
        fd=os.open(self.directory,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        return row

    def reserve(self,protocol_id,task,input_bound,output_cap,request_digest):
        if type(input_bound)is not int or input_bound<=0 or type(output_cap)is not int or not 16<=output_cap<=8192:
            raise ValueError('invalid_request_bounds')
        with self.lock():
            p,rows,reservations,settled,unverified=self._state()
            amount=input_bound*1250+output_cap*4250
            active={rid:r for rid,r in reservations.items() if rid not in settled}
            charged=sum(r['settled_nusd'] for r in settled.values())+sum(r['reserved_nusd'] for r in active.values())
            if (charged+amount>10*NANO or len(reservations)>=p['max_http_attempts']
                or sum(r['output_token_cap'] for r in reservations.values())+output_cap>p['max_reserved_output_tokens']):
                raise MetaAPIError('sprint_c_spending_or_attempt_cap')
            # Unknown/interrupted reservations retain full money; they must not
            # become a new path to parallel HTTP. Owner must stop and reconcile.
            if any(rid not in self.closed_transports for rid in active):raise MetaAPIError('sprint_c_outstanding_request_fail_closed')
            data={'reservation_id':uuid.uuid4().hex,'protocol_id':protocol_id,'task':task,
                  'input_token_bound':input_bound,'output_token_cap':output_cap,
                  'request_digest':request_digest,'reserved_nusd':amount}
            self._append(p,rows,'reservation',data)
            return data

    def settle(self,rid,receipt):
        with self.lock():
            p,rows,reservations,settled,unverified=self._state()
            if rid not in reservations or rid in settled or rid in unverified:raise ValueError('unknown_or_duplicate_settlement')
            validate_receipt(receipt,reservations[rid])
            if receipt['provider_response_id'] in {x['receipt']['provider_response_id'] for x in settled.values()}:
                raise ValueError('duplicate_provider_response_id')
            cost=receipt_cost(receipt)
            self._append(p,rows,'settlement',{'reservation_id':rid,'receipt':receipt,'settled_nusd':cost,
                'released_nusd':reservations[rid]['reserved_nusd']-cost})

    def unverified(self,rid):
        with self.lock():
            p,rows,reservations,settled,unknown=self._state()
            if rid not in reservations or rid in settled or rid in unknown:raise ValueError('unknown_or_duplicate_unverified')
            self._append(p,rows,'unverified_response',{'reservation_id':rid,'reason':'provider_receipt_not_verifiable'})

    def enable_closed_transport_policy(self):
        with self.lock():
            p,rows,*_=self._state()
            amendment={'version':'closed-transport-full-hold-v2','base_policy_id':p['policy_id'],
                'max_http_attempts':320,'max_reserved_output_tokens':1_310_720,
                'rule':'Closed local transports retain their full unresolved monetary holds; only live or unacknowledged requests block concurrency. No new authorization or historical release.'}
            amendment['amendment_id']=digest(amendment)
            path=self.directory/'operational-policy-v2.json'
            with path.open('x') as f:
                f.write(canonical(amendment)+'\n');f.flush();os.fsync(f.fileno())
            fd=os.open(self.directory,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
            return amendment

    def record_closed_transport(self,rid,evidence_digest):
        # Trusted owner call only after the HTTP client is closed and the failed
        # attempt record is durable. This NEVER settles or releases its money.
        with self.lock():
            p,rows,reservations,settled,_=self._state()
            if 'operational_amendment' not in p or rid not in reservations or rid in settled or rid in self.closed_transports:
                raise ValueError('closed_transport_not_eligible')
            if not isinstance(evidence_digest,str) or len(evidence_digest)!=64:raise ValueError('closed_evidence_required')
            self._append(p,rows,'transport_closed_unsettled',{'reservation_id':rid,
                'amendment_id':p['operational_amendment']['amendment_id'],'evidence_digest':evidence_digest,
                'reason':'owner_verified_local_transport_ended'})

    def summary(self):
        with self.lock():
            p,rows,reservations,settled,unknown=self._state()
            held=sum(r['reserved_nusd'] for rid,r in reservations.items() if rid not in settled)
            spent=sum(s['settled_nusd'] for s in settled.values());charge=spent+held
            historical=p['history']['historical_unresolved_held_nusd']
            return {'policy_id':p['policy_id'],'historical_reservations_usd':dollars(p['history']['historical_reservations_nusd']),
                'historical_observed_usage_estimate_usd':dollars(p['history']['historical_observed_usage_estimate_nusd']),
                'historical_verified_settlements_usd':0,'historical_unresolved_reservations_usd':dollars(historical),
                'additional_authorized_usd':10,'sprint_c_gross_reservations_usd':dollars(sum(r['reserved_nusd'] for r in reservations.values())),
                'sprint_c_settled_estimate_usd':dollars(spent),'sprint_c_outstanding_reservations_usd':dollars(held),
                'sprint_c_conservatively_accounted_usd':dollars(charge),'sprint_c_available_usd':dollars(10*NANO-charge),
                'aggregate_authorized_ceiling_usd':20,'aggregate_conservatively_accounted_usd':dollars(historical+charge),
                'remaining_aggregate_capacity_usd':dollars(20*NANO-historical-charge),
                'http_reservations':len(reservations),'verified_new_settlements':len(settled),'unverified_responses':len(unknown),
                'closed_unsettled_transports':len(self.closed_transports),'operational_policy_id':p.get('operational_amendment',{}).get('amendment_id'),
                'final_event_digest':rows[-1]['digest'] if rows else ZERO,'actual_provider_billing_usd':None,
                'note':'New verified settlements replace their active holds, not historical records. Historical observations are informational and not added twice. No original unused capacity transferred into Sprint C.'}


def receipt_cost(r):
    u=r['usage'];return (u['input_tokens']-u['cached_tokens'])*1250+u['cached_tokens']*150+u['output_tokens']*4250


def validate_receipt(r,reservation):
    if set(r)!={'source','provider_response_id','response_digest','request_digest','model','status','usage'}:
        raise ValueError('invalid_provider_receipt_shape')
    if (r['source']!='validated_fixed_endpoint_https_response' or r['model']!=PRICES['model'] or r['status']!='completed'
        or not isinstance(r['provider_response_id'],str) or not 1<=len(r['provider_response_id'])<=200
        or not isinstance(r['response_digest'],str) or len(r['response_digest'])!=64
        or r['request_digest']!=reservation['request_digest']):
        raise ValueError('unverifiable_provider_receipt')
    u=r['usage']
    if set(u)!={'input_tokens','output_tokens','total_tokens','cached_tokens'} or any(type(x)is not int or x<0 for x in u.values()):
        raise ValueError('invalid_usage_counts')
    if (u['total_tokens']!=u['input_tokens']+u['output_tokens'] or u['cached_tokens']>u['input_tokens']
        or u['input_tokens']>reservation['input_token_bound'] or u['output_tokens']>reservation['output_token_cap']
        or receipt_cost(r)>reservation['reserved_nusd']):
        raise ValueError('usage_outside_reserved_bounds')


def provider_receipt(response,reservation):
    """Called only on the returned HTTP envelope, never text/function arguments."""
    if not isinstance(response,dict) or response.get('error') is not None:raise ValueError('invalid_response')
    u=response.get('usage')
    if not isinstance(u,dict):raise ValueError('usage_missing')
    detail=u.get('input_tokens_details')
    if detail is not None and not isinstance(detail,dict):raise ValueError('invalid_usage_details')
    cached=(detail or {}).get('cached_tokens',0)
    if not isinstance(response.get('output'),list) or not response['output'] or not all(isinstance(x,dict) for x in response['output']):raise ValueError('invalid_response_output')
    receipt={'source':'validated_fixed_endpoint_https_response','provider_response_id':response.get('id'),
        'response_digest':digest(response),'request_digest':reservation['request_digest'],
        'model':response.get('model'),'status':response.get('status'),
        'usage':{k:u.get(k) for k in ('input_tokens','output_tokens','total_tokens')}|{'cached_tokens':cached}}
    validate_receipt(receipt,reservation)
    return receipt
