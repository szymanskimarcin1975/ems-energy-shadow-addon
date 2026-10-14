import sys,tempfile,unittest,sqlite3,threading,time,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shadow import Shadow
from exporter import export,validate
from analyzer import analyze,union_seconds
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.ledger=self.root/'test_ledger';self.ledger.mkdir();self.src=self.ledger/'shadow.sqlite';self.dst=self.root/'export.sqlite';self.sh=Shadow(self.src)
        self.sh.con.execute("INSERT INTO state VALUES('sources_digest','synthetic')");self.sh.con.commit()
        for sec in (0,20):
            t=datetime(2024,7,1,8,0,0,tzinfo=timezone.utc)+timedelta(seconds=sec);stamp=(t-timedelta(seconds=2)).isoformat()
            self.sh.process(dict(time=t.isoformat(),inverter_time=stamp,grid_time=stamp,boiler_time=stamp,heatpump_time=stamp,inverter_w=1000,grid_kw=0,boiler_w=500,heatpump_w=300,boiler_kwh=0,heatpump_kwh=0,boiler_kwh_time=stamp,heatpump_kwh_time=stamp,workday='on'))
    def tearDown(self):self.sh.close();self.tmp.cleanup()
    def run_export(self,**kw):return export(self.src,self.dst,'test_ledger','synthetic',**kw)
    def test_active_wal(self):
        self.assertTrue(Path(str(self.src)+'-wal').exists());r=self.run_export();self.assertTrue(r['complete']);self.assertEqual(r['samples'],2)
    def test_concurrent_write(self):
        stop=threading.Event()
        def writer():
            c=sqlite3.connect(self.src)
            try:
                while not stop.is_set():c.execute("INSERT OR REPLACE INTO state VALUES('synthetic_counter',?)",(str(time.time_ns()),));c.commit();time.sleep(.002)
            finally:c.close()
        t=threading.Thread(target=writer);t.start()
        try:self.assertTrue(self.run_export()['complete'])
        finally:stop.set();t.join()
    def test_uncommitted_not_exported(self):
        self.sh.con.execute('BEGIN IMMEDIATE');self.sh.con.execute("INSERT INTO events VALUES('pending','synthetic')")
        try:
            self.run_export();c=sqlite3.connect(self.dst)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM events WHERE sample_id='pending'").fetchone()[0],0);c.close()
        finally:self.sh.con.rollback()
    def test_disk_failure_after_backup(self):
        with patch('exporter.os.fsync',side_effect=OSError('simulated disk IO failure')):
            with self.assertRaises(OSError):self.run_export()
        self.assertFalse(self.dst.with_suffix('.manifest.json').exists())
        self.assertEqual(self.sh.con.execute('SELECT COUNT(*) FROM samples').fetchone()[0],2)
    def test_digest(self):
        with self.assertRaises(ValueError):export(self.src,self.dst,'test_ledger','wrong')
        self.assertFalse(self.dst.exists())
    def test_cancel(self):
        with self.assertRaises(TimeoutError):self.run_export(cancel=lambda:True)
        self.assertFalse(self.dst.exists())
    def test_destination_exists(self):
        self.dst.write_bytes(b'keep')
        with self.assertRaises(ValueError):self.run_export()
        self.assertEqual(self.dst.read_bytes(),b'keep')
    def test_wrong_ledger(self):
        with self.assertRaises(ValueError):export(self.src,self.dst,'wrong','synthetic')
    def test_source_read_only(self):
        c=sqlite3.connect(self.src.resolve().as_uri()+'?mode=ro',uri=True)
        with self.assertRaises(sqlite3.OperationalError):c.execute('DELETE FROM state')
        c.close()
    def test_disk_failure(self):
        with patch('exporter.os.open',side_effect=OSError('full')):
            with self.assertRaises(OSError):self.run_export()
        self.assertFalse(self.dst.exists())
    def test_corrupt(self):
        self.sh.close();self.src.write_bytes(b'broken');self.sh=type('Closed',(),{'close':lambda s:None})()
        with self.assertRaises(sqlite3.DatabaseError):self.run_export()
    def test_schema(self):
        self.sh.con.execute('DROP TABLE events');self.sh.con.commit()
        with self.assertRaises(ValueError):self.run_export()
    def test_grids_and_incomplete_export(self):
        self.run_export();r=analyze(self.dst,self.dst.with_suffix('.manifest.json'),'2024-07-01T10:00:00+02:00','2024-07-02T10:00:00+02:00')
        self.assertEqual([len(r['grids'][k]) for k in ('60','15','30')],[24,96,48]);self.assertAlmostEqual(r['grids']['60'][0]['categories']['building']['coverage_percent'],20/3600*100)
        self.dst.write_bytes(b'truncated')
        with self.assertRaises(ValueError):analyze(self.dst,self.dst.with_suffix('.manifest.json'),'2024-07-01T10:00:00+02:00','2024-07-02T10:00:00+02:00')
    def test_union_no_duplicates(self):
        a=datetime.now(timezone.utc);self.assertEqual(union_seconds([(a,a+timedelta(seconds=20)),(a,a+timedelta(seconds=20)),(a+timedelta(seconds=10),a+timedelta(seconds=30))]),30)
