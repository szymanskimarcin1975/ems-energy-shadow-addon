import unittest,tempfile,sqlite3,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from battery_service import BatteryService,PROOFS,read_config
from test_battery_executor import HA
PROFILE={'soc_operating_bounds':{'minimum':0,'maximum':100,'owner_approved':True},'operational_parameters':{'rated_energy_wh':9200,'max_charge_w':5000,'max_discharge_w':5000,'storage_control_mode':'Remote Control','storage_default_mode':'Maximize Self Consumption','storage_command_timeout_s':3600}}
class Local:
 def state(self):return {'owner':'EMS2','epoch':2}
class TestHA(HA):
 def state(self,e):
  if e=='number.example_timeout':return {'state':'3600'}
  if e=='select.example_default':return {'state':'Maximize Self Consumption'}
  if e=='input_boolean.example_auth':return {'state':getattr(self,'auth','on')}
  if e=='sensor.example_model':return {'state':'example-inverter'}
  if e=='sensor.example_firmware':return {'state':'example-firmware'}
  return super().state(e)
def config(mode='ACTIVE'):
 now=datetime.now(timezone.utc);device={'model':'example-inverter','firmware':'example-firmware'}
 return {'mode':mode,'device':device,'verified_evidence':{k:dict(verified=True,device=device,reference='synthetic-offline-evidence',verified_at=(now-timedelta(seconds=10)).isoformat(),valid_until=(now+timedelta(seconds=60)).isoformat()) for k in PROOFS},'safety_soc_bounds':{'minimum':0,'maximum':100},'owner_entity':'input_select.example_owner','authorization_entity':'input_boolean.example_auth','expected_epoch':2,'old_writers':['automation.old'],'sources':{'soc':'sensor.example_soc','command_mode':'select.mode','control_mode':'select.example_control','charge_limit':'number.charge','discharge_limit':'number.discharge','device_model':'sensor.example_model','device_firmware':'sensor.example_firmware','timeout':'number.example_timeout','default_mode':'select.example_default'},'bms_sources':{k:'sensor.example_bms_'+k for k in ('status','max_charge','peak_charge','max_discharge','peak_discharge')},'pending_request':{'request_id':'example_request','option':'Charge from Solar Power','expires_at':(now+timedelta(seconds=45)).isoformat()}}
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.ha=TestHA();self.s=BatteryService(self.tmp.name,Local(),'synthetic',ha=self.ha);self.addCleanup(self.s.close)
 def test_readonly_initializes_real_executor_without_transport_calls(self):
  with patch.object(self.ha,'state',side_effect=AssertionError('must not read actuator')):
   r=self.s.cycle(config('READ_ONLY'),PROFILE)
  self.assertTrue(r['executor_initialized']);self.assertIsNotNone(self.s.executor);self.assertEqual(r['effective_state'],'READ_ONLY');self.assertFalse(r['actuation_policy_enabled']);self.assertEqual(self.ha.calls,[])
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

class DeadlineTests(unittest.TestCase):
 def test_expired_transport_deadline_makes_no_request(self):
  from battery_executor import SupervisorHA
  import time
  ha=SupervisorHA('synthetic');ha.deadline=time.monotonic()-1
  with patch('urllib.request.urlopen') as network:
   with self.assertRaises(RuntimeError):ha.state('sensor.example_probe')
   network.assert_not_called()
