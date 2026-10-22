"""Supervisor stdin control, no network listener, shell, OAuth token or device API.
Package is immutable during a worker operation. Never automatically resumes.
"""
import hashlib,json,os,re,shutil,subprocess,sys,threading,zipfile
from pathlib import Path
PACKAGE=Path('/app/package.zip')
STAGE=Path('/data/package')
REPORT=Path('/config/mcp_installer_status.yaml')
ALLOWED={'install.sh','manual-ack-launch.sh','manual_ack_watchdog.py','deployment_core.py','ack.sh','diagnostic_verifier.py','MANUAL_ACK_PL.md','BASE_FILELIST','BASE_SHA256SUMS','CANDIDATE_SHA256SUMS','SHA256SUMS','mcp-1.18.0-ems.2-prepare.zip','mcp-1.18.0-ems.1-code-recovery.zip'}

def stage(expected):
 if not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('EXPECTED_SHA_REQUIRED')
 if PACKAGE.is_symlink() or PACKAGE.stat().st_size>20_000_000:raise ValueError('PACKAGE_REFUSED')
 data=PACKAGE.read_bytes()
 if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('PACKAGE_SHA_MISMATCH')
 if STAGE.is_symlink():raise ValueError("STAGE_SYMLINK_REFUSED")
 if STAGE.exists():
  # Reopening is read-only, not replay: require exact byte identity of every file.
  with zipfile.ZipFile(__import__('io').BytesIO(data)) as z:
   members={Path(i.filename).name:i for i in z.infolist()}
   actual={p.name for p in STAGE.iterdir()}
   if set(members)!=ALLOWED or actual!=ALLOWED:raise ValueError('EXISTING_STAGE_CHANGED')
   for name,i in members.items():
    target=STAGE/name
    if target.is_symlink() or not target.is_file() or target.read_bytes()!=z.read(i):raise ValueError('EXISTING_STAGE_CHANGED')
  sys.path.insert(0,str(STAGE))
  return
 STAGE.mkdir(mode=0o700)
 try:
  import io,stat
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   names=set()
   for i in z.infolist():
    p=Path(i.filename)
    if len(p.parts)!=2 or p.name not in ALLOWED or p.name in names or i.file_size>10_000_000 or stat.S_ISLNK(i.external_attr>>16):raise ValueError('ARCHIVE_REFUSED')
    names.add(p.name)
   if names!=ALLOWED or sum(i.file_size for i in z.infolist())>25_000_000:raise ValueError('ARCHIVE_INVENTORY_REFUSED')
   for i in z.infolist():(STAGE/Path(i.filename).name).write_bytes(z.read(i))
 except Exception:
  shutil.rmtree(STAGE);raise
 sys.path.insert(0,str(STAGE))
 from deployment_core import verify
 verify(STAGE,STAGE/'SHA256SUMS',exact=False)

class Controller:
 def __init__(self):self.worker=None
 def handle(self,r):
  if not isinstance(r,dict) or not isinstance(r.get('action'),str):raise ValueError()
  a=r['action']
  if a=='inspect' and set(r)=={'action'}:return deployment_diagnostics()
  if a in ('preflight','deploy'):
   if set(r)!=({'action','confirmation'} if a=='deploy' else {'action'}):raise ValueError()
   if self.worker and self.worker.poll() is None:raise ValueError('BUSY')
   if a=='deploy' and r['confirmation']!='CONFIRM_CORE_RESTART':raise ValueError()
   args=['python3',str(STAGE/'manual_ack_watchdog.py'),a]
   if a=='deploy':args+=['CONFIRM_CORE_RESTART']
   # No shell, no auto replay; stdin belongs to the supervisor control loop.
   self.worker=subprocess.Popen(args,stdin=subprocess.DEVNULL)
   return {'status':'STARTED_NOT_CONFIRMED'}
  if a=='status' and set(r)=={'action'}:
   import manual_ack_watchdog as w
   try:return w.status(w.BACK)
   except FileNotFoundError:return {'phase':'IDLE_NO_DEPLOYMENT_RECORD'}
  if a=='ack' and set(r)=={'action','operation','challenge','checks'}:
   import manual_ack_watchdog as w
   w.write_ack(STAGE,w.BACK,w.SOURCE,r['operation'],r['challenge'],r['checks'])
   return {'status':'ACK_RECORDED_NOT_YET_ACCEPTED'}
  raise ValueError('UNSUPPORTED_ACTION')

