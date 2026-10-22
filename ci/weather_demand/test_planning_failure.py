"""Synthetic worker errors and restart: no device transport."""
import json,sqlite3,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch,MagicMock
import demand_runtime as runtime
from demand_runtime import planning_error_report
from planning_runtime import Planner
from test_planning import fixture,T
from test_household_advisory import history
from plan_bridge import build

class FailureTests(unittest.TestCase):
 def test_no_exception_payload_or_dispatchable_plan(self):
  secret='https://example.invalid/?api_key=synthetic-private /private/path'
  for exc in (ValueError(secret),KeyError(secret),OSError(secret),sqlite3.OperationalError(secret)):
   r=planning_error_report(exc,T.isoformat(),'run')
   self.assertNotIn(secret,json.dumps(r));self.assertFalse(r['current_plan_usable_for_simulation'])
   self.assertFalse(r['control_enabled']);self.assertEqual(r['household_advisory']['decisions'],[])
   self.assertIsNone(build(r,{},T,0)['pending_request'])
 def test_fixed_error_codes(self):
  for exc,code in ((OSError('planning_storage_limit'),'PLANNING_STORAGE_LIMIT'),(ValueError('planning_config_too_large'),'PLANNING_CONFIG_TOO_LARGE'),(sqlite3.OperationalError('database is locked'),'PLANNING_SQLITE_ERROR')):
   self.assertEqual(planning_error_report(exc,T.isoformat(),'observe')['error']['code'],code)
 def test_unknown_stage_not_echoed(self):
  r=planning_error_report(ValueError('secret'),T.isoformat(),'secret')
  self.assertEqual(r['error']['stage'],'unknown');self.assertNotIn('secret',json.dumps(r))
 def worker_failure(self,stage):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);s,pred,at,cfg,opt=fixture(datetime.now(timezone.utc))
   opt['observation'].update(enabled=True,weather={'local_entity':'sensor.example_temperature','weather_entity':'weather.example','max_ha_age_seconds':900})
   opt['observation']['boiler_sources']['energy']='sensor.example_energy'
   pred.update(status='synthetic',training_rows=0,local_temperature_input={})
   for h in pred['horizon']:
    for v in h['scenarios'].values():v['temperature_used']=False
   op=root/'options.json';op.write_text(json.dumps(opt));cp=root/'planning.json';cp.write_text(json.dumps(cfg))
   api=MagicMock();api.call.side_effect=lambda method,path,*args:([dict(v,entity_id=k) for k,v in s.items()] if method=='GET' else {'service_response':{'weather.example':{'forecast':[]}}})
   planner=MagicMock();planner.last_report={'status':'old-ready'}
   getattr(planner,stage).side_effect=sqlite3.OperationalError('private SQL details')
   written={};argv=['worker','--options',str(op),'--root',str(root),'--planning-config',str(cp),'--stop-after-cycles','1']
   with patch.object(runtime,'ReadAPI',return_value=api),patch.object(runtime,'Planner',return_value=planner),patch.object(runtime.Store,'forecast',return_value=pred),patch.object(runtime,'atomic',side_effect=lambda p,r:written.update({str(p):r})),patch.dict('os.environ',{'SUPERVISOR_TOKEN':'synthetic'}),patch('sys.argv',argv),patch.object(runtime.signal,'signal'):
    self.assertEqual(runtime.main(),0)
   r=written['/ha_config/ems_shadow/planning_report.yaml'];self.assertEqual(r['error']['stage'],stage)
   self.assertEqual(r['error']['code'],'PLANNING_SQLITE_ERROR');self.assertIsNone(planner.last_report)
   self.assertFalse(r['current_plan_usable_for_simulation']);self.assertIn('/ha_config/ems_shadow/demand_report.yaml',written)
   self.assertEqual(api.call.call_count,2)
 def test_observe_failure_keeps_demand_capture(self):self.worker_failure('observe')
 def test_run_failure_discards_old_ready_plan(self):self.worker_failure('run')
 def test_below_reserve_restart_and_readonly_bridge(self):
  s,pred,at,cfg,opt=fixture();s['sensor.example_b1_soc']['state']='4.444445'
  cfg['include_current_slot']=True
  s['sensor.example_pv']['attributes']['detailedHourly'].insert(0,dict(period_start=T.isoformat(),pv_estimate=3,pv_estimate10=2))
  cfg.update(household_history_enabled=True,m1_scope_evidence={'scope':'whole_building_grid_exchange','confirmed_by':'installation_owner','confirmed_at':(T-timedelta(days=1)).isoformat()})
  approval={'soc_operating_bounds':{'minimum':5,'maximum':95,'owner_approved':True}}
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'planner.sqlite'
   for _ in range(2):
    planner=Planner(path)
    try:
     with patch('planning_runtime.load_profile',return_value=approval),patch('planning_runtime.load_history',return_value=history()),patch.object(planner.safety,'summary',return_value={'current_ha_set_valid':True}):r=planner.run(s,pred,at,cfg,opt)
     self.assertEqual(r['status'],'ADVISORY_HOUSEHOLD_SCHEDULE_READY');self.assertFalse(r['control_enabled'])
     for d in r['household_advisory']['decisions']:
      prev=9.2*4.444445/100
      for row in d['schedule']:
       if prev<.46:self.assertEqual(row['discharge_ac_kwh'],0)
       prev=row['stored_kwh']
     b=build(r,{'expected_fingerprint':r['planning_config_fingerprint'],'future_day_type':'workday','pv_scenario':'pv_estimate10'},T,0)
     self.assertEqual(b['status'],'PLAN_REQUEST_PREPARED')
     self.assertTrue(b['pending_request']['request_id'].startswith('plan_'))
     self.assertEqual(b['pending_request']['planning_config_fingerprint'],r['planning_config_fingerprint'])
     self.assertTrue(b['pending_request']['plan_id'])
     self.assertEqual(planner.c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
    finally:planner.c.close()
