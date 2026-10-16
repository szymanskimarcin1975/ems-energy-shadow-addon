import json,unittest
from unittest.mock import patch
from io import BytesIO
from ha_state_times import refresh
class API:base='http://synthetic';token='synthetic-only'
T='2026-10-16T05:00:00+00:00'
class Tests(unittest.TestCase):
 def test_consistent_value_and_times_with_original_retained(self):
  states={'sensor.example_snapshot':dict(state='1',last_reported='2026-10-01T00:00:00+00:00',attributes={})}
  rows={'sensor.example_snapshot':dict(state='2',unit='W',last_reported=T,last_updated=T,last_changed=T)}
  with patch('ha_state_times.urlopen',return_value=BytesIO(json.dumps(rows).encode())):refresh(API(),states,['sensor.example_snapshot'])
  self.assertEqual(states['sensor.example_snapshot']['state'],'2');self.assertEqual(states['sensor.example_snapshot']['rest_state'],'1');self.assertEqual(states['sensor.example_snapshot']['last_reported'],T)
 def test_failure_not_replaced_with_now(self):
  states={'sensor.example_snapshot':dict(state='1',last_reported=T)}
  with patch('ha_state_times.urlopen',side_effect=OSError('synthetic')):refresh(API(),states,['sensor.example_snapshot'])
  self.assertIsNone(states['sensor.example_snapshot']['last_reported'])
 def test_no_arbitrary_template_injection(self):
  with self.assertRaises(ValueError):refresh(API(),{},["sensor.example_bad' }} {{ secret"])
if __name__=='__main__':unittest.main()
