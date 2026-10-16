"""Scheduled battery executor. READ_ONLY by default; no authority from a report.
Hardware fallback and no-export protection require separate, expiring evidence.
"""
import json,math,sqlite3,time
from pathlib import Path
from datetime import datetime,timezone
from battery_executor import Executor,Policy,SupervisorHA
from soc_profile import planning_policy
CONFIG_PATH=Path('/ha_config/ems_shadow/battery_executor_config.yaml')
PROOFS=('bms_operating_envelope','physical_fallback','physical_no_export','old_command_reconciled','external_writer_fence')

def read_config():
 try:
  if CONFIG_PATH.stat().st_size>65536:raise ValueError('configuration_too_large')
  result=json.loads(CONFIG_PATH.read_text())
  if not isinstance(result,dict):raise ValueError('configuration_object_required')
  return result
 except (OSError,ValueError):return {'mode':'READ_ONLY','configuration_quality':'MISSING_OR_INVALID'}

def proof_reasons(config,now):
 reasons=[];device=config.get('device',{})
 if not device.get('model') or not device.get('firmware'):reasons.append('DEVICE_IDENTITY_UNCONFIRMED')
 for name in PROOFS:
  try:
   p=config['verified_evidence'][name]
   start=datetime.fromisoformat(p['verified_at']);end=datetime.fromisoformat(p['valid_until'])
   if p.get('verified') is not True or p.get('device')!=device or not isinstance(p.get('reference'),str) or not p['reference'].strip() or not start<=now<end or not 0<(end-start).total_seconds()<=86400:raise ValueError('invalid_evidence')
  except (KeyError,TypeError,ValueError):reasons.append(name.upper()+'_UNVERIFIED')
 return reasons

class FencedOwnership:
 def __init__(self,local,ha,config,clock):self.local=local;self.ha=ha;self.config=config;self.clock=clock
 def state(self):
  r=self.local.state();ok=False
  try:
   c=self.config
   if proof_reasons(c,self.clock()):return dict(r,external_fence_verified=False,commands_permitted=False)
   ok=(r['owner']=='EMS2' and r['epoch']==c['expected_epoch'] and self.ha.state(c['owner_entity'])['state']=='EMS2' and self.ha.state(c['authorization_entity'])['state']=='on')
   for entity in c['old_writers']:
    raw=self.ha.state(entity)
    ok=ok and raw.get('state')=='off' and raw.get('attributes',{}).get('current')==0
  except Exception:ok=False
  return dict(r,external_fence_verified=ok,commands_permitted=ok)

