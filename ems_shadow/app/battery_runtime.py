"""Battery readiness and guarded execution worker. READ_ONLY is the default.
Planning approval is distinct from device safety authority.
"""
import argparse,json,os,re,signal,sys,threading
from pathlib import Path
from soc_profile import planning_policy,load_profile
from datetime import datetime,timezone,timedelta
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
    def call(self,method,path,payload=None):
        if (method,path) not in (("GET","/states"),("POST","/template")):raise ValueError("read_only")
        req=Request("http://supervisor/core/api"+path,data=None if payload is None else json.dumps(payload).encode(),headers={"Authorization":"Bearer "+self.token,"Content-Type":"application/json"},method=method)
        try:
            with urlopen(req,timeout=5) as r:return json.load(r)
        except Exception:raise RuntimeError("ha_read_failed") from None
from battery_executor import Policy
from battery_service import BatteryService,read_config
from ownership import Ownership

MEMORY_TEMPLATE = """{% set ns=namespace(rows=[]) %}{% for id in ids %}{% set s=states[id] %}{% if s is not none %}{% set ns.rows=ns.rows+[{'entity_id':id,'state':s.state,'last_reported':s.last_reported.isoformat(),'last_updated':s.last_updated.isoformat(),'last_changed':s.last_changed.isoformat()}] %}{% endif %}{% endfor %}{{ns.rows|to_json}}"""
def in_memory_times(api,sources):
    ids=sorted(set(v for v in sources.values() if isinstance(v,str) and re.fullmatch(r'(sensor|binary_sensor|number|select)\.[a-z0-9_]+',v)))
    rows=api.call('POST','/template',{'template':MEMORY_TEMPLATE,'variables':{'ids':ids}})
    if isinstance(rows,str):rows=json.loads(rows)
    return states_by_id(rows)

BMS_TEMPLATE = """{% set ns=namespace(rows=[]) %}{% set device=device_id(soc_entity) %}{% for id in device_entities(device) if device %}{% set s=states[id] %}{% if s is not none %}{% set ns.rows=ns.rows+[{'entity_id':id,'state':s.state,'attributes':{'unit_of_measurement':s.attributes.get('unit_of_measurement')},'last_reported':s.last_reported.isoformat(),'last_updated':s.last_updated.isoformat(),'last_changed':s.last_changed.isoformat()}] %}{% endif %}{% endfor %}{{ {'device_found':device is not none,'rows':ns.rows}|to_json }}"""
def bms_snapshot(api,soc_entity,now):
    if not isinstance(soc_entity,str) or not re.fullmatch(r'sensor\.[a-z0-9_]+',soc_entity):raise ValueError('bms_binding')
    data=api.call('POST','/template',{'template':BMS_TEMPLATE,'variables':{'soc_entity':soc_entity}})
    if isinstance(data,str):data=json.loads(data)
    if not isinstance(data,dict) or data.get('device_found') is not True:raise ValueError('bms_device')
    rows=states_by_id(data['rows'])
    if soc_entity not in rows:raise ValueError('bms_source_not_device_member')
    roles={};limits={}
    suffixes={'status':'_status','max_charge':'_max_charge_power','peak_charge':'_peak_charge_power','max_discharge':'_max_discharge_power','peak_discharge':'_peak_discharge_power'}
    for role,suffix in suffixes.items():
        found=[r for id,r in rows.items() if id.endswith(suffix)]
        if len(found)!=1:raise ValueError('bms_role_ambiguous')
        raw=found[0];age=(now-datetime.fromisoformat(raw['last_reported'])).total_seconds()
        roles[role]={'entity_id':raw['entity_id'],'state':raw['state'],'ha_last_reported':raw['last_reported'],'ha_last_updated':raw.get('last_updated'),'age_seconds':age}
        if not 0<=age<=180:raise ValueError('bms_age')
        if role!='status':
            import math
            value=float(raw['state'])
            if raw.get('attributes',{}).get('unit_of_measurement')!='W' or not math.isfinite(value) or value<0:raise ValueError('bms_limit')
            limits[role]=value
    return {'quality':'HA_DEVICE_BOUND_SNAPSHOT','sources':roles,'charge_conservative_ceiling_w':min(Policy().max_charge_w,limits['max_charge'],limits['peak_charge']),'discharge_conservative_ceiling_w':min(Policy().max_discharge_w,limits['max_discharge'],limits['peak_discharge']),'peak_limit_semantics':'exposed upper bound only; dynamic BMS permission unconfirmed','device_measurement_time_confirmed':False,'commands_authorized':False}

