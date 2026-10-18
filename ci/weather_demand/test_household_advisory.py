import unittest,tempfile,json,subprocess,sys
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
from test_planning import fixture,T
from planning_runtime import plan,Planner,refresh_plan_report
from household_advisory import forecast,load_history
APPROVAL={'soc_operating_bounds':{'minimum':0,'maximum':100,'owner_approved':True}}
def history():
 rows=[]
 for i in range(72):
  start=T-timedelta(hours=i+1)
  rows.append(dict(start=start.isoformat(),end=(start+timedelta(hours=1)).isoformat(),min=100,mean=500,max=1000))
 return dict(unit='W',source_entity='sensor.example_house',retrieved_at=T.isoformat(),rows=rows)
def profile():return dict(ready=True,control_approved=False,power_w=750,unique_ha_snapshots=15,observed_start=(T-timedelta(minutes=30)).isoformat(),observed_end=T.isoformat())
def target():return [(T+timedelta(hours=i+1)).isoformat() for i in range(24)]
class HistoryTests(unittest.TestCase):
 def test_real_aggregates_not_training_or_measured_energy(self):
  r=forecast(history(),None,T.isoformat(),target());self.assertEqual(r['accepted_history_hours'],72)
  self.assertTrue(all(x['prediction_kwh']==.5 for x in r['horizon']));self.assertIsNone(r['history_reporting_coverage']);self.assertFalse(r['control_enabled'])
 def test_negative_hour_excluded_not_clamped(self):
  h=history();h['rows'][0]['min']=-1;r=forecast(h,None,T.isoformat(),target());self.assertEqual(r['accepted_history_hours'],71);self.assertEqual(r['rejected_history_hours']['invalid_or_negative_hour'],1)
 def test_no_future_knowledge(self):
  h=history();h['retrieved_at']=(T+timedelta(seconds=1)).isoformat();r=forecast(h,None,T.isoformat(),target());self.assertEqual(r['status'],'INSUFFICIENT_HOUSEHOLD_DATA')
 def test_duplicate_hour_never_adds_day(self):
  h=history();h['rows']=[h['rows'][0]]*4;r=forecast(h,None,T.isoformat(),target());self.assertEqual(r['accepted_history_hours'],1);self.assertTrue(all(x['prediction_kwh'] is None for x in r['horizon']))
 def test_missing_hour_not_interpolated(self):
  r=forecast(None,None,T.isoformat(),target());self.assertTrue(all(x['prediction_kwh'] is None for x in r['horizon']))
 def test_recent_observation_is_labelled_estimate(self):
  r=forecast(None,profile(),T.isoformat(),target());self.assertTrue(all(x['method']=='recent_qualified_snapshot_median_persistence' and x['prediction_kwh']==.75 for x in r['horizon']))
 def test_stale_recent_not_used(self):
  p=profile();p['observed_end']=(T-timedelta(minutes=5)).isoformat();self.assertEqual(forecast(None,p,T.isoformat(),target())['status'],'INSUFFICIENT_HOUSEHOLD_DATA')
 def test_expired_history_not_used(self):
  h=history();h['retrieved_at']=(T-timedelta(days=2)).isoformat();self.assertEqual(forecast(h,None,T.isoformat(),target())['status'],'INSUFFICIENT_HOUSEHOLD_DATA')
 def test_bad_disk_file_is_unavailable(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'history';p.write_text('{')
   with patch('household_advisory.HISTORY_PATH',p):self.assertIsNone(load_history())
class IntegratedTests(unittest.TestCase):
 def run_plan(self,peak=0,local_pv=False):
  a=list(fixture());a[3]['household_history_enabled']=True;a[3]['m1_scope_evidence']=dict(scope='whole_building_grid_exchange',confirmed_by='installation_owner',confirmed_at=(T-timedelta(days=1)).isoformat())
  a[3]['bms_peak_charge_entity']='sensor.example_peak';a[0]['sensor.example_peak']=dict(state=str(peak),attributes={'unit_of_measurement':'W'})
  if local_pv:
   from zoneinfo import ZoneInfo
   from datetime import datetime
   for row in a[0]['sensor.example_pv']['attributes']['detailedHourly']:row['period_start']=datetime.fromisoformat(row['period_start']).astimezone(ZoneInfo('Europe/Warsaw')).isoformat()
  for h in a[1]['horizon']:
   for v in h['scenarios'].values():v['prediction_kwh']=None
  with patch('planning_runtime.load_profile',return_value=APPROVAL),patch('household_advisory.load_history',return_value=history()):return plan(*a,building_profile=profile(),input_safety={'current_ha_set_valid':True})
 def test_household_independent_from_boiler_and_zero_peak_blocks_charging(self):
  r=self.run_plan();self.assertEqual(r['status'],'ADVISORY_HOUSEHOLD_SCHEDULE_READY');self.assertEqual(len(r['building_decisions']),4);self.assertEqual(r['boiler_forecast_blocker'],'ValueError:insufficient_load_forecast');self.assertFalse(r['control_enabled'])
  for d in r['building_decisions']:
   self.assertEqual(len(d['schedule']),24)
   self.assertTrue(all(x['charge_ac_kwh']==0 for x in d['schedule']));self.assertEqual(d['scenario_reserve_kwh'],0)
   self.assertTrue(all(x['discharge_ac_kwh']<=max(x['load_kwh']-x['pv_kwh'],0)+1e-9 for x in d['schedule']))
 def test_g13_weekend_scenario_remains_explicit(self):
  r=self.run_plan();self.assertEqual({d['future_day_type'] for d in r['building_decisions']},{'workday','nonworkday'})
 def test_regression_storage_after_separate_process_reopen(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'planning.sqlite';db=Planner(p);db.run(*fixture());db.run(*fixture());db.c.close()
   out=subprocess.check_output([sys.executable,'-c',"import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(c.execute('pragma integrity_check').fetchone()[0],c.execute('select count(*) from runs').fetchone()[0])",str(p)],text=True)
   self.assertEqual(out.strip(),'ok 1')

class TimezoneRegression(unittest.TestCase):
 def test_real_solcast_offset_matches_utc_targets(self):
  r=IntegratedTests().run_plan(local_pv=True)
  self.assertEqual(r['status'],'ADVISORY_HOUSEHOLD_SCHEDULE_READY')
  self.assertEqual(len(r['household_advisory']['decisions']),4)
