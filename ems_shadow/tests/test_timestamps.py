import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from shadow import snapshot_from_states, power, Shadow

class TimestampTests(unittest.TestCase):
    def setUp(self):
        self.sources=json.loads((Path(__file__).parent/'example_options.json').read_text())['sources']
        self.now=datetime(2026,10,12,8,0,tzinfo=timezone.utc)
        self.stamp=(self.now-timedelta(seconds=5)).isoformat()
        values=dict(inverter_w='1000',grid_kw='-1',boiler_w='500',heatpump_w='300',boiler_kwh='10',heatpump_kwh='5',workday='on')
        self.rows=[dict(entity_id=id,state=values[k],last_changed=self.stamp,last_updated=self.stamp,attributes={}) for k,id in self.sources.items()]
    def test_rest_iso_and_absent_reported(self):
        s=snapshot_from_states(self.sources,self.rows,self.now)
        self.assertEqual(power(s)['building'],2000)
        self.assertEqual(s['source_diagnostics']['inverter_w']['timestamp_field'],'last_updated')
    def test_null_numeric_empty_bad_reported_fallback(self):
        for bad in (None,123,{},[],True,'','bad','2026-10-12T08:00:00'):
            rows=json.loads(json.dumps(self.rows));rows[0]['last_reported']=bad
            s=snapshot_from_states(self.sources,rows,self.now)
            self.assertEqual(power(s)['building'],2000)
            self.assertEqual(s['source_diagnostics']['inverter_w']['timestamp_field'],'last_updated')
    def test_changed_fallback_conservative_age(self):
        self.rows[0]['last_updated']=None
        s=snapshot_from_states(self.sources,self.rows,self.now)
        self.assertEqual(s['source_diagnostics']['inverter_w']['timestamp_field'],'last_changed')
        self.rows[0]['last_changed']=(self.now-timedelta(hours=1)).isoformat()
        self.rows[1]['last_updated']=self.rows[0]['last_changed']
        with self.assertRaisesRegex(ValueError,'stale'):power(snapshot_from_states(self.sources,self.rows,self.now))
    def test_missing_entity_precise_error_and_no_power_energy(self):
        s=snapshot_from_states(self.sources,self.rows[1:],self.now)
        self.assertFalse(s['source_diagnostics']['inverter_w']['entity_present'])
        with tempfile.TemporaryDirectory() as tmp:
            sh=Shadow(Path(tmp)/'s.sqlite')
            try:
                self.assertEqual(sh.process(s),'invalid_timestamp_inverter_time')
                s['time']=(self.now+timedelta(seconds=20)).isoformat();sh.process(s)
                self.assertEqual(sh.report()['integrated_seconds'],0)
                self.assertEqual(sh.report()['energy'],[])
            finally:sh.close()
    def test_all_invalid_no_fabricated_timestamp(self):
        self.rows[0].update(last_reported=None,last_updated=1,last_changed='invalid')
        s=snapshot_from_states(self.sources,self.rows,self.now)
        self.assertIsNone(s['inverter_time'])
        with self.assertRaisesRegex(ValueError,'invalid_timestamp_inverter_time'):power(s)
    def test_reported_is_preferred(self):
        self.rows[0]['last_reported']=self.stamp
        self.assertEqual(snapshot_from_states(self.sources,self.rows,self.now)['source_diagnostics']['inverter_w']['timestamp_field'],'last_reported')

if __name__=='__main__':unittest.main()