def shared_owner(states):
    found=[s for s in states.values() if s.get('entity_id','').startswith('input_select.') and s.get('attributes',{}).get('friendly_name')=='EMS Battery Control Owner' and s.get('attributes',{}).get('options')==['UNKNOWN','LEGACY','EMS2']]
    if len(found)!=1:return {'entity_id':None,'state':'UNKNOWN','reason':'missing_or_ambiguous_shared_owner'}
    state=found[0].get('state')
    return {'entity_id':found[0]['entity_id'],'state':state if state in ('UNKNOWN','LEGACY','EMS2') else 'UNKNOWN','source':'HA_REST_CURRENT_STATE_NOT_TELEMETRY_CLOCK'}

def control_interface(states):
    # Diagnostic discovery only; never supplies an actuator configuration.
    required={'Remote Control','Maximize Self Consumption','Time of Use'}
    found=[s for s in states.values() if s.get('entity_id','').startswith('select.') and required.issubset(set(s.get('attributes',{}).get('options',[])))]
    if len(found)!=1:return {'state':'UNKNOWN','reason':'missing_or_ambiguous_control_interface','actuator_authority':False}
    raw=found[0]
    return {'entity_id':raw['entity_id'],'state':raw.get('state','UNKNOWN'),'ha_last_updated':raw.get('last_updated'),'actuator_authority':False,'meaning':'diagnostic discovery only; no automatic mode change'}


