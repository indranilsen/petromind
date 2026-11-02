"""Trusted host adapter. Mount only serialized responses in the agent runtime.

No imports from evaluator code. A Python object is not a sandbox: never expose
this process, vault, repository, or filesystem to an investigator.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

VERDICTS = {'SUPPORTED', 'NOT_ESTABLISHED', 'CONTRADICTED'}
SCOPES = {'measured_observation', 'documented_comparison', 'diagnostic_conclusion'}

def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)

def aggregate(values):
    if not values or not set(values) <= VERDICTS:
        raise ValueError('atomic verdict required')
    if 'CONTRADICTED' in values:
        return 'CONTRADICTED'
    return values[0] if len(set(values)) == 1 else 'PARTIALLY_SUPPORTED'

class ChallengeSession:
    """One case, five charged sensors, 24 calls, two bounded submission repairs."""
    def __init__(self, public_root, case_id, read_sensor):
        root = Path(public_root)
        ids = json.loads((root/'index.json').read_text())['case_ids']
        if case_id not in ids:
            raise ValueError('unknown case')
        self._case = json.loads((root/'cases'/f'{case_id}.json').read_text())
        self._docs = json.loads((root/'documents.json').read_text())
        self._graph = json.loads((root/'graph.json').read_text())['edges']
        self._history = json.loads((root/'history.json').read_text())
        self._read_sensor = read_sensor  # trusted host closure; no key access
        self._observed = copy.deepcopy(self._case['initial_measurements'])
        self._charged = set(self._observed)
        self._receipts = {'model:M1'} | {v['id'] for v in self._observed.values()}
        self._events = []
        self._sealed = False
        self._repairs = 0
        self._calls = 0
        self._record('initial_packet', {}, self._case)

    @property
    def audit(self):
        return copy.deepcopy(self._events)

    def _record(self, tool, args, result):
        event = dict(sequence=len(self._events), tool=tool, arguments=copy.deepcopy(args),
                     result=copy.deepcopy(result), previous=self._events[-1]['digest'] if self._events else '0'*64)
        event['digest'] = hashlib.sha256(canonical(event).encode()).hexdigest()
        self._events.append(event)
        return copy.deepcopy(result)

    def packet(self):
        return copy.deepcopy(self._case)

    def call(self, name, args):
        if self._sealed:
            return self._record(name, {}, {'error':'session_closed'})
        self._calls += 1
        if self._calls > 24:
            self._sealed = True
            return self._record(name, {}, {'error':'tool_limit'})
        if not isinstance(args, dict):
            return self._record(name, {}, {'error':'invalid_arguments'})
        try:
            if len(canonical(args))>64000:
                return self._record(name, {}, {'error':'arguments_too_large'})
            result = self._dispatch(name, args)
        except (TypeError, ValueError, KeyError, AttributeError):
            if name == 'submit_audit':
                self._repairs += 1
                if self._repairs >= 3:self._sealed = True
            return self._record(name, {}, {'error':'invalid_arguments'})
        return self._record(name, args, result)

    def _dispatch(self, name, args):
        if name == 'query_sensor' and set(args) == {'sensor'}:
            tag=args['sensor']
            catalog={s['id']:s for s in self._case['sensor_catalog']}
            if not isinstance(tag,str) or tag not in catalog:
                return {'error':'unknown_sensor'}
            if tag in self._observed:
                return self._observed[tag]
            if len(self._charged) >= 5:
                return {'error':'sensor_budget_exhausted'}
            self._charged.add(tag)
            # Whitelist the return schema; do not forward evaluator metadata.
            raw=self._read_sensor(tag)
            payload={k:copy.deepcopy(raw[k]) for k in ('id','sensor','unit','absolute_error_bound','samples')}
            payload['samples']=[{k:sample[k] for k in ('t_s','value','quality')} for sample in raw['samples']]
            self._observed[tag]=payload
            self._receipts.add(payload['id'])
            return payload
        if name == 'read_document' and set(args) == {'id'}:
            doc=next((d for d in self._docs if d['id']==args['id']),None)
            if doc:
                self._receipts.add(doc['id']);return doc
            return {'error':'unknown_document'}
        if name == 'search_history' and not args:
            self._receipts.update(d['id'] for d in self._history)
            return self._history
        if name == 'lookup_graph' and set(args) == {'node','hops'}:
            node,hops=args['node'],args['hops']
            if not isinstance(node,str) or type(hops) is not int or not 1<=hops<=2:
                return {'error':'invalid_graph_query'}
            visited={node};edges=[]
            for _ in range(hops):
                found=[e for e in self._graph if e['subject'] in visited or e['object'] in visited]
                for e in found:
                    if e not in edges:edges.append(e)
                visited.update(e[k] for e in found for k in ('subject','object'))
            edges=edges[:40]
            self._receipts.update(e['id'] for e in edges)
            return {'edges':edges,'truncated':len(edges)==40}
        if name == 'submit_audit':
            error=validate_submission(args,self._case,self._receipts,self._observed)
            if error:
                self._repairs+=1
                if self._repairs>=3:self._sealed=True
                return {'error':error,'field':'submission','correction':'Use exact supplied atomic statements, three top-level fields, returned citations and finite numeric values.',
                        'repairs_remaining':max(0,3-self._repairs)}
            self._sealed=True
            return {'accepted':True,'assessment':copy.deepcopy(args)}
        return {'error':'unknown_tool_or_arguments'}

def validate_submission(a, case, receipts, observed):
    if set(a) != {'verdict','findings','numeric_observations'}:
        return 'invalid_submission_shape'
    fs=a['findings'];nums=a['numeric_observations']
    if not isinstance(fs,list) or not isinstance(nums,list) or len(nums)>12:
        return 'invalid_arrays'
    claims={x['statement']:x for x in case['atomic_claims']}
    if len(fs)!=len(claims) or any(not isinstance(f,dict) for f in fs):
        return 'incomplete_atomic_findings'
    if {f.get('statement') for f in fs}!=set(claims):
        return 'unknown_or_duplicate_statement'
    for f in fs:
        required={'statement','scope','premises','basis','verdict','citations','missing_premise','next_evidence','justification'}
        if set(f)!=required or f['scope']!=claims[f['statement']]['scope'] or f['verdict'] not in VERDICTS:
            return 'invalid_finding'
        if not all(isinstance(f[k],str) and len(f[k])<=700 for k in ('statement','scope','basis','verdict','missing_premise','justification')):
            return 'invalid_text'
        if not f['justification'].strip() or f['basis'] not in {'measurement','documented','empirical_correlation','hypothesis','unsupported'}:
            return 'invalid_basis_or_justification'
        if not isinstance(f['premises'],list) or not 1<=len(f['premises'])<=4 or any(not isinstance(p,str) or len(p)>700 for p in f['premises']):
            return 'invalid_premises'
        if not isinstance(f['citations'],list) or len(f['citations'])>8 or any(not isinstance(c,str) or c not in receipts for c in f['citations']):
            return 'unreceived_citation'
        if f['verdict']!='NOT_ESTABLISHED' and not f['citations']:
            return 'missing_citation'
        n=f['next_evidence']
        if not isinstance(n,dict) or set(n)!={'kind','target','purpose'} or any(not isinstance(v,str) for v in n.values()):
            return 'invalid_next_evidence'
        if n['kind'] not in {'none','sensor','document','descriptive_test','no_verified_discriminating_test'}:
            return 'invalid_next_kind'
        if f['verdict']=='SUPPORTED' and (f['missing_premise'] or n!={'kind':'none','target':'','purpose':''}):
            return 'supported_has_gap'
        if f['verdict']=='NOT_ESTABLISHED' and not f['missing_premise'].strip():
            return 'missing_premise_required'
    if a['verdict']!=aggregate([f['verdict'] for f in fs]):
        return 'inconsistent_aggregate'
    # Numeric observations use exact returned raw values, identified by t_s:<seconds>.
    for n in nums:
        if not isinstance(n,dict) or set(n)!={'sensor','metric','value'}:
            return 'invalid_numeric_observation'
        value=n['value']
        if type(value) not in (int,float) or not math.isfinite(value):
            return 'invalid_numeric_value'
        sensor=observed.get(n['sensor'])
        if not sensor or not isinstance(n['metric'],str) or not n['metric'].startswith('t_s:'):
            return 'unobserved_numeric_sensor'
        try:t=int(n['metric'][4:])
        except ValueError:return 'invalid_numeric_metric'
        if not any(s['t_s']==t and s['value']==value and s['value'] is not None for s in sensor['samples']):
            return 'invented_numeric_observation'
    return None
