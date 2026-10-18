"""Scheduled battery executor. READ_ONLY by default; no authority from a report.
Hardware fallback and no-export protection require separate, expiring evidence.
"""
import hashlib,json,math,sqlite3,time
from pathlib import Path
from datetime import datetime,timezone
from battery_executor import Executor,Policy,SupervisorHA
from soc_profile import planning_policy
from telemetry_guard import snapshot
from fault_guard import FaultGuard,READY
from plan_bridge import read as read_plan,Journal
from dispatch_lifecycle import initialise as lifecycle_init,state as lifecycle_state,hold as lifecycle_hold
CONFIG_PATH=Path('/ha_config/ems_shadow/battery_executor_config.yaml')
PROOFS=('physical_fallback','physical_no_export','old_command_reconciled','external_writer_fence')

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
   self.db.execute("""CREATE TABLE IF NOT EXISTS shadow_gateway_requests(
    request_id TEXT PRIMARY KEY,payload_sha256 TEXT NOT NULL,state TEXT NOT NULL
    CHECK(state IN ('PENDING','REJECTED','UNKNOWN')),detail TEXT NOT NULL,updated_at TEXT NOT NULL)""")
   self.db.execute("INSERT OR IGNORE INTO runtime VALUES(1,0,'INITIALIZED')")
   self.fault_guard=FaultGuard(self.db)
   self.planner_journal=Journal(self.db)
   lifecycle_init(self.db)
  except BaseException:self.db.close();raise
 def cycle(self,config,profile):
  if isinstance(self.ha,SupervisorHA):self.ha.deadline=time.monotonic()+10
  now=self.clock();mode=config.get('mode','READ_ONLY');planning=planning_policy(profile)
  telemetry_sources=config.get('telemetry_sources',{})
  telemetry_quality=snapshot(self.ha,telemetry_sources,self.clock())
  fault_sources=config.get('fault_sources',{})
  fault_quality=self.fault_guard.observe(self.ha,fault_sources,self.clock())
  bridge_config=config.get('planner_bridge',{})
  bridge=read_plan(bridge_config,now,config.get('expected_epoch')) if bridge_config.get('enabled') is True else {'status':'PLAN_BRIDGE_DISABLED','pending_request':None,'advisory_only':True}
  reasons=proof_reasons(config,now)
  if bridge_config.get('enabled') is True:
   if bridge.get('advisory_only') is True:reasons.append('PLAN_NOT_APPROVED_FOR_CONTROL')
   if bridge.get('status') not in ('PLAN_REQUEST_PREPARED','PLAN_HOLD_NO_NEW_COMMAND'):reasons.append(bridge['status'])
  if fault_quality!=READY:reasons.append(fault_quality)
  if telemetry_quality!='HA_TRANSPORT_CHECK_PASSED_NOT_DEVICE_PROOF':reasons.append(telemetry_quality)
  if mode not in ('READ_ONLY','ACTIVE'):reasons.append('INVALID_EXECUTION_MODE')
  if not planning['owner_approved']:reasons.append('SOC_PLANNING_UNAPPROVED')
  # The owner-approved EMS envelope is an economic command boundary, not an
  # internal BMS limit. Device protections remain authoritative and live BMS
  # status/directional power limits are checked immediately before dispatch.
  operating_min,operating_max=planning.get('soc_min'),planning.get('soc_max')
  range_approved=(planning.get('owner_approved') is True and
                  type(operating_min) in (int,float) and type(operating_max) in (int,float) and
                  math.isfinite(operating_min) and math.isfinite(operating_max) and
                  0<=operating_min<operating_max<=100)
  if not range_approved:reasons.append('EMS_OPERATING_SOC_RANGE_UNAPPROVED')
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
  policy=Policy(enabled=enabled,operating_soc_min=operating_min if range_approved else None,operating_soc_max=operating_max if range_approved else None,soc_operating_range_approved=range_approved,rated_wh=9200,max_charge_w=5000,max_discharge_w=5000,handover_verified=not reasons,fallback_verified=not reasons,no_export_verified=not reasons)
  owner=FencedOwnership(self.local,self.ha,config,self.clock)
  self.executor=Executor(self.ha,policy,self.root/'battery-execution.sqlite',self.root/'battery-commands.lock',old_writers=old,soc_entity=sources.get('soc'),mode_entity=sources.get('command_mode'),power_entities=[sources.get('charge_limit'),sources.get('discharge_limit')],owner_entity=config.get('owner_entity'),ownership=owner,expected_epoch=config.get('expected_epoch'),clock=self.clock,control_entity=sources.get('control_mode'),bms_sources=config.get('bms_sources'),telemetry_check=lambda:self.live_quality(telemetry_sources,fault_sources))
  result='READ_ONLY' if mode=='READ_ONLY' else 'BLOCKED_SAFETY'
  intent=bridge.get('pending_request') if bridge_config.get('enabled') is True else config.get('pending_request')
  if bridge_config.get('enabled') is True and config.get('pending_request') is not None:
   enabled=False;result='MANUAL_AND_PLANNER_REQUEST_CONFLICT'
  # READ_ONLY never enters the actuator transport. A pending plan may be sent
  # only to the gateway's explicitly non-actuating rejection endpoint below.
  # The one exception is the explicit non-actuating HA gateway fence: it
  # accepts a planner intent only to durably reject it, proving the SHADOW
  # vertical path without entering the device command transport.
  shadow_gateway={'status':'NOT_APPLICABLE','writes_started':False,'physical_dispatch_supported':False}
  if mode=='READ_ONLY' and bridge_config.get('enabled') is True and isinstance(intent,dict):
   shadow_gateway=self.shadow_gateway_probe(intent,config.get('expected_epoch'))
   result='SHADOW_GATEWAY_'+shadow_gateway['status']
  if enabled:
   preflight=self.executor.preflight()
   if preflight:result=preflight;enabled=False
   elif not isinstance(intent,dict):result='ACTIVE_IDLE_NO_REQUEST'
   else:
    try:result=self.executor.execute(intent['request_id'],intent['option'],datetime.fromisoformat(intent['expires_at']),maximum_power_w=intent.get('maximum_power_w'),plan_id=intent.get('plan_id'),intent_check=(lambda:self.plan_still_current(bridge_config,intent)) if bridge_config.get('enabled') is True else None)
    except (ValueError,TypeError,KeyError):result='INVALID_REQUEST'
  self.planner_journal.observe(bridge,result)
  self.db.execute('UPDATE runtime SET cycles=cycles+1,last_result=? WHERE id=1',(result,))
  cycles=self.db.execute('SELECT cycles FROM runtime WHERE id=1').fetchone()[0]
  command_statuses=dict(self.db.execute('SELECT status,COUNT(*) FROM commands GROUP BY status'))
  return {'command_lifecycle':lifecycle_state(self.db),'hold':lifecycle_hold(self.db,self.clock(),bridge['status']) if bridge.get('pending_request') is None else None,'planner_bridge':bridge,'shadow_gateway':shadow_gateway,'fault_quality':fault_quality,'fault_recovery':dict(self.fault_guard.record),'telemetry_quality':telemetry_quality,'telemetry_age_limit_seconds':180,'telemetry_skew_limit_seconds':5,'new_command_block_does_not_cancel_active_command':True,'command_status_counts':command_statuses,'commands_ha_acknowledged':command_statuses.get('ACK',0),'delivery_uncertain':any(command_statuses.get(k,0) for k in ('PENDING','UNKNOWN')),'module':'battery_service','executor_initialized':True,'transport':'HA_QUEUED_COMMAND_GATEWAY','requested_mode':mode,'effective_state':result,'safety_reasons':reasons,'operational_parameters':expected,'planning_soc':planning,'ems_operating_soc_range':{'minimum':operating_min if range_approved else None,'maximum':operating_max if range_approved else None,'owner_approved':range_approved,'scope':'EMS_COMMAND_ENVELOPE_ONLY'},'hardware_soc_bounds':{'numeric_bms_bounds_exposed':False,'bms_remains_authoritative':True,'ems_does_not_override_bms':True},'cycles':cycles,'pending_request_present':isinstance(intent,dict),'actuation_policy_enabled':enabled,'device_execution_confirmed':False,'ack_semantics':'ACK means new HA command state readback, not physical completion','automatic_legacy_shutdown':False,'automatic_replay_after_unknown':False,'dispatch_contract':'EMS2_COMPOUND_V28','alternate_select_transport_available':False}
 def shadow_gateway_probe(self,intent,epoch):
  """One-shot READ_ONLY request to the installed no-hardware HA fence."""
  try:
   identity={k:intent[k] for k in ('request_id','plan_id','option','maximum_power_w','expires_at')}
   if (not isinstance(identity['request_id'],str) or not isinstance(identity['plan_id'],str) or
       type(epoch) is not int):raise ValueError('invalid_shadow_intent')
   # Expiry is refreshed by the planner and is not the command identity. Bind
   # the dedup key to the stable plan/action/power/epoch; never replay a prior
   # pending or uncertain reservation even if its transport expiry changed.
   digest_basis={k:identity[k] for k in ('request_id','plan_id','option','maximum_power_w')}
   digest=hashlib.sha256(json.dumps({'intent':digest_basis,'owner_epoch':epoch},sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
   self.db.execute('BEGIN IMMEDIATE')
   prior=self.db.execute('SELECT payload_sha256,state,detail FROM shadow_gateway_requests WHERE request_id=?',(identity['request_id'],)).fetchone()
   if prior:
    self.db.execute('COMMIT')
    if prior[0]!=digest:return {'status':'REQUEST_ID_CONFLICT_NO_REPLAY','writes_started':False,'physical_dispatch_supported':False,'automatic_retry':False}
    return {'status':'DUPLICATE_'+prior[1]+'_NO_REPLAY','detail':prior[2],'writes_started':False if prior[1]=='REJECTED' else None,'physical_dispatch_supported':False if prior[1]=='REJECTED' else None,'automatic_retry':False}
   self.db.execute('INSERT INTO shadow_gateway_requests VALUES(?,?,\'PENDING\',\'reserved_before_gateway\',?)',(identity['request_id'],digest,self.clock().isoformat()))
   self.db.execute('COMMIT')
  except Exception:
   if self.db.in_transaction:self.db.execute('ROLLBACK')
   return {'status':'UNKNOWN_LOCAL_RESERVATION_FAILED_NO_RETRY','writes_started':None,'physical_dispatch_supported':None,'automatic_retry':False}
  transport=getattr(self.ha,'shadow_dispatch',None)
  if transport is None:
   # No correlated HA response means no trustworthy decision about the gateway.
   # Persist UNKNOWN so this request_id cannot be replayed after restart.
   outcome={'status':'UNKNOWN','reason':'SHADOW_GATEWAY_METHOD_UNAVAILABLE_NOT_SENT',
            'writes_started':None,'physical_dispatch_supported':None,'not_sent':True}
  else:
   try:outcome=transport(intent,epoch)
   except Exception:outcome={'status':'UNKNOWN','reason':'GATEWAY_CALL_FAILED','writes_started':None,'physical_dispatch_supported':None}
  identity_ok=(isinstance(outcome,dict) and outcome.get('request_id')==identity['request_id'] and
               outcome.get('plan_id')==identity['plan_id'] and
               type(outcome.get('owner_epoch')) is int and outcome.get('owner_epoch')==epoch)
  accepted=(identity_ok and outcome.get('status')=='REJECTED_NO_HARDWARE_WRITE' and
            outcome.get('writes_started') is False and outcome.get('physical_dispatch_supported') is False)
  state='REJECTED' if accepted else 'UNKNOWN'
  detail=(str(outcome.get('reason',''))[:160] if isinstance(outcome,dict)
          else 'invalid_gateway_result')
  try:
   self.db.execute('BEGIN IMMEDIATE')
   self.db.execute('UPDATE shadow_gateway_requests SET state=?,detail=?,updated_at=? WHERE request_id=? AND payload_sha256=? AND state=\'PENDING\'',(state,detail,self.clock().isoformat(),identity['request_id'],digest))
   self.db.execute('COMMIT')
  except Exception:
   if self.db.in_transaction:self.db.execute('ROLLBACK')
   return {'status':'UNKNOWN_LOCAL_RESULT_COMMIT_FAILED_NO_RETRY','writes_started':None,'physical_dispatch_supported':None,'automatic_retry':False}
  return {'status':state,'reason':detail,
          'writes_started':False if state=='REJECTED' else (outcome.get('writes_started') if isinstance(outcome,dict) else None),
          'physical_dispatch_supported':False if state=='REJECTED' else (outcome.get('physical_dispatch_supported') if isinstance(outcome,dict) else None),
          'request_id':identity['request_id'],'plan_id':identity['plan_id'],'owner_epoch':epoch,
          'automatic_retry':False}
 def plan_still_current(self,config,intent):
  current=read_plan(config,self.clock(),self.local.state().get('epoch'))
  request=current.get('pending_request')
  return current.get('advisory_only') is False and isinstance(request,dict) and request['plan_id']==intent['plan_id'] and request['request_id']==intent['request_id']
 def live_quality(self,telemetry_sources,fault_sources):
  quality=self.fault_guard.observe(self.ha,fault_sources,self.clock())
  if quality!=READY:return quality
  return snapshot(self.ha,telemetry_sources,self.clock())
 def close(self):self.db.close()

