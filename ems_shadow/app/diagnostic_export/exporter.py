"""One-shot Online Backup. Never imports the mutating Shadow constructor."""
import argparse,hashlib,json,os,sqlite3,time,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
SCHEMA={'samples':['id','time','session','raw','quality'],'state':['key','value'],
'increments':['sample_id','category','tariff','method','start','end','kwh'],'events':['sample_id','reason']}
def utc(value):
    d=datetime.fromisoformat(value)
    if d.tzinfo is None:raise ValueError('timezone_required')
    return d.astimezone(timezone.utc)
def validate(db,digest):
    if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise ValueError('integrity_failure')
    for table,columns in SCHEMA.items():
        if [r[1] for r in db.execute('PRAGMA table_info('+table+')')]!=columns:raise ValueError('schema_mismatch')
    row=db.execute("SELECT value FROM state WHERE key='sources_digest'").fetchone()
    if not row or row[0]!=digest:raise ValueError('source_digest_mismatch')
    if db.execute('SELECT COUNT(*) FROM increments i LEFT JOIN samples s ON i.sample_id=s.id WHERE s.id IS NULL').fetchone()[0]:raise ValueError('orphan_increment')
    bounds=db.execute('SELECT MIN(time),MAX(time),COUNT(*) FROM samples').fetchone()
    for t in bounds[:2]:
        if t:utc(t)
    return dict(first_sample=bounds[0],last_sample=bounds[1],samples=bounds[2])

def export(source,destination,ledger_id,digest,timeout=30,cancel=None):
    source=Path(source);destination=Path(destination)
    if any(p.is_symlink() for p in (source,*source.parents)):raise ValueError('source_symlink')
    if source.name!='shadow.sqlite' or source.parent.name!=ledger_id:raise ValueError('ledger_path_mismatch')
    if not source.is_file():raise ValueError('source_missing')
    if source.resolve()==destination.resolve() or source.parent.resolve()==destination.parent.resolve():raise ValueError('destination_in_active_ledger')
    if any(p.is_symlink() for p in destination.parents):raise ValueError('destination_symlink')
    manifest=destination.with_suffix('.manifest.json');partial=destination.with_suffix('.partial')
    if any(p.exists() or p.is_symlink() for p in (destination,manifest,partial)):raise ValueError('destination_exists')
    if manifest.with_suffix('.partial.json').exists():raise ValueError('manifest_partial_exists')
    started=datetime.now(timezone.utc).isoformat();begin=time.monotonic();src=dst=None;complete=False;manifest_published=False
    try:
        fd=os.open(partial,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(fd)
        src=sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)
        # Source connection is never checkpointed, vacuumed or configured.
        dst=sqlite3.connect(partial)
        def progress(status,remaining,total):
            if (cancel and cancel()) or time.monotonic()-begin>timeout:raise TimeoutError('export_cancelled_or_timeout')
        src.backup(dst,pages=64,progress=progress,sleep=.05)
        if cancel and cancel():raise TimeoutError('export_cancelled')
        info=validate(dst,digest)
        dst.close();dst=None;src.close();src=None
        with open(partial,'rb') as f:os.fsync(f.fileno())
        hasher=hashlib.sha256()
        with open(partial,'rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):
                if time.monotonic()-begin>timeout:raise TimeoutError('export_timeout')
                hasher.update(chunk)
        h=hasher.hexdigest()
        data=dict(schema_version=1,ledger_id=ledger_id,ledger_identity='path_plus_expected_sources_digest',sources_digest=digest,
          started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),sha256=h,complete=True,**info)
        # Never overwrite an existing target. Manifest is the completion marker.
        os.link(partial,destination);partial.unlink()
        manifest_partial=manifest.with_suffix('.partial.json')
        fd=os.open(manifest_partial,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as f:json.dump(data,f,indent=2);f.flush();os.fsync(f.fileno())
        os.link(manifest_partial,manifest);manifest_published=True;manifest_partial.unlink()
        directory=os.open(destination.parent,os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
        complete=True;return data
    finally:
        if dst:dst.close()
        if src:src.close()
        if not complete:
            # Remove only this attempt's final manifest, never source or export data.
            # If removal fails, operator must quarantine the attempt despite manifest.
            if manifest_published and manifest.exists():
                try:manifest.unlink()
                except OSError:pass
def run_bounded(command,timeout):
    child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    try:
        output,_=child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        child.terminate()
        try:child.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            child.kill()
            try:child.communicate(timeout=1)
            except subprocess.TimeoutExpired:raise RuntimeError('worker_stop_unconfirmed') from None
        raise TimeoutError('worker_deadline_exceeded') from None
    if child.returncode!=0:raise RuntimeError('export_worker_failed')
    return output

def export_bounded(source,destination,ledger_id,digest,timeout=30):
    command=[sys.executable,str(Path(__file__).resolve()),'--worker','--source',str(source),
        '--destination',str(destination),'--ledger-id',ledger_id,'--sources-digest',digest,'--timeout',str(timeout)]
    output=run_bounded(command,timeout)
    data=json.loads(output)
    if data.get('complete') is not True:raise ValueError('worker_incomplete')
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--destination',required=True)
    p.add_argument('--ledger-id',required=True);p.add_argument('--sources-digest',required=True)
    p.add_argument('--worker',action='store_true');p.add_argument('--timeout',type=float,default=30)
    a=p.parse_args()
    if a.timeout<=0:raise ValueError('positive_timeout_required')
    fn=export if a.worker else export_bounded
    result=fn(a.source,a.destination,a.ledger_id,a.sources_digest,timeout=a.timeout)
    print(json.dumps(result))
