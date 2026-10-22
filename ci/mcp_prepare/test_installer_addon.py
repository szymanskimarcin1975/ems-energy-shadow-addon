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
 def test_status_without_deployment_is_explicit(self):
  import types
  fake=types.SimpleNamespace(BACK=Path('/missing'),status=MagicMock(side_effect=FileNotFoundError))
  with patch.dict('sys.modules',{'manual_ack_watchdog':fake}):
   self.assertEqual(a.Controller().handle({'action':'status'}),{'phase':'IDLE_NO_DEPLOYMENT_RECORD'})
 def test_startup_message_is_present_and_unbuffered(self):
  self.assertIn('READY_PACKAGE_VERIFIED_WAITING_FOR_REQUEST_NO_APPLY',(ROOT/'mcp_installer/runner.py').read_text())
  self.assertIn('PYTHONUNBUFFERED=1',(ROOT/'mcp_installer/Dockerfile').read_text())
 def test_read_only_stage_reopen_and_tamper_refusal(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);p=root/'package.zip';st=root/'stage';st.mkdir()
   with zipfile.ZipFile(p,'w') as z:
    for name in a.ALLOWED:z.writestr('package/'+name,'content-'+name);(st/name).write_text('content-'+name)
   sha=hashlib.sha256(p.read_bytes()).hexdigest()
   with patch.object(a,'PACKAGE',p),patch.object(a,'STAGE',st):
    a.stage(sha)
    (st/'ack.sh').write_text('tampered')
    with self.assertRaises(ValueError):a.stage(sha)
 def test_report_publication_contains_no_credentials(self):
  with tempfile.TemporaryDirectory() as t,patch.object(a,'REPORT',Path(t)/'status.yaml'),patch.object(a,'snapshot',return_value={'phase':'IDLE_NO_DEPLOYMENT_RECORD','worker_running':False}):
   a.publish(a.Controller());self.assertEqual(json.loads(a.REPORT.read_text())['phase'],'IDLE_NO_DEPLOYMENT_RECORD')
 def test_inspect_never_launches_worker(self):
  with patch.object(a,'deployment_diagnostics',return_value={'production_code':'ORIGINAL_VERIFIED'}),patch.object(a.subprocess,'Popen') as run:
   self.assertEqual(a.Controller().handle({'action':'inspect'}),{'production_code':'ORIGINAL_VERIFIED'})
   run.assert_not_called()
 def test_inspect_has_no_implicit_authorization(self):
  self.assertIn("report['deployment_permitted']=False",(ROOT/'mcp_installer/runner.py').read_text())
 def test_read_only_inspect_identifies_legacy_guard_and_unchanged_code(self):
  import types
  with tempfile.TemporaryDirectory() as directory:
   old=Path(directory)/'install.sh';old.write_text('ha core stop')
   fake=types.SimpleNamespace(SOURCE=Path(directory)/'source',BACK=Path(directory),status=MagicMock(side_effect=FileNotFoundError),watchdog_lease_held=lambda b:False)
   with patch.dict('sys.modules',{'manual_ack_watchdog':fake,'deployment_core':types.SimpleNamespace(verify=lambda *args:None)}),patch.object(a,'Path',return_value=old):
    report=a.deployment_diagnostics()
   self.assertEqual(report['legacy_installer_guard'],'OLD_STANDALONE_INSTALLER_MUST_BE_WITHDRAWN')
   self.assertEqual(report['production_code'],'ORIGINAL_VERIFIED')
   self.assertTrue(report['safe_to_update_installer'])
   self.assertFalse(report['deployment_permitted'])
   self.assertEqual(old.read_text(),'ha core stop')
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
