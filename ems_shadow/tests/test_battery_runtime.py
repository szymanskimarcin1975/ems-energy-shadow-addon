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
