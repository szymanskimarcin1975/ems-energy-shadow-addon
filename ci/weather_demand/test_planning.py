import json,sqlite3,tempfile,unittest,subprocess,sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
from planning_runtime import Planner,plan
T=datetime(2026,10,16,4,tzinfo=timezone.utc)
def fixture(now=T):
 at=now.isoformat();z=lambda v,u:dict(state=str(v),attributes={'unit_of_measurement':u},last_reported=at)
 solar={k:'sensor.example_'+k for k in ('ac_power','b1_power','b1_soc','b1_status')}
 o={'sources':{'grid_kw':'sensor.example_grid'},'observation':{'solar_sources':solar,'boiler_sources':{'workday':'binary_sensor.example_workday'}}}
 c=dict(enabled=True,capacity_entity='sensor.example_capacity',charge_limit_entity='sensor.example_charge',discharge_limit_entity='sensor.example_discharge',simulation_min_soc_percent=30,simulation_charge_eff=.95,simulation_discharge_eff=.95,working_rates_pln_kwh={'dolina':.6,'szczyt_przedpoludniowy':.9,'szczyt_popoludniowy':1.5},rates_effective_from='2026-01-01T00:00:00+00:00',rates_version='synthetic',rates_basis='synthetic',pv_updated_entity='sensor.example_pv_update',pv_forecast_entities=['sensor.example_pv'])
 s={solar['ac_power']:z(100,'W'),solar['b1_power']:z(-100,'W'),solar['b1_soc']:z(50,'%'),solar['b1_status']:dict(state='B_STATUS_DISCHARGE'),'sensor.example_grid':z(-.2,'kW'),c['capacity_entity']:z(9.2,'kWh'),c['charge_limit_entity']:z(5000,'W'),c['discharge_limit_entity']:z(5000,'W'),'binary_sensor.example_workday':dict(state='on'),c['pv_updated_entity']:dict(state=at)}
 target=(now+timedelta(hours=1)).replace(minute=0,second=0,microsecond=0)
 h=[dict(valid_for=(target+timedelta(hours=i)).isoformat(),scenarios={d:{'prediction_kwh':.8} for d in ('workday','nonworkday')}) for i in range(24)]
 s['sensor.example_pv']=dict(attributes={'detailedHourly':[dict(period_start=r['valid_for'],pv_estimate=1,pv_estimate10=.5) for r in h]})
 return s,{'horizon':h},at,c,o
class Tests(unittest.TestCase):
 def test_hypothetical_only_actual_solver(self):
  r=plan(*fixture());self.assertEqual(r['status'],'HYPOTHETICAL_SCHEDULE_READY');self.assertEqual(len(r['decisions']),4);self.assertFalse(r['control_enabled']);self.assertEqual(len(r['decisions'][0]['schedule']),24);self.assertIsNone(r['flows']['actual_pv_production_w'])
 def test_missing_soc(self):
  a=list(fixture());del a[0]['sensor.example_b1_soc'];r=plan(*a);self.assertEqual(r['status'],'BLOCKED_INPUT');self.assertEqual(r['decisions'],[])
 def test_missing_load(self):
  a=list(fixture());a[1]['horizon'][0]['scenarios']['workday']['prediction_kwh']=None;self.assertEqual(plan(*a)['status'],'BLOCKED_INPUT')
 def test_stale_pv(self):
  a=list(fixture());a[0]['sensor.example_pv_update']['state']='2026-10-01T00:00:00+00:00';self.assertEqual(plan(*a)['status'],'BLOCKED_INPUT')
 def test_unknown_workday(self):
  a=list(fixture());a[0]['binary_sensor.example_workday']['state']='unavailable';self.assertEqual(plan(*a)['status'],'BLOCKED_INPUT')
 def test_negative_balance_remains_blocked_for_control(self):
  a=list(fixture());a[0]['sensor.example_grid']['state']='2';r=plan(*a);self.assertEqual(r['balance']['status'],'INCONSISTENT_NEGATIVE_LOAD');self.assertFalse(r['control_enabled'])
 def test_sqlite_duplicate_reopen_integrity(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'new.sqlite';s=Planner(p);s.run(*fixture());s.run(*fixture());s.c.close()
   out=subprocess.check_output([sys.executable,'-c',"import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(c.execute('pragma integrity_check').fetchone()[0],c.execute('select count(*) from runs').fetchone()[0])",str(p)],text=True)
   self.assertEqual(out.strip(),'ok 1')
 def test_readonly_transaction_no_partial(self):
  with tempfile.TemporaryDirectory() as d:
   s=Planner(Path(d)/'a.sqlite');s.c.execute('PRAGMA query_only=ON')
   with self.assertRaises(sqlite3.Error):s.run(*fixture())
   self.assertEqual(s.c.execute('select count(*) from runs').fetchone()[0],0);s.c.close()
if __name__=='__main__':unittest.main()
