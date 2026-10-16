"""Read a bounded atomic planner report; prepare intents, never confer authority."""
import hashlib,json,math,re
from pathlib import Path
from datetime import datetime,timedelta,timezone
PLAN_PATH=Path('/ha_config/ems_shadow/planning_report.yaml')
def stamp(v):
 t=datetime.fromisoformat(v)
 if t.tzinfo is None:raise ValueError('PLAN_TIME_INVALID')
 return t.astimezone(timezone.utc)
def finite(v):return type(v) in (int,float) and math.isfinite(v)
def build(report,config,now,epoch):
 try:
  issued=stamp(report['generated_at']);valid=stamp(report['valid_until'])
  if not 0<=(now-issued).total_seconds()<=360 or not now<valid<=issued+timedelta(seconds=360):raise ValueError('PLAN_EXPIRED_OR_FUTURE')
  if report.get('status')!='ADVISORY_HOUSEHOLD_SCHEDULE_READY' or report.get('current_plan_usable_for_simulation') is not True or report.get('input_safety',{}).get('current_ha_set_valid') is not True:raise ValueError('PLAN_INPUT_QUALITY_UNCONFIRMED')
  expected=config.get('expected_fingerprint')
  if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected) or report.get('planning_config_fingerprint')!=expected:raise ValueError('PLAN_FINGERPRINT_UNCONFIRMED')
  future=config.get('future_day_type');pv=config.get('pv_scenario')
  if future not in ('workday','nonworkday') or pv not in ('pv_estimate','pv_estimate10'):raise ValueError('PLAN_SCENARIO_UNCONFIRMED')
  choices=[d for d in report['household_advisory']['decisions'] if d['future_day_type']==future and d['pv_scenario']==pv]
  if len(choices)!=1:raise ValueError('PLAN_SCENARIO_AMBIGUOUS')
  slots=choices[0]['schedule'];active=[];previous=None
  for row in slots:
   start=stamp(row['valid_for']);hours=row.get('hours',1)
   if not finite(hours) or not 0<hours<=1:raise ValueError('PLAN_SLOT_DURATION_INVALID')
   end=stamp(row['valid_to']) if 'valid_to' in row else start+timedelta(hours=hours)
   if abs((end-start).total_seconds()-hours*3600)>.01:raise ValueError('PLAN_SLOT_DURATION_INVALID')
   if previous is not None and start!=previous:raise ValueError('PLAN_SLOT_GAP_OR_OVERLAP')
   previous=end
   if start<=now<end:active.append((row,start,end,hours))
  if len(active)!=1:raise ValueError('NO_CURRENT_PLAN_SLOT')
  row,start,end,hours=active[0]
  vals=[row.get(k) for k in ('charge_ac_kwh','discharge_ac_kwh','load_kwh','pv_kwh')]
  if any(not finite(v) or v<0 for v in vals):raise ValueError('PLAN_ENERGY_INVALID')
  charge,discharge,load,pv_kwh=vals
  if charge>1e-9 and discharge>1e-9:raise ValueError('PLAN_SIMULTANEOUS_DIRECTIONS')
  if discharge>max(load-pv_kwh,0)+1e-8:raise ValueError('PLAN_BATTERY_EXPORT_FORBIDDEN')
  if charge<=1e-9 and discharge<=1e-9:return {'status':'PLAN_HOLD_NO_NEW_COMMAND','pending_request':None,'advisory_only':True}
  # Do not misrepresent grid charging as solar-only charging.
  option=('Charge from Solar Power' if charge<=max(pv_kwh-load,0)+1e-8 else 'Charge from Solar Power and Grid') if charge>1e-9 else 'Discharge to Minimize Import'
  watts=math.floor(max(charge,discharge)/hours*1000+1e-7)
  if not 0<watts<=5000:raise ValueError('PLAN_POWER_INVALID')
  if type(epoch) is not int:raise ValueError('PLAN_OWNER_EPOCH_UNCONFIRMED')
  # A rolling partial-hour revision has a stable UTC-hour command identity.
  identity={'hour':start.replace(minute=0,second=0,microsecond=0).isoformat(),'option':option,'maximum_power_w':watts,'epoch':epoch}
  request_id='plan_'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:48]
  plan_id=hashlib.sha256(json.dumps(report,sort_keys=True,allow_nan=False).encode()).hexdigest()
  expires=min(now+timedelta(seconds=45),valid,end)
  intent=dict(request_id=request_id,option=option,maximum_power_w=watts,expires_at=expires.isoformat(),plan_id=plan_id,plan_generated_at=issued.isoformat(),plan_valid_until=valid.isoformat(),slot_start=start.isoformat(),slot_end=end.isoformat(),planning_config_fingerprint=expected)
  return dict(status='PLAN_REQUEST_PREPARED',execution_mode_supported=option in ('Charge from Solar Power','Charge from Solar Power and Grid','Discharge to Minimize Import'),power_setpoint_policy='COMPOUND_GATEWAY_CLAMPS_TO_INVERTER_AND_LIVE_BMS; zero limits and SOC ceiling remain rejected',hold_does_not_cancel_existing_command=True,pending_request=intent,advisory_only=report.get('whole_building_schedule_approved') is not True,scenario={'future_day_type':future,'pv_scenario':pv},ack_semantics='Fresh HA state readback, not physical energy execution')
 except (KeyError,TypeError,ValueError,OverflowError) as e:
  return {'status':str(e) if isinstance(e,ValueError) else 'PLAN_INVALID','pending_request':None,'advisory_only':True}
def read(config,now,epoch):
 try:
  if PLAN_PATH.stat().st_size>524288:raise ValueError('PLAN_TOO_LARGE')
  return build(json.loads(PLAN_PATH.read_text()),config,now,epoch)
 except (OSError,ValueError,TypeError):return {'status':'PLAN_UNAVAILABLE','pending_request':None,'advisory_only':True}
class Journal:
 def __init__(self,db):
  self.db=db
  db.execute('CREATE TABLE IF NOT EXISTS planner_requests(request_id TEXT PRIMARY KEY,payload TEXT NOT NULL,result TEXT NOT NULL)')
 def observe(self,bridge,result):
  req=bridge.get('pending_request')
  if req:
   self.db.execute('INSERT INTO planner_requests VALUES(?,?,?) ON CONFLICT(request_id) DO UPDATE SET payload=excluded.payload,result=excluded.result',(req['request_id'],json.dumps(req,allow_nan=False),result))
