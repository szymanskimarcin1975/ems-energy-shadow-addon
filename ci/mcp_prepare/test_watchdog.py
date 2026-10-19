"""Isolated files, synthetic credentials and fake Supervisor only. No HA stop."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
import hashlib
import fcntl
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/mcp_prepare'))
spec=importlib.util.spec_from_file_location('wd',ROOT/'tools/mcp_prepare/watchdog.py')
wd=importlib.util.module_from_spec(spec);spec.loader.exec_module(wd)

class DeploymentTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.package=self.root/'package';self.package.mkdir()
  self.back=self.root/'recovery';self.back.mkdir(mode=0o700)
  self.source=self.root/'custom_components/mcp_server_http_transport';self.source.mkdir(parents=True)
  (self.source/'code.py').write_text('original')
  (self.back/'component').mkdir();(self.back/'component/code.py').write_text('original')
  (self.back/'PREPARED').write_text('PREPARED')
  for name,content in [('BASE_SHA256SUMS','original'),('CANDIDATE_SHA256SUMS','candidate')]:
   (self.package/name).write_text(hashlib.sha256(content.encode()).hexdigest()+'  ./code.py\n')
  with zipfile.ZipFile(self.package/'mcp-1.18.0-ems.2-prepare.zip','w') as z:
   z.writestr('custom_components/mcp_server_http_transport/code.py','candidate')
  self.sums()
  self.calls=[];self.now=0
 def tearDown(self):self.temp.cleanup()
 def sums(self):
  (self.package/'SHA256SUMS').write_text(''.join(wd.digest(p)+'  '+p.name+'\n' for p in self.package.iterdir() if p.name!='SHA256SUMS'))
 def core(self,action):self.calls.append(action);return True
 def clock(self):return self.now
 def pause(self,n):self.now+=n
 def deploy(self,health=lambda c:True,core=None):
  return wd.Deployment(self.package,self.back,self.source,health,core or self.core,self.clock,self.pause,deadline=10)
 def phase(self):return json.loads((self.back/'watchdog-state.json').read_text())['phase']
 def test_success(self):
  self.assertTrue(self.deploy().execute());self.assertEqual(self.phase(),'SUCCESS');self.assertEqual((self.source/'code.py').read_text(),'candidate')
 def test_failed_core_start_rollback_once(self):
  n=0
  def core(a):
   nonlocal n
   self.calls.append(a)
   if a=='start':n+=1;return n>1
   return True
  self.assertFalse(self.deploy(core=core).execute());self.assertEqual(self.phase(),'ROLLED_BACK');self.assertEqual(self.calls.count('start'),2)
 def test_broken_mcp_or_oauth_restores_code_only(self):
  data=self.root/'.storage';data.mkdir();(data/'untouched').write_text('sentinel')
  self.assertFalse(self.deploy(health=lambda candidate:not candidate).execute())
  self.assertEqual(self.phase(),'ROLLED_BACK');self.assertEqual((data/'untouched').read_text(),'sentinel');self.assertEqual((self.source/'code.py').read_text(),'original')
 def test_failed_rollback_no_loop(self):
  self.assertFalse(self.deploy(health=lambda c:False if c else self.calls.count('start')==0).execute())
  self.assertEqual(self.phase(),'RECOVERY_FAILED_OPERATOR_REQUIRED');self.assertEqual(self.calls.count('start'),2)
  with self.assertRaises(wd.Blocked):self.deploy().execute()
  self.assertEqual(self.calls.count('start'),2)
 def test_missing_authenticated_baseline_no_core_actions(self):
  with self.assertRaises(wd.Blocked):self.deploy(health=lambda c:False).execute()
  self.assertEqual(self.calls,[])
 def test_corrupted_backup_no_actions(self):
  (self.back/'component/code.py').write_text('corrupted')
  with self.assertRaises(wd.Blocked):self.deploy().execute()
  self.assertEqual(self.calls,[])
 def test_concurrent_apply_rollback_lock(self):
  with open(self.back/'deploy.lock','w') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with self.assertRaises(BlockingIOError):self.deploy().execute()
  self.assertEqual(self.calls,[])
 def test_stop_unknown_never_swaps_or_restarts(self):
  def core(a):
   self.calls.append(a)
   if a=='stop':raise wd.Blocked('CORE_OPERATION_UNKNOWN')
   return True
  self.assertFalse(self.deploy(core=core).execute());self.assertEqual(self.phase(),'UNKNOWN_REQUIRES_OPERATOR');self.assertNotIn('start',self.calls);self.assertEqual((self.source/'code.py').read_text(),'original')
 def test_restart_refuses_unresolved_previous_run(self):
  (self.back/'watchdog-state.json').write_text('{"phase":"INSTALLING"}')
  with self.assertRaises(wd.Blocked):self.deploy().execute()
  self.assertEqual(self.calls,[])
 def test_disconnect_does_not_kill_detached_process(self):
  marker=self.root/'survived'
  script=(ROOT/'tools/mcp_prepare/watchdog-launch.sh').read_text().replace('BACK=/config/mcp_prepare_ems2_recovery','BACK='+str(self.back))
  (self.package/'watchdog-launch.sh').write_text(script)
  worker='import time,pathlib,os,json;time.sleep(.2);pathlib.Path('+repr(str(marker))+').write_text(json.dumps({"pid":os.getpid(),"sid":os.getsid(0)}))'
  (self.package/'watchdog.py').write_text(worker)
  # Actual nohup+setsid launcher. This temporary worker has no HA access.
  proc=subprocess.run(['sh',str(self.package/'watchdog-launch.sh'),'CONFIRM_CORE_RESTART'],check=True,capture_output=True,text=True)
  self.assertIn('WATCHDOG_QUEUED',proc.stdout)
  import time
  until=time.monotonic()+3
  while not marker.exists() and time.monotonic()<until:time.sleep(.02)
  self.assertTrue(marker.exists())
  info=json.loads(marker.read_text());self.assertEqual(info['pid'],info['sid'])
 def test_launcher_requires_explicit_restart_argument(self):
  p=ROOT/'tools/mcp_prepare/watchdog-launch.sh'
  result=subprocess.run(['sh',str(p)],capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0);self.assertIn('EXPLICIT_RESTART_CONFIRMATION_REQUIRED',result.stdout)

class HealthTests(unittest.TestCase):
 def probe(self,behavior='ok',candidate=True):
  p=wd.Health.__new__(wd.Health);p.credentials={'access_token':'SYNTHETIC_SECRET'};p.host='synthetic.invalid';p.supervisor_token='SYNTHETIC_SUPERVISOR'
  def request(url,body=None,headers=None):
   if url.startswith('http://supervisor'):return (200,[]) if behavior=='api-list' else (200,{'message':'API running.'})
   rid=body['id']
   if behavior=='json-list':return 200,[]
   if behavior=='initialize-list' and body['method']=='initialize':return 200,{'id':rid,'result':[]}
   if behavior=='tools-list-invalid' and body['method']=='tools/list' and headers['Authorization'].endswith('SYNTHETIC_SECRET'):return 200,{'id':rid,'result':{'tools':[None]}}
   if behavior=='inspect-list' and body['method']=='tools/call':return 200,{'id':rid,'result':{'content':[{'type':'text','text':'[]'}]}}
   if headers['Authorization'].endswith('deliberately-invalid-probe'):
    return (200,{'result':{}}) if behavior=='ignores-auth' else (401,{})
   if behavior=='oauth-failed':return 401,{}
   if behavior=='plain-200':return 200,{}
   if body['method']=='initialize':return 200,{'id':rid,'result':{'protocolVersion':'2024-11-05','capabilities':{}}}
   if body['method']=='tools/call':return 200,{'id':rid,'result':{'isError':behavior=='non-admin','content':[{'type':'text','text':json.dumps({'status':'READ_ONLY','entry_id':'01M39WCJ1Y5FQTXXR2FZJBV76K'})}]}}
   names=wd.OLD_TOOLS|(wd.NEW_TOOLS if candidate and behavior!='missing-tools' else set())
   return 200,{'id':rid if behavior!='wrong-id' else 99,'result':{'tools':[{'name':x} for x in names]}}
  p.request=request;return p
 def test_authenticated_protocol_and_admin_read(self):self.assertTrue(self.probe()(True))
 def test_plain_http200_is_not_health(self):self.assertFalse(self.probe('plain-200')(True))
 def test_json_list_response_refused(self):self.assertFalse(self.probe('json-list')(True))
 def test_initialize_list_refused(self):self.assertFalse(self.probe('initialize-list')(True))
 def test_invalid_tools_items_refused(self):self.assertFalse(self.probe('tools-list-invalid')(True))
 def test_api_list_refused(self):self.assertFalse(self.probe('api-list')(True))
 def test_inspect_list_refused(self):self.assertFalse(self.probe('inspect-list')(True))
 def test_invalid_token_must_be_denied(self):self.assertFalse(self.probe('ignores-auth')(True))
 def test_oauth_failure(self):self.assertFalse(self.probe('oauth-failed')(True))
 def test_non_admin_denied(self):self.assertFalse(self.probe('non-admin')(True))
 def test_missing_tools(self):self.assertFalse(self.probe('missing-tools')(True))
 def test_wrong_rpc_identifier(self):self.assertFalse(self.probe('wrong-id')(True))
 def test_original_version_tools_after_rollback(self):self.assertTrue(self.probe(candidate=False)(False))
 def test_credential_permissions_and_no_secret_in_events(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'oauth-probe.json';path.write_text(json.dumps({'access_token':'SYNTHETIC_SECRET','public_origin':'https://synthetic.invalid'}));path.chmod(0o644)
   with self.assertRaises(wd.Blocked):wd.private_json(path)
   path.chmod(0o600)
   with self.assertRaises(ValueError):wd.private_json(path)  # Old arbitrary token files refused

if __name__=='__main__':unittest.main(verbosity=2)
