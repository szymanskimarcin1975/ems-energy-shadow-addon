import json,tempfile,unittest,sqlite3,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app/observation'))
from plan_bridge import build,Journal
NOW=datetime(2026,10,18,12,15,tzinfo=timezone.utc)
FP='a'*64
CFG={'enabled':True,'expected_fingerprint':FP,'future_day_type':'workday','pv_scenario':'pv_estimate10'}
def report(now=NOW,option='charge'):
 row={'valid_for':now.replace(minute=0,second=0,microsecond=0).isoformat(),'hours':1,'load_kwh':0,'pv_kwh':5 if option=='charge' else 0,'charge_ac_kwh':5 if option=='charge' else 0,'discharge_ac_kwh':0 if option=='charge' else 5}
 if option!='charge':row['load_kwh']=5
 return {'generated_at':now.isoformat(),'valid_until':(now+timedelta(seconds=360)).isoformat(),'status':'ADVISORY_HOUSEHOLD_SCHEDULE_READY','current_plan_usable_for_simulation':True,'input_safety':{'current_ha_set_valid':True},'planning_config_fingerprint':FP,'whole_building_schedule_approved':True,'household_advisory':{'decisions':[{'future_day_type':'workday','pv_scenario':'pv_estimate10','schedule':[row]}]}}
