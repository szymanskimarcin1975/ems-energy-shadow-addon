import tempfile,unittest,sqlite3,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
from battery_executor import Executor,Policy,GatewayRejected,SupervisorHA
from test_battery_executor import HA,Owner
from dispatch_lifecycle import initialise,state,hold,confirm_termination
class API(HA):
 def __init__(self):super().__init__();self.power=5000;self.mode='Maximize Self Consumption';self.offset=0;self.partial=False;self.late=False;self.stale_ack=False
 def state(self,e):
  if e in ('number.charge','number.discharge'):return {'state':str(self.power),'last_updated':('2000-01-01T00:00:00+00:00' if self.stale_ack else datetime.now(timezone.utc).isoformat())}
  if e=='select.mode':return {'state':self.mode,'last_updated':('2000-01-01T00:00:00+00:00' if self.stale_ack else datetime.now(timezone.utc).isoformat())}
  return super().state(e)
 def dispatch(self,e,option,watts,**kw):
  if getattr(self,'owner','EMS2')!='EMS2' or self.old!='off':raise GatewayRejected('synthetic_owner')
  self.calls.append((option,watts));self.power=watts
  if self.partial:raise TimeoutError('synthetic_after_power')
  self.mode=option
  if self.late:self.offset=70
  return {'applied_power_w':watts}
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'db.sqlite';self.ha=API()
  self.policy=Policy(enabled=True,operating_soc_min=5,operating_soc_max=95,soc_operating_range_approved=True,handover_verified=True,no_export_verified=True,fallback_verified=True)
  self.x=Executor(self.ha,self.policy,self.path,Path(self.tmp.name)/'lock',old_writers=['automation.old'],soc_entity='sensor.example_soc',mode_entity='select.mode',power_entities=['number.charge','number.discharge'],owner_entity='input_select.example_owner',ownership=Owner(),expected_epoch=2,clock=lambda:datetime.now(timezone.utc)+timedelta(seconds=self.ha.offset),control_entity='select.example_control',telemetry_check=lambda:'HA_TRANSPORT_CHECK_PASSED_NOT_DEVICE_PROOF',bms_sources={k:'sensor.example_bms_'+k for k in ('status','max_charge','peak_charge','max_discharge','peak_discharge')})
 def execute(self,id='request',option='Charge from Solar Power and Grid',watts=5000):return self.x.execute(id,option,datetime.now(timezone.utc)+timedelta(seconds=45),maximum_power_w=watts,plan_id='a'*64)
 def test_grid_charge_power_and_fresh_ack(self):self.assertEqual(self.execute(),'ACK');self.assertEqual(self.ha.calls,[('Charge from Solar Power and Grid',5000)])
 def test_clamp_to_live_peak(self):
  self.ha.peak_charge=1234;self.assertEqual(self.execute(),'ACK');self.assertEqual(self.ha.power,1234)
 def test_clamp_to_rated_inverter_ceiling(self):self.assertEqual(self.execute(watts=9000),'ACK');self.assertEqual(self.ha.power,5000)
 def test_requested_lower_limit_preserved(self):self.assertEqual(self.execute(watts=900),'ACK');self.assertEqual(self.ha.power,900)
 def test_soc_100_hard_block(self):self.ha.soc=100;self.assertEqual(self.execute(),'SOC_CEILING');self.assertEqual(self.ha.calls,[])
 def test_zero_peak_hard_block(self):self.ha.peak_charge=0;self.assertEqual(self.execute(),'BMS_DIRECTION_LIMIT_ZERO');self.assertEqual(self.ha.calls,[])
 def test_bms_error_hard_block(self):self.ha.bms_status='B_STATUS_FAULT';self.assertEqual(self.execute(),'BMS_STATUS_NOT_APPROVED');self.assertEqual(self.ha.calls,[])
 def test_stale_bms_hard_block(self):self.ha.bms_age=181;self.assertEqual(self.execute(),'BMS_HA_UPDATE_UNCONFIRMED');self.assertEqual(self.ha.calls,[])
 def test_legacy_owner_hard_block(self):self.ha.owner='LEGACY';self.assertEqual(self.execute(),'SHARED_OWNER_NOT_EMS2');self.assertEqual(self.ha.calls,[])
 def test_identical_request_not_repeated(self):self.assertEqual(self.execute(),'ACK');self.assertEqual(self.execute(),'DUPLICATE_ACK');self.assertEqual(len(self.ha.calls),1)
 def test_different_request_requires_termination(self):self.assertEqual(self.execute(),'ACK');self.assertEqual(self.execute('next','Discharge to Minimize Import'),'PREVIOUS_COMMAND_TERMINATION_UNCONFIRMED');self.assertEqual(len(self.ha.calls),1)
 def test_hold_not_cancellation_even_after_3600_seconds(self):
  self.execute();c=sqlite3.connect(self.path,isolation_level=None)
  try:
   r=hold(c,datetime.now(timezone.utc)+timedelta(seconds=3601),'plan_hold');self.assertEqual(r['status'],'HOLD_REQUIRES_TERMINATION');self.assertFalse(r['cancel_sent']);self.assertFalse(state(c)['termination_confirmed'])
  finally:c.close()
 def test_charge_hold_confirmed_termination_discharge_synthetic_only(self):
  self.assertEqual(self.execute(),'ACK');c=sqlite3.connect(self.path,isolation_level=None)
  try:
   now=datetime.now(timezone.utc);self.assertEqual(hold(c,now,'HOLD')['status'],'HOLD_REQUIRES_TERMINATION')
   evidence={'observed_at':now.isoformat(),'source':'verified_manufacturer_device_status','inverter_command_inactive_confirmed':True,'reference':'SYNTHETIC_TEST_ONLY_NOT_REAL_DEVICE_PROOF'}
   confirm_termination(c,'request',evidence,now);self.assertTrue(state(c)['termination_confirmed'])
  finally:c.close()
  self.assertEqual(self.execute('discharge','Discharge to Minimize Import',1000),'ACK');self.assertEqual(len(self.ha.calls),2)
 def test_partial_power_write_is_unknown_and_never_replayed(self):
  self.ha.partial=True;self.assertEqual(self.execute(),'UNKNOWN');self.ha.partial=False;self.assertEqual(self.execute('next'),'UNKNOWN_REQUIRES_RECONCILIATION');self.assertEqual(len(self.ha.calls),1)
 def test_delayed_ack_after_expiry_is_unknown(self):
  self.ha.late=True;self.assertEqual(self.execute(),'UNKNOWN');self.assertEqual(len(self.ha.calls),1)
 def test_old_matching_state_is_not_fresh_ack(self):
  self.ha.stale_ack=True;self.assertEqual(self.execute(),'UNKNOWN')
 def test_restart_preserves_active_state_and_dedup(self):
  self.execute();out=subprocess.check_output([sys.executable,'-c',"import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(c.execute('pragma integrity_check').fetchone()[0],c.execute('select status from active_dispatch').fetchone()[0],c.execute('select count(*) from commands').fetchone()[0])",str(self.path)],text=True)
  self.assertEqual(out.strip(),'ok ACK_ACTIVE_NOT_TERMINATED 1');self.assertEqual(self.execute('after_restart'),'PREVIOUS_COMMAND_TERMINATION_UNCONFIRMED')
 def test_unverified_termination_never_clears(self):
  self.execute();c=sqlite3.connect(self.path,isolation_level=None)
  try:
   with self.assertRaises(ValueError):confirm_termination(c,'request',{'observed_at':datetime.now(timezone.utc).isoformat()},datetime.now(timezone.utc))
   self.assertFalse(state(c)['termination_confirmed'])
  finally:c.close()
 def test_lifecycle_write_failure_no_transport(self):
  # SQLite cannot create its state directory; failure precedes any network call.
  self.x.db=Path(self.tmp.name)/'missing'/'x.sqlite'
  with self.assertRaises(sqlite3.Error):self.execute()
  self.assertEqual(self.ha.calls,[])
 def test_commit_failure_after_dispatch_remains_pending_on_reopen(self):
  from unittest.mock import patch
  with patch('dispatch_lifecycle.finish',side_effect=sqlite3.OperationalError('synthetic_disk_full')):
   with self.assertRaises(sqlite3.Error):self.execute()
  self.assertEqual(len(self.ha.calls),1)
  with sqlite3.connect(self.path) as c:
   self.assertEqual(c.execute('pragma integrity_check').fetchone()[0],'ok');self.assertEqual(c.execute('select status from commands').fetchone()[0],'PENDING');self.assertEqual(c.execute('select status from active_dispatch').fetchone()[0],'PENDING')
  self.assertEqual(self.execute('next'),'UNKNOWN_REQUIRES_RECONCILIATION')
 def test_real_transport_compound_gateway_only(self):
  from unittest.mock import patch
  ha=SupervisorHA('synthetic');reply={'status':'SERVICE_COMPLETED','request_id':'test','applied_power_w':1000,'plan_id':'a'*64,'owner_epoch':2,'owner':'EMS2','gateway_contract':'EMS2_COMPOUND_V28','writes_started':True,'option':'Charge from Solar Power and Grid'}
  with patch.object(ha,'_request',return_value={'service_response':reply}) as call:
   self.assertEqual(ha.dispatch('select.example_mode','Charge from Solar Power and Grid',1000,request_id='test',plan_id='a'*64,owner_epoch=2,expires_at=datetime.now(timezone.utc)+timedelta(seconds=30)),reply)
   self.assertEqual(call.call_args.args[0],'/services/ems_epoch_gateway/dispatch?return_response');self.assertEqual(call.call_args.args[1]['operation'],'dispatch')
