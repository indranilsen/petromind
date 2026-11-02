"""Owner-side JSON-lines bridge; NEVER run in or mount into a model sandbox.

This process exposes only one case packet and frozen adapter responses. It is a
transport, not an OS sandbox. The owner must keep its files/UID separate from any
agent with filesystem/exec tools. It does not read the answer key or scorer.
"""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--release-root',required=True)
    p.add_argument('--private-root',required=True)
    p.add_argument('--case',required=True)
    p.add_argument('--audit-out',required=True)
    a=p.parse_args()
    release=Path(a.release_root).resolve()
    spec=importlib.util.spec_from_file_location('frozen_challenge_adapter',release/'adapter.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    public=release/'public'
    ids=json.loads((public/'index.json').read_text())['case_ids']
    if a.case not in ids:raise ValueError('unknown case')
    vault_path=Path(a.private_root).resolve()/'build/private/vault'/f'{a.case}.json'
    # Host-only closure: no evaluator, references or metadata enter this response path.
    def read_sensor(tag):
        vault=json.loads(vault_path.read_text())
        return vault[tag]
    session=module.ChallengeSession(public,a.case,read_sensor)
    # Exclusive creation: never overwrite an earlier trusted transcript.
    fd=os.open(a.audit_out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as audit:
        def persist():
            audit.seek(0)
            json.dump(session.audit,audit,sort_keys=True,allow_nan=False)
            audit.write('\n');audit.truncate();audit.flush();os.fsync(audit.fileno())
        def emit(result):
            print(json.dumps({'result':result},allow_nan=False),flush=True)
        persist();emit(session.packet())
        for _ in range(32):
            line=sys.stdin.buffer.readline(65538)
            if not line:break
            if len(line)>65536:
                emit({'error':'transport_input_limit'});break
            try:
                req=json.loads(line)
                if not isinstance(req,dict) or set(req)!={'name','arguments'} or not isinstance(req['name'],str):
                    emit({'error':'transport_invalid_request'});continue
                result=session.call(req['name'],req['arguments'])
            except (ValueError,TypeError):
                emit({'error':'transport_invalid_request'});continue
            persist();emit(result)
            if isinstance(result,dict) and (result.get('accepted') or result.get('error') in {'session_closed','tool_limit'}):break
        persist()

if __name__=='__main__':
    try:main()
    except Exception:
        # Do not put paths, exception messages, data, stack frames or keys on model-facing streams.
        print(json.dumps({'result':{'error':'trusted_host_failure'}}),flush=True)
        sys.exit(1)
