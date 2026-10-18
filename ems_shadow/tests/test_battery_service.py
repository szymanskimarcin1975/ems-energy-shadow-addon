import unittest,tempfile,sqlite3,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from battery_service import BatteryService,PROOFS,read_config
from fault_guard import READY
from test_battery_executor import HA
PROFILE={'soc_operating_bounds':{'minimum':0,'maximum':100,'owner_approved':True},'operational_parameters':{'rated_energy_wh':9200,'max_charge_w':5000,'max_discharge_w':5000,'storage_control_mode':'Remote Control','storage_default_mode':'Maximize Self Consumption','storage_command_timeout_s':3600}}
class Local:
 def state(self):return {'owner':'EMS2','epoch':2}
class TestHA(HA):
 def current_states(self,entities):
  rows=super().current_states(entities)
  for role,e,unit,value in [('m1','sensor.example_m1','kW','-1'),('b1','sensor.example_b1','W','0'),('soc','sensor.example_soc','%',str(self.soc))]:
   if e in rows:
    rows[e].update(state=value,attributes={'unit_of_measurement':unit},last_reported=(datetime.now(timezone.utc)-timedelta(seconds=getattr(self,'telemetry_age',1))).isoformat())
  if getattr(self,'telemetry_fail',False):raise TimeoutError('synthetic')
  return rows
 def state(self,e):
  if e=='number.example_timeout':return {'state':'3600'}
  if e=='select.example_default':return {'state':'Maximize Self Consumption'}
  if e=='input_boolean.example_auth':return {'state':getattr(self,'auth','on')}
  if e=='sensor.example_model':return {'state':'example-inverter'}
  if e=='sensor.example_firmware':return {'state':'example-firmware'}
  return super().state(e)
def config(mode='ACTIVE'):
 now=datetime.now(timezone.utc);device={'model':'example-inverter','firmware':'example-firmware'}
 return {'telemetry_sources':{'m1_power':'sensor.example_m1','b1_power':'sensor.example_b1','soc':'sensor.example_soc'},'mode':mode,'device':device,'verified_evidence':{k:dict(verified=True,device=device,reference='synthetic-offline-evidence',verified_at=(now-timedelta(seconds=10)).isoformat(),valid_until=(now+timedelta(seconds=60)).isoformat()) for k in PROOFS},'safety_soc_bounds':{'minimum':0,'maximum':100},'owner_entity':'input_select.example_owner','authorization_entity':'input_boolean.example_auth','expected_epoch':2,'old_writers':['automation.old'],'sources':{'soc':'sensor.example_soc','command_mode':'select.mode','control_mode':'select.example_control','charge_limit':'number.charge','discharge_limit':'number.discharge','device_model':'sensor.example_model','device_firmware':'sensor.example_firmware','timeout':'number.example_timeout','default_mode':'select.example_default'},'bms_sources':{k:'sensor.example_bms_'+k for k in ('status','max_charge','peak_charge','max_discharge','peak_discharge')},'pending_request':{'maximum_power_w':5000,'plan_id':'a'*64,'request_id':'example_request','option':'Charge from Solar Power','expires_at':(now+timedelta(seconds=45)).isoformat()}}