def deployment_diagnostics():
 # Read-only inspection of fixed deployment paths; no Core operation or retry.
 import manual_ack_watchdog as w
 from deployment_core import verify
 report={}
 try:verify(w.SOURCE,STAGE/'BASE_SHA256SUMS');report['production_code']='ORIGINAL_VERIFIED'
 except Exception:
  try:verify(w.SOURCE,STAGE/'CANDIDATE_SHA256SUMS');report['production_code']='CANDIDATE_VERIFIED'
  except Exception:report['production_code']='UNVERIFIED'
 try:verify(w.BACK/'component',STAGE/'BASE_SHA256SUMS');report['recovery_code']='VERIFIED'
 except Exception:report['recovery_code']='UNVERIFIED'
 old=Path('/config/mcp-ems2/mcp-package/install.sh')
 report['legacy_installer_guard']='ABSENT'
 if old.exists() or old.is_symlink():
  try:
   import stat
   fd=os.open(old,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
   with os.fdopen(fd) as f:
    st=os.fstat(f.fileno())
    if not stat.S_ISREG(st.st_mode) or st.st_size>1000000:raise ValueError()
    report['legacy_installer_guard']='OLD_STANDALONE_INSTALLER_MUST_BE_WITHDRAWN' if 'ha core stop' in f.read() else 'NO_DIRECT_CORE_STOP_FOUND'
  except Exception:report['legacy_installer_guard']='UNREADABLE_DO_NOT_DEPLOY'
 try:
  report['deployment']=w.status(w.BACK)
 except FileNotFoundError:report['deployment']={'phase':'NO_DEPLOYMENT_RECORD'}
 except Exception:report['deployment']={'phase':'UNKNOWN_DO_NOT_DEPLOY'}
 try:
  report['deployment_lease_held']=w.watchdog_lease_held(w.BACK)
 except FileNotFoundError:report['deployment_lease_held']=False
 except Exception:report['deployment_lease_held']=None
 report['safe_to_update_installer']=(report['production_code']=='ORIGINAL_VERIFIED' and report['deployment']['phase']=='NO_DEPLOYMENT_RECORD' and report['deployment_lease_held'] is False)
 report['deployment_permitted']=False # diagnostics never authorizes APPLY
 return report

def snapshot(controller):
 try:state=controller.handle({'action':'status'})
 except Exception:state={'phase':'STATUS_UNAVAILABLE_DO_NOT_DEPLOY'}
 try:state['diagnostics']=deployment_diagnostics()
 except Exception:state['diagnostics']={'status':'UNAVAILABLE_DO_NOT_DEPLOY'}
 state['worker_running']=bool(controller.worker and controller.worker.poll() is None)
 state['worker_exit_code']=None if controller.worker is None else controller.worker.poll()
 return state

def publish(controller):
 # Fixed path JSON (valid YAML); no token, HTTP body or exception details.
 import tempfile
 value=snapshot(controller)
 fd,name=tempfile.mkstemp(prefix='.mcp-installer-status-',dir=REPORT.parent)
 try:
  with os.fdopen(fd,'w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
  os.replace(name,REPORT)
 finally:
  if os.path.exists(name):os.unlink(name)
 return value

def monitor(controller):
 previous=None
 while True:
  try:
   value=publish(controller)
   if value!=previous:print('INSTALLER_STATUS '+json.dumps(value),flush=True);previous=value
  except Exception:print('STATUS_REPORT_UNAVAILABLE',flush=True)
  threading.Event().wait(2)

def decode_requests(buffer,chunk):
 buffer+=chunk.decode('utf-8')
 if len(buffer)>8192:raise ValueError('INPUT_TOO_LARGE')
 result=[];decoder=json.JSONDecoder()
 while buffer.strip():
  buffer=buffer.lstrip()
  try:value,end=decoder.raw_decode(buffer)
  except json.JSONDecodeError:break
  result.append(value);buffer=buffer[end:]
 return result,buffer

def main():
 try:
  options=json.loads(Path('/data/options.json').read_text());stage(options['package_sha256'])
 except Exception:
  print('BLOCKED_PACKAGE_OR_OPTIONS');return 1
 c=Controller();buffer=""
 print("READY_PACKAGE_VERIFIED_WAITING_FOR_REQUEST_NO_APPLY",flush=True)
 print("READ_ONLY_DEPLOYMENT_DIAGNOSTICS "+json.dumps(deployment_diagnostics()),flush=True)
 threading.Thread(target=monitor,args=(c,),daemon=True).start()
 # EOF never stops the watchdog's container: Supervisor/Core can disconnect.
 while True:
  line=os.read(sys.stdin.fileno(),8192)
  if not line:
   threading.Event().wait(1);continue
  try:
   requests,buffer=decode_requests(buffer,line)
   for request in requests:
    try:print(json.dumps(c.handle(request)))
    except Exception:print('REQUEST_BLOCKED_NO_SECRET_DETAILS')
  except Exception:
   buffer='';print('REQUEST_BLOCKED_NO_SECRET_DETAILS')
if __name__=='__main__':sys.exit(main())