class BatteryService:
 def __init__(self,root,local_ownership,token,ha=None,clock=None):
  self.root=Path(root);self.local=local_ownership;self.ha=ha if ha is not None else SupervisorHA(token)
  self.clock=clock or (lambda:datetime.now(timezone.utc));self.executor=None
  self.db=sqlite3.connect(self.root/'battery-execution.sqlite',timeout=1,isolation_level=None)
  try:
   self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
   self.db.execute('CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,mode TEXT NOT NULL,status TEXT NOT NULL)')
   self.db.execute('CREATE TABLE IF NOT EXISTS runtime(id INTEGER PRIMARY KEY CHECK(id=1),cycles INTEGER NOT NULL,last_result TEXT NOT NULL)')
   self.db.execute("INSERT OR IGNORE INTO runtime VALUES(1,0,'INITIALIZED')")
  except BaseException:self.db.close();raise
 def cycle(self,config,profile):
  if isinstance(self.ha,SupervisorHA):self.ha.deadline=time.monotonic()+10
  now=self.clock();mode=config.get('mode','READ_ONLY');planning=planning_policy(profile)
  reasons=proof_reasons(config,now)
  if mode not in ('READ_ONLY','ACTIVE'):reasons.append('INVALID_EXECUTION_MODE')
  if not planning['owner_approved']:reasons.append('SOC_PLANNING_UNAPPROVED')
  bounds=config.get('safety_soc_bounds',{});lo,hi=bounds.get('minimum'),bounds.get('maximum')
  safe=(type(lo) in (int,float) and type(hi) in (int,float) and math.isfinite(lo) and math.isfinite(hi) and 0<=lo<hi<=100)
  if not safe:reasons.append('BMS_OPERATING_SOC_BOUNDS_UNCONFIRMED')
  operational=(profile or {}).get('operational_parameters',{})
  expected={'rated_energy_wh':9200,'max_charge_w':5000,'max_discharge_w':5000,'storage_control_mode':'Remote Control','storage_default_mode':'Maximize Self Consumption','storage_command_timeout_s':3600}
  if any(operational.get(k)!=v for k,v in expected.items()):reasons.append('OPERATIONAL_BASELINE_UNCONFIRMED')
  old=config.get('old_writers',[]);sources=config.get('sources',{})
  if not old or any(not isinstance(e,str) or not e.startswith('automation.') for e in old):reasons.append('LEGACY_WRITERS_UNCONFIRMED')
  if type(config.get('expected_epoch')) is not int:reasons.append('OWNER_EPOCH_UNCONFIRMED')
  if mode=='ACTIVE' and not reasons:
   try:
    if self.ha.state(sources['device_model'])['state']!=config['device']['model'] or self.ha.state(sources['device_firmware'])['state']!=config['device']['firmware']:raise ValueError('device_mismatch')
    if float(self.ha.state(sources['timeout'])['state'])!=3600 or self.ha.state(sources['default_mode'])['state']!='Maximize Self Consumption':raise ValueError('remote_settings_mismatch')
   except Exception:reasons.append('LIVE_DEVICE_IDENTITY_UNCONFIRMED')
  enabled=(mode=='ACTIVE' and not reasons)
  policy=Policy(enabled=enabled,soc_min=max(lo,planning['soc_min']) if safe and planning['owner_approved'] else None,soc_max=min(hi,planning['soc_max']) if safe and planning['owner_approved'] else None,soc_bounds_approved=safe,rated_wh=9200,max_charge_w=5000,max_discharge_w=5000,handover_verified=not reasons,fallback_verified=not reasons,no_export_verified=not reasons)
  owner=FencedOwnership(self.local,self.ha,config,self.clock)
  self.executor=Executor(self.ha,policy,self.root/'battery-execution.sqlite',self.root/'battery-commands.lock',old_writers=old,soc_entity=sources.get('soc'),mode_entity=sources.get('command_mode'),power_entities=[sources.get('charge_limit'),sources.get('discharge_limit')],owner_entity=config.get('owner_entity'),ownership=owner,expected_epoch=config.get('expected_epoch'),clock=self.clock,control_entity=sources.get('control_mode'),bms_sources=config.get('bms_sources'))
  result='READ_ONLY' if mode=='READ_ONLY' else 'BLOCKED_SAFETY'
  intent=config.get('pending_request')
  # READ_ONLY does not consume requests, fetch actuator state, or call services.
  if enabled:
   preflight=self.executor.preflight()
   if preflight:result=preflight;enabled=False
   elif not isinstance(intent,dict):result='ACTIVE_IDLE_NO_REQUEST'
   else:
    try:result=self.executor.execute(intent['request_id'],intent['option'],datetime.fromisoformat(intent['expires_at']))
    except (ValueError,TypeError,KeyError):result='INVALID_REQUEST'
  self.db.execute('UPDATE runtime SET cycles=cycles+1,last_result=? WHERE id=1',(result,))
  cycles=self.db.execute('SELECT cycles FROM runtime WHERE id=1').fetchone()[0]
  command_statuses=dict(self.db.execute('SELECT status,COUNT(*) FROM commands GROUP BY status'))
  return {'command_status_counts':command_statuses,'commands_ha_acknowledged':command_statuses.get('ACK',0),'delivery_uncertain':any(command_statuses.get(k,0) for k in ('PENDING','UNKNOWN')),'module':'battery_service','executor_initialized':True,'transport':'HA_QUEUED_COMMAND_GATEWAY','requested_mode':mode,'effective_state':result,'safety_reasons':reasons,'operational_parameters':expected,'planning_soc':planning,'safety_soc_bounds':bounds,'cycles':cycles,'pending_request_present':isinstance(intent,dict),'actuation_policy_enabled':enabled,'device_execution_confirmed':False,'ack_semantics':'ACK means new HA command state readback, not physical completion','automatic_legacy_shutdown':False,'automatic_replay_after_unknown':False}
 def close(self):self.db.close()
