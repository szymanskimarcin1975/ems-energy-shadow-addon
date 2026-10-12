import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'app'))
import json
import tempfile
import threading
import unittest
import fcntl
import subprocess
import time
from http.server import HTTPServer
from unittest.mock import patch
import runner
from mock_api import Handler

OPTIONS=Path(__file__).parent/"example_options.json"

class RunnerTests(unittest.TestCase):
    def test_real_http_capture_proxy_path(self):
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with patch.dict('os.environ',HA_URL='http://127.0.0.1:'+str(server.server_port)+'/core',HA_TOKEN='dummy',NO_PROXY='127.0.0.1'):
                from settings import load_sources
                sample=runner.capture(load_sources(OPTIONS))
                from shadow import power
                self.assertEqual(power(sample)['building'],2000)
        finally:server.shutdown();server.server_close();thread.join()
    def sample(self, t='2026-10-12T08:00:00+00:00'):
        from datetime import datetime,timedelta
        stamp=(datetime.fromisoformat(t)-timedelta(seconds=5)).isoformat()
        s=dict(time=t,inverter_w=1000,grid_kw=-1,boiler_w=500,heatpump_w=300,
               boiler_kwh=10,heatpump_kwh=5,workday='on')
        for k in ('inverter','grid','boiler','heatpump','boiler_kwh','heatpump_kwh'): s[k+'_time']=stamp
        return s
    def test_run_stop_restart_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'report.yaml'; stop=threading.Event()
            def one(*_): stop.set(); return self.sample()
            with patch.dict('os.environ',SUPERVISOR_TOKEN='test-only'),patch.object(runner,'capture',one):
                runner.run(tmp,target,stop,options_path=OPTIONS)
            first=json.loads(target.read_text()); self.assertEqual(first['samples'],1)
            self.assertFalse(first['running']); self.assertEqual(first['valid_measurements_percent'],100)
            stop.clear()
            def two(*_): stop.set(); return self.sample('2026-10-12T08:00:20+00:00')
            with patch.dict('os.environ',SUPERVISOR_TOKEN='test-only'),patch.object(runner,'capture',two): runner.run(tmp,target,stop,options_path=OPTIONS)
            r=json.loads(target.read_text()); self.assertEqual(r['samples'],2)
            self.assertEqual(r['integrated_seconds'],0)
    def test_capture_failure_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'report.yaml'; stop=threading.Event()
            def fail(*_): stop.set(); raise RuntimeError('secret must not appear')
            with patch.dict('os.environ',SUPERVISOR_TOKEN='test-only'),patch.object(runner,'capture',fail): runner.run(tmp,target,stop,options_path=OPTIONS)
            r=json.loads(target.read_text()); self.assertEqual(r['failed_capture_attempts'],1)
            self.assertNotIn('secret',target.read_text())
    def test_second_instance_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(Path(tmp)/'observer.lock','a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError): runner.run(tmp,Path(tmp)/'report.yaml',options_path=OPTIONS)
    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'r.yaml'; p.symlink_to(Path(tmp)/'victim')
            with self.assertRaises(RuntimeError):runner.atomic_report(p,{})
    def test_real_process_sigterm_and_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=str(Path(__file__).resolve().parents[1]/'app')
            script='''import sys,os,signal,threading
sys.path.insert(0,sys.argv[1])
import runner
os.environ['SUPERVISOR_TOKEN']='test-only'
runner.capture=lambda *_: %s
e=threading.Event()
signal.signal(signal.SIGTERM,lambda *_: e.set())
runner.run(sys.argv[2],sys.argv[2]+'/report.yaml',e,options_path=sys.argv[3])
''' % repr(self.sample())
            p=subprocess.Popen([sys.executable,'-c',script,root,tmp,str(OPTIONS)],stdout=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    if (Path(tmp)/'report.yaml').exists():break
                    time.sleep(.02)
                self.assertTrue((Path(tmp)/'report.yaml').exists())
                p.terminate();self.assertEqual(p.wait(timeout=5),0)
                r=json.loads((Path(tmp)/'report.yaml').read_text())
                self.assertFalse(r['running']);self.assertEqual(r['samples'],1)
                self.assertTrue((Path(tmp)/'ledgers'/'synthetic_ci'/'shadow.sqlite').exists())
            finally:
                if p.poll() is None:p.kill();p.wait()

if __name__=='__main__':unittest.main()
