"""New regression: repeated parent signals must not signal nested children twice."""
import os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
class SignalOnceTests(unittest.TestCase):
 def test_nested_gateway_forwards_term_once(self):
  with tempfile.TemporaryDirectory() as d:
   count=Path(d)/'count';ready=Path(d)/'ready'
   worker="import signal,time,pathlib; p=pathlib.Path("+repr(str(count))+"); deadline=None\ndef term(*_):\n global deadline\n p.write_text(p.read_text()+'T' if p.exists() else 'T'); deadline=time.monotonic()+.5\nsignal.signal(signal.SIGTERM,term); pathlib.Path("+repr(str(ready))+").touch()\nwhile deadline is None or time.monotonic()<deadline:time.sleep(.01)"
   wrapper="from staging.gateway import run; import sys; sys.exit(run("+repr([sys.executable,'-c',worker])+",grace=2,kill_grace=.2))"
   child=subprocess.Popen([sys.executable,'-c',wrapper],start_new_session=True)
   try:
    deadline=time.monotonic()+5
    while not ready.exists() and time.monotonic()<deadline:time.sleep(.01)
    self.assertTrue(ready.exists())
    child.send_signal(signal.SIGTERM);time.sleep(.15);child.send_signal(signal.SIGTERM)
    self.assertEqual(child.wait(timeout=5),0)
    self.assertEqual(count.read_text(),'T')
   finally:
    if child.poll() is None:
     os.killpg(child.pid,signal.SIGKILL);child.wait()
