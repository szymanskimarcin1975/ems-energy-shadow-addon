import unittest
from dispatch_simulator import simulate
class Tests(unittest.TestCase):
 def runplan(self,slots,**kw):
  return simulate(slots,2,1,.5,1,1,.95,.95,**kw)
 def test_gate(self):self.assertFalse(self.runplan([])['control_enabled']);self.assertTrue(self.runplan([])['status'].startswith('BLOCKED'))
 def test_real_balance_and_limits(self):
  slots=[dict(load_kwh=.3,pv_kwh=0,price_pln_kwh=.6,hours=1),dict(load_kwh=.8,pv_kwh=0,price_pln_kwh=1.5,hours=1)]
  r=self.runplan(slots,topology_confirmed=True);self.assertFalse(r['control_enabled'])
  for s,p in zip(slots,r['schedule']):
   self.assertAlmostEqual(s['load_kwh']+p['charge_ac_kwh']+p['pv_export_kwh'],s['pv_kwh']+p['discharge_ac_kwh']+p['import_kwh'])
   self.assertGreaterEqual(p['stored_kwh'],.5-1e-9);self.assertLessEqual(p['stored_kwh'],2+1e-9)
 def test_no_battery_export(self):
  r=self.runplan([dict(load_kwh=0,pv_kwh=1,price_pln_kwh=1,hours=1)],topology_confirmed=True)
  self.assertEqual(r['schedule'][0]['discharge_ac_kwh'],0)
 def test_missing_input_not_zero(self):
  with self.assertRaises(ValueError):self.runplan([dict(load_kwh=None,pv_kwh=0,price_pln_kwh=1,hours=1)],topology_confirmed=True)
if __name__=='__main__':unittest.main()
