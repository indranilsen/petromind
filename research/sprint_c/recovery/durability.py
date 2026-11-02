"""Owner-local persistence and a fixed authorization registry. No HTTP."""
import fcntl,json,os,plistlib,sqlite3,subprocess,sys
from pathlib import Path


def is_macos():return sys.platform=='darwin'


def sync_file(fd):
    os.fsync(fd)
    if is_macos():
        flag=getattr(fcntl,'F_FULLFSYNC',None)
        if flag is None:raise ValueError('mac_fullfsync_unavailable')
        fcntl.fcntl(fd,flag,0)


def sync_dir(root):
    fd=os.open(root,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def durable_text(path,text,exclusive=True):
    path=Path(path)
    flags=os.O_WRONLY|os.O_CREAT|(os.O_EXCL if exclusive else os.O_APPEND)
    fd=os.open(path,flags,0o600)
    with os.fdopen(fd,'w' if exclusive else 'a') as f:
        f.write(text);f.flush();os.fsync(f.fileno());sync_dir(path.parent);sync_file(f.fileno())


def sqlite_settings(db,initialize=False):
    if initialize:db.execute('PRAGMA journal_mode=DELETE')
    if db.execute('PRAGMA journal_mode').fetchone()[0].lower()!='delete':raise ValueError('rollback_journal_required')
    db.execute('PRAGMA synchronous=EXTRA');db.execute('PRAGMA fullfsync=ON');db.execute('PRAGMA busy_timeout=0')
    if db.execute('PRAGMA synchronous').fetchone()[0]!=3 or db.execute('PRAGMA fullfsync').fetchone()[0]!=1:
        raise ValueError('required_sqlite_durability_unavailable')


def authorization_registry(proposal):
    scope=proposal.get('original_policy_id',proposal['proposal_id'])
    return Path.home()/'.local/share/petromind-sprint-c-authorizations'/f'{scope}.json'


def local_surface(root):
    root=Path(root).resolve()
    if not is_macos():return {'platform':sys.platform,'filesystem':'not_macos','local_macos_approved':False}
    home=Path.home().resolve()
    excluded=[home/'Desktop',home/'Documents',home/'Library/Mobile Documents',home/'Library/CloudStorage']
    if any(root==p or p in root.parents for p in excluded) or any(x.name.lower().startswith(('dropbox','onedrive','google drive')) for x in [root,*root.parents]):
        raise ValueError('synced_or_file_provider_path_forbidden')
    result=subprocess.run(['/bin/df','-P',str(root)],capture_output=True,text=True,check=True)
    device=result.stdout.strip().splitlines()[-1].split()[0]
    if not device.startswith('/dev/disk'):raise ValueError('local_block_volume_required')
    raw=subprocess.check_output(['/usr/sbin/diskutil','info','-plist',device])
    info=plistlib.loads(raw)
    if (str(info.get('FilesystemType','')).lower()!='apfs' or info.get('VolumeNetwork') is True
        or info.get('ReadOnlyVolume') is True or info.get('ReadOnlyMedia') is True):
        raise ValueError('writable_local_apfs_required')
    return {'platform':'darwin','filesystem':'apfs','local_macos_approved':True,
            'same_device':root.stat().st_dev,'file_provider_exclusions_checked':True,
            'owner_assertion_required':'No custom sync tool, disk image backed by a synced file, network share or active clone.'}
