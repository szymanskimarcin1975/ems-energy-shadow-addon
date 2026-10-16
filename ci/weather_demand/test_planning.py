import json,sqlite3,tempfile,unittest,subprocess,sys
from pathlib import Path
from unittest.mock import patch
from collections import namedtuple
from datetime import datetime,timedelta,timezone
from planning_runtime import Planner,plan
T=datetime(2026,10,16,4,tzinfo=timezone.utc)
def fixture(now=T):
 at=now.isoformat();z=lambda v,u:dict(state=str(v),attributes={'unit_of_measurement':u},last_reported=at)
 solar={k:'sensor.example_'+k for k in ('ac_power','b1_power','b1_soc','b1_status')}
 o={'sources':{'grid_kw':'sensor.example_grid'},'observation':{'solar_sources':solar,'boiler_sources':{'workday':'binary_sensor.example_workday'}}}
 c=dict(enabled=True,capacity_entity='sensor.example_capacity',charge_limit_entity='sensor.example_charge',discharge_limit_entity='sensor.example_discharge',simulation_min_soc_percent=30,simulation_charge_eff=.95,simulation_discharge_eff=.95,working_rates_pln_kwh={'dolina':.6,'szczyt_przedpoludniowy':.9,'szczyt_popoludniowy':1.5},rates_effective_from='2026-01-01T00:00:00+00:00',rates_version='synthetic',rates_basis='synthetic',pv_updated_entity='sensor.example_pv_update',pv_forecast_entities=['sensor.example_pv'])
 s={solar['ac_power']:z(100,'W'),solar['b1_power']:z(-100,'W'),solar['b1_soc']:z(50,'%'),solar['b1_status']:dict(state='B_STATUS_DISCHARGE'),'sensor.example_grid':z(-.2,'kW'),c['capacity_entity']:z(9.2,'kWh'),c['charge_limit_entity']:z(5000,'W'),c['discharge_limit_entity']:z(5000,'W'),'binary_sensor.example_workday':dict(state='on'),c['pv_updated_entity']:dict(state=at)}
 target=(now+timedelta(hours=1)).replace(minute=0,second=0,microsecond=0)
 h=[dict(valid_for=(target+timedelta(hours=i)).isoformat(),scenarios={d:{'prediction_kwh':.8} for d in ('workday','nonworkday')}) for i in range(24)]
 s['sensor.example_pv']=dict(attributes={'detailedHourly':[dict(period_start=r['valid_for'],pv_estimate=1,pv_estimate10=.5) for r in h]})
 return s,{'horizon':h},at,c,o