class Tests(unittest.TestCase):
 def setUp(self):
  fault=patch('fault_guard.FaultGuard.observe',return_value=READY);fault.start();self.addCleanup(fault.stop)
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.ha=TestHA();self.s=BatteryService(self.tmp.name,Local(),'synthetic',ha=self.ha);self.addCleanup(self.s.close)
 def test_readonly_initializes_real_executor_without_transport_calls(self):
  with patch.object(self.ha,'state',side_effect=AssertionError('must not read actuator')):
   r=self.s.cycle(config('READ_ONLY'),PROFILE)
  self.assertTrue(r['executor_initialized']);self.assertIsNotNone(self.s.executor);self.assertEqual(r['effective_state'],'READ_ONLY');self.assertFalse(r['actuation_policy_enabled']);self.assertEqual(self.ha.calls,[])
 def test_fault_in_live_guard_blocks_without_transport(self):
  with patch.object(self.s.fault_guard,'observe',side_effect=[READY,'INVERTER_FAULT']):
   r=self.s.cycle(config(),PROFILE)
  self.assertEqual(r['effective_state'],'INVERTER_FAULT');self.assertEqual(self.ha.calls,[])
 def test_fault_during_cycle_blocks_active(self):
  with patch.object(self.s.fault_guard,'observe',return_value='INVERTER_FAULT'):
   r=self.s.cycle(config(),PROFILE)
  self.assertIn('INVERTER_FAULT',r['safety_reasons']);self.assertEqual(self.ha.calls,[])
 def test_active_synthetic_full_path_and_ack(self):
  r=self.s.cycle(config(),PROFILE);self.assertEqual(r['effective_state'],'ACK');self.assertEqual(len(self.ha.calls),1);self.assertFalse(r['device_execution_confirmed']);self.assertEqual(r['commands_ha_acknowledged'],1)
 def test_missing_hardware_evidence_does_not_disable_legacy(self):
  c=config();c['verified_evidence']={};r=self.s.cycle(c,PROFILE);self.assertFalse(r['actuation_policy_enabled']);self.assertEqual(self.ha.calls,[]);self.assertIn('PHYSICAL_FALLBACK_UNVERIFIED',r['safety_reasons'])
 def test_unknown_soc_safety_not_replaced_by_planning_range(self):
  c=config();c['safety_soc_bounds']={};r=self.s.cycle(c,PROFILE);self.assertIn('BMS_OPERATING_SOC_BOUNDS_UNCONFIRMED',r['safety_reasons']);self.assertEqual(self.ha.calls,[])
 def test_old_running_blocks_before_intent(self):
  self.ha.old='on';r=self.s.cycle(config(),PROFILE);self.assertEqual(r['effective_state'],'OWNERSHIP_UNCONFIRMED');self.assertEqual(self.ha.calls,[])
 def test_shared_legacy_blocks(self):
  self.ha.owner='LEGACY';self.assertEqual(self.s.cycle(config(),PROFILE)['effective_state'],'OWNERSHIP_UNCONFIRMED');self.assertEqual(self.ha.calls,[])
 def test_authorization_missing_blocks(self):
  self.ha.auth='unavailable';self.assertEqual(self.s.cycle(config(),PROFILE)['effective_state'],'OWNERSHIP_UNCONFIRMED');self.assertEqual(self.ha.calls,[])
 def test_zero_peak_charge_blocks(self):
  self.ha.peak_charge=0;r=self.s.cycle(config(),PROFILE);self.assertEqual(r['effective_state'],'BMS_DIRECTION_LIMIT_ZERO');self.assertEqual(self.ha.calls,[])
 def test_stale_telemetry_blocks_service_before_intent(self):
  self.ha.telemetry_age=181;r=self.s.cycle(config(),PROFILE)
  self.assertEqual(r['effective_state'],'BLOCKED_SAFETY');self.assertIn('HA_TELEMETRY_STALE_OR_FUTURE',r['safety_reasons']);self.assertEqual(self.ha.calls,[])
 def test_telemetry_connection_failure_fails_closed(self):
  self.ha.telemetry_fail=True;r=self.s.cycle(config(),PROFILE)
  self.assertIn('TELEMETRY_READ_UNCONFIRMED',r['safety_reasons']);self.assertEqual(self.ha.calls,[])
 def test_missing_source_mapping_blocks_not_implicit_defaults(self):
  c=config();del c['telemetry_sources'];r=self.s.cycle(c,PROFILE)
  self.assertIn('TELEMETRY_SOURCES_UNCONFIRMED',r['safety_reasons']);self.assertEqual(self.ha.calls,[])
 def test_readonly_reports_quality_without_actuation(self):
  self.ha.telemetry_age=181;r=self.s.cycle(config('READ_ONLY'),PROFILE)
  self.assertEqual(r['effective_state'],'READ_ONLY');self.assertEqual(r['telemetry_quality'],'HA_TELEMETRY_STALE_OR_FUTURE');self.assertEqual(self.ha.calls,[])
 def test_final_executor_check_rejects_changed_telemetry(self):
  original=self.ha.current_states;counter=[0]
  def changing(entities):
   if 'sensor.example_m1' in entities:
    counter[0]+=1
    if counter[0]>=3:self.ha.telemetry_age=181
   return original(entities)
  self.ha.current_states=changing
  r=self.s.cycle(config(),PROFILE)
  self.assertEqual(r['effective_state'],'HA_TELEMETRY_STALE_OR_FUTURE');self.assertEqual(self.ha.calls,[])
 def test_unknown_result_no_retry_after_restart(self):
  c=config();self.ha.fail=True;self.assertEqual(self.s.cycle(c,PROFILE)['effective_state'],'UNKNOWN');self.s.close()
  self.s=BatteryService(self.tmp.name,Local(),'synthetic',ha=self.ha);self.ha.fail=False;c['pending_request']['request_id']='after_restart'
  self.assertEqual(self.s.cycle(c,PROFILE)['effective_state'],'UNKNOWN_REQUIRES_RECONCILIATION');self.assertEqual(len(self.ha.calls),1)
 def test_dedup_and_integrity_separate_process(self):
  c=config();self.assertEqual(self.s.cycle(c,PROFILE)['effective_state'],'ACK');self.assertEqual(self.s.cycle(c,PROFILE)['effective_state'],'DUPLICATE_ACK');self.assertEqual(len(self.ha.calls),1)
  p=Path(self.tmp.name)/'battery-execution.sqlite';out=subprocess.check_output([sys.executable,'-c',"import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(c.execute('pragma integrity_check').fetchone()[0],c.execute('select count(*) from commands').fetchone()[0])",str(p)],text=True);self.assertEqual(out.strip(),'ok 1')
 def test_sqlite_write_failure_does_not_issue_readonly_command(self):
  self.s.db.execute('PRAGMA query_only=ON')
  with self.assertRaises(sqlite3.Error):self.s.cycle(config('READ_ONLY'),PROFILE)
  self.assertEqual(self.ha.calls,[])
 def test_stale_evidence_blocks(self):
  c=config();c['verified_evidence']['physical_fallback']['valid_until']='2020-01-01T00:00:00+00:00';r=self.s.cycle(c,PROFILE);self.assertFalse(r['actuation_policy_enabled']);self.assertEqual(self.ha.calls,[])
 def test_corrupt_configuration_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'config';p.write_text('{')
   with patch('battery_service.CONFIG_PATH',p):self.assertEqual(read_config()['mode'],'READ_ONLY')

