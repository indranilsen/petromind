"""API-free disposable storage checks and separate-session witness gate."""
import fcntl,json,os,secrets,sqlite3,subprocess,sys,time
from pathlib import Path
from petromind.eval_protocol import digest
from . import durability


def fsync_dir(root):
    durability.sync_dir(root)


def validate(root,surface='hosted_disposable'):
    root=Path(root).resolve();root.mkdir(mode=0o700)
    facts=durability.local_surface(root) if surface=='trusted_local_owner' else {'platform':'hosted','local_macos_approved':False}
    if surface=='trusted_local_owner' and not facts['local_macos_approved']:raise ValueError('trusted_local_mac_required')
    nonce=secrets.token_hex(24);durability.durable_text(root/'nonce',nonce)
    checks={}
    log=root/'append';head=root/'head'
    with log.open('x') as f:f.write('one\n');f.flush();durability.sync_file(f.fileno())
    fsync_dir(root);checks['sequential_append_readback']=log.read_text()=='one\n'
    with (root/'head.new').open('x') as f:f.write('1');f.flush();durability.sync_file(f.fileno())
    os.replace(root/'head.new',head);fsync_dir(root);checks['file_directory_fsync_atomic_replace']=head.read_text()=='1'
    with (root/'lock').open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        code="import fcntl,sys; f=open(sys.argv[1],'a');\ntry: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)\nexcept BlockingIOError: sys.exit(23)\nsys.exit(1)"
        checks['lock_exclusion']=subprocess.run([sys.executable,'-c',code,str(root/'lock')],capture_output=True).returncode==23
    checks['lock_release']=subprocess.run([sys.executable,'-c',"import fcntl,sys;f=open(sys.argv[1],'a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)",str(root/'lock')],capture_output=True).returncode==0
    checks['process_restart_readback']=subprocess.check_output([sys.executable,'-c',"import sys;from pathlib import Path;print(Path(sys.argv[1]).read_text(),end='')",str(log)],text=True)=='one\n'
    partial=root/'interrupted-append';partial.write_bytes(b'one\npartial')
    checks['interrupted_append_detected']=not partial.read_bytes().endswith(b'\n')
    divergent=root/'divergent-head';divergent.write_text('2')
    checks['interrupted_checkpoint_detected']=int(divergent.read_text())!=len(log.read_text().splitlines())
    db=root/'crash.sqlite';c=sqlite3.connect(db);durability.sqlite_settings(c,initialize=True);c.execute('CREATE TABLE events (n INTEGER)');c.commit();c.close()
    code="import sqlite3,sys,os;from research.sprint_c.recovery.durability import sqlite_settings;c=sqlite3.connect(sys.argv[1]);sqlite_settings(c);c.execute('BEGIN IMMEDIATE');c.execute('INSERT INTO events VALUES (1)');os._exit(7)"
    subprocess.run([sys.executable,'-c',code,str(db)],capture_output=True)
    c=sqlite3.connect(db);checks['interrupted_sqlite_transaction_rolled_back']=c.execute('SELECT COUNT(*) FROM events').fetchone()[0]==0 and c.execute('PRAGMA integrity_check').fetchone()[0]=='ok';c.close()
    # Independent processes validate transactional single-writer / read snapshots.
    # This disposable snapshot test deliberately has a reader, unlike the money
    # owner. Allow normal SQLite reader contention here only; money timeout stays 0.
    writer="import sqlite3,sys,time;from research.sprint_c.recovery.durability import sqlite_settings;c=sqlite3.connect(sys.argv[1]);sqlite_settings(c);c.execute('PRAGMA busy_timeout=5000');\nfor i in range(100):\n c.execute('INSERT INTO events VALUES (?)',(i,));c.commit();time.sleep(.001)"
    w=subprocess.Popen([sys.executable,'-c',writer,str(db)])
    good=True;seen=[]
    while w.poll() is None:
        c=sqlite3.connect(db);n=c.execute('SELECT COUNT(*) FROM events').fetchone()[0];c.close();seen.append(n)
        if len(seen)>1 and seen[-1]<seen[-2]:good=False
    checks['concurrent_writer_reader_snapshots']=good and w.returncode==0
    checks['divergent_view_detection']=digest({'nonce':nonce,'head':1})!=digest({'nonce':'other','head':1})
    report={'version':'local-storage-checks-v2','filesystem':facts,'nonce':nonce,'surface':surface,'checks':checks,
        'passed':all(checks.values()),'separate_session_witness_complete':False,
        'device':root.stat().st_dev,'inode':root.stat().st_ino,'not_a_universal_durability_proof':True}
    report['report_id']=digest(report);durability.durable_text(root/'validation.json',json.dumps(report,indent=2)+'\n')
    return report


