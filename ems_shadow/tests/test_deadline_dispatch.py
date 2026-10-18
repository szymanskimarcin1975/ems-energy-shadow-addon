import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app/observation'))
from deadline_dispatch import simulate_deadlines
class Tests(unittest.TestCase):
 def slot(self,price=1,target=None,load=0,pv=0):return dict(load_kwh=load,pv_kwh=pv,price_pln_kwh=price,hours=1,target_after_kwh=target)
 def runplan(self,slots,charge=5,initial=4.1):return simulate_deadlines(slots,9.2,initial,0,charge,5,.95,.95)
 def test_exact_full_capacity_not_quantised_away(self):
  r=self.runplan([self.slot(),self.slot(target=9.2)]);self.assertEqual(r['deadline_status'],'MET_IN_SIMULATION');self.assertAlmostEqual(r['schedule'][-1]['stored_kwh'],9.2)
 def test_zero_bms_charge_reports_shortfall_not_fake_energy(self):
  r=self.runplan([self.slot(target=9.2)],charge=0);self.assertEqual(r['deadline_status'],'UNREACHABLE_WITH_CURRENT_CONSTRAINTS');self.assertEqual(r['schedule'][0]['stored_kwh'],4.1)
 def test_economics_prefers_earlier_cheap_energy(self):
  r=self.runplan([self.slot(.1),self.slot(2,target=9.2)],initial=5);self.assertGreater(r['schedule'][0]['charge_ac_kwh'],r['schedule'][1]['charge_ac_kwh'])
 def test_pv_preferred_and_not_battery_export(self):
  r=self.runplan([self.slot(1,pv=5),self.slot(1,target=9.2)],initial=5);self.assertEqual(r['schedule'][0]['import_kwh'],0)
  self.assertTrue(all(s['discharge_ac_kwh']==0 for s in r['schedule']))
 def test_energy_conservation(self):
  r=self.runplan([self.slot(load=1),self.slot(load=1,target=9.2)]);before=4.1
  for s in r['schedule']:
   self.assertAlmostEqual(s['stored_kwh'],before+s['charge_ac_kwh']*.95-s['discharge_ac_kwh']/.95);before=s['stored_kwh']
 def test_no_deadline_is_explicit(self):self.assertEqual(self.runplan([self.slot()])['deadline_status'],'NO_DEADLINE_IN_MODELLED_WINDOW')

 def test_same_price_grid_cycle_is_rejected_by_terminal_value(self):
  slots=[self.slot(.6368,load=.5) for _ in range(8)]
  r=simulate_deadlines(slots,9.2,4.,0,5,5,.9,.9,terminal_value_pln_per_kwh=.6368)
  self.assertFalse(r['terminal_value_assumed_zero'])
  self.assertAlmostEqual(r['schedule'][-1]['stored_kwh'],4.)
  self.assertTrue(all(s['charge_ac_kwh']==0 and s['discharge_ac_kwh']==0 for s in r['schedule']))

 def test_expensive_period_uses_existing_energy_before_cheap_discharge(self):
  slots=[self.slot(.6368,load=.6) for _ in range(4)]+[self.slot(1.5109,load=.6) for _ in range(4)]
  r=simulate_deadlines(slots,9.2,4.,0,5,5,.9,.9,terminal_value_pln_per_kwh=.6368)
  self.assertTrue(all(s['discharge_ac_kwh']==0 for s in r['schedule'][:4]))
  self.assertGreater(sum(s['discharge_ac_kwh'] for s in r['schedule'][4:]),0)

 def test_solar_surplus_still_charges_battery(self):
  slots=[self.slot(.6368,pv=3,load=.5),self.slot(1.5109,load=.8)]
  r=simulate_deadlines(slots,9.2,3.,0,5,5,.9,.9,terminal_value_pln_per_kwh=.6368)
  self.assertGreater(r['schedule'][0]['charge_ac_kwh'],0)
  self.assertEqual(r['schedule'][0]['import_kwh'],0)
  self.assertLess(r['schedule'][1]['import_kwh'],.8)

 def test_owner_95_ceiling_clamps_charge_and_deadline(self):
  ceiling=9.2*.95
  slots=[self.slot(.6368,pv=5),self.slot(1.5109,load=2,target=ceiling)]
  r=simulate_deadlines(slots,9.2,6.,.46,5,5,.9,.9,maximum_kwh=ceiling)
  self.assertEqual(r['deadline_status'],'MET_IN_SIMULATION')
  self.assertAlmostEqual(r['scenario_ceiling_kwh'],ceiling)
  self.assertTrue(all(x['stored_kwh']<=ceiling+1e-9 for x in r['schedule']))
  self.assertFalse(r['control_enabled'])

 def test_initial_100_above_95_ceiling_never_charges_higher(self):
  ceiling=9.2*.95
  slots=[self.slot(.6368,pv=5),self.slot(1.5109,load=1)]
  r=simulate_deadlines(slots,9.2,9.2,.46,5,5,.9,.9,maximum_kwh=ceiling)
  self.assertTrue(r['initial_above_scenario_ceiling'])
  previous=9.2
  for row in r['schedule']:
   self.assertLessEqual(row['stored_kwh'],max(ceiling,previous)+1e-9)
   if previous>ceiling+1e-9:self.assertAlmostEqual(row['charge_ac_kwh'],0.)
   previous=row['stored_kwh']

 def test_target_above_approved_ceiling_rejected(self):
  with self.assertRaisesRegex(ValueError,'invalid_target'):
   simulate_deadlines([self.slot(target=9.2)],9.2,5.,.46,5,5,.9,.9,maximum_kwh=8.74)


 def test_soc_95_ceiling_and_soc_5_floor(self):
  ceiling=9.2*.95;floor=9.2*.05
  at_ceiling=simulate_deadlines([self.slot(.6368,pv=5,load=.2)],9.2,ceiling,floor,5,5,.9,.9,maximum_kwh=ceiling)
  self.assertEqual(at_ceiling['schedule'][0]['charge_ac_kwh'],0)
  self.assertLessEqual(at_ceiling['schedule'][0]['stored_kwh'],ceiling+1e-9)
  at_floor=simulate_deadlines([self.slot(1.5109,load=2)],9.2,floor,floor,5,5,.9,.9,maximum_kwh=ceiling)
  self.assertEqual(at_floor['schedule'][0]['discharge_ac_kwh'],0)
  self.assertGreaterEqual(at_floor['schedule'][0]['stored_kwh'],floor-1e-9)

 def test_normal_charge_and_discharge_within_5_95(self):
  floor=9.2*.05;ceiling=9.2*.95
  slots=[self.slot(.6368,pv=4,load=.5),
         self.slot(.6368,load=.5,target=6.),
         self.slot(1.5109,load=2.)]
  r=simulate_deadlines(slots,9.2,4.6,floor,5,5,.9,.9,terminal_value_pln_per_kwh=.6368,maximum_kwh=ceiling)
  self.assertGreater(sum(x['charge_ac_kwh'] for x in r['schedule']),0)
  self.assertGreater(sum(x['discharge_ac_kwh'] for x in r['schedule']),0)
  self.assertTrue(all(floor-1e-9<=x['stored_kwh']<=ceiling+1e-9 for x in r['schedule']))
