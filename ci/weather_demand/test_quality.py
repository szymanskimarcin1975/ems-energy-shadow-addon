import copy,json,sqlite3,subprocess,sys,tempfile,unittest
from pathlib import Path
from datetime import timedelta
from test_planning import fixture,T
from balance_quality import Quality
class Tests(unittest.TestCase):
 def setUp(self):self.c=sqlite3.connect(':memory:',isolation_level=None);self.q=Quality(self.c)
 def tearDown(self):self.c.close()
 def test_profile_requires_distinct_timed_snapshots(self):
  for i in range(7):
   s,_,at,_,o=fixture(T+timedelta(seconds=i*120));self.q.observe(s,at,o)
  r=self.q.summary(at);self.assertTrue(r['ready']);self.assertEqual(r['power_w'],300);self.assertIsNone(r['energy_integrated_kwh']);self.assertIsNone(r['device_report_coverage'])
 def test_repeat_does_not_refresh(self):
  s,_,at,_,o=fixture();self.q.observe(s,at,o)
  at2=(T+timedelta(seconds=20)).isoformat();self.assertEqual(self.q.observe(s,at2,o),'REPEATED_HA_SNAPSHOT');self.assertEqual(self.q.summary(at2)['unique_ha_snapshots'],1)
 def test_rest_cache_difference_not_a_new_ha_snapshot(self):
  s,_,at,_,o=fixture();self.q.observe(s,at,o)
  s['sensor.example_grid']['rest_state']='different_cached_state'
  s['sensor.example_grid']['rest_last_reported']='2026-10-01T00:00:00+00:00'
  self.assertEqual(self.q.observe(s,(T+timedelta(seconds=20)).isoformat(),o),'REPEATED_HA_SNAPSHOT')
 def test_negative_retained_and_rejected(self):
  s,_,at,_,o=fixture();s['sensor.example_grid']['state']='2';self.q.observe(s,at,o)
  row=json.loads(self.c.execute('select record from balance_checks').fetchone()[0]);self.assertEqual(row['candidate_building_w'],-1900);self.assertFalse(self.q.summary(at)['ready'])
 def test_gap_breaks_profile(self):
  for i in list(range(7))+[20]:
   s,_,at,_,o=fixture(T+timedelta(seconds=i*120));self.q.observe(s,at,o)
  self.assertFalse(self.q.summary(at)['ready'])
 def test_stale_and_skew(self):
  s,_,at,_,o=fixture();s['sensor.example_grid']['last_reported']=(T-timedelta(seconds=500)).isoformat();self.q.observe(s,at,o);self.assertEqual(self.q.summary(at)['unique_ha_snapshots'],0)
 def test_all_reasons_kept(self):
  s,_,at,_,o=fixture();s['sensor.example_ac_power']['last_reported']=(T+timedelta(seconds=30)).isoformat();s['sensor.example_grid']['last_reported']=(T-timedelta(seconds=500)).isoformat()
  self.q.observe(s,at,o);r=self.q.summary(at)['rejection_reason_counts_30m']
  self.assertEqual(r['FUTURE_AC'],1);self.assertEqual(r['STALE_M1'],1);self.assertEqual(r['HA_SKEW'],1)
 def test_rollback_no_partial(self):
  s,_,at,_,o=fixture();self.c.execute('pragma query_only=ON')
  with self.assertRaises(sqlite3.Error):self.q.observe(s,at,o)
  self.assertEqual(self.c.execute('select count(*) from balance_checks').fetchone()[0],0)
 def test_source_change_blocks_mixing(self):
  s,_,at,_,o=fixture();self.q.observe(s,at,o);o=copy.deepcopy(o);o['sources']['grid_kw']='sensor.example_other'
  with self.assertRaises(ValueError):self.q.observe(s,(T+timedelta(seconds=20)).isoformat(),o)
  self.assertEqual(self.c.execute('select count(*) from balance_checks').fetchone()[0],1)
 def test_reopen_in_separate_process(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'test.sqlite';c=sqlite3.connect(p,isolation_level=None);q=Quality(c);s,_,at,_,o=fixture();q.observe(s,at,o);c.close()
   out=subprocess.check_output([sys.executable,'-c',"import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(c.execute('pragma integrity_check').fetchone()[0],c.execute('select count(*) from balance_reports').fetchone()[0])",str(p)],text=True);self.assertEqual(out.strip(),'ok 1')
if __name__=='__main__':unittest.main()