class Tests(unittest.TestCase):
 def b(self,r=None,at=NOW):return build(r or report(),CFG,at,2)
 def test_current_plan_request(self):
  r=self.b();self.assertEqual(r['status'],'PLAN_REQUEST_PREPARED');self.assertEqual(r['pending_request']['option'],'Charge from Solar Power');self.assertEqual(r['pending_request']['maximum_power_w'],5000)
 def test_expired_and_future_plan(self):
  self.assertEqual(self.b(at=NOW+timedelta(seconds=361))['status'],'PLAN_EXPIRED_OR_FUTURE');self.assertEqual(self.b(at=NOW-timedelta(seconds=1))['status'],'PLAN_EXPIRED_OR_FUTURE')
 def test_advisory_report_never_grants_authority(self):
  r=report();r['whole_building_schedule_approved']=False;self.assertTrue(self.b(r)['advisory_only'])
 def test_fingerprint_change_blocks(self):
  r=report();r['planning_config_fingerprint']='b'*64;self.assertEqual(self.b(r)['status'],'PLAN_FINGERPRINT_UNCONFIRMED')
 def test_future_slot_not_executed_early(self):
  r=report();r['household_advisory']['decisions'][0]['schedule'][0]['valid_for']=(NOW+timedelta(hours=1)).isoformat();self.assertEqual(self.b(r)['status'],'NO_CURRENT_PLAN_SLOT')
 def test_duplicate_identity_not_new_per_poll(self):self.assertEqual(self.b()['pending_request']['request_id'],self.b(at=NOW+timedelta(seconds=1))['pending_request']['request_id'])
 def test_logical_plan_identity_stable_across_report_refresh(self):
  first=self.b(report(NOW));refreshed=self.b(report(NOW+timedelta(seconds=20)),NOW+timedelta(seconds=20))
  self.assertEqual(first['pending_request']['request_id'],refreshed['pending_request']['request_id'])
  self.assertEqual(first['pending_request']['plan_id'],refreshed['pending_request']['plan_id'])
 def test_refresh_across_hour_changes_slot_identity(self):
  before=NOW.replace(minute=59,second=50);after=before+timedelta(seconds=20)
  first=self.b(report(before),before);second=self.b(report(after),after)
  self.assertNotEqual(first['pending_request']['request_id'],second['pending_request']['request_id'])
 def test_epoch_changes_request_identity(self):self.assertNotEqual(self.b()['pending_request']['request_id'],build(report(),CFG,NOW,3)['pending_request']['request_id'])
 def test_export_forbidden(self):
  r=report(option='discharge');r['household_advisory']['decisions'][0]['schedule'][0]['discharge_ac_kwh']=6;self.assertEqual(self.b(r)['status'],'PLAN_BATTERY_EXPORT_FORBIDDEN')
 def test_grid_charge_not_mislabelled_solar(self):
  r=report();r['household_advisory']['decisions'][0]['schedule'][0]['pv_kwh']=0;self.assertEqual(self.b(r)['pending_request']['option'],'Charge from Solar Power and Grid')
 def test_hold_does_not_issue_or_cancel(self):
  r=report();r['household_advisory']['decisions'][0]['schedule'][0]['charge_ac_kwh']=0;self.assertEqual(self.b(r)['status'],'PLAN_HOLD_NO_NEW_COMMAND')
 def test_plan_quality_blocks(self):
  r=report();r['input_safety']['current_ha_set_valid']=False;self.assertEqual(self.b(r)['status'],'PLAN_INPUT_QUALITY_UNCONFIRMED')
 def test_overlapping_slots_block(self):
  r=report();d=r['household_advisory']['decisions'][0];d['schedule']*=2;self.assertEqual(self.b(r)['status'],'PLAN_SLOT_GAP_OR_OVERLAP')
 def test_unknown_result_journal_reopen(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.sqlite';c=sqlite3.connect(p,isolation_level=None);j=Journal(c);j.observe(self.b(),'UNKNOWN');j.observe(self.b(),'UNKNOWN');c.close()
   out=subprocess.check_output([sys.executable,'-c',"import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(c.execute('pragma integrity_check').fetchone()[0],c.execute('select count(*) from planner_requests').fetchone()[0])",str(p)],text=True);self.assertEqual(out.strip(),'ok 1')
class FullPath(unittest.TestCase):
 def setUp(self):
  from battery_service import BatteryService
  from test_battery_service import Local
  from test_battery_service import TestHA,Local,config,PROFILE
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'plan.yaml';self.now=datetime.now(timezone.utc)
  class API(TestHA):
   def __init__(api):super().__init__();api.returned='Charge from Solar Power';api.remote=5000;api.fault='I_STATUS_MPPT';api.shadow_calls=[]
   def current_states(api,ids):
    ids=list(ids)
    if set(ids)=={'sensor.example_inverter','sensor.example_vendor'}:
     return {e:{'state':api.fault if e=='sensor.example_inverter' else '0x0','last_reported':api.source_at.isoformat()} for e in ids}
    return super().current_states(ids)
   def state(api,e):
    if e in ('number.charge','number.discharge'):return {'state':str(api.remote),'last_updated':datetime.now(timezone.utc).isoformat()}
    if e=='select.mode':return {'state':api.returned,'last_updated':datetime.now(timezone.utc).isoformat()}
    return super().state(e)
   def select(api,e,o,**kw):
    if getattr(api,'owner','EMS2')!='EMS2' or api.old!='off':raise AssertionError('synthetic_gateway_owner_rejected')
    api.returned=o;super().record_dispatch(e,o,**kw)
   def dispatch(api,e,o,power_w,**kw):
    api.remote=power_w;api.select(e,o,**kw);return {'applied_power_w':power_w}
   def shadow_dispatch(api,intent,epoch):
    api.shadow_calls.append((dict(intent),epoch))
    return {'status':'REJECTED_NO_HARDWARE_WRITE','reason':'TRUSTED_PHYSICAL_FENCE_UNVERIFIED','writes_started':False,'physical_dispatch_supported':False,'request_id':intent['request_id'],'plan_id':intent['plan_id'],'owner_epoch':epoch}
  self.ha=API();self.s=BatteryService(self.tmp.name,Local(),'synthetic',ha=self.ha);self.addCleanup(self.s.close)
  self.cfg=config();self.cfg['pending_request']=None;self.cfg['planner_bridge']=CFG;self.cfg['fault_sources']={'inverter_status':'sensor.example_inverter','vendor_status':'sensor.example_vendor'};self.profile=PROFILE
  for back in (240,120,0):
   self.ha.source_at=self.now-timedelta(seconds=back);self.s.fault_guard.observe(self.ha,self.cfg['fault_sources'],self.ha.source_at+timedelta(seconds=1))
  self.ha.source_at=self.now
  p=patch('plan_bridge.PLAN_PATH',self.path);p.start();self.addCleanup(p.stop);self.write(report(self.now))
 def write(self,r):self.path.write_text(json.dumps(r))
 def cycle(self):return self.s.cycle(self.cfg,self.profile)
 def test_request_gateway_executor_ack_dedup(self):
  a=self.cycle();self.assertEqual(a['effective_state'],'ACK');self.assertEqual(len(self.ha.calls),1);self.assertEqual(self.cycle()['effective_state'],'DUPLICATE_ACK');self.assertEqual(len(self.ha.calls),1)
 def test_readonly_plan_reaches_non_actuating_ha_gateway_once(self):
  self.cfg['mode']='READ_ONLY';r=self.cycle();self.assertIsNotNone(r['planner_bridge']['pending_request']);self.assertEqual(r['effective_state'],'SHADOW_GATEWAY_REJECTED');self.assertEqual(r['shadow_gateway']['status'],'REJECTED');self.assertFalse(r['shadow_gateway']['writes_started']);self.assertEqual(self.ha.calls,[]);self.assertEqual(len(self.ha.shadow_calls),1)
  again=self.cycle();self.assertEqual(again['shadow_gateway']['status'],'DUPLICATE_REJECTED_NO_REPLAY');self.assertEqual(len(self.ha.shadow_calls),1);self.assertEqual(self.ha.calls,[])
 def test_readonly_unknown_gateway_result_is_not_replayed_after_restart(self):
  from battery_service import BatteryService
  from test_battery_service import Local
  self.cfg['mode']='READ_ONLY';self.ha.shadow_calls=[]
  self.ha.shadow_dispatch=lambda intent,epoch: (self.ha.shadow_calls.append((intent,epoch)) or {'status':'UNKNOWN','reason':'timeout','writes_started':None,'physical_dispatch_supported':None})
  self.assertEqual(self.cycle()['shadow_gateway']['status'],'UNKNOWN');self.assertEqual(len(self.ha.shadow_calls),1);self.s.close()
  self.s=BatteryService(self.tmp.name,Local(),'synthetic',ha=self.ha);self.addCleanup(self.s.close)
  self.assertEqual(self.cycle()['shadow_gateway']['status'],'DUPLICATE_UNKNOWN_NO_REPLAY');self.assertEqual(len(self.ha.shadow_calls),1);self.assertEqual(self.ha.calls,[])
 def test_soc_100_rejected(self):
  self.ha.soc=100;self.assertEqual(self.cycle()['effective_state'],'SOC_CEILING');self.assertEqual(self.ha.calls,[])
 def test_bms_zero_rejected(self):
  self.ha.peak_charge=0;self.assertEqual(self.cycle()['effective_state'],'BMS_DIRECTION_LIMIT_ZERO');self.assertEqual(self.ha.calls,[])
 def test_stale_rejected(self):
  self.ha.telemetry_age=181;self.assertIn('HA_TELEMETRY_STALE_OR_FUTURE',self.cycle()['safety_reasons']);self.assertEqual(self.ha.calls,[])
 def test_fault_rejected(self):
  self.ha.fault='I_STATUS_FAULT';self.assertIn('INVERTER_FAULT',self.cycle()['safety_reasons']);self.assertEqual(self.ha.calls,[])
 def test_legacy_rejected(self):
  self.ha.owner='LEGACY';self.assertEqual(self.cycle()['effective_state'],'OWNERSHIP_UNCONFIRMED');self.assertEqual(self.ha.calls,[])
 def test_expired_plan_rejected(self):
  self.write(report(self.now-timedelta(seconds=400)));self.assertIn('PLAN_EXPIRED_OR_FUTURE',self.cycle()['safety_reasons']);self.assertEqual(self.ha.calls,[])
 def test_power_setpoint_is_applied_through_gateway(self):
  r=report(self.now);r['household_advisory']['decisions'][0]['schedule'][0]['charge_ac_kwh']=1;self.write(r);self.assertEqual(self.cycle()['effective_state'],'ACK');self.assertEqual(self.ha.remote,1000);self.assertEqual(len(self.ha.calls),1)
 def test_advisory_approval_required(self):
  r=report(self.now);r['whole_building_schedule_approved']=False;self.write(r);self.assertIn('PLAN_NOT_APPROVED_FOR_CONTROL',self.cycle()['safety_reasons']);self.assertEqual(self.ha.calls,[])
 def test_unknown_not_retried(self):
  self.ha.fail=True;self.assertEqual(self.cycle()['effective_state'],'UNKNOWN');self.ha.fail=False;self.assertEqual(self.cycle()['effective_state'],'DUPLICATE_UNKNOWN');self.assertEqual(len(self.ha.calls),1)
 def test_grid_charge_uses_compound_gateway(self):
  r=report(self.now);r['household_advisory']['decisions'][0]['schedule'][0]['pv_kwh']=0;self.write(r)
  outcome=self.cycle();self.assertTrue(outcome['planner_bridge']['execution_mode_supported']);self.assertEqual(outcome['effective_state'],'ACK');self.assertEqual(self.ha.calls[0][1],'Charge from Solar Power and Grid')
 def test_plan_changes_during_final_check_no_command(self):
  with patch.object(self.s,'plan_still_current',side_effect=[True,False]):r=self.cycle()
  self.assertEqual(r['effective_state'],'PLAN_CHANGED_OR_EXPIRED');self.assertEqual(self.ha.calls,[])
 def test_forecast_to_real_solver_to_request_to_gateway_ack(self):
  from weather_demand import predict
  from deadline_dispatch import simulate_deadlines
  rows=[]
  for i in range(8):
   start=self.now-timedelta(days=i+1,hours=1);end=start+timedelta(hours=1)
   rows.append(dict(target='boiler',slot=self.now.hour,day_type='workday',quality_approved=True,coverage=1,temperature_quality='approved',temperature_c=10,kwh=2,start=start.isoformat(),end=end.isoformat(),available_at=end.isoformat(),local_day=start.date().isoformat()))
  forecast=predict(rows,self.now.isoformat(),self.now.hour,'workday',None)
  self.assertEqual(forecast['prediction_kwh'],2);self.assertFalse(forecast['temperature_used'])
  solved=simulate_deadlines([dict(load_kwh=forecast['prediction_kwh'],pv_kwh=7,price_pln_kwh=1,hours=1,target_after_kwh=9.2)],9.2,4.6,0,5,5,.95,.95)
  r=report(self.now);slot=dict(solved['schedule'][0],valid_for=self.now.replace(minute=0,second=0,microsecond=0).isoformat(),hours=1,load_kwh=2,pv_kwh=7)
  r['household_advisory']['decisions'][0]['schedule']=[slot];self.write(r)
  intent=build(r,CFG,self.now,2)['pending_request'];self.ha.remote=intent['maximum_power_w']
  result=self.cycle();self.assertEqual(result['effective_state'],'ACK');self.assertEqual(len(self.ha.calls),1)

class OwnershipDryRun(unittest.TestCase):
 def test_transfer_and_rollback_persist_without_any_device_transport(self):
  from ownership import Ownership
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'owner.sqlite';o=Ownership(path,{'example':'synthetic'})
   self.assertEqual(o.state()['owner'],'LEGACY')
   with self.assertRaises(ValueError):o.transition('unsafe',0,'EMS2',old_stopped=True,external_fence_verified=True)
   o.transition('begin',0,'TRANSFER_PENDING');o.transition('take',1,'EMS2',old_stopped=True,external_fence_verified=True)
   self.assertEqual(o.state()['owner'],'EMS2');self.assertEqual(o.transition('take',1,'EMS2',old_stopped=True,external_fence_verified=True),'DUPLICATE')
   o.transition('stop',2,'BLOCKED')
   with self.assertRaises(ValueError):o.transition('unsafe_back',3,'LEGACY')
   o.transition('back',3,'LEGACY',new_stopped=True,external_fence_verified=True);o.close()
   o=Ownership(path,{'example':'synthetic'});self.assertEqual(o.state()['owner'],'LEGACY');self.assertEqual(o.state()['epoch'],4);self.assertFalse(o.state()['commands_permitted']);o.close()
   out=subprocess.check_output([sys.executable,'-c',"import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(c.execute('pragma integrity_check').fetchone()[0],c.execute('select count(*) from audit').fetchone()[0])",str(path)],text=True);self.assertEqual(out.strip(),'ok 4')
