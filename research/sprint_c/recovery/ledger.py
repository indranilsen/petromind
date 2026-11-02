"""Owner-reviewed SQLite continuation; immutable source ledger remains external.

One local owner controls the lifecycle. This is never a hosted repair/reset.
SQLite transactions commit reservations before HTTP; updates/deletes are forbidden.
"""
import fcntl,json,os,sqlite3,uuid
from pathlib import Path
from petromind.audit import canonical
from petromind.eval_protocol import digest
from petromind.meta_api import MetaAPIError
from research.sprint_c.accounting import validate_receipt,receipt_cost,NANO
from .reconcile import verify_proposal

ZERO='0'*64


def approval(proposal,reviewer,database):
    verify_proposal(proposal)
    if not isinstance(reviewer,str) or not reviewer.strip():raise ValueError('owner_reviewer_required')
    r={'version':'owner-loss-bound-review-v1','proposal_id':proposal['proposal_id'],'reviewer':reviewer,
       'decision':'ACCEPT_CONSERVATIVE_LOSS_BOUND_NOT_EXACT_RECOVERY','execution_surface':'trusted_local_owner',
       'additional_money_authorized':0,'continuation_database':str(Path(database).resolve()),'continuation_output':str(Path(database).resolve().parent/'run')}
    r['review_id']=digest(r);return r


def verify_review(proposal,review):
    verify_proposal(proposal)
    if (digest({k:v for k,v in review.items() if k!='review_id'})!=review['review_id']
        or review.get('proposal_id')!=proposal['proposal_id'] or not review.get('reviewer','').strip()
        or review.get('decision')!='ACCEPT_CONSERVATIVE_LOSS_BOUND_NOT_EXACT_RECOVERY'
        or review.get('execution_surface')!='trusted_local_owner' or review.get('additional_money_authorized')!=0):
        raise ValueError('explicit_owner_review_required')


