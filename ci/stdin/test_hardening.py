import sys,tempfile,threading,subprocess,unittest,time,json
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parent))
from worker import supervised,Monitor,ResourceLimit
class Tests(unittest.TestCase):
    def test_publication_hang_is_bounded(self):
        with self.assertRaises(TimeoutError):supervised([sys.executable,'-c','import time; time.sleep(60)'],threading.Event(),.1)
    def test_monitor_cancels_child(self):
        with self.assertRaises(ResourceLimit):supervised([sys.executable,'-c','import time;time.sleep(60)'],threading.Event(),5,monitor=lambda pid:(_ for _ in ()).throw(ResourceLimit('ram_budget')))
    def test_stop_unconfirmed(self):
        child=Mock();child.communicate.side_effect=subprocess.TimeoutExpired('synthetic',1)
        with patch('worker.subprocess.Popen',return_value=child):
            with self.assertRaisesRegex(RuntimeError,'worker_stop_unconfirmed'):supervised(['synthetic'],threading.Event(),0)
        child.kill.assert_called_once()
    def test_wal_growth_limit(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'shadow.sqlite';m=Monitor(source)
            with open(str(source)+'-wal','wb') as f:f.truncate(65*1024*1024)
            with self.assertRaises(ResourceLimit):m(__import__('os').getpid())
    def test_insufficient_cadence_is_not_success(self):
        with tempfile.TemporaryDirectory() as d:self.assertEqual(Monitor(Path(d)/'x').summary()['impact_conclusion'],'insufficient_observation')
    def test_observer_stale(self):
        with tempfile.TemporaryDirectory() as d:
            report=Path(d)/'report';report.write_text(json.dumps(dict(running=True,samples=10,last_sample='2026-01-01T00:00:00+00:00')))
            with self.assertRaises(ResourceLimit):Monitor(Path(d)/'x',report)(__import__('os').getpid())
if __name__=='__main__':unittest.main()

class FailureTests(unittest.TestCase):
    def test_report_write_failure_preserves_old_file(self):
        from controller import atomic_json
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'report.yaml';p.write_text('old')
            with patch('controller.os.fsync',side_effect=OSError('synthetic write failure')):
                with self.assertRaises(OSError):atomic_json(p,{'new':'aggregate'})
            self.assertEqual(p.read_text(),'old')
    def test_failed_request_not_retried_after_restart(self):
        from controller import Controller
        from test_controller import request
        with tempfile.TemporaryDirectory() as d:
            c=Controller(d,'synthetic',lambda r,s:(_ for _ in ()).throw(OSError('write failure')),enabled=True,cooldown=0)
            r=request();c.submit(r);c.future.result();self.assertEqual(c.db.execute('SELECT status FROM requests').fetchone()[0],'FAILED');c.close()
            c=Controller(d,'synthetic',lambda r,s:None,enabled=True,cooldown=0)
            try:
                with self.assertRaises(ValueError):c.submit(r)
            finally:c.close()
    def test_low_available_ram(self):
        original=Path.read_text
        def read(p,*args,**kw):
            if str(p)=='/proc/meminfo':return 'MemAvailable: 1 kB\n'
            return original(p,*args,**kw)
        with tempfile.TemporaryDirectory() as d,patch.object(Path,'read_text',read):
            with self.assertRaises(ResourceLimit):Monitor(Path(d)/'x')(__import__('os').getpid())