class ShadowGatewayProbeTests(unittest.TestCase):
 def test_missing_transport_is_unknown_persisted_and_never_replayed(self):
  with tempfile.TemporaryDirectory() as d:
   service=BatteryService(d,Local(),'synthetic',ha=TestHA())
   intent=config('READ_ONLY')['pending_request']
   first=service.shadow_gateway_probe(intent,2)
   self.assertEqual(first['status'],'UNKNOWN')
   self.assertEqual(first['reason'],'SHADOW_GATEWAY_METHOD_UNAVAILABLE_NOT_SENT')
   self.assertFalse(first['automatic_retry'])
   row=service.db.execute('SELECT state FROM shadow_gateway_requests WHERE request_id=?',(intent['request_id'],)).fetchone()
   self.assertEqual(row[0],'UNKNOWN')
   second=service.shadow_gateway_probe(intent,2)
   self.assertEqual(second['status'],'DUPLICATE_UNKNOWN_NO_REPLAY')
   self.assertEqual(service.ha.calls,[])
   service.close()
 def test_uncorrelated_rejection_is_unknown(self):
  with tempfile.TemporaryDirectory() as d:
   ha=TestHA();ha.shadow_dispatch=lambda intent,epoch:{'status':'REJECTED_NO_HARDWARE_WRITE','writes_started':False,'physical_dispatch_supported':False,'reason':'untrusted'}
   service=BatteryService(d,Local(),'synthetic',ha=ha);intent=config('READ_ONLY')['pending_request']
   result=service.shadow_gateway_probe(intent,2)
   self.assertEqual(result['status'],'UNKNOWN')
   row=service.db.execute('SELECT state FROM shadow_gateway_requests WHERE request_id=?',(intent['request_id'],)).fetchone()
   self.assertEqual(row[0],'UNKNOWN');service.close()
 def test_only_correlated_explicit_nonactuating_rejection_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   ha=TestHA()
   def reject(intent,epoch):
    return {'status':'REJECTED_NO_HARDWARE_WRITE','writes_started':False,'physical_dispatch_supported':False,
      'request_id':intent['request_id'],'plan_id':intent['plan_id'],'owner_epoch':epoch,'reason':'explicit_fence'}
   ha.shadow_dispatch=reject;service=BatteryService(d,Local(),'synthetic',ha=ha);intent=config('READ_ONLY')['pending_request']
   result=service.shadow_gateway_probe(intent,2)
   self.assertEqual(result['status'],'REJECTED')
   self.assertFalse(result['writes_started']);service.close()

