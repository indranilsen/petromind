"""Owner orchestrator. Scoring is a separate command after all remote contexts end."""
import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import secrets
import sys
import time
from dataclasses import asdict
from pathlib import Path

from petromind.agent import AgentConfig, run_tool_agent
from petromind.audit import canonical
from petromind.eval_protocol import DEFAULT_PRICES, digest, runtime_versions, source_digest
from petromind.eval_runner import append_json, read_jsonl, usage_and_cost
from .client import SettlingClient
from research.synthetic_challenge.integration.verify_readiness import verify
from research.muse_integration.bridge import Bridge, tools
from .accounting import SettlementLedger, PRICES
from .interventions import PROMPTS, VARIANTS

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT/'research/synthetic_challenge'
VERSION = 'sprint-c-citation-verdict-v1'


def code_digest():
    return digest({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for folder in (ROOT/'research/sprint_c',ROOT/'research/muse_integration',ROOT/'research/sprint_a')
                   for p in sorted(folder.glob('*.py'))})


def write_new(path, value):
    with Path(path).open('x') as f:
        f.write(canonical(value)+'\n');f.flush();os.fsync(f.fileno())


def prepare(out, private, ledger_dir, platform_proxy=False):
    out=Path(out).resolve()
    if out.exists(): raise ValueError('fresh_output_required')
    verification=verify(RELEASE,private,ROOT)
    ledger=SettlementLedger(ledger_dir)
    ids=json.loads((RELEASE/'public/index.json').read_text())['case_ids']
    # Opaque public-ID order only. No private key read for selection or retrieval.
    ids=sorted(ids,key=lambda c:digest([VERSION,c]))
    protocol={'version':VERSION,'code_digest':code_digest(),'production_digest':source_digest(),
        'runtime':runtime_versions(),'public_root_digest':json.loads((RELEASE/'FREEZE.json').read_text())['public_root_digest'],
        'agent_config':asdict(AgentConfig(model='muse-spark-1.3',max_turns=8,max_tool_calls=24,max_output_tokens=4096,
                         reasoning_effort='medium',run_timeout=360,variant='sensor_only')),
        'prompts':PROMPTS,'prompt_digests':{v:digest(x) for v,x in PROMPTS.items()},'tools':tools(),'variants':list(VARIANTS),
        'retrieval':{'all_variants':'Identical PR33 B direct one-hop source-scoped lookup','context_limit':4,'history_tool':False},
        'cases':ids,'pilot_cases':ids[:1], 'order':{c:list(VARIANTS[i%4:]+VARIANTS[:i%4]) for i,c in enumerate(ids)},
        'accounting_policy_id':ledger.summary()['policy_id'],'settlement_prices':PRICES,
        'prices':{**DEFAULT_PRICES,'verified_date':'2026-11-02'},
        'price_note':'Official Meta standard Muse Spark rates checked 2026-11-02: $1.25 input/$4.25 output per million; no contributor mode or web tools.',
        'platform_proxy':platform_proxy,'max_additional_estimated_usd':10.0,'ledger_directory':str(Path(ledger_dir).resolve()),
        'preflight_accounting_receipt':ledger.summary(),'verification':verification,
        'semantic_review':'Required and ungraded until qualified independent review',
        'limitations':['Seven correlated tasks from one synthetic incident; not population accuracy.',
            'No provider seed parameter is available in the existing transport; one stochastic run per cell.',
            'Remote Muse receives no filesystem/exec/network tools; trusted owner process can read private files.',
            'No scoring until model sessions end; no intervention tuning after outcomes.',
            'Pilot repeated in suite with separate fresh contexts; duplicates are not independent samples.',
            'Historical reservations remain held. New verified HTTPS-envelope usage settles active holds; unknown/failed requests retain full holds and stop further execution.',
            'Previously inspected synthetic tasks are development reuse, not unseen generalization. No new physical facts or reference labels enter the intervention.']}
    protocol['protocol_id']=digest(protocol)
    out.mkdir(parents=True,mode=0o700)
    write_new(out/'protocol.json',protocol)
    return {'status':'prepared','protocol_id':protocol['protocol_id'],'pilot_cases':ids[:1], 'variants':list(VARIANTS), 'spending':ledger.summary()}


