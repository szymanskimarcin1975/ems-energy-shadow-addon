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
