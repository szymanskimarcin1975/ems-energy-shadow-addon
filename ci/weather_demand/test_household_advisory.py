import unittest,tempfile,json,subprocess,sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from test_planning import fixture,T
from planning_runtime import plan,Planner,refresh_plan_report
from deadline_dispatch import simulate_deadlines
from boiler_offline.g13 import tariff
from zoneinfo import ZoneInfo
from household_advisory import forecast,load_history,actual_hourly_rows,schedule
APPROVAL={'soc_operating_bounds':{'minimum':0,'maximum':100,'owner_approved':True}}
def history_at(now):
 rows=[]
 for i in range(72):
  start=now-timedelta(hours=i+1)
  rows.append(dict(start=start.isoformat(),end=(start+timedelta(hours=1)).isoformat(),min=100,mean=500,max=1000))
 return dict(unit='W',source_entity='sensor.example_house',retrieved_at=now.isoformat(),rows=rows)
def history():return history_at(T)
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
 def test_duplicate_hour_never_counts_as_multiple_training_days(self):
  h=history();h['rows']=[h['rows'][0]]*4;r=forecast(h,None,T.isoformat(),target());self.assertEqual(r['accepted_history_hours'],1);self.assertTrue(all(not x['uncertainty_calibrated'] for x in r['horizon']));self.assertTrue(all(x['prediction_kwh'] is not None for x in r['horizon']));self.assertTrue(any('conservative_max_observed_hour_uncalibrated' in x['method'] for x in r['horizon']))
 def test_missing_hour_not_interpolated(self):
  r=forecast(None,None,T.isoformat(),target());self.assertTrue(all(x['prediction_kwh'] is None for x in r['horizon']))
 def test_daily_error_bias_uses_only_repeated_completed_actuals_and_is_capped(self):
  r=forecast(history(),None,T.isoformat(),target()[:1],error_biases={7:{'median_error_kwh':1.0,'samples':3}})
  self.assertEqual(r['horizon'][0]['prediction_kwh'],.75)
  self.assertEqual(r['horizon'][0]['prior_error_correction']['applied_kwh'],.25)
  self.assertFalse(r['horizon'][0]['uncertainty_calibrated'])
 def test_recent_observation_is_labelled_estimate(self):
  r=forecast(None,profile(),T.isoformat(),target());self.assertTrue(all(x['method']=='recent_qualified_snapshot_persistence_uncalibrated' and x['prediction_kwh']==.75 for x in r['horizon']))
 def test_stale_recent_not_used(self):
  p=profile();p['observed_end']=(T-timedelta(minutes=5)).isoformat();self.assertEqual(forecast(None,p,T.isoformat(),target())['status'],'INSUFFICIENT_HOUSEHOLD_DATA')
 def test_expired_history_not_used(self):
  h=history();h['retrieved_at']=(T-timedelta(days=2)).isoformat();self.assertEqual(forecast(h,None,T.isoformat(),target())['status'],'INSUFFICIENT_HOUSEHOLD_DATA')
 def test_bad_disk_file_is_unavailable(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'history';p.write_text('{')
   with patch('household_advisory.HISTORY_PATH',p):self.assertIsNone(load_history())
class ForecastAdaptationTests(unittest.TestCase):
 def test_persisted_daily_errors_reopen_and_correct_uncalibrated_forecast(self):
  rows=actual_hourly_rows(history(),T.isoformat());same=[r for r in rows if r['local_hour']==5]
  self.assertEqual(len(same),3)
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'planning.sqlite';db=Planner(path)
   for row in same:
    generated=(datetime.fromisoformat(row['target_at'])-timedelta(hours=1)).isoformat()
    db.c.execute('INSERT INTO household_forecasts VALUES(?,?,?,?,?,?)',
      ('sensor.example_house',row['target_at'],generated,row['local_hour'],.2,'test_forecast'))
   self.assertEqual(db.reconcile_forecast_errors('sensor.example_house',rows),3)
   db.c.close()
   reopened=Planner(path);biases=reopened.error_biases('sensor.example_house',T.isoformat())
   self.assertEqual(biases[5]['samples'],3);self.assertAlmostEqual(biases[5]['median_error_kwh'],.3)
   prediction=forecast(history(),None,T.isoformat(),[(T+timedelta(hours=23)).isoformat()],error_biases=biases)
   self.assertAlmostEqual(prediction['horizon'][0]['prediction_kwh'],.75)
   self.assertFalse(prediction['horizon'][0]['uncertainty_calibrated'])
   reopened.c.close()

class RollingEconomicsTests(unittest.TestCase):
 def monday_inputs(self,pv_profile,soc=20):
  now=datetime(2026,10,19,0,tzinfo=ZoneInfo('Europe/Warsaw')).astimezone(timezone.utc)
  states,_,at,c,o=fixture(now)
  c['household_history_enabled']=True
  c['m1_scope_evidence']=dict(scope='whole_building_grid_exchange',confirmed_by='installation_owner',confirmed_at=(now-timedelta(days=1)).isoformat())
  c['bms_peak_charge_entity']='sensor.example_peak'
  states['sensor.example_peak']=dict(state='5000',attributes={'unit_of_measurement':'W'},last_reported=at)
  work=o['observation']['boiler_sources']['workday']
  states[work]['state']='on'
  states[o['observation']['solar_sources']['b1_soc']]['state']=str(soc)
  rows=states['sensor.example_pv']['attributes']['detailedHourly']
  while len(rows)<48:
   next_time=datetime.fromisoformat(rows[-1]['period_start'])+timedelta(hours=1)
   rows.append(dict(period_start=next_time.isoformat(),pv_estimate=0,pv_estimate10=0))
  for row in rows:
   local=datetime.fromisoformat(row['period_start']).astimezone(ZoneInfo('Europe/Warsaw'))
   pv=pv_profile(local)
   row['pv_estimate']=pv;row['pv_estimate10']=pv
  states['sensor.example_pv_update']['state']=at
  c['working_rates_pln_kwh']={'dolina':.6368,'szczyt_przedpoludniowy':.9235,'szczyt_popoludniowy':1.5109}
  with patch('household_advisory.load_history',return_value=history_at(now)):
   report=schedule(states,at,c,o,profile(),{'current_ha_set_valid':True},
      {'owner_approved':True,'soc_min':0,'soc_max':100})
  return report
 def test_sunday_cheap_then_cheap_avoids_unnecessary_cycle(self):
  slots=[dict(load_kwh=.5,pv_kwh=0,price_pln_kwh=.6368,hours=1,target_after_kwh=None) for _ in range(48)]
  r=simulate_deadlines(slots,9.2,4,0,5,5,.95,.95,terminal_value_pln_per_kwh=.6368*.95)
  self.assertAlmostEqual(sum(x['charge_ac_kwh'] for x in r['schedule']),0)
  self.assertAlmostEqual(sum(x['discharge_ac_kwh'] for x in r['schedule']),0)
  self.assertGreater(r['terminal_value_credit_pln'],0)
  self.assertFalse(r['terminal_value_assumed_zero'])
 def test_monday_low_pv_prepares_only_modeled_need_before_peak(self):
  r=self.monday_inputs(lambda local:.1)
  d=next(x for x in r['decisions'] if x['future_day_type']=='workday' and x['pv_scenario']=='pv_estimate')
  peak=d['peak_windows'][0];self.assertEqual(datetime.fromisoformat(peak['starts_at']).astimezone(ZoneInfo('Europe/Warsaw')).hour,16)
  before=next(x for x in d['schedule'] if x['valid_to']==peak['starts_at'])
  self.assertGreaterEqual(before['stored_kwh']+1e-9,peak['target_stored_kwh'])
  self.assertLess(before['stored_kwh'],9.2)
  self.assertGreater(sum(x['grid_charge_ac_kwh'] for x in d['schedule'] if x['valid_to']<=peak['starts_at']),0)
  self.assertLess(peak['target_stored_kwh'],9.2)
  self.assertFalse(d['control_enabled'])
 def test_solar_surplus_reduces_grid_precharge_and_uses_pv_headroom(self):
  low=self.monday_inputs(lambda local:.1)
  sun=self.monday_inputs(lambda local:1.5 if 12<=local.hour<16 else .1)
  a=next(x for x in low['decisions'] if x['future_day_type']=='workday' and x['pv_scenario']=='pv_estimate')
  b=next(x for x in sun['decisions'] if x['future_day_type']=='workday' and x['pv_scenario']=='pv_estimate')
  ta=a['peak_windows'][0]['starts_at'];tb=b['peak_windows'][0]['starts_at']
  grid_a=sum(x['grid_charge_ac_kwh'] for x in a['schedule'] if x['valid_to']<=ta)
  grid_b=sum(x['grid_charge_ac_kwh'] for x in b['schedule'] if x['valid_to']<=tb)
  pv_b=sum(x['pv_charge_ac_kwh'] for x in b['schedule'] if x['valid_to']<=tb)
  self.assertGreater(pv_b,0);self.assertLess(grid_b,grid_a)
  self.assertFalse(b['control_enabled'])

class IntegratedTests(unittest.TestCase):
 def run_plan(self,peak=0,local_pv=False):
  a=list(fixture());a[3]['household_history_enabled']=True;a[3]['m1_scope_evidence']=dict(scope='whole_building_grid_exchange',confirmed_by='installation_owner',confirmed_at=(T-timedelta(days=1)).isoformat())
  a[3]['bms_peak_charge_entity']='sensor.example_peak';a[0]['sensor.example_peak']=dict(state=str(peak),attributes={'unit_of_measurement':'W'})
  pv_rows=a[0]['sensor.example_pv']['attributes']['detailedHourly']
  from datetime import datetime
  while len(pv_rows)<48:
   previous=datetime.fromisoformat(pv_rows[-1]['period_start'])
   next_time=previous+timedelta(hours=1)
   pv_rows.append(dict(period_start=next_time.isoformat(),pv_estimate=pv_rows[(len(pv_rows)-24)%24]['pv_estimate'],pv_estimate10=pv_rows[(len(pv_rows)-24)%24]['pv_estimate10']))
  if local_pv:
   from zoneinfo import ZoneInfo
   for row in pv_rows:row['period_start']=datetime.fromisoformat(row['period_start']).astimezone(ZoneInfo('Europe/Warsaw')).isoformat()
  a[3]['working_rates_pln_kwh']={'dolina':.6368,'szczyt_przedpoludniowy':.9235,'szczyt_popoludniowy':1.5109}
  for h in a[1]['horizon']:
   for v in h['scenarios'].values():v['prediction_kwh']=None
  with patch('planning_runtime.load_profile',return_value=APPROVAL),patch('household_advisory.load_history',return_value=history()):return plan(*a,building_profile=profile(),input_safety={'current_ha_set_valid':True})
 def test_household_independent_from_boiler_and_zero_peak_blocks_charging(self):
  r=self.run_plan();self.assertEqual(r['status'],'ADVISORY_HOUSEHOLD_SCHEDULE_READY');self.assertEqual(len(r['building_decisions']),4);self.assertEqual(r['boiler_forecast_blocker'],'ValueError:insufficient_load_forecast');self.assertFalse(r['control_enabled'])
  for d in r['building_decisions']:
   self.assertEqual(len(d['schedule']),48)
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