def cross(root,mode):
    root=Path(root).resolve();report=json.loads((root/'validation.json').read_text());nonce=(root/'nonce').read_text()
    if report['nonce']!=nonce:raise ValueError('storage_nonce_diverged')
    if mode=='writer':
        log=root/'cross-log';head=root/'cross-head';log.write_text('');head.write_text('0')
        (root/'cross-start').write_text(str(time.time_ns()))
        for i in range(1,501):
            with (root/'cross-lock').open('a') as f:
                fcntl.flock(f,fcntl.LOCK_EX)
                n=len(log.read_text().splitlines());h=int(head.read_text())
                if n!=h:break
                with log.open('a') as stream:stream.write(str(i)+'\n');stream.flush();durability.sync_file(stream.fileno())
                with (root/'cross-head.new').open('w') as stream:stream.write(str(i));stream.flush();durability.sync_file(stream.fileno())
                os.replace(root/'cross-head.new',head);fsync_dir(root)
            time.sleep(.02)
        success=n==h and i==500
        value={'mode':mode,'nonce':nonce,'pid':os.getpid(),'passed':success,'iterations':i,'rows':len(log.read_text().splitlines()),'head':int(head.read_text()),'finished_ns':time.time_ns()}
    else:
        if not (root/'cross-start').exists():raise ValueError('writer_must_start_first')
        start=int((root/'cross-start').read_text());observed=0;success=True;first=time.time_ns()
        for _ in range(500):
            with (root/'cross-lock').open('a') as f:
                fcntl.flock(f,fcntl.LOCK_EX)
                n=len((root/'cross-log').read_text().splitlines());h=int((root/'cross-head').read_text())
                if n!=h:success=False;break
                if h<500:observed+=1
            time.sleep(.01)
        value={'mode':mode,'nonce':nonce,'pid':os.getpid(),'passed':success,'observed_active_writer':observed>0,'started_ns':first,'writer_started_ns':start,'finished_ns':time.time_ns()}
    value['device']=root.stat().st_dev;value['inode']=root.stat().st_ino;value['result_id']=digest(value)
    durability.durable_text(root/f'cross-{mode}.json',json.dumps(value,indent=2)+'\n');return value


CHECKS={'sequential_append_readback','file_directory_fsync_atomic_replace','lock_exclusion','lock_release',
        'process_restart_readback','interrupted_append_detected','interrupted_checkpoint_detected',
        'interrupted_sqlite_transaction_rolled_back','concurrent_writer_reader_snapshots','divergent_view_detection'}


def witness_certificate(root):
    root=Path(root).resolve();v=json.loads((root/'validation.json').read_text());w=json.loads((root/'cross-writer.json').read_text());r=json.loads((root/'cross-reader.json').read_text())
    for obj,key in ((v,'report_id'),(w,'result_id'),(r,'result_id')):
        if digest({k:x for k,x in obj.items() if k!=key})!=obj[key]:raise ValueError('storage_report_modified')
    if v.get('version')!='local-storage-checks-v2' or set(v['checks'])!=CHECKS or any(x is not True for x in v['checks'].values()):raise ValueError('required_storage_checks_missing')
    if not (v['passed'] is True and w['passed'] is True and r['passed'] is True and r['observed_active_writer'] is True
            and w['pid']!=r['pid'] and w['mode']=='writer' and r['mode']=='reader'
            and r['writer_started_ns']<=r['started_ns']<w['finished_ns'] and w['iterations']==500 and w['rows']==w['head']==500):
        raise ValueError('cross_session_storage_not_verified')
    identity=(root.stat().st_dev,root.stat().st_ino)
    if any((x['device'],x['inode'])!=identity for x in (v,w,r)) or len({x['nonce'] for x in (v,w,r)})!=1:raise ValueError('divergent_storage_views')
    if (root/'nonce').read_text()!=v['nonce'] or (root/'cross-log').read_text().splitlines()!=[str(i) for i in range(1,501)] or (root/'cross-head').read_text()!='500':raise ValueError('storage_diverged_after_probe')
    if v['surface']=='trusted_local_owner' and durability.local_surface(root)!=v['filesystem']:raise ValueError('local_filesystem_changed')
    c={'version':'local-storage-certificate-v2','validation_id':v['report_id'],'writer_id':w['result_id'],'reader_id':r['result_id'],'nonce':v['nonce'],
       'surface':v['surface'],'passed':True,'owner_directory':str(root),'not_a_universal_durability_proof':True}
    c['certificate_id']=digest(c);return c


def certify(root):
    root=Path(root).resolve();c=witness_certificate(root)
    durability.durable_text(root/'certificate.json',json.dumps(c,indent=2)+'\n');return c


def verify_certificate(path,require_local=True):
    path=Path(path).resolve();saved=json.loads(path.read_text())
    if require_local and saved.get('surface')!='trusted_local_owner':raise ValueError('hosted_execution_forbidden')
    if saved!=witness_certificate(path.parent):raise ValueError('storage_certificate_or_current_view_changed')
    return saved
