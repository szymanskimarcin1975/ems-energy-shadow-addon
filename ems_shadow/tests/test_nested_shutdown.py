"""Real process regression: nested shutdown may need up to 17s, container budget 30s."""
import subprocess,sys,unittest
from observation.shutdown_budget import shutdown_all
class NestedShutdownTests(unittest.TestCase):
 def test_nested_legacy_gets_grace_before_outer_kill(self):
  code="import signal,time,sys; signal.signal(signal.SIGTERM,lambda *_:(time.sleep(11),sys.exit(0))); print('ready',flush=True); time.sleep(60)"
  child=subprocess.Popen([sys.executable,'-c',code],start_new_session=True,stdout=subprocess.PIPE,text=True)
  try:
   self.assertEqual(child.stdout.readline().strip(),'ready')
   result=shutdown_all(child,[],budget=22)
   self.assertEqual(result['state'],'STOPPED')
   self.assertEqual(child.returncode,0,'outer supervisor killed nested graceful shutdown')
   self.assertLess(result['elapsed_seconds'],22)
  finally:
   if child.poll() is None:child.kill();child.wait()
   child.stdout.close()
