import unittest
from datetime import timedelta,datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
from test_planning import fixture,T
from test_household_advisory import history,APPROVAL
from household_advisory import schedule
from soc_profile import planning_policy
class Tests(unittest.TestCase):
 def run_at(self,now):
  states,pred,at,cfg,opt=fixture(now);cfg['include_current_slot']=True
  floor=now.replace(minute=0,second=0,microsecond=0)
  pv_rows=states['sensor.example_pv']['attributes']['detailedHourly']
  pv_rows.insert(0,dict(period_start=floor.isoformat(),pv_estimate=1,pv_estimate10=.5))
  while len(pv_rows)<48:
   prior=datetime.fromisoformat(pv_rows[-1]['period_start'])
   pv_rows.append(dict(period_start=(prior+timedelta(hours=1)).isoformat(),pv_estimate=1,pv_estimate10=.5))
  h=history();h['retrieved_at']=at
  with patch('household_advisory.load_history',return_value=h):return schedule(states,at,cfg,opt,None,{'current_ha_set_valid':True},planning_policy(APPROVAL))
 def test_partial_current_hour_and_rolling_48h(self):
  now=T+timedelta(minutes=15);r=self.run_at(now)
  for d in r['decisions']:
   rows=d['schedule'];self.assertEqual(rows[0]['valid_for'],now.isoformat());self.assertAlmostEqual(rows[0]['hours'],.75);self.assertEqual(len(rows),48);self.assertAlmostEqual(sum(s['hours'] for s in rows),47.75)
   for a,b in zip(rows,rows[1:]):self.assertEqual(a['valid_to'],b['valid_for'])
 def test_deadline_is_end_at_1600_not_1700(self):
  r=self.run_at(T+timedelta(hours=9,minutes=30)) # 15:30 local
  for d in r['decisions']:
   first=d['schedule'][0];self.assertEqual(datetime.fromisoformat(first['valid_to']).astimezone(ZoneInfo('Europe/Warsaw')).hour,16);self.assertAlmostEqual(first['hours'],.5);self.assertGreaterEqual(first['target_after_kwh'],0);self.assertLess(first['target_after_kwh'],9.2);self.assertFalse(d['workday_peak_preparation']['target_percent_fixed'])
 def test_temperature_response_is_explicitly_held_disabled(self):
  import demand_runtime,tempfile,json
  from pathlib import Path
  with tempfile.TemporaryDirectory() as d:
   store=demand_runtime.Store(Path(d)/'test.sqlite',{})
   try:
    for i in range(14):
     start=T-timedelta(days=i+1,hours=1);end=start+timedelta(hours=1)
     row=dict(target='boiler',slot=7,day_type='workday',quality_approved=True,coverage=1,temperature_quality='approved',temperature_c=5 if i<7 else 15,kwh=2 if i<7 else .5,start=start.isoformat(),end=end.isoformat(),available_at=end.isoformat(),local_day=start.date().isoformat())
     store.c.execute('INSERT INTO training VALUES(?,?)',(str(i),json.dumps(row)))
    def forecast(temp):
     record={'local':{'temperature_c':temp,'status':'valid_ha_observation','ha_reported_at':T.isoformat()}}
     store.c.execute('INSERT OR REPLACE INTO captures VALUES(?,?)',(T.isoformat(),json.dumps(record)))
     return store.forecast(T.isoformat(),[],'weather.example')
    cold=forecast(5);warm=forecast(15)
    self.assertFalse(cold['temperature_model_enabled']);a=cold['horizon'][0]['scenarios']['workday'];b=warm['horizon'][0]['scenarios']['workday']
    self.assertIsNotNone(a['prediction_kwh']);self.assertEqual(a['prediction_kwh'],b['prediction_kwh']);self.assertFalse(a['temperature_used'])
   finally:store.c.close()
