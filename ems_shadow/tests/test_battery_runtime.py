import unittest
from datetime import datetime,timezone,timedelta
from battery_runtime import evaluate
class Tests(unittest.TestCase):
 def report(self,state='50',age=1):
  now=datetime.now(timezone.utc)
  raw={'state':state,'last_reported':(now-timedelta(seconds=age)).isoformat()}
  keys=('b1_soc','b1_power','b1_status','ac_power','m1_import','m1_export')
  return evaluate({'sensor.example_source':raw},dict.fromkeys(keys,'sensor.example_source'),now)
 def test_fresh_never_enables(self):
  r=self.report();self.assertFalse(r['commands_enabled']);self.assertEqual(r['state'],'BLOCKED');self.assertIsNone(r['policy']['soc_min'])
 def test_stale_visible(self):self.assertTrue(self.report(age=1000)['input_issues'])
 def test_future_visible(self):self.assertTrue(self.report(age=-10)['input_issues'])
 def test_unavailable_visible(self):self.assertTrue(self.report('unavailable')['input_issues'])
 def test_no_device_timestamp_claim(self):self.assertFalse(self.report()['device_measurement_time_confirmed'])

 def test_cached_rest_does_not_prove_source_failure(self):
  now=datetime.now(timezone.utc);id='sensor.example_battery'
  raw={'state':'B_STATUS_CHARGE','last_reported':(now-timedelta(hours=1)).isoformat(),'last_updated':(now-timedelta(hours=1)).isoformat(),'last_changed':(now-timedelta(hours=1)).isoformat()}
  mem=dict(raw,last_reported=(now-timedelta(seconds=1)).isoformat())
  r=evaluate({id:raw},{'b1_status':id},now,{id:mem})
  self.assertFalse(r['inputs']['b1_status']['device_time_confirmed'])
  self.assertEqual(r['inputs']['b1_status']['memory_quality'],'HA_WRITE_RECENT_DEVICE_TIME_UNCONFIRMED')
  self.assertNotIn('b1_status:HA_UPDATE_STALE_OR_FUTURE',r['input_issues'])
 def test_read_api_refuses_actuator_paths(self):
  from battery_runtime import ReadAPI
  with self.assertRaises(ValueError):ReadAPI('synthetic').call('POST','/services/select/select_option',{})

 def test_unavailable_not_hidden_by_fresh_memory_report(self):
  now=datetime.now(timezone.utc);id='sensor.example_battery'
  raw={'state':'unavailable','last_reported':now.isoformat()}
  r=evaluate({id:raw},{'b1_status':id},now,{id:raw})
  self.assertIn('b1_status:UNAVAILABLE',r['input_issues'])
 def test_report_expiry_is_explicit(self):
  r=self.report();self.assertEqual((datetime.fromisoformat(r['valid_until'])-datetime.fromisoformat(r['recorded_at'])).total_seconds(),60)

 def test_shared_owner_requires_unique_exact_contract(self):
  from battery_runtime import shared_owner
  x={'entity_id':'input_select.example_owner','state':'LEGACY','attributes':{'friendly_name':'EMS Battery Control Owner','options':['UNKNOWN','LEGACY','EMS2']}}
  self.assertEqual(shared_owner({'a':x})['state'],'LEGACY')
  self.assertEqual(shared_owner({'a':x,'b':dict(x,entity_id='input_select.example_other')})['state'],'UNKNOWN')
  self.assertEqual(shared_owner({})['state'],'UNKNOWN')

 def test_control_interface_discovery_never_authorizes(self):
  from battery_runtime import control_interface
  raw={'entity_id':'select.example_control','state':'Time of Use','attributes':{'options':['Remote Control','Maximize Self Consumption','Time of Use']}}
  r=control_interface({'x':raw});self.assertEqual(r['state'],'Time of Use');self.assertFalse(r['actuator_authority'])
  self.assertEqual(control_interface({'a':raw,'b':dict(raw,entity_id='select.example_other')})['state'],'UNKNOWN')
 def test_missing_remote_mode_is_reported(self):
  r=self.report();self.assertIn('REMOTE_CONTROL_NOT_CONFIRMED',r['blockers']);self.assertFalse(r['commands_enabled'])

 def test_bms_snapshot_binds_actual_ha_device_and_zero_charge(self):
  from battery_runtime import bms_snapshot
  now=datetime.now(timezone.utc);soc='sensor.example_soc'
  rows=[{'entity_id':soc,'state':'100','last_reported':now.isoformat()}]
  for role,value in [('status','B_STATUS_PRESERVE_CHARGE'),('max_charge_power',5000),('peak_charge_power',0),('max_discharge_power',5000),('peak_discharge_power',5000)]:
   rows.append({'entity_id':'sensor.example_b1_'+role,'state':str(value),'last_reported':now.isoformat(),'attributes':{'unit_of_measurement':'W'}})
  class API:
   def call(self,*args):return {'device_found':True,'rows':rows}
  r=bms_snapshot(API(),soc,now);self.assertEqual(r['charge_conservative_ceiling_w'],0);self.assertEqual(r['discharge_conservative_ceiling_w'],5000);self.assertFalse(r['commands_authorized'])
 def test_bms_does_not_infer_binding_when_device_missing(self):
  from battery_runtime import bms_snapshot
  class API:
   def call(self,*args):return {'device_found':False,'rows':[]}
  with self.assertRaises(ValueError):bms_snapshot(API(),'sensor.example_soc',datetime.now(timezone.utc))

class PlanningTests(unittest.TestCase):
 def test_explicit_owner_range_does_not_grant_safety_authority(self):
  from battery_runtime import planning_policy
  p=planning_policy({'soc_operating_bounds':{'minimum':0,'maximum':100,'owner_approved':True}})
  self.assertTrue(p['owner_approved']);self.assertEqual((p['soc_min'],p['soc_max']),(0,100));self.assertFalse(p['bms_safety_confirmed'])
 def test_no_implicit_default(self):
  from battery_runtime import planning_policy
  for p in (None,{}, {'soc_operating_bounds':{'minimum':0,'maximum':100}}):self.assertFalse(planning_policy(p)['owner_approved'])
 def test_invalid_bounds(self):
  from battery_runtime import planning_policy
  for lo,hi in ((False,100),(0,101),(100,0),(0,float('nan'))):self.assertFalse(planning_policy({'soc_operating_bounds':{'minimum':lo,'maximum':hi,'owner_approved':True}})['owner_approved'])
