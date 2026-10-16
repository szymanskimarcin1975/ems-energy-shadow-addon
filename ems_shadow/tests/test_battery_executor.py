import unittest,tempfile,sqlite3
from pathlib import Path
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from battery_executor import Executor,Policy
class HA:
 def __init__(self):self.calls=[];self.old='off';self.soc=50;self.fail=False;self.ack=True
 def state(self,e):
  if e=='automation.old':return {'state':self.old,'attributes':{'current':0}}
  if e=='sensor.soc':return {'state':str(self.soc),'last_reported':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}
  if e.startswith('number.'):return {'state':'5000'}
  return {'state':'Charge from Solar Power','last_updated':datetime.now(timezone.utc).isoformat() if self.ack else '2000-01-01T00:00:00+00:00'}
 def select(self,e,o):
  self.calls.append((e,o))
  if self.fail:raise TimeoutError()
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.ha=HA()
  self.p=Policy(enabled=True,soc_min=30,soc_max=90,soc_bounds_approved=True,handover_verified=True,no_export_verified=True,fallback_verified=True)
 def executor(self,p=None):
  return Executor(self.ha,p or self.p,Path(self.tmp.name)/'c.sqlite',Path(self.tmp.name)/'l',old_writers=['automation.old'],soc_entity='sensor.soc',mode_entity='select.mode',power_entities=['number.charge','number.discharge'])
 def run_command(self,x,id='r',mode='Charge from Solar Power'):
  return x.execute(id,mode,datetime.now(timezone.utc)+timedelta(seconds=30))
 def test_disabled_no_files_no_api(self):
  self.assertEqual(self.run_command(self.executor(Policy())),'DISABLED');self.assertEqual(list(Path(self.tmp.name).iterdir()),[]);self.assertEqual(self.ha.calls,[])
 def test_no_approval_blocks(self):
  self.assertEqual(self.run_command(self.executor(replace(self.p,soc_bounds_approved=False))),'UNAPPROVED_SAFETY');self.assertEqual(self.ha.calls,[])
 def test_old_running_blocks(self):
  self.ha.old='on';self.assertEqual(self.run_command(self.executor()),'OLD_WRITER_NOT_QUIESCENT');self.assertEqual(self.ha.calls,[])
 def test_reserve_blocks(self):
  self.ha.soc=30;self.assertEqual(self.run_command(self.executor(),mode='Discharge to Minimize Import'),'SOC_RESERVE')
 def test_export_forbidden(self):
  self.assertEqual(self.run_command(self.executor(),mode='Discharge to Maximize Export'),'FORBIDDEN_MODE')
 def test_dedup_restart(self):
  self.assertEqual(self.run_command(self.executor()),'ACK');self.assertEqual(self.run_command(self.executor()),'DUPLICATE_ACK');self.assertEqual(len(self.ha.calls),1)
  with sqlite3.connect(Path(self.tmp.name)/'c.sqlite') as db:self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
 def test_unknown_no_retry_no_old_resume(self):
  self.ha.fail=True;self.assertEqual(self.run_command(self.executor()),'UNKNOWN');self.assertEqual(self.run_command(self.executor(),'r2'),'UNKNOWN_REQUIRES_RECONCILIATION');self.assertEqual(len(self.ha.calls),1)
 def test_stale_ack_unknown(self):
  self.ha.ack=False;self.assertEqual(self.run_command(self.executor()),'UNKNOWN')
 def test_nonfinite_soc(self):
  self.ha.soc=float('nan');self.assertEqual(self.run_command(self.executor()),'INVALID_SOC')
