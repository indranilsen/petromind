"""Owner-only bridge. Muse is a remote text API with ONLY these function tools.

No callable file/exec/network tools are exposed. The owner may access private
files; the remote model cannot. Never attach this process to a general agent.
"""
import json
import os
import selectors
import subprocess
import sys
from dataclasses import dataclass

from petromind.audit import canonical


def tool(name, description, properties, required):
    return {'type': 'function', 'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties,
                           'required': required, 'additionalProperties': False}}


def tools():
    string = {'type': 'string'}
    finding = {'type': 'object', 'additionalProperties': False,
        'properties': {
            'statement': string, 'scope': {'type':'string', 'enum':['measured_observation','documented_comparison','diagnostic_conclusion']},
            'premises': {'type':'array','items': string, 'minItems':1,'maxItems':4},
            'basis': {'type':'string','enum':['measurement','documented','empirical_correlation','hypothesis','unsupported']},
            'verdict': {'type':'string','enum':['SUPPORTED','NOT_ESTABLISHED','CONTRADICTED']},
            'citations': {'type':'array','items':string,'maxItems':8},
            'missing_premise': string,
            'next_evidence': {'type':'object','additionalProperties':False,
                'properties':{'kind':{'type':'string','enum':['none','sensor','document','descriptive_test','no_verified_discriminating_test']},'target':string,'purpose':string},
                'required':['kind','target','purpose']}, 'justification':string},
        'required':['statement','scope','premises','basis','verdict','citations','missing_premise','next_evidence','justification']}
    return [tool('query_sensor','Request one catalog sensor. Initial and new distinct sensors count toward five, even missing/frozen; repeats cached.',{'sensor':string},['sensor']),
            tool('lookup_graph','Retrieve source-scoped relationships relevant to a public node. Retain provenance, assumptions and limitations; topology is synthetic.',{'node':string},['node']),
            tool('read_document','Read one document ID from the packet resources or returned provenance. No URL fetching.',{'id':string},['id']),
            tool('submit_audit','Submit all exact atomic statements with their supplied scope. Apply the packet aggregate rule and use only received citations. String fields at most 700 characters.',
                 {'verdict': {'type':'string','enum':['SUPPORTED','NOT_ESTABLISHED','CONTRADICTED','PARTIALLY_SUPPORTED']},
                  'findings': {'type':'array','items':finding},
                  'numeric_observations':{'type':'array','maxItems':12,'items':{'type':'object','additionalProperties':False,
                    'properties':{'sensor':string,'metric':{'type':'string','description':'t_s:<integer seconds>, quoting an exact returned raw sample'},'value':{'type':'number'}},'required':['sensor','metric','value']}}},
                 ['verdict','findings','numeric_observations'])]


@dataclass
class ToolRecord:
    tool: str
    arguments_json: str
    sequence: int
    digest: str


class Bridge:
    budget = 5
    def __init__(self, release, private, case, audit_out, variant):
        if variant not in ('B','E'): raise ValueError('invalid_variant')
        self.variant = variant
        self.process = subprocess.Popen([sys.executable, str(release/'integration/trusted_host.py'),
            '--release-root',str(release),'--private-root',str(private), '--case',case,
            '--audit-out',str(audit_out)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True,
            env={'PATH':os.defpath,'PYTHONNOUSERSITE':'1'})
        self.packet = self.receive()
        if self.packet.get('case_id') != case:
            self.close(); raise ValueError('trusted_host_start_failed')
        self.observed = set(self.packet['initial_sensors'])
        self.audit_trail = []
        self.result = None
        self.stop = None
        self.context_calls = 0
        self.allowed_nodes = {s['id'] for s in self.packet['sensor_catalog']}
        self.allowed_nodes.update({'U','D','K','L','S','R_L','R_K','P_S','incident','claim:diagnosis'})
        self.allowed_nodes.update('candidate:'+c for c in ('hydrate','scale','debris','choke_motion','boundary_change','sensor_bias'))
        self.allowed_nodes.update({'doc:ini','doc:example','doc:limits','doc:mechanisms','doc:phase'})

    @property
    def remaining_budget(self): return max(0, 5-len(self.observed))

    def receive(self):
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout=10): raise ValueError('trusted_host_timeout')
        line = self.process.stdout.readline(200000)
        value = json.loads(line)
        if set(value) != {'result'}: raise ValueError('invalid_host_envelope')
        return value['result']

    def call(self, name, args):
        self.process.stdin.write(canonical({'name':name,'arguments':args})+'\n')
        self.process.stdin.flush()
        return self.receive()

    def dispatch(self, name, args):
        # Unknown/path-based calls never reach a filesystem API. All admissible
        # evidence is requested from the unchanged host, not a private key object.
        safe = isinstance(args,dict) and name in {t['name'] for t in tools()}
        host_args = args
        if safe and name in ('lookup_graph','read_document'):
            self.context_calls += 1
            if self.context_calls > 4:
                safe = False
            if name == 'lookup_graph':
                safe = safe and set(args)=={'node'} and isinstance(args['node'],str) and args['node'] in self.allowed_nodes
                if safe: host_args = {'node':args['node'],'hops':1 if self.variant=='B' else 2}
        result = self.call(name,host_args) if safe else {'error':'tool_or_scope_not_allowed'}
        if name=='query_sensor' and isinstance(result,dict) and 'sensor' in result:
            self.observed.add(result['sensor'])
        if name=='lookup_graph' and isinstance(result,dict):
            for edge in result.get('edges',[]):
                self.allowed_nodes.update((edge['subject'],edge['object']))
        if result.get('accepted'):
            self.result = result['assessment']
        if result.get('error') in ('session_closed','tool_limit'):
            self.stop = result['error']
        # Transport record only; authoritative scorer uses frozen host hash chain.
        from petromind.eval_protocol import digest
        self.audit_trail.append(ToolRecord(name, canonical(args if isinstance(args,dict) else {}),
            len(self.audit_trail)+1,digest(result)))
        return result

    def close(self):
        if self.process.stdin and not self.process.stdin.closed: self.process.stdin.close()
        try: self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill(); self.process.wait()
        if self.process.stdout: self.process.stdout.close()
