"""Separate diagnostic publisher. Aggregates only, no SQLite access or services."""
import json,sys,time,signal,threading,math,os,tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
def atomic(path,data):
 p=Path(path)
 if p.parent.is_symlink() or p.is_symlink():raise ValueError('report_symlink_refused')
 p.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.observation-',dir=p.parent)
 try:
  with os.fdopen(fd,'w') as f:json.dump(data,f,allow_nan=False);f.flush();os.fsync(f.fileno())
  os.replace(tmp,p)
 finally:
  try:os.unlink(tmp)
  except FileNotFoundError:pass
ALLOWED={'solar':{'observations','rejections','quarantined','power_integration_enabled','m1_deltas'},'boiler':{'observations','power_kwh','register_kwh','integrated_seconds'},'weather':{'observations','forecast_records'}}
def safe_metrics(role,raw):
 out={}
 for key in ALLOWED[role]:
  v=raw.get(key)
  if key=='m1_deltas' and isinstance(v,dict):out[key]={k:x for k,x in v.items() if k in ('m1_import','m1_export') and type(x) in (int,float) and math.isfinite(x)}
  elif type(v) in (int,float,bool) and math.isfinite(v):out[key]=v
 return out

def report(root,enabled,now=None):
 now=now or datetime.now(timezone.utc);roles={}
 for role in ALLOWED:
  entry={'state':'DISABLED' if not enabled else 'UNKNOWN','metrics':{},'last_cycle_at':None}
  if enabled:
   try:
    q=json.loads((root/(role+'-quality.json')).read_text());t=datetime.fromisoformat(q['recorded_at']);age=(now-t).total_seconds()
    limits=360 if role=='weather' else 65
    entry.update(last_cycle_at=t.isoformat(),age_seconds=age,metrics=safe_metrics(role,q.get('metrics',{})),completed_cycles=q['completed_cycles'])
    entry['state']='RUNNING' if 0<=age<=limits and q.get('status')=='COMPLETED' else 'DEGRADED' if 0<=age<=limits else 'UNKNOWN'
    s=json.loads((root/(role+'-supervision.json')).read_text())
    if now.timestamp()-s['recorded_at']>5 or s['state'] in ('UNKNOWN','DISABLED','STOPPED'):entry['state']=s['state'] if now.timestamp()-s['recorded_at']<=5 else 'UNKNOWN'
    resource=s.get('resource_status',{})
    if resource.get('state')=='VERIFIED':
     entry['resources']={k:resource[k] for k in ('rss_bytes','cpu_percent_one_core') if type(resource.get(k)) in (float,int) and math.isfinite(resource[k])}
   except (OSError,ValueError,TypeError,KeyError):entry['state']='UNKNOWN'
  roles[role]=entry
 return {'schema_version':1,'generated_at':now.isoformat(),'valid_until':(now+timedelta(seconds=6)).isoformat(),'status_semantics':'snapshot; after valid_until treat states as UNKNOWN','new_layer_enabled':enabled,'roles':roles,'control_enabled':False,'solar_power_integration_enabled':False,'billing_approved':False,'ha_timestamps_are_device_reports':False}

def main():
 enabled=len(sys.argv)==2 and sys.argv[1]=='true'
 stop=threading.Event()
 for s in (signal.SIGTERM,signal.SIGINT):signal.signal(s,lambda *_:stop.set())
 while not stop.is_set():
  try:
   atomic('/ha_config/ems_shadow/observation_report.yaml',report(Path('/data/observation-v1'),enabled))
  except Exception:print('observation_publication_failed',flush=True)
  stop.wait(2)
if __name__=='__main__':main()
