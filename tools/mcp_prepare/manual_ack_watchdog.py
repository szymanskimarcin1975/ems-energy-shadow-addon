"""One-shot MCP code update with operator ACK; NO new OAuth credentials.
The owner attests existing OAuth/MCP tests. A fresh diagnostic backup is checked
locally; that file alone cannot prove OAuth or all requested client checks.
"""
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import tempfile
import time
import urllib.request
import urllib.error
from deployment_core import Blocked, Deployment, verify, digest

BACK=Path('/config/mcp_prepare_ems2_recovery')
SOURCE=Path('/config/custom_components/mcp_server_http_transport')
STATE='manual-watchdog-state.json'
ACK='manual-watchdog-ack.json'
CHECKS=('core_running','existing_oauth_verified','old_tools_verified','both_new_tools_verified','diagnostic_verified')

@contextmanager
def lock(path,nonblocking=False):
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|(fcntl.LOCK_NB if nonblocking else 0));yield
    finally:os.close(fd)

def read_json(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd) as stream:
        st=os.fstat(stream.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size>32768:raise Blocked('UNSAFE_STATE_FILE')
        value=json.load(stream)
        if not isinstance(value,dict):raise Blocked('INVALID_STATE')
        return value

def atomic_json(path,value):
    fd,name=tempfile.mkstemp(prefix='.manual-state-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if os.path.exists(name):os.unlink(name)

def watchdog_lease_held(backup):
    fd=os.open(backup/'deploy.lock',os.O_RDWR|os.O_NOFOLLOW)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return True
        return False
    finally:os.close(fd)

class LocalAPI:
    """Existing addon Supervisor access only. No new credential, no device calls."""
    def __init__(self):
        self.reason='NOT_CHECKED'
        self.token=os.environ.get('SUPERVISOR_TOKEN')
        if not self.token:raise Blocked('EXISTING_SUPERVISOR_ACCESS_REQUIRED')
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*a,**k):raise Blocked('REDIRECT_REFUSED')
        self.http=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def __call__(self,candidate=False):
        # This tests REST availability, NEVER claims to test OAuth/MCP.
        try:
            req=urllib.request.Request('http://supervisor/core/api/',headers={'Authorization':'Bearer '+self.token})
            with self.http.open(req,timeout=5) as response:
                data=response.read(4097)
                if len(data)>4096:
                    self.reason='CORE_API_RESPONSE_TOO_LARGE';return False
                body=json.loads(data)
                ok=response.status==200 and isinstance(body,dict) and body.get('message')=='API running.'
                self.reason='CORE_API_READY' if ok else 'CORE_API_INVALID_RESPONSE'
                return ok
        except urllib.error.HTTPError as error:
            self.reason={401:'CORE_API_AUTH_DENIED_CHECK_HOMEASSISTANT_API_PERMISSION',403:'CORE_API_FORBIDDEN'}.get(error.code,'CORE_API_HTTP_ERROR')
            return False
        except (OSError,ValueError,Blocked):
            self.reason='CORE_API_UNAVAILABLE_OR_INVALID';return False

def diagnostic_valid(root,config,state):
    # Exact candidate verifier is packaged, not dynamically supplied by caller.
    path=root/'diagnostic_verifier.py'
    spec=importlib.util.spec_from_file_location('ems_manual_diagnostic_verifier',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    op=state['diagnostic_operation_id']
    outcome=module.run(str(config),op,'status')
    if outcome.get('status')!='COMPLETE':return False
    path=config/'ems_prepare_backups'/op/'manifest.json'
    m=read_json(path)
    if m.get('operation_id')!=op or m.get('state')!='COMPLETE':return False
    stamp=datetime.fromisoformat(m['at']).timestamp()
    return state['waiting_started_at']<=stamp<=time.time()+5

def valid_ack(ack,state):
    return set(ack)=={'operation_id','challenge','candidate_sha256','package_manifest_sha256','diagnostic_operation_id','checks'} and all(ack.get(k)==state[k] for k in ('operation_id','challenge','candidate_sha256','package_manifest_sha256','diagnostic_operation_id')) and isinstance(ack['checks'],dict) and set(ack['checks'])==set(CHECKS) and all(ack['checks'][k] is True for k in CHECKS)

def write_ack(root,backup,source,op,challenge,checks,clock=time.monotonic,diag=diagnostic_valid):
    # Separate short lock: does not release/compete with the Core deployment lock.
    with lock(backup/'ack.lock'):
        state=read_json(backup/STATE)
        if state['phase']!='WAITING_ACK' or clock()>=state['deadline_monotonic']:raise Blocked('NOT_WAITING_OR_EXPIRED')
        if op!=state['operation_id'][:12] or challenge!=state['challenge']:raise Blocked('WRONG_UPDATE')
        if not watchdog_lease_held(backup):raise Blocked('NO_RUNNING_WATCHDOG_LEASE')
        if not isinstance(checks,dict) or set(checks)!=set(CHECKS) or not all(checks[k] is True for k in CHECKS):raise Blocked('ALL_MCP_CHECKS_REQUIRED')
        verify(root,root/'SHA256SUMS',exact=False)
        verify(source,root/'CANDIDATE_SHA256SUMS')
        if digest(root/'SHA256SUMS')!=state['package_manifest_sha256']:raise Blocked('WRONG_DEPLOYMENT_PACKAGE')
        if digest(root/'mcp-1.18.0-ems.2-prepare.zip')!=state['candidate_sha256']:raise Blocked('WRONG_PACKAGE')
        if not diag(root,source.parent.parent,state):raise Blocked('FRESH_MCP_DIAGNOSTIC_REQUIRED')
        if clock()>=state['deadline_monotonic']:raise Blocked('ACK_EXPIRED_DURING_CHECK')
        value={k:state[k] for k in ('operation_id','challenge','candidate_sha256','package_manifest_sha256','diagnostic_operation_id')};value['checks']=checks
        fd=os.open(backup/ACK,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
        fd=os.open(backup,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
        return value

class ManualDeployment(Deployment):
    def __init__(self,*args,ack_seconds=900,diagnostic=diagnostic_valid,**kwargs):
        super().__init__(*args,**kwargs)
        if not 30<=ack_seconds<=900:raise Blocked('ACK_WINDOW_OUT_OF_RANGE')
        self.ack_seconds=ack_seconds;self.diagnostic=diagnostic;self.state={}
        self.state_path=self.backup/STATE
        self.log_path=self.backup/'manual-watchdog-events.jsonl'
    def _record(self,phase,**updates):
        self.state.update(updates,phase=phase,time_utc=datetime.now().astimezone().isoformat())
        atomic_json(self.state_path,self.state)
        record={k:self.state[k] for k in ('phase','time_utc','operation_id','candidate_sha256','rollback_attempted')}
        fd=os.open(self.log_path,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as f:f.write(json.dumps(record)+'\n');f.flush();os.fsync(f.fileno())
    def event(self,phase,**updates):
        with lock(self.backup/'ack.lock'):self._record(phase,**updates)
    def wait_ack(self):
        while True:
            with lock(self.backup/'ack.lock'):
                if self.clock()>=self.state['deadline_monotonic']:
                    self._record('ACK_TIMEOUT');return False
                try:
                    ack=read_json(self.backup/ACK)
                    valid=valid_ack(ack,self.state)
                except (OSError,ValueError,KeyError,Blocked):valid=False
                if valid:
                    if digest(self.root/'SHA256SUMS')!=self.state['package_manifest_sha256']:raise Blocked('DEPLOYMENT_PACKAGE_CHANGED')
                    verify(self.source,self.root/'CANDIDATE_SHA256SUMS')
                    if self.diagnostic(self.root,self.source.parent.parent,self.state) and self.clock()<self.state['deadline_monotonic']:
                        os.rename(self.backup/ACK,self.backup/'manual-ack-consumed.json')
                        self._record('SUCCESS_ACK_CONSUMED');return True
            if not self.health(True):
                self.event('CORE_API_FAILED_WHILE_WAITING_ACK');return False
            self.pause(2)
    def rollback_once(self,original):
        if self.state['rollback_attempted']:raise Blocked('ROLLBACK_ALREADY_ATTEMPTED')
        self.event('ROLLBACK_ONCE',rollback_attempted=True)
        try:
            verify(self.backup/'component',self.root/'BASE_SHA256SUMS')
            verify(original,self.root/'BASE_SHA256SUMS')
            self.swap_stopped(original,'manual-failed-candidate')
            started=self.core('start')
            ok=started and self.wait_health(False)
        except Exception:ok=False
        self.event('ROLLED_BACK_API_ONLY_MCP_UNVERIFIED' if ok else 'RECOVERY_FAILED_OPERATOR_REQUIRED')
        return False
    def execute(self):
        if not self.backup.is_dir() or self.backup.is_symlink() or self.backup.stat().st_uid!=os.geteuid() or self.backup.stat().st_mode&0o077:raise Blocked('PRIVATE_VERIFIED_RECOVERY_REQUIRED')
        with lock(self.backup/'deploy.lock',nonblocking=True):
            if self.state_path.exists() or (self.backup/'watchdog-state.json').exists():raise Blocked('EXISTING_OPERATION_RECONCILE_NO_REPLAY')
            verify(self.root,self.root/'SHA256SUMS',exact=False)
            verify(self.backup/'component',self.root/'BASE_SHA256SUMS')
            verify(self.source,self.root/'BASE_SHA256SUMS')
            if not (self.backup/'PREPARED').is_file():raise Blocked('PREPARE_REQUIRED')
            if not self.health(False):raise Blocked('LOCAL_CORE_API_BASELINE_REQUIRED')
            self.state={'operation_id':secrets.token_hex(16),'challenge':secrets.token_hex(6),'candidate_sha256':digest(self.root/'mcp-1.18.0-ems.2-prepare.zip'),'package_manifest_sha256':digest(self.root/'SHA256SUMS'),'rollback_attempted':False,'watchdog_pid':os.getpid()}
            self.state['diagnostic_operation_id']=self.state['operation_id']
            if (self.source.parent.parent/'ems_prepare_backups'/self.state['diagnostic_operation_id']).exists():raise Blocked('DIAGNOSTIC_ID_ALREADY_EXISTS')
            self.event('ARMED')
            original=self.prepare_stage(False);candidate=self.prepare_stage(True)
            if not self.core('check'):self.event('CONFIG_CHECK_FAILED_NO_CHANGE');return False
            self.event('INSTALLING')
            try:
                self.swap_stopped(candidate,'manual-pre-install')
                started=self.core('start')
                if started and self.wait_health(True):
                    self.event('WAITING_ACK',waiting_started_at=time.time(),deadline_monotonic=self.clock()+self.ack_seconds,deadline_utc=time.time()+self.ack_seconds)
                    print('WAITING_ACK_USE_STATUS_FOR_DIAGNOSTIC_ID',flush=True)
                    if self.wait_ack():return True
            except Blocked:
                self.event('UNKNOWN_REQUIRES_OPERATOR');return False
            except Exception:
                self.event('WATCHDOG_ERROR_ATTEMPT_ONE_RECOVERY')
            return self.rollback_once(original)

def status(backup):
    s=read_json(backup/STATE)
    return {k:s.get(k) for k in ('phase','operation_id','challenge','candidate_sha256','package_manifest_sha256','diagnostic_operation_id','deadline_utc','rollback_attempted')}

def preflight(root,backup,source,api_factory=LocalAPI):
    # Fixed stage labels only: never print HTTP bodies, headers or exception text.
    stages=(('PACKAGE',lambda:verify(root,root/'SHA256SUMS',exact=False)),
            ('RECOVERY_CODE',lambda:verify(backup/'component',root/'BASE_SHA256SUMS')),
            ('PRODUCTION_CODE',lambda:verify(source,root/'BASE_SHA256SUMS')))
    for name,check in stages:
        try:check()
        except (OSError,ValueError,KeyError,Blocked):
            print('PREFLIGHT_'+name+'_FAILED');return 1
        print('PREFLIGHT_'+name+'_PASS')
    try:api=api_factory()
    except Blocked:
        print('PREFLIGHT_SUPERVISOR_TOKEN_MISSING');return 1
    if not api(False):
        print('PREFLIGHT_'+api.reason);return 1
    print('CODE_BACKUP_AND_LOCAL_API_PASS_OAUTH_MCP_NOT_TESTED');return 0

def main():
    args=sys.argv[1:];root=Path(__file__).resolve().parent
    try:
        if args==['status']:
            print(json.dumps(status(BACK),indent=2));return 0
        if len(args)==3 and args[0]=='ack':
            print('ACK potwierdza wszystkie 5 kontroli przez istniejace MCP: Core, OAuth, stare narzedzia, oba nowe narzedzia i diagnostyke.')
            if input('Po wykonaniu kontroli wpisz TAK: ').strip()!='TAK':raise Blocked('OPERATOR_DID_NOT_CONFIRM')
            write_ack(root,BACK,SOURCE,args[1],args[2],{k:True for k in CHECKS})
            print('ACK_RECORDED_NOT_YET_ACCEPTED_CHECK_FINAL_STATUS');return 0
        if args==['preflight']:
            return preflight(root,BACK,SOURCE)
        if args!=['deploy','CONFIRM_CORE_RESTART']:raise Blocked('EXPLICIT_RESTART_APPROVAL_REQUIRED')
        old=Path('/config/mcp-ems2/mcp-package/install.sh')
        if old.is_file() and 'ha core stop' in old.read_text():raise Blocked('OLD_STANDALONE_INSTALLER_MUST_BE_WITHDRAWN')
        ok=ManualDeployment(root,BACK,SOURCE,LocalAPI()).execute()
        print('ACCEPTED_BY_OPERATOR' if ok else 'NOT_ACCEPTED_READ_STATUS');return 0 if ok else 1
    except (OSError,ValueError,KeyError,Blocked,EOFError):
        print('BLOCKED_NO_SECRET_DETAILS_CHECK_LOCAL_STATUS');return 1

if __name__=='__main__':raise SystemExit(main())
