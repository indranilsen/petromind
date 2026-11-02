"""Small single-owner append-only SQLite phase journal. Money is nanodollars.

The prior account is imported as a bound liability, never rewritten. Ended
transports can retain full holds without preventing unrelated new cells.
"""
import fcntl,json,os,sqlite3,uuid
from pathlib import Path
from petromind.audit import canonical
from petromind.eval_protocol import digest
from petromind.meta_api import MetaAPIError
from research.sprint_c.accounting import receipt_cost
from research.sprint_c.recovery import durability
from .client import validate_receipt

NANO=1_000_000_000
PHASE_CAP=30*NANO


def validate_policy(p):
    if p.get('version')!='sprint-c-additional-30-v1' or digest({k:v for k,v in p.items() if k!='policy_id'})!=p.get('policy_id'):raise ValueError('phase_policy_invalid')
    if p['phase_cap_nusd']!=PHASE_CAP or p['cumulative_c_cap_nusd']!=40*NANO or p['legacy_carried_nusd']!=5357073350:raise ValueError('authorization_or_carry_changed')
    if p['max_requests']!=560 or p['max_output_tokens']!=4096:raise ValueError('phase_limits_changed')


def owner_approval(policy,reviewer):
    validate_policy(policy)
    if not isinstance(reviewer,str) or not reviewer.strip():raise ValueError('owner_name_required')
    value={'version':'owner-phase2-additional-30-v1','policy_id':policy['policy_id'],
           'reviewer':reviewer,'decision':'AUTHORIZE_ADDITIONAL_ESTIMATED_USAGE',
           'additional_authorization_nusd':PHASE_CAP}
    value['authorization_id']=digest(value);return value


def verify_owner_approval(policy,value):
    if not isinstance(value,dict) or value!=owner_approval(policy,value.get('reviewer')):raise ValueError('explicit_phase_authorization_required')


