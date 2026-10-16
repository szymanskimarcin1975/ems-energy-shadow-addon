import unittest,tempfile,sqlite3
from pathlib import Path
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from battery_executor import Executor,Policy
class HA:
 def __init__(self):self.calls=[];self.old='off';self.soc=50;self.fail=False;self.ack=True
 def state(self,e):
  if e=='select.example_control':return {'state':getattr(self,'control','Remote Control')}
  if e=='input_select.example_owner':return {'state':getattr(self,'owner','EMS2')}
  if e=='automation.old':return {'state':self.old,'attributes':{'current':0}}
  if e=='sensor.example_soc':return {'state':str(self.soc),'last_reported':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}
  if e.startswith('number.'):return {'state':'5000'}
  return {'state':'Charge from Solar Power','last_updated':datetime.now(timezone.utc).isoformat() if self.ack else '2000-01-01T00:00:00+00:00'}
 def select(self,e,o,**kwargs):
  self.calls.append((e,o))
  if self.fail:raise TimeoutError()
class Owner:
 def state(self):return {'owner':'EMS2','epoch':2,'commands_permitted':True,'external_fence_verified':True}
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.ha=HA()
  self.p=Policy(enabled=True,soc_min=30,soc_max=90,soc_bounds_approved=True,handover_verified=True,no_export_verified=True,fallback_verified=True)
 def executor(self,p=None):
  return Executor(self.ha,p or self.p,Path(self.tmp.name)/'c.sqlite',Path(self.tmp.name)/'l',old_writers=['automation.old'],soc_entity='sensor.example_soc',mode_entity='select.mode',power_entities=['number.charge','number.discharge'],owner_entity='input_select.example_owner',ownership=Owner(),expected_epoch=2,control_entity='select.example_control')
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
 def test_soc_ceiling_blocks_charge(self):
  self.ha.soc=90;self.assertEqual(self.run_command(self.executor()),'SOC_CEILING');self.assertEqual(self.ha.calls,[])
 def test_unknown_survives_reopen(self):
  self.ha.fail=True;self.assertEqual(self.run_command(self.executor()),'UNKNOWN')
  self.ha.fail=False;self.assertEqual(self.run_command(self.executor(),'after_restart'),'UNKNOWN_REQUIRES_RECONCILIATION')
 def test_missing_soc_limits(self):
  self.assertEqual(self.run_command(self.executor(replace(self.p,soc_min=None))),'INVALID_SOC_LIMITS')
 def test_transport_exception_has_no_original_secret(self):
  from battery_executor import SupervisorHA
  from unittest.mock import patch
  import traceback
  with patch('urllib.request.urlopen',side_effect=RuntimeError('synthetic-secret')):
   try:SupervisorHA('example').state('sensor.example_soc')
   except RuntimeError as e:
    text=''.join(traceback.format_exception(e));self.assertNotIn('synthetic-secret',text);self.assertIn('ha_transport_error',text)
 def test_sqlite_failure_before_intent_sends_no_command(self):
  x=self.executor();x.db=Path(self.tmp.name)/'missing'/'db.sqlite'
  with self.assertRaises(sqlite3.OperationalError):self.run_command(x)
  self.assertEqual(self.ha.calls,[])

 def test_shared_legacy_blocks_even_if_local_owner_approved(self):
  self.ha.owner='LEGACY';self.assertEqual(self.run_command(self.executor()),'SHARED_OWNER_NOT_EMS2');self.assertEqual(self.ha.calls,[])
 def test_shared_unknown_blocks(self):
  self.ha.owner='UNKNOWN';self.assertEqual(self.run_command(self.executor()),'SHARED_OWNER_NOT_EMS2');self.assertEqual(self.ha.calls,[])
 def test_missing_local_owner_blocks(self):
  x=self.executor();x.ownership=None;self.assertEqual(self.run_command(x),'OWNERSHIP_UNCONFIRMED');self.assertEqual(self.ha.calls,[])
 def test_owner_epoch_change_blocks(self):
  x=self.executor();x.expected_epoch=3;self.assertEqual(self.run_command(x),'OWNERSHIP_UNCONFIRMED');self.assertEqual(self.ha.calls,[])

 def test_deadline_expires_before_live_reads_no_send(self):
  x=self.executor(); start=datetime.now(timezone.utc); times=iter([start+timedelta(seconds=31)])
  x.clock=lambda:next(times)
  self.assertEqual(x.execute('late','Charge from Solar Power',start+timedelta(seconds=30),now=start),'EXPIRED_REQUEST')
  self.assertEqual(self.ha.calls,[])
 def test_deadline_expires_during_final_validation_no_send(self):
  x=self.executor(); start=datetime.now(timezone.utc); times=iter([start,start,start+timedelta(seconds=31)])
  x.clock=lambda:next(times)
  self.assertEqual(x.execute('late2','Charge from Solar Power',start+timedelta(seconds=30),now=start),'EXPIRED_REQUEST')
  with sqlite3.connect(x.db) as db:self.assertEqual(db.execute('SELECT status FROM commands').fetchone()[0],'REJECTED')
  self.assertEqual(self.ha.calls,[])

 def test_non_remote_mode_blocks(self):
  self.ha.control='Time of Use';self.assertEqual(self.run_command(self.executor()),'REMOTE_CONTROL_NOT_ACTIVE');self.assertEqual(self.ha.calls,[])
 def test_missing_control_entity_blocks(self):
  x=self.executor();x.control_entity=None;self.assertEqual(self.run_command(x),'INCOMPLETE_CONFIGURATION');self.assertEqual(self.ha.calls,[])
 def test_unavailable_command_interface_blocks(self):
  original=self.ha.state
  self.ha.state=lambda e:{'state':'unavailable'} if e=='select.mode' else original(e)
  self.assertEqual(self.run_command(self.executor()),'COMMAND_INTERFACE_UNAVAILABLE');self.assertEqual(self.ha.calls,[])

 def test_real_transport_uses_shared_queue_not_direct_select(self):
  from battery_executor import SupervisorHA
  from unittest.mock import patch
  ha=SupervisorHA('synthetic');deadline=datetime.now(timezone.utc)+timedelta(seconds=30)
  with patch.object(ha,'_request',return_value={'service_response':{'status':'SERVICE_COMPLETED'}}) as request:
   ha.select('select.mode','Charge from Solar Power',request_id='queue1',expires_at=deadline)
  path,data=request.call_args.args
  self.assertEqual(path,'/services/script/ems_battery_command_gateway?return_response')
  self.assertEqual(data['caller'],'EMS2');self.assertEqual(data['request_id'],'queue1')
 def test_gateway_rejection_is_not_device_ack(self):
  from battery_executor import SupervisorHA,GatewayRejected
  from unittest.mock import patch
  with patch.object(SupervisorHA,'_request',return_value={'service_response':{'status':'REJECTED'}}):
   with self.assertRaises(GatewayRejected):SupervisorHA('synthetic').select('select.mode','Charge from Solar Power',request_id='no',expires_at=datetime.now(timezone.utc))
 def test_executor_known_gateway_rejection_persists_rejected(self):
  from battery_executor import GatewayRejected
  def reject(*args,**kwargs):raise GatewayRejected('gateway_rejected')
  self.ha.select=reject
  self.assertEqual(self.run_command(self.executor()),'REJECTED')
  with sqlite3.connect(Path(self.tmp.name)/'c.sqlite') as db:self.assertEqual(db.execute('select status from commands').fetchone()[0],'REJECTED')