class Tests(unittest.TestCase):
 def test_hypothetical_only_actual_solver(self):
  r=plan(*fixture());self.assertEqual(r['status'],'HYPOTHETICAL_SCHEDULE_READY');self.assertEqual(len(r['decisions']),4);self.assertFalse(r['control_enabled']);self.assertEqual(len(r['decisions'][0]['schedule']),24);self.assertIsNone(r['flows']['actual_pv_production_w'])
 def test_static_ratings_not_falsely_required_to_change(self):
  a=list(fixture())
  for e in ('sensor.example_capacity','sensor.example_charge','sensor.example_discharge'):
   a[0][e]['last_reported']='2026-10-01T00:00:00+00:00'
  r=plan(*a);self.assertEqual(r['status'],'HYPOTHETICAL_SCHEDULE_READY');self.assertFalse(r['control_enabled'])
 def test_stale_dynamic_soc_still_rejected(self):
  a=list(fixture());a[0]['sensor.example_b1_soc']['last_reported']='2026-10-01T00:00:00+00:00'
  r=plan(*a);self.assertEqual(r['status'],'BLOCKED_INPUT');self.assertIn('sensor.example_b1_soc',r['reason'])
 def test_whole_building_is_conditional_not_confirmed(self):
  r=plan(*fixture(),building_profile={'ready':True,'power_w':300});self.assertEqual(len(r['building_decisions']),4)
  self.assertFalse(r['active_control_readiness']['ready'])
  self.assertEqual(r['building_candidate']['status'],'CONDITIONAL_ESTIMATE_ONLY')
  for d in r['building_decisions']:
   self.assertEqual(len(d['schedule']),24)
   self.assertAlmostEqual(d['schedule'][0]['load_kwh'],.3)
 def test_negative_blocks_whole_building_only(self):
  a=list(fixture());a[0]['sensor.example_grid']['state']='2'
  r=plan(*a);self.assertEqual(r['building_decisions'],[]);self.assertEqual(len(r['decisions']),4)
  self.assertLess(r['balance']['candidate_building_w'],0)
 def test_legacy_controller_state_audited_without_commands(self):
  a=list(fixture());a[3]['legacy_controller_entities']=['automation.example_old']
  a[0]['automation.example_old']={'state':'on'}
  r=plan(*a);self.assertEqual(r['active_control_readiness']['legacy_controllers']['automation.example_old'],'on');self.assertFalse(r['control_enabled'])
 def test_disk_guard_blocks_quality_writes_too(self):
  with tempfile.TemporaryDirectory() as d:
   s=Planner(Path(d)/'test.sqlite');states,_,at,_,options=fixture()
   with patch('planning_runtime.shutil.disk_usage',return_value=namedtuple('Usage','total used free')(100,100,0)):
    with self.assertRaises(OSError):s.observe(states,at,options)
   self.assertEqual(s.c.execute('select count(*) from balance_checks').fetchone()[0],0);s.c.close()
 def test_owner_scope_removes_only_scope_blocker(self):
  a=list(fixture());a[3]['m1_scope_evidence']={'scope':'whole_building_grid_exchange','confirmed_by':'installation_owner','confirmed_at':'2026-10-15T00:00:00+00:00'}
  r=plan(*a,building_profile={'ready':True,'power_w':300})
  self.assertTrue(r['m1_scope']['confirmed'])
  self.assertNotIn('M1_SCOPE_UNCONFIRMED',r['active_control_readiness']['blockers'])
  self.assertIn('DEVICE_TIME_SYNC_UNCONFIRMED',r['active_control_readiness']['blockers'])
  self.assertFalse(r['active_control_readiness']['ready']);self.assertFalse(r['balance']['topology_confirmed'])
  self.assertFalse(r['control_enabled']);self.assertEqual(len(r['building_decisions']),4)
 def test_invalid_or_future_scope_evidence_fails_closed(self):
  for when in ('bad','2027-01-01T00:00:00+00:00'):
   a=list(fixture());a[3]['m1_scope_evidence']={'scope':'whole_building_grid_exchange','confirmed_by':'installation_owner','confirmed_at':when}
   r=plan(*a);self.assertFalse(r['m1_scope']['confirmed']);self.assertIn('M1_SCOPE_UNCONFIRMED',r['active_control_readiness']['blockers'])
 def test_live_soc_below_scenario_floor_keeps_advisory_running(self):
  a=list(fixture());a[0]['sensor.example_b1_soc']['state']='20'
  r=plan(*a,building_profile={'ready':True,'power_w':300})
  self.assertEqual(r['status'],'HYPOTHETICAL_SCHEDULE_READY')
  self.assertEqual(len(r['building_decisions']),4);self.assertFalse(r['control_enabled'])
  self.assertEqual(r['battery']['soc_percent'],20)
  for d in r['building_decisions']:
   previous=d['initial_stored_kwh']
   for row in d['schedule']:
    self.assertGreaterEqual(row['stored_kwh']+1e-9,min(previous,d['scenario_reserve_kwh']))
    previous=row['stored_kwh']
 def test_missing_soc(self):
  a=list(fixture());del a[0]['sensor.example_b1_soc'];r=plan(*a);self.assertEqual(r['status'],'BLOCKED_INPUT');self.assertEqual(r['decisions'],[])
 def test_missing_load(self):
  a=list(fixture());a[1]['horizon'][0]['scenarios']['workday']['prediction_kwh']=None;self.assertEqual(plan(*a)['status'],'BLOCKED_INPUT')
 def test_stale_pv(self):
  a=list(fixture());a[0]['sensor.example_pv_update']['state']='2026-10-01T00:00:00+00:00';self.assertEqual(plan(*a)['status'],'BLOCKED_INPUT')
 def test_unknown_workday(self):
  a=list(fixture());a[0]['binary_sensor.example_workday']['state']='unavailable';self.assertEqual(plan(*a)['status'],'BLOCKED_INPUT')
 def test_negative_balance_remains_blocked_for_control(self):
  a=list(fixture());a[0]['sensor.example_grid']['state']='2';r=plan(*a);self.assertEqual(r['balance']['status'],'INCONSISTENT_NEGATIVE_LOAD');self.assertFalse(r['control_enabled'])
 def test_sqlite_duplicate_reopen_integrity(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'new.sqlite';s=Planner(p);s.run(*fixture());s.run(*fixture());s.c.close()
   out=subprocess.check_output([sys.executable,'-c',"import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(c.execute('pragma integrity_check').fetchone()[0],c.execute('select count(*) from runs').fetchone()[0])",str(p)],text=True)
   self.assertEqual(out.strip(),'ok 1')
 def test_readonly_transaction_no_partial(self):
  with tempfile.TemporaryDirectory() as d:
   s=Planner(Path(d)/'a.sqlite');s.c.execute('PRAGMA query_only=ON')
   with self.assertRaises(sqlite3.Error):s.run(*fixture())
   self.assertEqual(s.c.execute('select count(*) from runs').fetchone()[0],0);s.c.close()
if __name__=='__main__':unittest.main()

import unittest
from unittest.mock import patch
from planning_runtime import plan
class ApprovalTests(unittest.TestCase):
 def test_approved_profile_changes_actual_simulation_floor(self):
  profile={'soc_operating_bounds':{'minimum':0,'maximum':100,'owner_approved':True}}
  with patch('planning_runtime.load_profile',return_value=profile):r=plan(*fixture())
  self.assertEqual(r['status'],'HYPOTHETICAL_SCHEDULE_READY')
  self.assertEqual(r['battery']['simulated_min_soc_percent'],0)
  self.assertTrue(r['planning_soc_policy']['applied_to_simulation'])
  self.assertTrue(all(d['scenario_reserve_kwh']==0 for d in r['decisions']))
  self.assertFalse(r['control_enabled'])
 def test_missing_profile_keeps_existing_scenario_and_no_authority(self):
  with patch('planning_runtime.load_profile',return_value=None):r=plan(*fixture())
  self.assertEqual(r['battery']['simulated_min_soc_percent'],30)
  self.assertFalse(r['planning_soc_policy']['applied_to_simulation'])
  self.assertFalse(r['control_enabled'])