class Journal:
    def __init__(self,path,policy,plan,initialize=False):
        validate_policy(policy);self.path=Path(path).resolve();self.policy=policy;self.plan=plan;
        self.approval=json.loads((self.path.parent/'owner-authorization.json').read_text());verify_owner_approval(policy,self.approval)
        self.db=None;self.owner=None;self.legacy_owner=None
        if str(self.path)!=policy['database']:raise ValueError('registered_database_changed')
        if digest({k:v for k,v in plan.items() if k!='plan_id'})!=plan['plan_id'] or plan['plan_id']!=policy['plan_id']:raise ValueError('phase_plan_changed')
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.owner=(self.path.parent/'owner.lock').open('a')
        try:
            fcntl.flock(self.owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.anchors=self.path.with_name(self.path.name+'.anchors')
            if initialize:
                marker=self.path.with_name('activation.json')
                durability.durable_text(marker,canonical({'policy_id':policy['policy_id'],'database':str(self.path)})+'\n')
                fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
                self.db=sqlite3.connect(self.path,timeout=0,isolation_level=None);durability.sqlite_settings(self.db,initialize=True)
                self.db.execute('CREATE TABLE events(sequence INTEGER PRIMARY KEY, body TEXT NOT NULL, digest TEXT NOT NULL UNIQUE)')
                for op in ('UPDATE','DELETE'):
                    self.db.execute(f"CREATE TRIGGER no_{op.lower()} BEFORE {op} ON events BEGIN SELECT RAISE(ABORT,'append_only'); END")
                self.anchors.mkdir(mode=0o700);durability.sync_dir(self.path.parent)
                self._append_raw('authorization',{'policy_id':policy['policy_id'],'owner_authorization_id':self.approval['authorization_id'],'legacy_carried_nusd':policy['legacy_carried_nusd'],'additional_cap_nusd':PHASE_CAP},[])
            else:
                if not self.path.is_file():raise ValueError('phase_prepare_required')
                self.db=sqlite3.connect(self.path,timeout=0,isolation_level=None);durability.sqlite_settings(self.db)
                if json.loads(self.path.with_name('activation.json').read_text())!={'policy_id':policy['policy_id'],'database':str(self.path)}:raise ValueError('phase_activation_changed')
            self.state(repair_tail=True)
        except Exception:self.close();raise

    def close(self):
        if self.db:self.db.close();self.db=None
        if self.owner:self.owner.close();self.owner=None
        if self.legacy_owner:self.legacy_owner.close();self.legacy_owner=None

    def _append_raw(self,kind,data,rows):
        row={'sequence':len(rows)+1,'previous_hash':rows[-1][2] if rows else '0'*64,'kind':kind,'data':data};h=digest(row)
        self.db.execute('BEGIN IMMEDIATE')
        try:self.db.execute('INSERT INTO events VALUES(?,?,?)',(row['sequence'],canonical(row),h));self.db.execute('COMMIT')
        except Exception:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            raise
        durability.durable_text(self.anchors/f"{row['sequence']:06d}-{h}.json",canonical({'sequence':row['sequence'],'digest':h})+'\n')

    def append(self,kind,data):self._append_raw(kind,data,self.state()['rows'])

    def state(self,repair_tail=False):
        if self.db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('phase_sqlite_corrupt')
        rows=self.db.execute('SELECT sequence,body,digest FROM events ORDER BY sequence').fetchall()
        previous='0'*64;res={};settled={};closed=set();started={};finished={};provider=set();allowed={x['cell_id']:x for x in self.plan['cells']}
        for i,(seq,raw,h) in enumerate(rows,1):
            row=json.loads(raw)
            if seq!=i or row['sequence']!=i or row['previous_hash']!=previous or digest(row)!=h:raise ValueError('phase_chain_corrupt')
            d=row['data'];kind=row['kind'];rid=d.get('reservation_id')
            if i==1:
                if kind!='authorization' or d!={'policy_id':self.policy['policy_id'],'owner_authorization_id':self.approval['authorization_id'],'legacy_carried_nusd':self.policy['legacy_carried_nusd'],'additional_cap_nusd':PHASE_CAP}:raise ValueError('phase_genesis_changed')
            elif kind=='cell_start':
                cid=d['cell_id']
                if cid in started or allowed.get(cid)!=d or any(k not in finished for k in started):raise ValueError('cell_replay_or_active_cell')
                started[cid]=d
            elif kind=='reservation':
                if rid in res or d['cell_id'] not in started or d['cell_id'] in finished or any(k not in closed for k in res):raise ValueError('concurrent_or_unknown_request')
                if type(d['input_token_bound'])is not int or not 0<d['input_token_bound']<=1032192 or type(d['output_token_cap'])is not int or not 16<=d['output_token_cap']<=4096:raise ValueError('invalid_request_bounds')
                if d['reserved_nusd']!=d['input_token_bound']*1250+d['output_token_cap']*4250:raise ValueError('reservation_cost_changed')
                res[rid]=d
            elif kind=='settlement':
                if rid not in res or rid in settled or rid in closed:raise ValueError('invalid_settlement_order')
                validate_receipt(d['receipt'],res[rid]);pid=d['receipt']['provider_response_id']
                if pid in provider or digest(pid) in self.policy['historical_provider_id_hashes'] or d['settled_nusd']!=receipt_cost(d['receipt']):raise ValueError('duplicate_provider_or_amount')
                provider.add(pid);settled[rid]=d
            elif kind=='transport_closed':
                if rid not in res or rid in closed or d['basis'] not in ('synchronous_stream_scope_exited','exclusive_owner_restart'):raise ValueError('invalid_transport_closure')
                closed.add(rid)
            elif kind=='diagnostic':
                if rid not in res:raise ValueError('diagnostic_without_request')
            elif kind=='cell_finish':
                cid=d['cell_id']
                if cid not in started or cid in finished or any(r['cell_id']==cid and k not in closed for k,r in res.items()):raise ValueError('cell_finish_with_active_transport')
                if d['status'] not in ('completed','failed','interrupted') or len(d['result_sha256'])!=64:raise ValueError('cell_finish_invalid')
                finished[cid]=d
            else:raise ValueError('unknown_phase_event')
            phase=sum(s['settled_nusd'] for s in settled.values())+sum(r['reserved_nusd'] for k,r in res.items() if k not in settled)
            if phase>PHASE_CAP or phase+self.policy['legacy_carried_nusd']>self.policy['cumulative_c_cap_nusd'] or len(res)>self.policy['max_requests']:raise ValueError('phase_cap_exceeded')
            previous=h
        if not rows:raise ValueError('missing_phase_genesis')
        expected={f'{seq:06d}-{h}.json' for seq,_,h in rows};actual={p.name for p in self.anchors.iterdir()}
        # A committed tail row may precede its external anchor at process death.
        # Recover that one anchor from intact SQLite; never recover deleted DB rows.
        if repair_tail and expected-actual=={f'{rows[-1][0]:06d}-{rows[-1][2]}.json'} and not actual-expected:
            seq,_,h=rows[-1];durability.durable_text(self.anchors/f'{seq:06d}-{h}.json',canonical({'sequence':seq,'digest':h})+'\n');actual=expected
        if actual!=expected:raise ValueError('phase_anchor_set_mismatch')
        for seq,_,h in rows:
            if json.loads((self.anchors/f'{seq:06d}-{h}.json').read_text())!={'sequence':seq,'digest':h}:raise ValueError('phase_anchor_corrupt')
        return {'rows':rows,'reservations':res,'settlements':settled,'closed':closed,'started':started,'finished':finished,'phase_nusd':phase,'last_digest':previous}

    def start(self,cell):
        s=self.state()
        if cell not in self.plan['cells'] or cell['cell_id'] in s['started'] or any(k not in s['finished'] for k in s['started']):raise ValueError('cell_replay_or_active_cell')
        self.append('cell_start',cell)

    def reserve(self,cell,input_bound,output_cap,request_digest):
        s=self.state();n=input_bound*1250+output_cap*4250
        if s['phase_nusd']+n>PHASE_CAP or s['phase_nusd']+n+self.policy['legacy_carried_nusd']>40*NANO:raise MetaAPIError('phase_spending_cap')
        if len(s['reservations'])>=self.policy['max_requests']:raise MetaAPIError('phase_request_cap')
        if any(k not in s['closed'] for k in s['reservations']):raise MetaAPIError('phase_live_request')
        if cell['cell_id'] not in s['started'] or cell['cell_id'] in s['finished']:raise ValueError('cell_not_active')
        if type(input_bound)is not int or not 0<input_bound<=1032192 or type(output_cap)is not int or not 16<=output_cap<=4096:raise ValueError('invalid_request_bounds')
        r={'reservation_id':uuid.uuid4().hex,'cell_id':cell['cell_id'],'input_token_bound':input_bound,'output_token_cap':output_cap,'request_digest':request_digest,'reserved_nusd':n}
        self.append('reservation',r);return r

    def diagnostic(self,rid,value):self.append('diagnostic',{'reservation_id':rid,'evidence':value})

    def settle(self,rid,value):
        s=self.state()
        if rid not in s['reservations'] or rid in s['settlements'] or rid in s['closed']:raise ValueError('settlement_not_allowed')
        validate_receipt(value,s['reservations'][rid])
        if digest(value['provider_response_id']) in self.policy['historical_provider_id_hashes'] or any(x['receipt']['provider_response_id']==value['provider_response_id'] for x in s['settlements'].values()):raise ValueError('duplicate_provider_response')
        self.append('settlement',{'reservation_id':rid,'receipt':value,'settled_nusd':receipt_cost(value)})

    def end_transport(self,rid,basis):
        s=self.state()
        if rid not in s['reservations'] or rid in s['closed'] or basis not in ('synchronous_stream_scope_exited','exclusive_owner_restart'):raise ValueError('invalid_transport_closure')
        self.append('transport_closed',{'reservation_id':rid,'basis':basis,'liability_released':False})

    def finish(self,cell,status,result_sha256):
        s=self.state();cid=cell['cell_id']
        if cid not in s['started'] or cid in s['finished'] or status not in ('completed','failed','interrupted') or len(result_sha256)!=64:raise ValueError('invalid_cell_finish')
        if any(r['cell_id']==cid and k not in s['closed'] for k,r in s['reservations'].items()):raise ValueError('active_transport_blocks_finish')
        self.append('cell_finish',{'cell_id':cid,'status':status,'result_sha256':result_sha256})

    def recover_transports(self):
        s=self.state()
        for rid in s['reservations']:
            if rid not in s['closed']:self.end_transport(rid,'exclusive_owner_restart')

    def summary(self):
        s=self.state();settled=sum(x['settled_nusd'] for x in s['settlements'].values());held=s['phase_nusd']-settled
        return {'policy_id':self.policy['policy_id'],'additional_authorization_usd':30,'phase_settled_estimate_usd':settled/NANO,
                'phase_unresolved_holds_usd':held/NANO,'phase_available_usd':(PHASE_CAP-s['phase_nusd'])/NANO,
                'legacy_carried_usd':self.policy['legacy_carried_nusd']/NANO,'sprint_c_cumulative_cap_usd':40,
                'sprint_c_cumulative_accounted_usd':(self.policy['legacy_carried_nusd']+s['phase_nusd'])/NANO,
                'historical_PR33_held_usd':9.8840695,'phase_http_requests':len(s['reservations']),
                'unresolved_requests':len(s['reservations'])-len(s['settlements']),'last_digest':s['last_digest'],'provider_invoice':None}