class LocalLedger:
    def __init__(self,path,proposal,review):
        verify_review(proposal,review)
        self.path=Path(path).resolve();self.proposal=proposal;self.review=review
        if str(self.path)!=review.get('continuation_database'):raise ValueError('reviewed_database_path_changed')
        if not self.path.is_file():raise ValueError('explicit_initialization_required')
        self.owner_lock=(self.path.parent/'owner.lock').open('a')
        try:fcntl.flock(self.owner_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            self.owner_lock.close();raise ValueError('single_owner_already_running') from None
        self.anchors=self.path.with_name(self.path.name+'.anchors')
        self.db=sqlite3.connect(self.path,timeout=0,isolation_level=None)
        self.db.execute('PRAGMA synchronous=FULL');self.db.execute('PRAGMA busy_timeout=0')
        try:self.state()
        except Exception:self.close();raise

    @classmethod
    def initialize(cls,path,proposal,review):
        verify_review(proposal,review);path=Path(path).resolve();path.parent.mkdir(parents=True,exist_ok=True)
        if str(path)!=review.get('continuation_database'):raise ValueError('reviewed_database_path_changed')
        if path.exists():raise FileExistsError(path)
        activation=path.with_name(path.name+'.activation.json')
        with activation.open('x') as f:
            f.write(canonical({'proposal_id':proposal['proposal_id'],'review_id':review['review_id'],'database':str(path)})+'\n');f.flush();os.fsync(f.fileno())
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        db=sqlite3.connect(path,isolation_level=None)
        try:
            db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE events (sequence INTEGER PRIMARY KEY, body TEXT NOT NULL, digest TEXT NOT NULL UNIQUE)')
            db.execute("CREATE TRIGGER no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append_only'); END")
            db.execute("CREATE TRIGGER no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append_only'); END")
            body={'sequence':1,'previous_hash':ZERO,'kind':'conservative_carry_forward',
                'data':{'proposal_id':proposal['proposal_id'],'review_id':review['review_id'],
                        'historical_held_nusd':proposal['historical_held_nusd'],
                        'carried_sprint_c_liability_nusd':proposal['sprint_c_carried_liability_nusd']}}
            db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO events VALUES (?,?,?)',(1,canonical(body),digest(body)));db.execute('COMMIT')
        finally:db.close()
        fd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        anchors=path.with_name(path.name+'.anchors');anchors.mkdir(mode=0o700)
        cls.write_anchor(anchors,1,digest(body))
        fd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        return cls(path,proposal,review)

    @staticmethod
    def write_anchor(directory,seq,event_digest):
        path=directory/f'{seq:06d}-{event_digest}.json'
        with path.open('x') as f:
            f.write(canonical({'sequence':seq,'digest':event_digest})+'\n');f.flush();os.fsync(f.fileno())
        fd=os.open(directory,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)

    def checkpoint(self):
        seq,raw,h=self.db.execute('SELECT sequence,body,digest FROM events ORDER BY sequence DESC LIMIT 1').fetchone()
        self.write_anchor(self.anchors,seq,h)

    def close(self):
        if getattr(self,'db',None):self.db.close();self.db=None
        if getattr(self,'owner_lock',None):self.owner_lock.close();self.owner_lock=None

    def state(self):
        if self.db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('database_integrity_failed')
        rows=self.db.execute('SELECT sequence,body,digest FROM events ORDER BY sequence').fetchall()
        previous=ZERO;res={};settled={};unknown=set();provider=set()
        for index,(seq,raw,h) in enumerate(rows,1):
            row=json.loads(raw)
            if seq!=index or row['sequence']!=seq or row['previous_hash']!=previous or digest(row)!=h:raise ValueError('continuation_chain_invalid')
            d=row['data'];kind=row['kind']
            if index==1:
                expected={'proposal_id':self.proposal['proposal_id'],'review_id':self.review['review_id'],
                          'historical_held_nusd':self.proposal['historical_held_nusd'],
                          'carried_sprint_c_liability_nusd':self.proposal['sprint_c_carried_liability_nusd']}
                if kind!='conservative_carry_forward' or d!=expected:raise ValueError('carry_forward_changed')
            elif kind=='reservation':
                rid=d['reservation_id']
                if rid in res or any(k not in settled for k in res):raise ValueError('unresolved_or_duplicate_request')
                if (type(d['input_token_bound'])is not int or type(d['output_token_cap'])is not int or not 16<=d['output_token_cap']<=4096
                    or not 0<d['input_token_bound']<=1032192 or d['reserved_nusd']!=d['input_token_bound']*1250+d['output_token_cap']*4250):
                    raise ValueError('invalid_reservation_amount')
                res[rid]=d
            elif kind=='settlement':
                rid=d['reservation_id']
                if rid not in res or rid in settled or rid in unknown:raise ValueError('duplicate_or_unknown_settlement')
                validate_receipt(d['receipt'],res[rid])
                if (d['receipt']['provider_response_id'] in provider or digest(d['receipt']['provider_response_id']) in self.proposal.get('historical_provider_id_hashes',[])
                    or d['settled_nusd']!=receipt_cost(d['receipt'])):raise ValueError('invalid_provider_identity_or_amount')
                provider.add(d['receipt']['provider_response_id']);settled[rid]=d
            elif kind=='unverified_response':
                rid=d['reservation_id']
                if rid not in res or rid in settled or rid in unknown:raise ValueError('invalid_unverified_event')
                unknown.add(rid)
            else:raise ValueError('invalid_continuation_event')
            charged=self.proposal['sprint_c_carried_liability_nusd']+sum(x['settled_nusd'] for x in settled.values())+sum(x['reserved_nusd'] for k,x in res.items() if k not in settled)
            if charged>10*NANO or len(res)+self.proposal['archived_http_attempt_count']>320 or sum(x['output_token_cap'] for x in res.values())+self.proposal['historical_reserved_output_token_bound']>1310720:
                raise ValueError('continuation_exceeds_original_authorization')
            previous=h
        if not rows:raise ValueError('missing_carry_forward')
        expected={f'{seq:06d}-{h}.json' for seq,_,h in rows}
        if not self.anchors.is_dir() or {p.name for p in self.anchors.iterdir()}!=expected:raise ValueError('immutable_anchor_set_mismatch')
        for seq,_,h in rows:
            if json.loads((self.anchors/f'{seq:06d}-{h}.json').read_text())!={'sequence':seq,'digest':h}:raise ValueError('anchor_changed')
        return rows,res,settled,unknown,charged

    def append(self,kind,data,rows):
        row={'sequence':len(rows)+1,'previous_hash':rows[-1][2],'kind':kind,'data':data}
        self.db.execute('INSERT INTO events VALUES (?,?,?)',(row['sequence'],canonical(row),digest(row)))

    def reserve(self,protocol_id,task,input_bound,output_cap,request_digest):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            rows,res,settled,_,charged=self.state()
            amount=input_bound*1250+output_cap*4250
            if any(k not in settled for k in res):raise MetaAPIError('recovery_unresolved_request')
            if charged+amount>10*NANO or len(res)+self.proposal['archived_http_attempt_count']>=320 or sum(x['output_token_cap'] for x in res.values())+output_cap+self.proposal['historical_reserved_output_token_bound']>1310720:
                raise MetaAPIError('recovery_original_spending_cap')
            if type(input_bound)is not int or not 0<input_bound<=1032192 or type(output_cap)is not int or not 16<=output_cap<=4096:raise ValueError('invalid_frozen_request_bound')
            r={'reservation_id':uuid.uuid4().hex,'protocol_id':protocol_id,'task':task,'input_token_bound':input_bound,
               'output_token_cap':output_cap,'request_digest':request_digest,'reserved_nusd':amount}
            self.append('reservation',r,rows);self.db.execute('COMMIT');self.checkpoint();return r
        except Exception:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            raise

    def settle(self,rid,receipt):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            rows,res,settled,unknown,_=self.state()
            if rid not in res or rid in settled or rid in unknown:raise ValueError('unknown_or_duplicate_settlement')
            validate_receipt(receipt,res[rid])
            if (receipt['provider_response_id'] in {s['receipt']['provider_response_id'] for s in settled.values()}
                or digest(receipt['provider_response_id']) in self.proposal.get('historical_provider_id_hashes',[])):raise ValueError('duplicate_provider_response')
            self.append('settlement',{'reservation_id':rid,'receipt':receipt,'settled_nusd':receipt_cost(receipt)},rows)
            self.db.execute('COMMIT');self.checkpoint()
        except Exception:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            raise

    def unverified(self,rid):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            rows,res,settled,unknown,_=self.state()
            if rid not in res or rid in settled or rid in unknown:raise ValueError('invalid_unverified_request')
            self.append('unverified_response',{'reservation_id':rid},rows);self.db.execute('COMMIT');self.checkpoint()
        except Exception:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            raise

    def summary(self):
        rows,res,settled,_,charged=self.state()
        return {'kind':'CONSERVATIVE_CARRY_FORWARD_NOT_EXACT_RECOVERY','proposal_id':self.proposal['proposal_id'],
            'review_id':self.review['review_id'],'historical_PR33_held_usd':self.proposal['historical_held_nusd']/NANO,
            'sprint_c_original_ceiling_usd':10,'carried_sprint_c_liability_usd':self.proposal['sprint_c_carried_liability_nusd']/NANO,
            'new_settled_estimate_usd':sum(x['settled_nusd'] for x in settled.values())/NANO,
            'new_unsettled_holds_usd':sum(x['reserved_nusd'] for k,x in res.items() if k not in settled)/NANO,
            'sprint_c_accounted_usd':charged/NANO,'sprint_c_available_usd':(10*NANO-charged)/NANO,
            'total_C_http_reservations':122+len(res),'last_digest':rows[-1][2],
            'provider_invoice':None}
