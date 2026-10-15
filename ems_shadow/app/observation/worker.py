"""Read-only observation worker; only supervisor GET states and weather forecast read service."""
import argparse,json,os,signal,sys,threading,time,uuid,hashlib
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from adapter import Adapter,CHANNELS
INTERVALS={'solar':20,'boiler':20,'weather':300}

def atomic(path,data):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 tmp=p.with_suffix('.tmp')
 with tmp.open('w') as f:json.dump(data,f,allow_nan=False);f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
class ReadAPI:
 def __init__(self,token,base='http://supervisor/core/api'):
  self.token=token;self.base=base
 def call(self,method,path,payload=None):
  if not ((method=='GET' and path=='/states') or (method=='POST' and path=='/services/weather/get_forecasts?return_response')):raise ValueError('request_not_allowlisted')
  request=Request(self.base+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'},method=method)
  with urlopen(request,timeout=5) as r:return json.load(r)
def states_by_id(value):
 if not isinstance(value,list) or not all(isinstance(x,dict) and isinstance(x.get('entity_id'),str) for x in value):raise ValueError('invalid_states_response')
 if len({x['entity_id'] for x in value})!=len(value):raise ValueError('duplicate_entity_response')
 return {x['entity_id']:x for x in value}
def record(entity,unit,s):
 return {'entity_id':entity,'value':s.get('state'),'unit':s.get('attributes',{}).get('unit_of_measurement',unit),'last_reported':s.get('last_reported'),'last_updated':s.get('last_updated'),'last_changed':s.get('last_changed')}
class Processor:
 def __init__(self,role,path,config):
  self.role=role;self.config=config
  if role=='solar':self.store=Adapter(path,config)
  elif role=='weather':
   from weather.storage import WeatherStore
   self.store=WeatherStore(path,config)
  elif role=='boiler':
   if set(config)!= {'power','energy','workday'}:raise ValueError('invalid_boiler_config')
   sys.path.insert(0,str(Path(__file__).parent/'boiler_offline'))
   from storage import Ledger
   fingerprint=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
   self.store=Ledger(path,'boiler_observation_v1',fingerprint)
  else:raise ValueError('role_not_enabled')
 def process(self,id,captured,states):
  issues=[]
  if self.role=='solar':
   for ch,entity in self.config.items():
    try:issues.append([ch,self.store.ingest(ch,id,captured,record(entity,CHANNELS[ch],states.get(entity,{})))])
    except (ValueError,TypeError,KeyError):issues.append([ch,'invalid_api_record'])
  elif self.role=='weather':
   entity=self.config['local_entity'];self.store.observe(id,captured,record(entity,'°C',states.get(entity,{})))
  else:
   sample={'time':captured}
   for role,entity in self.config.items():
    raw=states.get(entity,{})
    if raw.get('entity_id')!=entity:raw={}
    key={'power':'boiler_w','energy':'boiler_kwh','workday':'workday'}[role]
    expected={'power':'W','energy':'kWh','workday':None}[role]
    sample[key]=raw.get('state') if raw.get('attributes',{}).get('unit_of_measurement')==expected else None
    sample[{'power':'boiler_time','energy':'boiler_kwh_time','workday':'workday_time'}[role]]=raw.get('last_reported')
   self.store.ingest(id,sample)
  return issues
 def forecasts(self,id,captured,response):
  entity=self.config['weather_entity'];rows=response.get('service_response',{}).get(entity,{}).get('forecast')
  if not isinstance(rows,list):raise ValueError('invalid_forecast_response')
  for row in rows:
   if not isinstance(row,dict):raise ValueError('invalid_forecast_record')
   self.store.forecast(id,captured,row['datetime'],row['temperature'])
 def metrics(self):
  if self.role=='solar':
   c=self.store.c
   return {'observations':c.execute('select count(*) from observations').fetchone()[0], 'rejections':c.execute("select count(*) from observations where quality not in ('valid_observation','baseline','valid_register_delta','repeated_ha_write')").fetchone()[0], 'm1_deltas':dict(c.execute('select channel,sum(kwh) from deltas group by channel')), 'quarantined':c.execute('select count(*) from quarantine').fetchone()[0], 'power_integration_enabled':False}
  if self.role=='weather':
   c=self.store.c
   return {'observations':c.execute('select count(*) from weather_observations').fetchone()[0],'forecast_records':c.execute('select count(*) from weather_forecasts').fetchone()[0]}
  c=self.store.db
  return {'observations':c.execute('select count(*) from split_v1_samples').fetchone()[0], 'power_kwh':c.execute("select coalesce(sum(kwh),0) from split_v1_intervals where category='boiler' and method='power_trapezoid'").fetchone()[0], 'register_kwh':c.execute("select coalesce(sum(kwh),0) from split_v1_intervals where category='boiler' and method='register_delta'").fetchone()[0], 'integrated_seconds':c.execute("select coalesce(sum(seconds),0) from split_v1_intervals where category='boiler' and method='power_trapezoid'").fetchone()[0]}
 def close(self):self.store.close()
def main():
 p=argparse.ArgumentParser();p.add_argument('--role',choices=['solar','weather','boiler'],required=True);p.add_argument('--options',default='/data/options.json');p.add_argument('--root',default='/data/observation-v1');p.add_argument('--stop-after-cycles',type=int);a=p.parse_args()
 options=json.loads(Path(a.options).read_text())['observation']
 if options.get('enabled') is not True:raise SystemExit(78)
 config=options[{'solar':'solar_sources','weather':'weather','boiler':'boiler_sources'}[a.role]]
 root=Path(a.root);root.mkdir(parents=True,exist_ok=True)
 if root.is_symlink():raise ValueError('symlink_refused')
 processor=Processor(a.role,root/(a.role+'.sqlite'),config);api=ReadAPI(os.environ['SUPERVISOR_TOKEN']);stop=threading.Event();seq=commits=0;session=uuid.uuid4().hex;next_forecast=0
 for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stop.set())
 try:
  while not stop.is_set():
   phase={'pid':os.getpid(),'sequence':seq,'phase':'polling'};atomic(root/(a.role+'-heartbeat.json'),phase)
   captured=datetime.now(timezone.utc).isoformat();id=session+':'+str(seq)
   try:
    states=states_by_id(api.call('GET','/states'));captured=datetime.now(timezone.utc).isoformat()
    atomic(root/(a.role+'-heartbeat.json'),dict(phase,phase='writing'))
    quality=processor.process(id,captured,states);commits+=1 # completed processing, individual rows committed before return
    if a.role=='weather' and time.monotonic()>=next_forecast:
     response=api.call('POST','/services/weather/get_forecasts?return_response',{'entity_id':config['weather_entity'],'type':'hourly'})
     processor.forecasts(id,captured,response);next_forecast=time.monotonic()+3600
    status='COMPLETED'
   except (OSError,ValueError,KeyError,TypeError):status='API_OR_DATA_ERROR'
   # SQLite storage exceptions terminate this worker, never the legacy observer.
   try:
    atomic(root/(a.role+'-quality.json'),{'role':a.role,'recorded_at':datetime.now(timezone.utc).isoformat(),'completed_cycles':seq+1,'completed_processing_cycles':commits,'status':status,'metrics':processor.metrics()})
   except OSError:pass # diagnostics failure must not roll back completed observations
   # The loop announces planned waiting only after processing and diagnostics end.
   seq+=1;atomic(root/(a.role+'-heartbeat.json'),{'pid':os.getpid(),'sequence':seq,'phase':'completed','completed_cycles':seq,'committed_cycles':commits,'status':status,'captured_at':datetime.now(timezone.utc).isoformat()})
   if a.stop_after_cycles and seq>=a.stop_after_cycles:break
   stop.wait(INTERVALS[a.role])
 finally:processor.close()
if __name__=='__main__':main()
