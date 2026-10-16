"""Synthetic Jinja/state/action model only; not a Supervisor or inverter test."""
import ast,math,unittest
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from jinja2 import Environment,StrictUndefined
from gateway_dispatch import branch,extend,ROLES
NOW=datetime(2026,10,16,16,tzinfo=timezone.utc)
BIND={k:('sensor.example_'+k) for k in ROLES};BIND.update(owner='input_select.example_owner',authorization='input_boolean.example_auth',safety_min='input_number.example_min',safety_max='input_number.example_max',control_mode='select.example_control',command_mode='select.example_mode',charge_limit='number.example_charge',discharge_limit='number.example_discharge',old_writers=['automation.example_old'])
class Stop(Exception):pass
class States:
 def __init__(self):
  self.rows={}
  values=dict(owner='EMS2',authorization='on',soc=50,safety_min=0,safety_max=100,control_mode='Remote Control',command_mode='Maximize Self Consumption',fault_status='I_STATUS_MPPT',vendor_status='0x0',m1_power=-1,b1_power=0,bms_status='B_STATUS_IDLE',max_charge=5000,peak_charge=5000,max_discharge=5000,peak_discharge=5000,charge_limit=5000,discharge_limit=5000)
  for role,value in values.items():self.rows[BIND[role]]=SimpleNamespace(state=str(value),last_reported=NOW,last_updated=NOW,attributes={'unit_of_measurement':{'soc':'%','m1_power':'kW','b1_power':'W','max_charge':'W','peak_charge':'W','max_discharge':'W','peak_discharge':'W'}.get(role)})
  self.rows['automation.example_old']=SimpleNamespace(state='off',last_reported=NOW,last_updated=NOW,attributes={'current':0})
 def __call__(self,e):return self.rows[e].state if e in self.rows else 'unknown'
 def __getitem__(self,e):return self.rows.get(e)
class Harness:
 def __init__(self):
  self.states=States();self.calls=[];self.break_after_power=None
  self.env=Environment(undefined=StrictUndefined)
  import re
  self.env.filters['regex_match']=lambda v,p:bool(re.match(p,v))
  def numeric(x):
   try:return math.isfinite(float(x))
   except (ValueError,TypeError):return False
  self.ctx={'states':self.states,'state_attr':lambda e,k:self.states[e].attributes.get(k) if self.states[e] else None,'is_state':lambda e,s:self.states(e)==s,'is_number':numeric,'now':lambda:NOW,'as_timestamp':lambda t:t.timestamp() if isinstance(t,datetime) else datetime.fromisoformat(t).timestamp()}
 def render(self,x):
  if isinstance(x,str) and ('{{' in x or '{%' in x):
   v=self.env.from_string(x).render(**self.ctx).strip()
   try:return ast.literal_eval(v)
   except (SyntaxError,ValueError):return v
  if isinstance(x,dict):return {k:self.render(v) for k,v in x.items()}
  if isinstance(x,list):return [self.render(v) for v in x]
  return x
 def seq(self,steps):
  for step in steps:
   if 'variables' in step:
    for k,v in step['variables'].items():self.ctx[k]=self.render(v)
   elif 'if' in step:
    ok=all(self.render(c['value_template']) is True for c in step['if'])
    self.seq(step.get('then',[]) if ok else step.get('else',[]))
   elif 'action' in step:
    target=self.render(step['target']['entity_id']);data=self.render(step['data']);self.calls.append((step['action'],target,data))
    s=self.states[target];s.state=str(data.get('value',data.get('option')));s.last_updated=NOW+timedelta(milliseconds=1)
    if step['action']=='number.set_value' and self.break_after_power:self.break_after_power(self)
   elif 'stop' in step:raise Stop()
 def run(self,option='Charge from Solar Power and Grid',watts=5000,caller='EMS2'):
  self.ctx.update(caller=caller,operation='dispatch',command_value={'option':option,'power_w':watts},request_id='synthetic_request',expires_at=(NOW+timedelta(seconds=45)).timestamp())
  try:self.seq([branch(BIND)])
  except Stop:pass
  return self.ctx.get('reply')
