#!/usr/bin/env python3
"""Offline log/checkpoint coherence probe. Never contains credentials or HTTP.

Run writer and reader in separate execution sessions sharing --directory.
A failure does not identify the storage implementation; it forbids trusting that
surface for a live money ledger without independent reconciliation.
"""
import argparse,fcntl,json,os,time
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('mode',choices=['writer','reader']);p.add_argument('--directory',required=True);a=p.parse_args()
r=Path(a.directory)
if a.mode=='writer':
    r.mkdir(mode=0o700)
    (r/'log').write_text('');(r/'head').write_text('0')
    for i in range(1,501):
        with (r/'lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            count=len((r/'log').read_text().splitlines());head=int((r/'head').read_text())
            if count!=head:
                (r/'writer-failure.json').write_text(json.dumps({'iteration':i,'log_rows':count,'head':head})+'\n');break
            with (r/'log').open('a') as f:f.write(str(i)+'\n');f.flush();os.fsync(f.fileno())
            with (r/'head.new').open('w') as f:f.write(str(i));f.flush();os.fsync(f.fileno())
            os.replace(r/'head.new',r/'head')
        time.sleep(.02)
else:
    for i in range(500):
        with (r/'lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            count=len((r/'log').read_text().splitlines());head=int((r/'head').read_text())
            if count!=head:
                print(json.dumps({'status':'COHERENCE_FAILURE','reader_iteration':i,'log_rows':count,'head':head}));break
        time.sleep(.01)
    else:print(json.dumps({'status':'no_mismatch_observed','not_a_durability_guarantee':True}))
