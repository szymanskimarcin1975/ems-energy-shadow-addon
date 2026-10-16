import unittest
from building_balance import inspect
T='2026-10-16T05:00:00+00:00'
def state(v,u,t=T):return dict(state=str(v),attributes={'unit_of_measurement':u},last_reported=t)
class Tests(unittest.TestCase):
 def test_charging_not_double_counted(self):
  r=inspect(state(-5074,'W'),state(-5.397,'kW'),T);self.assertAlmostEqual(r['candidate_building_w'],323);self.assertFalse(r['control_enabled']);self.assertFalse(r['battery_added_separately'])
 def test_negative_retained_not_clamped(self):
  r=inspect(state(468.5,'W'),state(2.047,'kW'),T);self.assertEqual(r['status'],'INCONSISTENT_NEGATIVE_LOAD');self.assertLess(r['candidate_building_w'],0)
 def test_no_topology_assumption(self):self.assertEqual(inspect(state(100,'W'),state(-.3,'kW'),T)['status'],'DIAGNOSTIC_ONLY')
 def test_invalid_not_zero(self):self.assertIsNone(inspect(state('unavailable','W'),state(0,'kW'),T)['candidate_building_w'])
 def test_wrong_units(self):self.assertEqual(inspect(state(1,'kW'),state(0,'kW'),T)['status'],'INVALID_INPUT')
 def test_future(self):self.assertEqual(inspect(state(1,'W','2026-10-16T06:00:00+00:00'),state(0,'kW'),T)['status'],'INVALID_INPUT')
if __name__=='__main__':unittest.main()
