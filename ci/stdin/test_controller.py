import sys,unittest,tempfile,threading,io,time
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parent))
from controller import Controller,validate,read_requests,aggregate_report
from worker import supervised
NOW=lambda:datetime.now(timezone.utc)
def request(id='request_0001'):
    n=NOW();return dict(operation='diagnostic_export',request_id=id,ledger_id='synthetic',expires_at=(n+timedelta(seconds=120)).isoformat(),start=(n-timedelta(days=2)).isoformat(),end=(n-timedelta(days=1)).isoformat())
class Tests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.c=None
    def tearDown(self):
        if self.c:self.c.close()
        self.tmp.cleanup()
    def controller(self,worker=lambda r,s:None,enabled=True):self.c=Controller(self.tmp.name,'synthetic',worker,enabled,cooldown=0);return self.c
    def test_disabled(self):
        self.controller(enabled=False)
        with self.assertRaises(ValueError):self.c.submit(request())
    def test_valid(self):self.controller();self.assertEqual(self.c.submit(request()),'ACCEPTED');self.c.future.result();self.assertEqual(self.c.db.execute('SELECT status FROM requests').fetchone()[0],'COMPLETE')
    def test_operation(self):
        r=request();r['operation']='shell'
        with self.assertRaises(ValueError):validate(r,'synthetic',NOW())
    def test_id(self):
        r=request();r['request_id']='../../x'
        with self.assertRaises(ValueError):validate(r,'synthetic',NOW())
    def test_ledger(self):
        with self.assertRaises(ValueError):validate(request(),'wrong',NOW())
    def test_expired(self):
        r=request();r['expires_at']=(NOW()-timedelta(seconds=1)).isoformat()
        with self.assertRaises(ValueError):validate(r,'synthetic',NOW())
    def test_extra_field(self):
        r=request();r['command']='danger'
        with self.assertRaises(ValueError):validate(r,'synthetic',NOW())
    def test_duplicate_persisted(self):
        self.controller();r=request();self.c.submit(r);self.c.future.result();self.c.close();self.c=None;self.controller()
        with self.assertRaises(ValueError):self.c.submit(r)
    def test_single_active(self):
        event=threading.Event();self.controller(worker=lambda r,s:event.wait(2));self.c.submit(request())
        try:
            with self.assertRaises(ValueError):self.c.submit(request('request_0002'))
        finally:event.set();self.c.future.result()
    def test_unknown_restart(self):
        self.controller();self.c.db.execute("INSERT INTO requests VALUES('old',0,'RUNNING',NULL)");self.c.db.commit();self.c.close();self.c=None;self.controller()
        with self.assertRaises(ValueError):self.c.submit(request())
    def test_stdin_duplicates_and_oversize(self):
        calls=[];read_requests(io.StringIO('{"x":1,"x":2}\n'+'x'*5000+'\n{}\n'),calls.append);self.assertEqual(calls,[{}])
    def test_safe_projection(self):
        r=aggregate_report({'grids':{},'raw':'secret','token':'secret'},request());self.assertNotIn('secret',str(r))
    def test_timeout(self):
        with self.assertRaises(TimeoutError):supervised([sys.executable,'-c','import time;time.sleep(60)'],threading.Event(),.1)
    def test_cancel(self):
        stop=threading.Event();stop.set()
        with self.assertRaises(TimeoutError):supervised([sys.executable,'-c','import time;time.sleep(60)'],stop,5)
if __name__=='__main__':unittest.main()

class IntegrationTests(unittest.TestCase):
    def test_worker_backup_and_safe_report(self):
        import hashlib,json
        app=Path(__file__).resolve().parents[2]/'ems_shadow/app'
        if not app.exists():app=Path('/app')
        sys.path.insert(0,str(app))
        from shadow import Shadow
        from worker import Worker
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ledger=root/'ledgers/synthetic';ledger.mkdir(parents=True);s=Shadow(ledger/'shadow.sqlite')
            try:
                s.con.execute("INSERT INTO state VALUES('sources_digest','synthetic')");s.con.commit()
                for sec in (0,20):
                    t=NOW()-timedelta(days=1)+timedelta(seconds=sec);stamp=(t-timedelta(seconds=2)).isoformat()
                    s.process(dict(time=t.isoformat(),inverter_time=stamp,grid_time=stamp,boiler_time=stamp,heatpump_time=stamp,inverter_w=1000,grid_kw=0,boiler_w=500,heatpump_w=300,boiler_kwh=0,heatpump_kwh=0,boiler_kwh_time=stamp,heatpump_kwh_time=stamp,workday='on'))
                modules=app/'diagnostic_export'
                if not modules.exists():modules=Path('/app/diagnostic_export')
                worker=Worker(root,root/'reports','synthetic','synthetic',modules,app)
                r=request();worker(r,threading.Event())
                report=json.loads((root/'reports/request_0001.yaml').read_text());self.assertEqual([len(report['grids'][k]) for k in ('60','15','30')],[24,96,48]);self.assertNotIn('inverter_w',str(report));self.assertNotIn('raw',report)
                self.assertTrue((root/'diagnostic_exports/request_0001/snapshot.sqlite').exists());self.assertFalse(any(p.suffix=='.sqlite' for p in (root/'reports').iterdir()))
            finally:s.close()
    def test_cooldown_and_quota(self):
        with tempfile.TemporaryDirectory() as d:
            c=Controller(d,'synthetic',lambda r,s:None,enabled=True,cooldown=60,max_exports=2)
            try:
                c.submit(request());c.future.result()
                with self.assertRaises(ValueError):c.submit(request('request_0002'))
            finally:c.close()
    def test_second_controller_refused(self):
        with tempfile.TemporaryDirectory() as d:
            c=Controller(d,'synthetic',lambda r,s:None,enabled=True)
            try:
                with self.assertRaises(BlockingIOError):Controller(d,'synthetic',lambda r,s:None,enabled=True)
            finally:c.close()
    def test_long_expiration(self):
        r=request();r['expires_at']=(NOW()+timedelta(hours=1)).isoformat()
        with self.assertRaises(ValueError):validate(r,'synthetic',NOW())
