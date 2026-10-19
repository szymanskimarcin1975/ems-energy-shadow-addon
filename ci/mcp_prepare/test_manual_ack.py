"""Only temporary files, fake Core/Supervisor and real detached process launch."""
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/mcp_prepare'))
import manual_ack_watchdog as w

class ManualACK(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=self.base/'package';self.root.mkdir()
  self.config=self.base/'config';self.source=self.config/'custom_components/mcp_server_http_transport';self.source.mkdir(parents=True)
  (self.source/'code.py').write_text('original')
  self.back=self.config/'recovery';self.back.mkdir(mode=0o700)
  shutil.copytree(self.source,self.back/'component');(self.back/'PREPARED').write_text('PREPARED')
  for name,value in [('BASE_SHA256SUMS','original'),('CANDIDATE_SHA256SUMS','candidate')]:
   (self.root/name).write_text(hashlib.sha256(value.encode()).hexdigest()+'  ./code.py\n')
  shutil.copyfile(ROOT/'tools/mcp_prepare/prepare_operations.py',self.root/'diagnostic_verifier.py')
  with zipfile.ZipFile(self.root/'mcp-1.18.0-ems.2-prepare.zip','w') as z:z.writestr('custom_components/mcp_server_http_transport/code.py','candidate')
  (self.root/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(self.root.iterdir())))
  self.now=0;self.calls=[];self.hook=None;self.once=False
 def tearDown(self):self.tmp.cleanup()
 def core(self,a):self.calls.append(a);return True
 def clock(self):return self.now
 def pause(self,n):
  self.now+=n
  if self.hook and not self.once and (self.back/w.STATE).exists() and self.state()['phase']=='WAITING_ACK':self.once=True;self.hook()
 def state(self):return w.read_json(self.back/w.STATE)
 def controller(self,health=lambda c:True,core=None):return w.ManualDeployment(self.root,self.back,self.source,health,core or self.core,self.clock,self.pause,deadline=20,ack_seconds=30)
 def diagnostic(self,stamp=None):
  s=self.state();path=self.config/'ems_prepare_backups'/s['diagnostic_operation_id'];(path/'original').mkdir(parents=True)
  (path/'original/f.py').write_text('synthetic diagnostic code')
  stamp=s['waiting_started_at']+.001 if stamp is None else stamp
  (path/'manifest.json').write_text(json.dumps(dict(state='COMPLETE',operation_id=s['diagnostic_operation_id'],at=datetime.fromtimestamp(stamp,timezone.utc).isoformat(),sha256={'f.py':hashlib.sha256(b'synthetic diagnostic code').hexdigest()})))
 def ack(self,op=None,challenge=None,checks=None):
  s=self.state();return w.write_ack(self.root,self.back,self.source,op or s['operation_id'][:12],challenge or s['challenge'],checks if checks is not None else {k:True for k in w.CHECKS},clock=self.clock)
 def ready_ack(self):self.diagnostic();self.ack()
 def test_success_requires_fresh_diagnostic_and_owner_ack(self):
  self.hook=self.ready_ack
  self.assertTrue(self.controller().execute());self.assertEqual(self.state()['phase'],'SUCCESS_ACK_CONSUMED');self.assertEqual(self.calls.count('start'),1);self.assertTrue((self.back/'manual-ack-consumed.json').exists())
 def test_no_ack_rolls_back_once(self):
  self.assertFalse(self.controller().execute());self.assertEqual(self.state()['phase'],'ROLLED_BACK_API_ONLY_MCP_UNVERIFIED');self.assertEqual(self.calls.count('start'),2);self.assertEqual((self.source/'code.py').read_text(),'original')
 def test_wrong_operation_rejected(self):
  def hook():
   self.diagnostic()
   with self.assertRaises(w.Blocked):self.ack(op='0'*12)
  self.hook=hook;self.assertFalse(self.controller().execute());self.assertEqual(self.calls.count('start'),2)
 def test_wrong_challenge_rejected(self):
  def hook():
   self.diagnostic()
   with self.assertRaises(w.Blocked):self.ack(challenge='0'*12)
  self.hook=hook;self.assertFalse(self.controller().execute())
 def test_missing_diagnostic_cannot_ack(self):
  def hook():
   with self.assertRaises(w.Blocked):self.ack()
  self.hook=hook;self.assertFalse(self.controller().execute())
 def test_old_diagnostic_cannot_ack(self):
  def hook():
   self.diagnostic(stamp=self.state()['waiting_started_at']-10)
   with self.assertRaises(w.Blocked):self.ack()
  self.hook=hook;self.assertFalse(self.controller().execute())
 def test_missing_owner_check_cannot_ack(self):
  def hook():
   self.diagnostic();c={k:True for k in w.CHECKS};c['existing_oauth_verified']=False
   with self.assertRaises(w.Blocked):self.ack(checks=c)
  self.hook=hook;self.assertFalse(self.controller().execute())
 def test_nonboolean_attestation_refused(self):
  def hook():
   self.diagnostic()
   with self.assertRaises(w.Blocked):self.ack(checks={k:1 for k in w.CHECKS})
  self.hook=hook;self.assertFalse(self.controller().execute())
 def test_duplicate_ack_refused(self):
  def hook():
   self.ready_ack()
   with self.assertRaises(FileExistsError):self.ack()
  self.hook=hook;self.assertTrue(self.controller().execute())
 def test_late_ack_refused(self):
  def hook():
   self.diagnostic();self.now=self.state()['deadline_monotonic']
   with self.assertRaises(w.Blocked):self.ack()
  self.hook=hook;self.assertFalse(self.controller().execute())
 def test_changed_candidate_refused(self):
  def hook():
   self.diagnostic();(self.source/'code.py').write_text('tampered')
   with self.assertRaises(w.Blocked):self.ack()
  self.hook=hook;self.assertFalse(self.controller().execute())
 def test_dead_watchdog_does_not_accept_ack_or_resume(self):
  def hook():
   self.diagnostic();raise KeyboardInterrupt()
  self.hook=hook
  with self.assertRaises(KeyboardInterrupt):self.controller().execute()
  self.assertEqual(self.state()['phase'],'WAITING_ACK')
  with self.assertRaises(w.Blocked):self.ack()
  before=list(self.calls)
  with self.assertRaises(w.Blocked):self.controller().execute()
  self.assertEqual(self.calls,before)
 def test_forged_ack_without_diagnostic_not_accepted(self):
  def hook():
   state=self.state();ack={k:state[k] for k in ('operation_id','challenge','candidate_sha256','package_manifest_sha256','diagnostic_operation_id')};ack['checks']={k:True for k in w.CHECKS};w.atomic_json(self.back/w.ACK,ack)
  self.hook=hook;self.assertFalse(self.controller().execute());self.assertEqual(self.calls.count('start'),2)
 def test_corrupted_diagnostic_after_ack_not_accepted(self):
  def hook():
   self.ready_ack();state=self.state();(self.config/'ems_prepare_backups'/state['diagnostic_operation_id']/'original/f.py').write_text('corrupted')
  self.hook=hook;self.assertFalse(self.controller().execute());self.assertEqual(self.calls.count('start'),2)
 def test_ack_from_other_update_not_accepted(self):
  def hook():
   self.diagnostic();state=self.state();ack={k:state[k] for k in ('operation_id','challenge','candidate_sha256','package_manifest_sha256','diagnostic_operation_id')};ack['operation_id']='0'*32;ack['checks']={k:True for k in w.CHECKS};w.atomic_json(self.back/w.ACK,ack)
  self.hook=hook;self.assertFalse(self.controller().execute())
 def test_other_valid_package_cannot_ack_same_mcp_code(self):
  def hook():
   self.diagnostic();(self.root/'another-file.txt').write_text('another valid package')
   (self.root/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(self.root.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))
   with self.assertRaises(w.Blocked):self.ack()
  self.hook=hook;self.assertFalse(self.controller().execute())
 def test_watchdog_runtime_error_attempts_one_recovery(self):
  def hook():raise RuntimeError('synthetic watchdog failure')
  self.hook=hook;self.assertFalse(self.controller().execute());self.assertEqual(self.calls.count('start'),2);self.assertEqual(self.state()['phase'],'ROLLED_BACK_API_ONLY_MCP_UNVERIFIED')
 def test_core_start_failure_restores_once(self):
  starts=0
  def core(a):
   nonlocal starts
   self.calls.append(a)
   if a=='start':starts+=1;return starts>1
   return True
  self.assertFalse(self.controller(core=core).execute());self.assertEqual(self.calls.count('start'),2);self.assertEqual(self.state()['phase'],'ROLLED_BACK_API_ONLY_MCP_UNVERIFIED')
 def test_failed_rollback_does_not_loop(self):
  def core(a):self.calls.append(a);return a!='start'
  self.assertFalse(self.controller(core=core).execute());self.assertEqual(self.calls.count('start'),2);self.assertEqual(self.state()['phase'],'RECOVERY_FAILED_OPERATOR_REQUIRED')
  with self.assertRaises(w.Blocked):self.controller().execute()
  self.assertEqual(self.calls.count('start'),2)
 def test_api_loss_while_waiting_rolls_back(self):
  lost=False
  def hook():
   nonlocal lost;lost=True
  self.hook=hook
  self.assertFalse(self.controller(health=lambda c:not c or not lost).execute());self.assertEqual(self.calls.count('start'),2)
 def test_slow_initial_api_then_ack(self):
  count=0
  def health(c):
   nonlocal count
   if c:count+=1;return count>2
   return True
  self.hook=self.ready_ack;self.assertTrue(self.controller(health=health).execute())
 def test_unknown_supervisor_stop_never_swaps(self):
  def core(a):
   self.calls.append(a)
   if a=='stop':raise w.Blocked('CORE_OPERATION_UNKNOWN')
   return True
  self.assertFalse(self.controller(core=core).execute());self.assertEqual(self.state()['phase'],'UNKNOWN_REQUIRES_OPERATOR');self.assertEqual((self.source/'code.py').read_text(),'original');self.assertNotIn('start',self.calls)
 def test_installer_and_watchdog_share_lock(self):
  with w.lock(self.back/'deploy.lock'):
   with self.assertRaises(BlockingIOError):self.controller().execute()
  self.assertEqual(self.calls,[])
 def test_restart_never_replays_previous_operation(self):
  (self.back/w.STATE).write_text('{"phase":"WAITING_ACK"}')
  with self.assertRaises(w.Blocked):self.controller().execute()
  self.assertEqual(self.calls,[])
 def test_no_oauth_credential_needed(self):
  self.hook=self.ready_ack
  with patch.dict(os.environ,{},clear=True):self.assertTrue(self.controller().execute())
  self.assertFalse((self.back/'oauth-probe.json').exists())
 def test_detached_launcher_survives_parent_exit(self):
  text=(ROOT/'tools/mcp_prepare/manual-ack-launch.sh').read_text().replace('BACK=/config/mcp_prepare_ems2_recovery','BACK='+str(self.back))
  (self.root/'manual-ack-launch.sh').write_text(text);marker=self.base/'survived'
  (self.root/'manual_ack_watchdog.py').write_text('import time,pathlib,os,json;time.sleep(.2);pathlib.Path('+repr(str(marker))+').write_text(json.dumps({"pid":os.getpid(),"sid":os.getsid(0)}))')
  # The real launcher checks presence only; no real ha binary is executed.
  binpath=self.base/'bin';binpath.mkdir();(binpath/'ha').write_text('#!/bin/sh\nexit 99\n');(binpath/'ha').chmod(0o700)
  env=dict(os.environ);env['PATH']=str(binpath)+':'+env['PATH']
  proc=subprocess.run(['sh',str(self.root/'manual-ack-launch.sh'),'CONFIRM_CORE_RESTART'],env=env,capture_output=True,text=True,check=True)
  self.assertIn('QUEUED_NOT_INSTALLED',proc.stdout)
  until=time.monotonic()+3
  while not marker.exists() and time.monotonic()<until:time.sleep(.02)
  info=json.loads(marker.read_text());self.assertEqual(info['pid'],info['sid'])

if __name__=='__main__':unittest.main(verbosity=2)