class DeadlineTests(unittest.TestCase):
 def test_expired_transport_deadline_makes_no_request(self):
  from battery_executor import SupervisorHA
  import time
  ha=SupervisorHA('synthetic');ha.deadline=time.monotonic()-1
  with patch('urllib.request.urlopen') as network:
   with self.assertRaises(RuntimeError):ha.state('sensor.example_probe')
   network.assert_not_called()

class ReadOnlyGatewayTransportTests(unittest.TestCase):
 def test_shadow_dispatch_calls_only_ha_non_actuating_gateway_and_validates_identity(self):
  import json
  from unittest.mock import patch
  from battery_executor import SupervisorHA
  intent={'request_id':'req_1','plan_id':'a'*64,'option':'Charge from Solar Power','maximum_power_w':1000,'expires_at':(datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat()}
  reply={'gateway_contract':'EMS2_COMPOUND_V28','status':'REJECTED','writes_started':False,'physical_dispatch_supported':False,'device_execution_confirmed':False,'request_id':'req_1','plan_id':'a'*64,'owner_epoch':0,'reason':'TRUSTED_PHYSICAL_FENCE_UNVERIFIED'}
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self):return json.dumps({'service_response':reply}).encode()
  ha=SupervisorHA('synthetic-token')
  with patch('urllib.request.urlopen',return_value=Response()) as post:
   result=ha.shadow_dispatch(intent,0)
  req=post.call_args.args[0]
  self.assertTrue(req.full_url.endswith('/services/ems_epoch_gateway/dispatch?return_response'))
  self.assertEqual(result['status'],'REJECTED_NO_HARDWARE_WRITE')
  self.assertFalse(result['writes_started']);self.assertFalse(result['physical_dispatch_supported'])

 def test_shadow_dispatch_mismatched_request_id_is_unknown(self):
  import json
  from unittest.mock import patch
  from battery_executor import SupervisorHA
  intent={'request_id':'req_1','plan_id':'a'*64,'option':'Charge from Solar Power','maximum_power_w':1000,'expires_at':(datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat()}
  reply={'gateway_contract':'EMS2_COMPOUND_V28','status':'REJECTED','writes_started':False,'physical_dispatch_supported':False,'device_execution_confirmed':False,'request_id':'other','plan_id':'a'*64,'owner_epoch':0}
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self):return json.dumps({'service_response':reply}).encode()
  with patch('urllib.request.urlopen',return_value=Response()):
   result=SupervisorHA('synthetic-token').shadow_dispatch(intent,0)
  self.assertEqual(result['status'],'UNKNOWN');self.assertEqual(result['reason'],'GATEWAY_CONTRACT_OR_IDENTITY_MISMATCH')

