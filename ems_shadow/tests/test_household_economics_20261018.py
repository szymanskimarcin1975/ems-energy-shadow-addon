"""Synthetic advisory economics tests. No Home Assistant or inverter IO."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]/'app'
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'observation'))
from household_advisory import schedule

ZONE=ZoneInfo('Europe/Warsaw')


class AdvisoryEconomics(unittest.TestCase):
 def test_sunday_now_includes_monday_evening_peak_and_only_needed_reserve(self):
  now=datetime(2026,10,18,7,30,tzinfo=timezone.utc)
  now_iso=now.isoformat()
  def reading(value,unit):
   return {'state':str(value),'attributes':{'unit_of_measurement':unit},'last_reported':now_iso}
  def pv_day(date):
   return [{'period_start':datetime(date[0],date[1],date[2],h,tzinfo=ZONE).isoformat(),
            'pv_estimate':0.,'pv_estimate10':0.} for h in range(24)]
  states={
   'sensor.example_soc':reading(75,'%'),
   'sensor.example_capacity':reading(9.2,'kWh'),
   'sensor.example_charge':reading(5000,'W'),
   'sensor.example_discharge':reading(5000,'W'),
   'sensor.example_pv_updated':{'state':now_iso,'attributes':{},'last_reported':now_iso},
   'sensor.example_pv_today':{'state':'0','attributes':{'detailedHourly':pv_day((2026,10,18))}},
   'sensor.example_pv_tomorrow':{'state':'0','attributes':{'detailedHourly':pv_day((2026,10,19))}},
   'binary_sensor.example_workday':{'state':'off','attributes':{},'last_reported':now_iso},
  }
  config={
   'capacity_entity':'sensor.example_capacity','charge_limit_entity':'sensor.example_charge','discharge_limit_entity':'sensor.example_discharge',
   'pv_updated_entity':'sensor.example_pv_updated','pv_forecast_entities':['sensor.example_pv_today','sensor.example_pv_tomorrow'],
   'working_rates_pln_kwh':{'dolina':.6368,'szczyt_przedpoludniowy':.9235,'szczyt_popoludniowy':1.5109},
   'rates_effective_from':'2026-10-01T00:00:00+02:00',
   'simulation_charge_eff':.9,'simulation_discharge_eff':.9,'include_current_slot':True,
  }
  options={'observation':{'solar_sources':{'b1_soc':'sensor.example_soc'},'boiler_sources':{'workday':'binary_sensor.example_workday'}}}
  profile={
   'ready':True,'control_approved':False,'unique_ha_snapshots':10,
   'observed_start':(now-timedelta(minutes=25)).isoformat(),
   'observed_end':(now-timedelta(minutes=1)).isoformat(),
   'power_w':500.
  }
  with patch('household_advisory.load_history',return_value=None):
   result=schedule(states,now_iso,config,options,profile,{'current_ha_set_valid':True},
                   {'owner_approved':True,'soc_min':0,'soc_max':100})
  self.assertFalse(result['control_enabled'])
  self.assertEqual(len(result['decisions']),4)
  workday=next(x for x in result['decisions'] if x['future_day_type']=='workday' and x['pv_scenario']=='pv_estimate')
  weekend=next(x for x in result['decisions'] if x['future_day_type']=='nonworkday' and x['pv_scenario']=='pv_estimate')
  self.assertGreaterEqual(len(workday['schedule']),36)
  self.assertEqual(workday['deadline_count'],1)
  self.assertEqual(weekend['deadline_count'],0)
  target=next(x for x in workday['schedule'] if x['target_after_kwh'] is not None)
  self.assertEqual(datetime.fromisoformat(target['valid_to']).astimezone(ZONE).hour,16)
  self.assertAlmostEqual(target['target_after_kwh'],5*.5/.9,places=6)
  self.assertLess(target['target_after_kwh'],9.2)
  self.assertFalse(workday['terminal_value_assumed_zero'])
  self.assertAlmostEqual(workday['terminal_value_pln_per_kwh'],.6368)
  self.assertTrue(all(x['discharge_ac_kwh']<1e-9 for x in workday['schedule']
                      if datetime.fromisoformat(x['valid_for']).astimezone(ZONE).date()==datetime(2026,10,18).date()))
  self.assertIsNone(result['workday_soc_deadline']['target_percent'])
  self.assertEqual(result['workday_soc_deadline']['policy'],'FORECAST_NET_EXPENSIVE_HOURS_ENERGY_NOT_FIXED_100_PERCENT')


if __name__=='__main__':unittest.main()