def load(out, private):
    protocol=json.loads((Path(out)/'protocol.json').read_text())
    if digest({k:v for k,v in protocol.items() if k!='protocol_id'})!=protocol['protocol_id']:
        raise ValueError('protocol_changed')
    if protocol['version']!=VERSION or protocol['code_digest']!=code_digest() or protocol['production_digest']!=source_digest() or protocol['runtime']!=runtime_versions():
        raise ValueError('code_or_runtime_changed_create_versioned_protocol')
    verify(RELEASE,private,ROOT)
    if SettlementLedger(protocol['ledger_directory']).summary()['policy_id']!=protocol['accounting_policy_id']:
        raise ValueError('accounting_authorization_changed')
    return protocol


def decode(name, raw):
    # Frozen statements plus four findings may exceed the production parser's
    # 8KiB argument limit. Research-only bounded 64KiB contract matches host.
    if len(raw.encode())>64000:return None
    from petromind.agent import _reject_constant, _unique_keys
    try:
        value=json.loads(raw,parse_constant=_reject_constant,object_pairs_hook=_unique_keys)
        return value if isinstance(value,dict) else None
    except (ValueError,RecursionError):return None


def run(out, private, stage):
    out=Path(out).resolve();private=Path(private).resolve()
    protocol=load(out,private)
    if not os.environ.get('MODEL_API_KEY'):raise ValueError('missing_model_api_key')
    ledger=SettlementLedger(protocol['ledger_directory'])
    stage_dir=out/stage;stage_dir.mkdir(exist_ok=True,mode=0o700)
    if stage=='suite':
        pilot=read_jsonl(out/'pilot/results.jsonl')
        if len(pilot)!=4 or not all(r['status']=='completed' for r in pilot):
            raise ValueError('complete_paired_pilot_required')
    with (out/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        attempted={(r['task_id'],r['variant']) for r in read_jsonl(stage_dir/'attempts.jsonl')}
        for cid in (protocol['pilot_cases'] if stage=='pilot' else protocol['cases']):
            for variant in protocol['order'][cid]:
                if (cid,variant) in attempted:continue
                task={'task_id':cid,'variant':variant}
                append_json(stage_dir/'attempts.jsonl',{'protocol_id':protocol['protocol_id'],**task})
                cell=stage_dir/f'{cid}-{variant}';cell.mkdir(mode=0o700)
                bridge=None;client=None;start=time.monotonic()
                try:
                    bridge=Bridge(RELEASE,private,cid,cell/'host-audit.private.json','B')
                    # Only the case packet crosses this boundary. Private root,
                    # ledger, protocol paths and scorer are never initial input.
                    client=SettlingClient(protocol,ledger,{**task,'stage':stage})
                    result=run_tool_agent(bridge,client,AgentConfig(**protocol['agent_config']),
                        instructions=protocol['prompts'][variant],tools=protocol['tools'],
                        initial_history=[{'role':'user','content':[{'type':'input_text','text':canonical(bridge.packet)}]}],
                        prompt_version=VERSION,submission_reason='synthetic_assessment_submitted',
                        is_complete=lambda:bridge.result is not None,stop_reason=lambda:bridge.stop,
                        decode_arguments=decode,
                        on_event=lambda e:append_json(cell/'events.jsonl',asdict(e)))
                    row={'protocol_id':protocol['protocol_id'],**task,'stage':stage,
                         'status':result.status,'reason':result.reason,'requests':result.requests,
                         'usage':usage_and_cost(result.events,result.requests,protocol['prices']),
                         'latency_seconds':time.monotonic()-start,'charged_sensors':sorted(bridge.observed),
                         'context_calls':bridge.context_calls,'assessment':bridge.result}
                except (ValueError, OSError):
                    row={'protocol_id':protocol['protocol_id'],**task,'stage':stage,
                         'status':'failed','reason':'trusted_runner_error',
                         'requests':client.requests if client else 0,
                         'usage':{'estimated_cost_usd':0,'cost_complete':False},
                         'latency_seconds':time.monotonic()-start,'charged_sensors':sorted(bridge.observed) if bridge else [],
                         'context_calls':bridge.context_calls if bridge else 0,'assessment':None}
                finally:
                    if client:client.close()
                    if bridge:bridge.close()
                events=json.loads((cell/'host-audit.private.json').read_text()) if (cell/'host-audit.private.json').exists() else []
                row['host_final_digest']=events[-1]['digest'] if events else None
                write_new(cell/'result.json',row)
                append_json(stage_dir/'results.jsonl',row)
                print(canonical({'stage':stage,**task,'status':row['status'],'reason':row['reason'],
                                  'requests':row['requests'],'spending':ledger.summary()}),flush=True)
                if row['reason'] in ('sprint_c_spending_or_attempt_cap','sprint_c_outstanding_request_fail_closed','sprint_c_provider_usage_not_verifiable','sprint_c_accounting_settlement_failed','api_http_error','api_connection_error','api_timeout','trusted_runner_error'):
                    return {'status':'stopped','reason':row['reason'],'spending':ledger.summary()}
    return {'status':'stage_finished','stage':stage,'spending':ledger.summary()}


def score(out, private, stage):
    # Deliberately separate entry point, no key/HTTP client instantiated here.
    out=Path(out).resolve();private=Path(private).resolve();protocol=load(out,private)
    stage_dir=out/stage
    if not stage_dir.exists():raise ValueError('stage_not_run')
    rows=read_jsonl(stage_dir/'results.jsonl')
    reports={};packets=[];review_mapping={}
    for variant in VARIANTS:
        audits={}
        for row in rows:
            if row['variant']!=variant:continue
            cell=stage_dir/f"{row['task_id']}-{variant}"
            events=json.loads((cell/'host-audit.private.json').read_text())
            if events[-1]['digest']!=row['host_final_digest']:raise ValueError('audit_final_digest_changed')
            audits[row['task_id']]=events
            review_id=secrets.token_hex(12)
            review_mapping[review_id]={'case_id':row['task_id'],'variant':variant}
            packets.append({'review_id':review_id,'public_packet':events[0]['result'],
                'tool_events':events[1:],'submission':row['assessment'],
                'review':{'physical_interpretation':None,'evidence_scope':None,'necessity_sufficiency':None,
                          'missing_premises':None,'next_evidence_usefulness':None},'reviewer':None})
        audit_file=stage_dir/f'{variant}-audits.private.json'
        write_new(audit_file,audits)
        score_file=stage_dir/f'{variant}-score.private.json'
        with score_file.open('x') as target:
            subprocess.run([sys.executable,str(private/'evaluate.py'),'--public',str(RELEASE/'public'),
                '--key',str(private/'build/private/answer_key.json'),'--audits',str(audit_file)],
                stdout=target,check=True,env={'PATH':os.defpath,'PYTHONNOUSERSITE':'1'})
        reports[variant]=json.loads(score_file.read_text())
    packets.sort(key=lambda p:p['review_id'])
    write_new(stage_dir/'human-review-packets.private.json',packets)
    write_new(stage_dir/'reviewer-unblinding.private.json',review_mapping)
    summary={'protocol_id':protocol['protocol_id'],'stage':stage,'variants':reports,
        'spending':SettlementLedger(protocol['ledger_directory']).summary(),
        'model_calls':sum(r['requests'] for r in rows),
        'known_usage_cost_usd':sum(r['usage']['estimated_cost_usd'] for r in rows),
        'semantic_review_required':True,'total_score':None}
    write_new(stage_dir/'report.private.json',summary)
    return {'status':'scored','stage':stage,'model_calls':summary['model_calls'],
            'mechanical_points_of_29':{v:r['mechanical_points_of_29'] for v,r in reports.items()},
            'spending':summary['spending'],'semantic_total':None}


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['authorize','prepare','pilot','suite','score'])
    p.add_argument('--out');p.add_argument('--private-root');p.add_argument('--prior-run')
    p.add_argument('--ledger-directory');p.add_argument('--platform-proxy',action='store_true');p.add_argument('--stage',choices=['pilot','suite'],default='suite')
    a=p.parse_args();os.umask(0o077)
    if a.action=='authorize':
        if not a.ledger_directory or not a.prior_run:p.error('original ledger and prior run required')
        result=SettlementLedger.authorize(a.ledger_directory,a.prior_run).summary()
    elif a.action=='prepare':
        if not a.ledger_directory:p.error('--ledger-directory must reference original Session A ledger')
        result=prepare(a.out,a.private_root,a.ledger_directory,a.platform_proxy)
    elif a.action=='score':result=score(a.out,a.private_root,a.stage)
    else:result=run(a.out,a.private_root,a.action)
    print(canonical(result))

if __name__=='__main__':main()
