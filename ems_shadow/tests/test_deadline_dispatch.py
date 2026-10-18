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
