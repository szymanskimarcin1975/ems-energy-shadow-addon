import unittest
from datetime import datetime,timedelta,timezone
from cold_baseline import baseline
T=datetime(2026,10,16,tzinfo=timezone.utc)
def seq(n=46):
 return [dict(captured_at=(T+timedelta(seconds=i*20)).isoformat(),register_kwh=100+i/180,quality='valid',local={'temperature_c':10}) for i in range(n)]
class Tests(unittest.TestCase):
 def test_real_delta(self):
  r=seq();b=baseline(r,r[-1]['captured_at']);self.assertAlmostEqual(b['prediction_kwh'],1);self.assertFalse(b['valid_for_control'])
 def test_no_short_window(self):
  r=seq(45);self.assertIsNone(baseline(r,r[-1]['captured_at'])['prediction_kwh'])
 def test_gap(self):
  r=seq();del r[20:25];self.assertIsNone(baseline(r,r[-1]['captured_at'])['prediction_kwh'])
 def test_reset(self):
  r=seq();r[-1]['register_kwh']=0;self.assertIsNone(baseline(r,r[-1]['captured_at'])['prediction_kwh'])
 def test_invalid(self):
  r=seq();r[20]['quality']='invalid';self.assertIsNone(baseline(r,r[-1]['captured_at'])['prediction_kwh'])
 def test_stale(self):
  self.assertIsNone(baseline(seq(),(T+timedelta(hours=1)).isoformat())['prediction_kwh'])
 def test_no_fabricated_temperature_response(self):
  r=seq();b=baseline(r,r[-1]['captured_at']);self.assertFalse(b['temperature_response_identified']);self.assertIsNone(b['prediction_interval_kwh'])
if __name__=='__main__':unittest.main()
