import io,json,os,signal,sqlite3,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from controller import read_requests
from gateway import run
class Tests(unittest.TestCase):
    def scenario(self,controller=None,kill=False):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);marker=root/'samples';pid=root/'pid'
            observer="import time,pathlib; p=pathlib.Path(%r); n=0\nwhile True:\n n+=1;q=p.with_suffix('.tmp');q.write_text(str(n));q.replace(p);time.sleep(.02)"%str(marker)
            program="import sys,pathlib,os;sys.path.insert(0,%r);from gateway import run;pathlib.Path(%r).write_text(str(os.getpid()));raise SystemExit(run(%r,%r,retry=.05,grace=.2,kill_grace=.2))"%(str(Path(__file__).resolve().parent),str(pid),[sys.executable,'-c',observer],controller)
            child=subprocess.Popen([sys.executable,'-c',program],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+3
                while not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
                self.assertTrue(marker.exists());time.sleep(.12);before=int(marker.read_text());time.sleep(.2)
                self.assertGreater(int(marker.read_text()),before)
                child.send_signal(signal.SIGINT if kill else signal.SIGTERM)
                out,err=child.communicate(timeout=2);self.assertEqual(child.returncode,0,err.decode())
                return out.decode()
            finally:
                if child.poll() is None:
                    child.terminate()
                    try:child.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        child.kill();child.communicate(timeout=1)
    def test_disabled_no_controller(self):self.assertIn('DISABLED',self.scenario())
    def test_controller_spawn_failure(self):self.assertIn('controller_start_failed',self.scenario(['/nonexistent/synthetic']))
    def test_controller_init_failure(self):self.assertIn('controller_exited',self.scenario([sys.executable,'-c','import sqlite3;raise sqlite3.DatabaseError()']))
    def test_controller_runtime_failure(self):self.assertIn('controller_exited',self.scenario([sys.executable,'-c','import time;time.sleep(.1);raise OSError()']))
    def test_controller_blocked_close_bounded(self):self.scenario([sys.executable,'-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)'])
    def test_sigint(self):self.scenario([sys.executable,'-c','import time;time.sleep(60)'],True)
    def test_sqlite_submit_failure_visible(self):
        with self.assertRaises(sqlite3.OperationalError):read_requests(io.StringIO('{}\n'),lambda _:(_ for _ in ()).throw(sqlite3.OperationalError()))
    def test_stdin_io_failure(self):
        class Broken:
            def readline(self,*_):raise OSError()
        with self.assertRaises(OSError):read_requests(Broken(),lambda _:None)

class ActualControllerTests(unittest.TestCase):
    scenario=Tests.scenario
    def command(self,body):
        return [sys.executable,'-c',"import sys;sys.path.insert(0,%r);"%str(Path(__file__).resolve().parent)+body]
    def test_actual_corrupt_control_database(self):
        self.scenario(self.command("import tempfile,pathlib;from controller import Controller;t=tempfile.TemporaryDirectory();pathlib.Path(t.name,'requests.sqlite').write_bytes(b'not sqlite');Controller(t.name,'synthetic',lambda r,s:None,True)"))
    def test_actual_directory_failure(self):
        self.scenario(self.command("import tempfile,pathlib;from controller import Controller;t=tempfile.TemporaryDirectory();p=pathlib.Path(t.name,'file');p.write_text('x');Controller(p,'synthetic',lambda r,s:None,True)"))
    def test_actual_lock_failure(self):
        self.scenario(self.command("import tempfile;from controller import Controller;t=tempfile.TemporaryDirectory();c=Controller(t.name,'synthetic',lambda r,s:None,True);Controller(t.name,'synthetic',lambda r,s:None,True)"))
    def test_actual_stdin_failure(self):
        self.scenario(self.command("from controller import read_requests;read_requests(None,lambda r:None)"))
    def test_future_database_failure_disables_requests(self):
        from controller import Controller
        from test_controller import request
        with tempfile.TemporaryDirectory() as d:
            c=Controller(d,'synthetic',lambda r,s:None,True)
            try:
                with patch.object(c,'_status',side_effect=sqlite3.OperationalError()):
                    c.submit(request())
                    with self.assertRaises(sqlite3.OperationalError):c.future.result(timeout=2)
                    deadline=time.monotonic()+1
                    while not c.stop.is_set() and time.monotonic()<deadline:time.sleep(.01)
                    self.assertTrue(c.stop.is_set())
            finally:c.close()
