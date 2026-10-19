"""Supervisor stdin control, no network listener, shell, OAuth token or device API.
Package is immutable during a worker operation. Never automatically resumes.
"""
import hashlib,json,os,re,shutil,subprocess,sys,threading,zipfile
from pathlib import Path
PACKAGE=Path('/config/mcp-installer-package.zip')
STAGE=Path('/data/package')
ALLOWED={'install.sh','manual-ack-launch.sh','manual_ack_watchdog.py','deployment_core.py','ack.sh','diagnostic_verifier.py','MANUAL_ACK_PL.md','BASE_FILELIST','BASE_SHA256SUMS','CANDIDATE_SHA256SUMS','SHA256SUMS','mcp-1.18.0-ems.2-prepare.zip','mcp-1.18.0-ems.1-code-recovery.zip'}

def stage(expected):
 if not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('EXPECTED_SHA_REQUIRED')
 if PACKAGE.is_symlink() or PACKAGE.stat().st_size>20_000_000:raise ValueError('PACKAGE_REFUSED')
 data=PACKAGE.read_bytes()
 if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('PACKAGE_SHA_MISMATCH')
 if STAGE.exists():raise ValueError('EXISTING_STAGE_NO_REPLAY')
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
   return w.status(w.BACK)
  if a=='ack' and set(r)=={'action','operation','challenge','checks'}:
   import manual_ack_watchdog as w
   w.write_ack(STAGE,w.BACK,w.SOURCE,r['operation'],r['challenge'],r['checks'])
   return {'status':'ACK_RECORDED_NOT_YET_ACCEPTED'}
  raise ValueError('UNSUPPORTED_ACTION')

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