if __name__=='__main__':unittest.main()

class DiagnosticTests(unittest.TestCase):
    def test_all_reasons(self):
        from analyzer import source_quality
        s=dict(time='2024-07-02T10:00:00+00:00',inverter_time='2024-07-02T09:59:59+00:00',grid_time='2024-07-02T09:59:50+00:00',boiler_time='2024-07-02T09:50:00+00:00',heatpump_time='2024-07-02T10:00:00+00:00',inverter_w=100,grid_kw=0,boiler_w=200,heatpump_w=250,workday='on')
        r=source_quality(s);self.assertIn('solar_skew',r['inverter']);self.assertIn('stale',r['boiler']);self.assertIn('too_fresh',r['heatpump']);self.assertIn('inconsistent',r['balance'])
    def test_clipped_intervals(self):
        a=datetime(2024,7,2,tzinfo=timezone.utc);left=a+timedelta(seconds=5);right=a+timedelta(seconds=15)
        self.assertEqual(union_seconds([(max(a,left),min(a+timedelta(seconds=20),right))]),10)

class SafetyAuditTests(unittest.TestCase):
    def test_blocked_worker_bounded(self):
        from exporter import run_bounded
        begin=time.monotonic()
        with self.assertRaises(TimeoutError):run_bounded([sys.executable,'-c','import time;time.sleep(60)'],.1)
        self.assertLess(time.monotonic()-begin,3)
    def test_bounded_success(self):
        from exporter import export_bounded
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ledger=root/'synthetic';ledger.mkdir();s=Shadow(ledger/'shadow.sqlite')
            try:
                s.con.execute("INSERT INTO state VALUES('sources_digest','test')");s.con.commit()
                r=export_bounded(ledger/'shadow.sqlite',root/'snapshot.sqlite','synthetic','test',timeout=5)
                self.assertTrue(r['complete'])
            finally:s.close()
    def test_shm_observation_and_db_wal_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ledger=root/'synthetic';ledger.mkdir();source=ledger/'shadow.sqlite';s=Shadow(source)
            try:
                s.con.execute("INSERT INTO state VALUES('sources_digest','test')");s.con.commit()
                paths=[source,Path(str(source)+'-wal'),Path(str(source)+'-shm')]
                before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
                export(source,root/'snapshot.sqlite','synthetic','test')
                after=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
                self.assertEqual(before[:2],after[:2])
                # Observation only: SHM changes are legal SQLite read coordination.
                print('synthetic_shm_changed='+str(before[2]!=after[2]))
            finally:s.close()
    def test_failing_manifest_sync_not_published(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ledger=root/'synthetic';ledger.mkdir();source=ledger/'shadow.sqlite';s=Shadow(source)
            try:
                s.con.execute("INSERT INTO state VALUES('sources_digest','test')");s.con.commit()
                calls=[0];original=__import__('os').fsync
                def fail_second(fd):
                    calls[0]+=1
                    if calls[0]==2:raise OSError('simulated full disk')
                    return original(fd)
                with patch('exporter.os.fsync',side_effect=fail_second):
                    with self.assertRaises(OSError):export(source,root/'snapshot.sqlite','synthetic','test')
                self.assertFalse((root/'snapshot.manifest.json').exists())
            finally:s.close()
