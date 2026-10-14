"""Private, allowlisted export requests. Does not connect to HA or ledger SQLite."""
import fcntl,json,os,re,sqlite3,threading
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
KEYS={'operation','request_id','ledger_id','expires_at','start','end'}
def instant(s):
    if not isinstance(s,str):raise ValueError('invalid_timestamp')
    d=datetime.fromisoformat(s)
    if d.tzinfo is None:raise ValueError('timezone_required')
    return d.astimezone(timezone.utc)
def validate(value,ledger,now):
    if not isinstance(value,dict) or set(value)!=KEYS:raise ValueError('invalid_request_fields')
    if value['operation']!='diagnostic_export':raise ValueError('invalid_operation')
    if not isinstance(value['request_id'],str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,64}',value['request_id']):raise ValueError('invalid_request_id')
    if value['ledger_id']!=ledger:raise ValueError('ledger_mismatch')
    expires=instant(value['expires_at']);start=instant(value['start']);end=instant(value['end'])
    if not 0<(expires-now).total_seconds()<=300:raise ValueError('expired_or_excessive_validity')
    if (end-start).total_seconds()!=86400 or end>now:raise ValueError('invalid_analysis_period')
    return value

def atomic_json(path,value):
    path=Path(path)
    if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('symlink_refused')
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    tmp=path.with_suffix('.tmp')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as f:json.dump(value,f,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def aggregate_report(result,request):
    grids={}
    for minutes in ('60','15','30'):
        projected=[]
        for row in result.get('grids',{}).get(minutes,[]):
            clean={k:row[k] for k in ('start','end','samples','valid','rejected')}
            instant(clean['start']);instant(clean['end'])
            for k in ('samples','valid','rejected'):
                if type(clean[k]) is not int or clean[k]<0:raise ValueError('invalid_aggregate')
            clean['quality']={k:v for k,v in row['quality'].items() if re.fullmatch(r'(baseline|valid_sampled|restart_or_invalid_baseline|communication_gap|negative_power|power_balance_inconsistent|solar_skew|invalid_number|invalid_workday|stale_or_unsettled_(inverter|grid|boiler|heatpump)_time|invalid_timestamp_[a-z_]+|timezone_required_[a-z_]+)',k) and type(v) is int}
            clean['source_issues']={k:v for k,v in row.get('source_issues',{}).items() if re.fullmatch(r'(inverter|grid|boiler|heatpump|workday|balance|capture):(future|too_fresh|stale|invalid_timestamp|solar_skew|invalid_number|negative_power|inconsistent|invalid_workday|invalid_time)',k) and type(v) is int}
            clean['categories']={}
            for category in ('building','boiler','heatpump'):
                data=row['categories'][category]
                import math
                for k in ('integrated_seconds','coverage_percent','missing_seconds'):
                    if type(data[k]) not in (int,float) or not math.isfinite(data[k]) or data[k]<0:raise ValueError('invalid_category_aggregate')
                clean['categories'][category]={k:data[k] for k in ('integrated_seconds','coverage_percent','missing_seconds','candidate_full_coverage')}
                clean['categories'][category]['training_approved']=False
            projected.append(clean)
        grids[minutes]=projected
    return {'schema_version':1,'request_id':request['request_id'],'ledger_id':request['ledger_id'],
        'start':request['start'],'end':request['end'],'topology_confirmed':False,'grids':grids,
        'note':'Diagnostic quality only; not approved training or billing data.'}

class Controller:
    def __init__(self,root,ledger,worker,enabled=False,cooldown=60,max_exports=3):
        if type(enabled) is not bool:raise ValueError('enabled_boolean_required')
        self.root=Path(root);self.ledger=ledger;self.worker=worker;self.enabled=enabled
        if any(p.is_symlink() for p in (self.root,*self.root.parents)):raise ValueError('symlink_refused')
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.lock=open(self.root/'controller.lock','a')
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BaseException:self.lock.close();raise
        self.db=sqlite3.connect(self.root/'requests.sqlite',check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,received REAL,status TEXT,reason TEXT)');self.db.commit()
        # No automatic replay after restart; UNKNOWN blocks all new exports.
        self.db.execute("UPDATE requests SET status='UNKNOWN',reason='interrupted_requires_review' WHERE status IN ('ACCEPTED','RUNNING')");self.db.commit()
        self.mutex=threading.Lock();self.pool=ThreadPoolExecutor(max_workers=1);self.stop=threading.Event()
        self.cooldown=cooldown;self.max_exports=max_exports;self.future=None
    def submit(self,value,now=None):
        now=now or datetime.now(timezone.utc)
        if not self.enabled:raise ValueError('export_disabled')
        if self.stop.is_set():raise ValueError('controller_unhealthy')
        validate(value,self.ledger,now)
        with self.mutex:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                if self.db.execute('SELECT 1 FROM requests WHERE id=?',(value['request_id'],)).fetchone():raise ValueError('request_already_seen')
                if self.db.execute("SELECT 1 FROM requests WHERE status IN ('ACCEPTED','RUNNING','UNKNOWN')").fetchone():raise ValueError('export_active_or_unconfirmed')
                count,last=self.db.execute('SELECT COUNT(*),MAX(received) FROM requests').fetchone()
                if count>=self.max_exports:raise ValueError('export_quota')
                if last is not None and now.timestamp()-last<self.cooldown:raise ValueError('export_cooldown')
                self.db.execute('INSERT INTO requests VALUES(?,?,?,NULL)',(value['request_id'],now.timestamp(),'ACCEPTED'));self.db.commit()
            except Exception:self.db.rollback();raise
            # Reservation precedes scheduling; a crash here is recovered as UNKNOWN.
            self.future=self.pool.submit(self._execute,dict(value))
            self.future.add_done_callback(self._completed)
            return 'ACCEPTED'
    def _completed(self,future):
        if not future.cancelled() and future.exception() is not None:
            self.stop.set()
            print('export_controller_error; requests_disabled; observation_unaffected',flush=True)
    def _status(self,id,status,reason=None):
        with self.mutex:
            self.db.execute('UPDATE requests SET status=?,reason=? WHERE id=?',(status,reason,id));self.db.commit()
    def _execute(self,request):
        id=request['request_id']
        try:
            self._status(id,'RUNNING')
            if instant(request['expires_at'])<=datetime.now(timezone.utc):raise ValueError('expired_before_execution')
            self.worker(request,self.stop)
            self._status(id,'COMPLETE')
        except Exception as e:
            # No exception text, token, path or raw data in statuses.
            status='UNKNOWN' if isinstance(e,RuntimeError) and str(e)=='worker_stop_unconfirmed' else 'FAILED'
            self._status(id,status,type(e).__name__)
    def close(self):
        self.stop.set();self.pool.shutdown(wait=True,cancel_futures=True);self.db.close();self.lock.close()

def read_requests(stream,submit):
    while True:
        line=stream.readline(4097)
        if not line:return
        if len(line.encode('utf-8'))>4096 or not line.endswith('\n'):
            while line and not line.endswith('\n'):line=stream.readline(4097)
            continue
        try:
            def unique(pairs):
                d={}
                for k,v in pairs:
                    if k in d:raise ValueError('duplicate_field')
                    d[k]=v
                return d
            submit(json.loads(line,object_pairs_hook=unique))
        except (ValueError,TypeError):print('export_request_rejected',flush=True)
        except Exception:
            print('export_controller_error; observation_unaffected',flush=True)
            raise
