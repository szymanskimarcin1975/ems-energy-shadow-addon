"""Read-only readiness worker. No actuator transport is constructed or invoked.
SOC thresholds are deliberately unapproved and never default to 0/100.
"""
import argparse,json,os,signal,sys,threading
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen

def atomic(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(data,f,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)

def states_by_id(rows):
    if not isinstance(rows,list):raise ValueError("invalid_states")
    result={r["entity_id"]:r for r in rows}
    if len(result)!=len(rows):raise ValueError("duplicate_states")
    return result

class ReadAPI:
    def __init__(self,token):self.token=token
    def call(self,method,path):
        if (method,path)!=("GET","/states"):raise ValueError("read_only")
        req=Request("http://supervisor/core/api/states",headers={"Authorization":"Bearer "+self.token},method="GET")
        try:
            with urlopen(req,timeout=5) as r:return json.load(r)
        except Exception:raise RuntimeError("ha_read_failed") from None
from battery_executor import Policy

def evaluate(states,sources,now):
    result={};issues=[]
    for role in ('b1_soc','b1_power','b1_status','ac_power','m1_import','m1_export'):
        entity=sources.get(role);raw=states.get(entity,{})
        value=raw.get('state');age=None;quality='MISSING'
        try:
            t=datetime.fromisoformat(raw['last_reported'])
            age=(now-t).total_seconds()
            quality='HA_UPDATE_FRESH' if 0<=age<=180 else 'HA_UPDATE_STALE_OR_FUTURE'
            if value in (None,'unknown','unavailable'):quality='UNAVAILABLE'
        except (KeyError,TypeError,ValueError):quality='INVALID_HA_TIMESTAMP'
        result[role]={'entity_id':entity,'state':value,'ha_last_reported':raw.get('last_reported'),'age_seconds':age,'quality':quality}
        if quality!='HA_UPDATE_FRESH':issues.append(role+':'+quality)
    return {'recorded_at':now.isoformat(),'component':'battery_executor_readiness',
      'state':'BLOCKED','mode':'READ_ONLY','commands_enabled':False,'commands_sent':0,
      'policy':{'rated_wh':Policy().rated_wh,'max_charge_w':Policy().max_charge_w,'max_discharge_w':Policy().max_discharge_w,'soc_min':None,'soc_max':None,'soc_bounds_approved':False},
      'blockers':['SOC_BOUNDS_UNAPPROVED','EXTERNAL_OWNERSHIP_FENCE_UNVERIFIED','PHYSICAL_FALLBACK_UNVERIFIED','NO_BATTERY_EXPORT_UNVERIFIED'],
      'input_issues':issues,'inputs':result,'device_measurement_time_confirmed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--options',default='/data/options.json');p.add_argument('--root',default='/data/observation-v1');p.add_argument('--report',default='/ha_config/ems_shadow/battery_executor_report.yaml');p.add_argument('--cycles',type=int);p.add_argument('--interval',type=float,default=20);a=p.parse_args()
    options=json.loads(Path(a.options).read_text()).get('observation',{})
    if options.get('enabled') is not True:return 78
    sources=options.get('solar_sources',{});api=ReadAPI(os.environ['SUPERVISOR_TOKEN'])
    stop=threading.Event();seq=0;root=Path(a.root);root.mkdir(parents=True,exist_ok=True)
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stop.set())
    while not stop.is_set():
        try:
            states=states_by_id(api.call('GET','/states'))
            report=evaluate(states,sources,datetime.now(timezone.utc))
        except Exception:
            report={'recorded_at':datetime.now(timezone.utc).isoformat(),'component':'battery_executor_readiness','state':'UNKNOWN','mode':'READ_ONLY','commands_enabled':False,'commands_sent':0,'reason':'read_failed'}
        seq+=1
        try:atomic(a.report,report)
        except OSError:print('battery_readiness_report_write_failed',flush=True)
        atomic(root/'battery-heartbeat.json',{'pid':os.getpid(),'sequence':seq,'phase':'completed','completed_cycles':seq,'committed_cycles':0,'status':report['state'],'captured_at':datetime.now(timezone.utc).isoformat()})
        if a.cycles and seq>=a.cycles:break
        stop.wait(a.interval)
    return 0
if __name__=='__main__':raise SystemExit(main())
