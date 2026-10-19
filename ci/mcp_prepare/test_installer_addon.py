"""No production network, Core or device commands."""
import importlib.util,json,os,subprocess,tempfile,unittest,zipfile,hashlib
from pathlib import Path
from unittest.mock import patch,MagicMock
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('addon',ROOT/'mcp_installer/runner.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class AddonTests(unittest.TestCase):
 def test_supervisor_json_without_newline_is_processed(self):
  requests,left=a.decode_requests('',b'{"action":"preflight"}')
  self.assertEqual(requests,[{'action':'preflight'}]);self.assertEqual(left,'')
 def test_split_stdin_and_multiple_messages(self):
  requests,left=a.decode_requests('',b'{"action":')
  self.assertEqual(requests,[])
  requests,left=a.decode_requests(left,b'"status"}{"action":"preflight"}')
  self.assertEqual(requests,[{'action':'status'},{'action':'preflight'}]);self.assertEqual(left,'')
 def test_oversize_stdin_refused(self):
  with self.assertRaises(ValueError):a.decode_requests('',b'x'*8193)
 def test_permissions_and_no_public_listener(self):
  text=(ROOT/'mcp_installer/config.yaml').read_text()
  for x in ('homeassistant_api: true','hassio_api: true','hassio_role: manager','boot: manual','path: /config'):self.assertIn(x,text)
  for x in ('ports:','host_network:','docker_api:','privileged:'):self.assertNotIn(x,text)
 def test_python_is_in_image_not_installed_at_runtime(self):
  s=(ROOT/'mcp_installer/Dockerfile').read_text();self.assertIn('python:3.14.8-slim',s);self.assertNotIn('apk add',s)
 def test_no_automatic_deploy(self):
  with patch.object(a.subprocess,'Popen') as run:
   c=a.Controller();self.assertIsNone(c.worker);run.assert_not_called()
 def test_explicit_restart_confirmation_required(self):
  with patch.object(a.subprocess,'Popen') as run,self.assertRaises(ValueError):a.Controller().handle({'action':'deploy','confirmation':'yes'})
  run.assert_not_called()
 def test_no_parallel_worker(self):
  c=a.Controller();c.worker=MagicMock();c.worker.poll.return_value=None
  with patch.object(a.subprocess,'Popen') as run,self.assertRaises(ValueError):c.handle({'action':'preflight'})
  run.assert_not_called()
 def test_no_shell_or_arbitrary_command(self):
  with patch.object(a.subprocess,'Popen') as run:
   for r in ({'action':'shell'},{'action':'preflight','path':'/etc'},{'action':'deploy','confirmation':'CONFIRM_CORE_RESTART','cmd':'id'}):
    with self.assertRaises(ValueError):a.Controller().handle(r)
   run.assert_not_called()
 def test_deploy_is_detached_from_stdin(self):
  with patch.object(a.subprocess,'Popen') as run:
   a.Controller().handle({'action':'deploy','confirmation':'CONFIRM_CORE_RESTART'})
   self.assertEqual(run.call_args.kwargs['stdin'],subprocess.DEVNULL)
   self.assertNotIn('shell',run.call_args.kwargs)
 def test_stage_bad_sha_never_extracts(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'package.zip';p.write_bytes(b'not zip')
   with patch.object(a,'PACKAGE',p),patch.object(a,'STAGE',Path(t)/'stage'),self.assertRaises(ValueError):a.stage('0'*64)
   self.assertFalse((Path(t)/'stage').exists())
 def test_archive_traversal_refused(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'package.zip'
   with zipfile.ZipFile(p,'w') as z:z.writestr('../evil.py','x')
   with patch.object(a,'PACKAGE',p),patch.object(a,'STAGE',Path(t)/'stage'),self.assertRaises(ValueError):a.stage(hashlib.sha256(p.read_bytes()).hexdigest())
   self.assertFalse((Path(t)/'stage').exists())
 def test_supervisor_unknown_is_not_retried(self):
  import sys
  sys.path.insert(0,str(ROOT/'tools/mcp_prepare'))
  from deployment_core import Deployment,Blocked
  with patch('deployment_core.subprocess.run',return_value=MagicMock(returncode=70)) as run,self.assertRaises(Blocked):Deployment.run_core('start')
  self.assertEqual(run.call_count,1)
if __name__=='__main__':unittest.main(verbosity=2)