def evaluate(states,sources,now,memory=None,profile=None):
    result={};issues=[]
    planning=planning_policy(profile)
    interface=control_interface(states)
    for role in ('b1_soc','b1_power','b1_status','ac_power','m1_import','m1_export'):
        entity=sources.get(role);raw=states.get(entity,{})
        value=raw.get('state');age=None;quality='MISSING'
        try:
            t=datetime.fromisoformat(raw['last_reported'])
            age=(now-t).total_seconds()
            quality='HA_UPDATE_FRESH' if 0<=age<=180 else 'HA_UPDATE_STALE_OR_FUTURE'
            if value in (None,'unknown','unavailable'):quality='UNAVAILABLE'
        except (KeyError,TypeError,ValueError):quality='INVALID_HA_TIMESTAMP'
        mem=(memory or {}).get(entity,{})
        mem_age=None;memory_quality='UNCONFIRMED'
        try:
            mem_age=(now-datetime.fromisoformat(mem['last_reported'])).total_seconds()
            memory_quality='HA_WRITE_RECENT_DEVICE_TIME_UNCONFIRMED' if 0<=mem_age<=180 else 'HA_WRITE_OLD_OR_FUTURE'
            if mem.get('state')!=value:memory_quality='STATE_CHANGED_BETWEEN_REQUESTS'
        except (KeyError,TypeError,ValueError):pass
        result[role]={'entity_id':entity,'state':value,'ha_last_reported':raw.get('last_reported'),'ha_last_updated':raw.get('last_updated'),'ha_last_changed':raw.get('last_changed'),'age_seconds':age,'quality':quality,'memory_last_reported':mem.get('last_reported'),'memory_last_updated':mem.get('last_updated'),'memory_last_changed':mem.get('last_changed'),'memory_age_seconds':mem_age,'memory_quality':memory_quality,'device_time_confirmed':False}
        if quality!='HA_UPDATE_FRESH' and not (quality=='HA_UPDATE_STALE_OR_FUTURE' and memory_quality=='HA_WRITE_RECENT_DEVICE_TIME_UNCONFIRMED'):issues.append(role+':'+quality)
    return {'recorded_at':now.isoformat(),'valid_until':(now+timedelta(seconds=60)).isoformat(),'status_semantics':'snapshot; after valid_until process state is UNKNOWN','component':'battery_executor_readiness',
      'state':'BLOCKED','mode':'READ_ONLY','commands_enabled':False,'commands_sent':0,
      'policy':{'rated_wh':Policy().rated_wh,'max_charge_w':Policy().max_charge_w,'max_discharge_w':Policy().max_discharge_w,'soc_min':None,'soc_max':None,'soc_bounds_approved':False},
      'blockers':[*(['SOC_PLANNING_OWNER_APPROVAL_MISSING'] if not planning['owner_approved'] else []),'BMS_OPERATING_ENVELOPE_UNCONFIRMED','EXTERNAL_OWNERSHIP_FENCE_UNVERIFIED','PHYSICAL_FALLBACK_UNVERIFIED','NO_BATTERY_EXPORT_UNVERIFIED']+([] if interface['state']=='Remote Control' else ['REMOTE_CONTROL_NOT_CONFIRMED']),
      'planning_policy':planning,'control_interface':interface,'input_issues':issues,'inputs':result,'device_measurement_time_confirmed':False,'shared_owner':shared_owner(states)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--options',default='/data/options.json');p.add_argument('--root',default='/data/observation-v1');p.add_argument('--report',default='/ha_config/ems_shadow/battery_executor_report.yaml');p.add_argument('--cycles',type=int);p.add_argument('--interval',type=float,default=20);a=p.parse_args()
    options=json.loads(Path(a.options).read_text()).get('observation',{})
    if options.get('enabled') is not True:return 78
    sources=options.get('solar_sources',{});api=ReadAPI(os.environ['SUPERVISOR_TOKEN'])
    stop=threading.Event();seq=0;root=Path(a.root);root.mkdir(parents=True,exist_ok=True)
    ownership=Ownership(root/'battery-ownership.sqlite',sources)
    service=None
    try:service=BatteryService(root,ownership,os.environ['SUPERVISOR_TOKEN'])
    except Exception:pass
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stop.set())
    while not stop.is_set():
        try:
            states=states_by_id(api.call('GET','/states'))
            try:memory=in_memory_times(api,sources);template_status='AVAILABLE'
            except Exception:memory={};template_status='UNAVAILABLE'
            profile=load_profile()
            report=evaluate(states,sources,datetime.now(timezone.utc),memory,profile)
            report['template_status']=template_status
            try:report['bms']=bms_snapshot(api,sources.get('b1_soc'),datetime.now(timezone.utc))
            except Exception:report['bms']={'quality':'UNCONFIRMED','commands_authorized':False}
            if report['bms']['quality']=='UNCONFIRMED':report['blockers'].append('BMS_LIMITS_UNCONFIRMED')
            else:
                if report['bms']['charge_conservative_ceiling_w']==0:report['blockers'].append('BMS_CHARGE_CEILING_ZERO')
                if report['bms']['sources']['status']['state'] not in {'B_STATUS_STANDBY','B_STATUS_IDLE','B_STATUS_CHARGE','B_STATUS_DISCHARGE'}:report['blockers'].append('BMS_STATUS_NOT_APPROVED_FOR_ACTUATION')
            try:
                report['execution_service']=service.cycle(read_config(),profile) if service else {'executor_initialized':False,'effective_state':'INITIALIZATION_ERROR','actuation_policy_enabled':False}
            except Exception:report['execution_service']={'executor_initialized':False,'effective_state':'EXECUTION_ERROR','actuation_policy_enabled':False,'delivery_uncertain':True}
            execution=report['execution_service']
            report['mode']=execution.get('requested_mode','READ_ONLY')
            report['commands_enabled']=execution.get('actuation_policy_enabled',False)
            counts=execution.get('command_status_counts',{})
            report['commands_sent']=None if execution.get('delivery_uncertain') else counts.get('ACK',0)
            if report['mode']=='ACTIVE':
                report['state']=execution.get('effective_state','UNKNOWN')
                report['blockers']=execution.get('safety_reasons',[])
                if execution.get('actuation_policy_enabled') is not True:report['blockers']=report['blockers']+[report['state']]
            report['ownership']=ownership.state()
            report['owner_states_consistent']=report['shared_owner']['state']==report['ownership']['owner']
            if not report['owner_states_consistent']:report['blockers'].append('OWNERSHIP_MISMATCH_NO_AUTOMATIC_RECONCILIATION')
        except Exception:
            report={'recorded_at':datetime.now(timezone.utc).isoformat(),'component':'battery_executor_readiness','state':'UNKNOWN','mode':'UNKNOWN','commands_enabled':False,'commands_sent':None,'reason':'read_failed'}
        seq+=1
        report['completed_cycles']=seq
        report.setdefault('valid_until',(datetime.now(timezone.utc)+timedelta(seconds=60)).isoformat())
        report.setdefault('status_semantics','snapshot; after valid_until process state is UNKNOWN')
        try:atomic(a.report,report)
        except OSError:print('battery_readiness_report_write_failed',flush=True)
        atomic(root/'battery-heartbeat.json',{'pid':os.getpid(),'sequence':seq,'phase':'completed','completed_cycles':seq,'committed_cycles':0,'status':report['state'],'captured_at':datetime.now(timezone.utc).isoformat()})
        if a.cycles and seq>=a.cycles:break
        stop.wait(a.interval)
    if service:
        try:service.close()
        except Exception:pass
    ownership.close()
    return 0
if __name__=='__main__':raise SystemExit(main())
