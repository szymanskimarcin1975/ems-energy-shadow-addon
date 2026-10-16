import unittest,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app/observation'))
from weather_demand import temperature_feature,predict
class Tests(unittest.TestCase):
 def setUp(self):self.at=datetime(2026,10,16,12,tzinfo=timezone.utc);self.local={'status':'valid_ha_observation','temperature_c':5,'ha_reported_at':self.at.isoformat()}
 def f(self,local,lead=1):return temperature_feature(local,15,self.at.isoformat(),(self.at+timedelta(hours=lead)).isoformat())
 def test_actual_local_value_used_short_horizon(self):self.assertEqual(self.f(self.local)['temperature_c'],5)
 def test_future_weather_not_local_repeated_all_day(self):self.assertEqual(self.f(self.local,3)['temperature_c'],15)
 def test_missing_and_stale_local_fallback_to_forecast(self):
  self.assertEqual(self.f({})['temperature_c'],15);self.local['ha_reported_at']=(self.at-timedelta(seconds=901)).isoformat();self.assertFalse(self.f(self.local)['local_input_used'])
 def test_bad_local_no_zero_fill(self):
  self.local['temperature_c']='unavailable';self.assertEqual(self.f(self.local)['temperature_c'],15)
 def test_both_missing_has_no_value(self):self.assertIsNone(temperature_feature({},None,self.at.isoformat(),(self.at+timedelta(hours=1)).isoformat())['temperature_c'])
 def test_temperature_affects_supported_analogue_not_accuracy_claim(self):
  rows=[]
  for i in range(14):
   start=self.at-timedelta(days=i+1,hours=1);end=start+timedelta(hours=1)
   rows.append(dict(target='boiler',slot=14,day_type='workday',quality_approved=True,coverage=1,temperature_quality='approved',start=start.isoformat(),end=end.isoformat(),available_at=end.isoformat(),local_day=start.date().isoformat(),temperature_c=5 if i<7 else 15,kwh=2 if i<7 else .5))
  cold=predict(rows,self.at.isoformat(),14,'workday',self.f(self.local)['temperature_c']);warm=predict(rows,self.at.isoformat(),14,'workday',15)
  self.assertEqual(cold['prediction_kwh'],2);self.assertEqual(warm['prediction_kwh'],.5);self.assertFalse(cold['uncertainty_calibrated'])
 def test_insufficient_training_never_manufactured(self):self.assertIsNone(predict([],self.at.isoformat(),14,'workday',5)['prediction_kwh'])
