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
  if e.startswith('number.'):return {'state':str(getattr(self,'remote',5000)),'last_updated':datetime.now(timezone.utc).isoformat()}
  return {'state':'Charge from Solar Power','last_updated':datetime.now(timezone.utc).isoformat() if self.ack else '2000-01-01T00:00:00+00:00'}
 def current_states(self,entities):
  result={}
  for e in entities:
   role=e.removeprefix('sensor.example_bms_')
   result[e]={'entity_id':e,'state':getattr(self,'bms_status','B_STATUS_IDLE') if role=='status' else str(getattr(self,role,5000)),'attributes':{'unit_of_measurement':'W'},'last_reported':(datetime.now(timezone.utc)-timedelta(seconds=getattr(self,'bms_age',1))).isoformat()}
  return result
 def record_dispatch(self,e,o,**kwargs):
  self.calls.append((e,o))
  if self.fail:raise TimeoutError()
 def dispatch(self,e,o,power_w,**kwargs):
  self.remote=power_w;self.record_dispatch(e,o,**kwargs);return {'applied_power_w':power_w}
class Owner:
 def state(self):return {'owner':'EMS2','epoch':2,'commands_permitted':True,'external_fence_verified':True}
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.ha=HA()
  self.p=Policy(enabled=True,operating_soc_min=5,operating_soc_max=95,soc_operating_range_approved=True,handover_verified=True,no_export_verified=True,fallback_verified=True)
 def executor(self,p=None):
  return Executor(self.ha,p or self.p,Path(self.tmp.name)/'c.sqlite',Path(self.tmp.name)/'l',old_writers=['automation.old'],soc_entity='sensor.example_soc',mode_entity='select.mode',power_entities=['number.charge','number.discharge'],owner_entity='input_select.example_owner',ownership=Owner(),expected_epoch=2,control_entity='select.example_control',telemetry_check=lambda:'HA_TRANSPORT_CHECK_PASSED_NOT_DEVICE_PROOF',bms_sources={k:'sensor.example_bms_'+k for k in ('status','max_charge','peak_charge','max_discharge','peak_discharge')})
 def run_command(self,x,id='r',mode='Charge from Solar Power'):
  return x.execute(id,mode,datetime.now(timezone.utc)+timedelta(seconds=30),maximum_power_w=5000,plan_id='a'*64)
 def test_disabled_no_files_no_api(self):
  self.assertEqual(self.run_command(self.executor(Policy())),'DISABLED');self.assertEqual(list(Path(self.tmp.name).iterdir()),[]);self.assertEqual(self.ha.calls,[])
 def test_no_approval_blocks(self):
  self.assertEqual(self.run_command(self.executor(replace(self.p,soc_operating_range_approved=False))),'UNAPPROVED_SAFETY');self.assertEqual(self.ha.calls,[])
 def test_old_running_blocks(self):
  self.ha.old='on';self.assertEqual(self.run_command(self.executor()),'OLD_WRITER_NOT_QUIESCENT');self.assertEqual(self.ha.calls,[])
 def test_reserve_blocks(self):
  self.ha.soc=5;self.assertEqual(self.run_command(self.executor(),mode='Discharge to Minimize Import'),'SOC_RESERVE')
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
  self.ha.soc=95;self.assertEqual(self.run_command(self.executor()),'SOC_CEILING');self.assertEqual(self.ha.calls,[])
 def test_operating_envelope_blocks_only_outward_direction(self):
  self.ha.soc=96;self.assertEqual(self.run_command(self.executor()),'SOC_CEILING');self.assertEqual(self.ha.calls,[])
  self.ha.soc=4;self.assertEqual(self.run_command(self.executor(),'low-soc','Discharge to Minimize Import'),'SOC_RESERVE');self.assertEqual(self.ha.calls,[])
 def test_unknown_survives_reopen(self):
  self.ha.fail=True;self.assertEqual(self.run_command(self.executor()),'UNKNOWN')
  self.ha.fail=False;self.assertEqual(self.run_command(self.executor(),'after_restart'),'UNKNOWN_REQUIRES_RECONCILIATION')
 def test_missing_soc_limits(self):
  self.assertEqual(self.run_command(self.executor(replace(self.p,operating_soc_min=None))),'INVALID_SOC_LIMITS')
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
  x.clock=lambda:next(times,start+timedelta(seconds=31))
  self.assertEqual(x.execute('late','Charge from Solar Power',start+timedelta(seconds=30),now=start,maximum_power_w=5000,plan_id='a'*64),'EXPIRED_REQUEST')
  self.assertEqual(self.ha.calls,[])
 def test_deadline_expires_during_final_validation_no_send(self):
  x=self.executor(); start=datetime.now(timezone.utc); times=iter([start,start,start+timedelta(seconds=31)])
  x.clock=lambda:next(times,start+timedelta(seconds=31))
  self.assertEqual(x.execute('late2','Charge from Solar Power',start+timedelta(seconds=30),now=start,maximum_power_w=5000,plan_id='a'*64),'EXPIRED_REQUEST')
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

 def test_alternate_select_removed(self):
  from battery_executor import SupervisorHA
  self.assertFalse(hasattr(SupervisorHA('synthetic'),'select'))
 def test_executor_known_gateway_rejection_persists_rejected(self):
  from battery_executor import GatewayRejected
  def reject(*args,**kwargs):raise GatewayRejected('gateway_rejected')
  self.ha.dispatch=reject
  self.assertEqual(self.run_command(self.executor()),'REJECTED')
  with sqlite3.connect(Path(self.tmp.name)/'c.sqlite') as db:self.assertEqual(db.execute('select status from commands').fetchone()[0],'REJECTED')

 def test_bms_zero_charge_blocks(self):
  self.ha.peak_charge=0;self.assertEqual(self.run_command(self.executor()),'BMS_DIRECTION_LIMIT_ZERO');self.assertEqual(self.ha.calls,[])
 def test_bms_charge_zero_does_not_invent_discharge_zero(self):
  self.ha.peak_charge=0;self.assertEqual(self.run_command(self.executor(),mode='Discharge to Minimize Import'),'UNKNOWN')
  self.assertEqual(len(self.ha.calls),1) # fake ACK is charge-only; no real command.
 def test_bms_preserve_is_unapproved_not_assumed_fault(self):
  self.ha.bms_status='B_STATUS_PRESERVE_CHARGE';self.assertEqual(self.run_command(self.executor()),'BMS_STATUS_NOT_APPROVED');self.assertEqual(self.ha.calls,[])
 def test_bms_fault_blocks(self):
  self.ha.bms_status='B_STATUS_FAULT';self.assertEqual(self.run_command(self.executor()),'BMS_STATUS_NOT_APPROVED')
 def test_bms_derated_limit_clamps_compound_power(self):
  self.ha.max_charge=2000;self.assertEqual(self.run_command(self.executor()),'ACK');self.assertEqual(self.ha.remote,2000)
 def test_missing_bms_mapping_blocks(self):
  x=self.executor();x.bms={};self.assertEqual(self.run_command(x),'BMS_SOURCES_UNCONFIRMED')
 def test_stale_bms_blocks(self):
  self.ha.bms_age=1000;self.assertEqual(self.run_command(self.executor()),'BMS_HA_UPDATE_UNCONFIRMED')
 def test_nan_bms_blocks(self):
  self.ha.peak_charge=float('nan');self.assertEqual(self.run_command(self.executor()),'BMS_LIMIT_INVALID')


class DirectionalSOCTests(unittest.TestCase):
 setUp=Tests.setUp
 executor=Tests.executor
 def test_soc_100_can_return_by_discharge_but_not_charge(self):
  self.ha.soc=100;x=self.executor()
  self.assertEqual(x.live_guard('Charge from Solar Power',datetime.now(timezone.utc)),'SOC_CEILING')
  self.assertIsNone(x.live_guard('Discharge to Minimize Import',datetime.now(timezone.utc)))
 def test_soc_4_can_return_by_charge_but_not_discharge(self):
  self.ha.soc=4;x=self.executor()
  self.assertIsNone(x.live_guard('Charge from Solar Power',datetime.now(timezone.utc)))
  self.assertEqual(x.live_guard('Discharge to Minimize Import',datetime.now(timezone.utc)),'SOC_RESERVE')