class Tests(unittest.TestCase):
 def test_grid_charge_two_writes_same_queue_run(self):
  h=Harness();r=h.run();self.assertEqual(r['status'],'SERVICE_COMPLETED');self.assertEqual([c[0] for c in h.calls],['number.set_value','select.select_option']);self.assertEqual(h.calls[1][2]['option'],'Charge from Solar Power and Grid')
 def test_clamp_to_bms_and_requested(self):
  h=Harness();h.states[BIND['peak_charge']].state='1200';r=h.run(watts=4500);self.assertEqual(r['applied_power_w'],1200);self.assertEqual(h.calls[0][2]['value'],1200)
 def test_clamp_inverter_nominal(self):
  h=Harness();r=h.run(watts=8000);self.assertEqual(r['applied_power_w'],5000)
 def test_soc_100_not_clamped_to_allowed(self):
  h=Harness();h.states[BIND['soc']].state='100';self.assertEqual(h.run()['reason'],'SOC_CEILING');self.assertEqual(h.calls,[])
 def test_zero_peak_not_changed_to_charge(self):
  h=Harness();h.states[BIND['peak_charge']].state='0';self.assertEqual(h.run()['reason'],'BMS_DIRECTION_LIMIT_ZERO');self.assertEqual(h.calls,[])
 def test_legacy_owner_rejected(self):
  h=Harness();h.states[BIND['owner']].state='LEGACY';self.assertEqual(h.run()['status'],'REJECTED');self.assertEqual(h.calls,[])
 def test_running_legacy_writer_rejected(self):
  h=Harness();h.states['automation.example_old'].state='on';self.assertEqual(h.run()['status'],'REJECTED');self.assertEqual(h.calls,[])
 def test_fault_rejected(self):
  h=Harness();h.states[BIND['fault_status']].state='I_STATUS_FAULT';self.assertEqual(h.run()['reason'],'INVERTER_FAULT_OR_VENDOR_ERROR');self.assertEqual(h.calls,[])
 def test_stale_and_unsynchronised_rejected(self):
  for lag in (181,6):
   h=Harness();h.states[BIND['m1_power']].last_reported=NOW-timedelta(seconds=lag);self.assertEqual(h.run()['status'],'REJECTED');self.assertEqual(h.calls,[])
 def test_direction_change_after_write_is_unknown_not_clean_reject(self):
  h=Harness();h.break_after_power=lambda a:setattr(a.states[BIND['peak_charge']],'state','0');self.assertEqual(h.run()['status'],'PARTIAL_OR_UNKNOWN');self.assertEqual(len(h.calls),1)
 def test_communication_state_loss_after_write_no_mode(self):
  h=Harness();h.break_after_power=lambda a:setattr(a.states[BIND['bms_status']],'state','unavailable');self.assertEqual(h.run()['status'],'PARTIAL_OR_UNKNOWN');self.assertEqual(len(h.calls),1)
 def test_discharge_requires_import(self):
  h=Harness();h.states[BIND['m1_power']].state='1';self.assertEqual(h.run(option='Discharge to Minimize Import')['reason'],'NO_FRESH_GRID_IMPORT');self.assertEqual(h.calls,[])
 def test_export_mode_never_allowlisted(self):
  h=Harness();self.assertEqual(h.run(option='Discharge to Maximize Export')['status'],'REJECTED');self.assertEqual(h.calls,[])
 def test_legacy_sequence_preserved_exactly(self):
  old={'mode':'queued','sequence':[{'variables':{'reply':{}}},{'stop':'legacy remains unchanged'}]};new=extend(old,BIND);self.assertEqual(new['sequence'][0],old['sequence'][0]);self.assertEqual(new['sequence'][2:],old['sequence'][1:]);self.assertEqual(len(old['sequence']),2)
 def test_bool_power_invalid(self):
  h=Harness();self.assertEqual(h.run(watts=True)['status'],'REJECTED');self.assertEqual(h.calls,[])
