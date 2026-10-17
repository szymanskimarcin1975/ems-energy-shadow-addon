import io,json,sys,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from meter_freshness_runtime import snapshot

class MockResponse(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self,*_): self.close()

class Tests(unittest.TestCase):
    def test_fresh_and_stale_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'options.json'
            p.write_text(json.dumps({'sources':{'boiler_w':'sensor.example_boiler','heatpump_w':'sensor.example_heatpump'}}))
            rows=[
                {'entity_id':'sensor.example_boiler','state':'400','last_reported':'2026-10-17T18:02:00+00:00'},
                {'entity_id':'sensor.example_heatpump','state':'100','last_reported':'2026-10-17T17:55:00+00:00'}]
            called=[]
            def opener(request,timeout):
                called.append((request.get_method(),timeout))
                return MockResponse(json.dumps(rows).encode())
            v=snapshot(str(p),token='example_not_real',opener=opener,now=datetime(2026,10,17,18,3,tzinfo=timezone.utc))
            self.assertEqual(v['sources']['boiler_w']['status'],'FRESH')
            self.assertEqual(v['sources']['heatpump_w']['status'],'STALE')
            self.assertEqual(called,[('GET',5)])
            self.assertNotIn('sensor.example_boiler',json.dumps(v))
            self.assertFalse(v['automatic_restart_permitted'])
    def test_unconfigured_fails_closed_without_io(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'options.json';p.write_text('{"sources":{}}')
            v=snapshot(str(p),token='test',opener=lambda *_:self.fail('network called'))
            self.assertEqual(v['status'],'SOURCES_NOT_CONFIGURED')
    def test_http_failure_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'options.json';p.write_text('{"sources":{"boiler_w":"a","heatpump_w":"b"}}')
            v=snapshot(str(p),token='test',opener=lambda *_: (_ for _ in ()).throw(OSError('failed')))
            self.assertEqual(v['status'],'READ_UNAVAILABLE')
if __name__=='__main__':unittest.main()
