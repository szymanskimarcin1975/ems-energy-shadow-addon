import copy,json,sqlite3,tempfile,subprocess,sys,unittest
from pathlib import Path
from datetime import timedelta
from test_planning import fixture,T
from control_safety import Safety,HandoverDryRun
from planning_runtime import plan

def sample(i=0):
    args=list(fixture(T+timedelta(seconds=120*i)))
    args[0]['sensor.example_b1_status']['last_reported']=args[2]
    return args

class TelemetryTests(unittest.TestCase):
    def setUp(self):self.c=sqlite3.connect(':memory:',isolation_level=None);self.s=Safety(self.c)
    def tearDown(self):self.c.close()
    def test_actual_intervals_and_repeats(self):
        for i in range(7):
            a=sample(i);self.s.observe(a[0],a[2],a[4])
        self.s.observe(a[0],(T+timedelta(seconds=740)).isoformat(),a[4])
        r=self.s.summary((T+timedelta(seconds=740)).isoformat())
        self.assertTrue(r['current_ha_set_valid'])
        self.assertEqual(r['ha_reporting_intervals']['b1']['distinct_ha_reports'],7)
        self.assertEqual(r['ha_reporting_intervals']['b1']['min_median_max_seconds'],[120,120,120])
        self.assertIsNone(r['real_device_reporting_coverage']);self.assertFalse(r['external_writer_fence_installed'])
    def test_same_value_new_ha_timestamp_is_ha_observation_only(self):
        for i in range(2):
            a=sample(i);self.s.observe(a[0],a[2],a[4])
        r=self.s.summary(a[2]);self.assertEqual(r['ha_reporting_intervals']['ac']['distinct_ha_reports'],2)
        self.assertFalse(r['ha_reporting_intervals']['ac']['device_cycle_confirmed'])
    def test_all_reasons_and_no_interpolation(self):
        a=sample();a[0]['sensor.example_ac_power']['last_reported']=(T+timedelta(seconds=10)).isoformat()
        a[0]['sensor.example_b1_power']['last_reported']=(T-timedelta(seconds=500)).isoformat()
        r=self.s.observe(a[0],a[2],a[4]);self.assertFalse(r['ha_set_valid'])
        self.assertTrue({'FUTURE_AC','STALE_B1','HA_SET_SKEW'}<=set(r['reasons']))
    def test_missing_status_not_valid(self):
        a=sample();del a[0]['sensor.example_b1_status'];r=self.s.observe(a[0],a[2],a[4])
        self.assertFalse(r['ha_set_valid']);self.assertIn('TIMESTAMP_STATUS',r['reasons'])
    def test_sign_status_conflict(self):
        a=sample();a[0]['sensor.example_b1_power']['state']='100'
        self.assertIn('B1_SIGN_STATUS_CONFLICT',self.s.observe(a[0],a[2],a[4])['reasons'])
    def test_timestamp_replay_conflict_and_out_of_order(self):
        a=sample(1);self.s.observe(a[0],a[2],a[4])
        a[0]['sensor.example_ac_power']['state']='101'
        r=self.s.observe(a[0],(T+timedelta(seconds=140)).isoformat(),a[4]);self.assertFalse(r['ha_set_valid'])
        self.assertIn('SAME_TIMESTAMP_CHANGED_VALUE_AC',r['reasons'])
        b=sample();r=self.s.observe(b[0],(T+timedelta(seconds=160)).isoformat(),b[4])
        self.assertIn('OUT_OF_ORDER_AC',r['reasons'])
    def test_source_mix_refused_and_transaction_rolled_back(self):
        a=sample();self.s.observe(a[0],a[2],a[4]);b=sample(1);b[4]['sources']['grid_kw']='sensor.example_other'
        with self.assertRaises(ValueError):self.s.observe(b[0],b[2],b[4])
        self.assertEqual(self.c.execute('select count(*) from safety_checks').fetchone()[0],1)
    def test_readonly_and_reopen(self):
        a=sample();self.c.execute('pragma query_only=ON')
        with self.assertRaises(sqlite3.Error):self.s.observe(a[0],a[2],a[4])
        self.assertEqual(self.c.execute('select count(*) from safety_checks').fetchone()[0],0)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.sqlite';c=sqlite3.connect(p,isolation_level=None);s=Safety(c);s.observe(a[0],a[2],a[4]);c.close()
            out=subprocess.check_output([sys.executable,'-c',"import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(c.execute('pragma integrity_check').fetchone()[0],c.execute('select count(*) from safety_samples').fetchone()[0])",str(p)],text=True)
            self.assertEqual(out.strip(),'ok 5')
    def test_duplicate_and_expired_summary(self):
        a=sample();self.s.observe(a[0],a[2],a[4]);self.assertEqual(self.s.observe(a[0],a[2],a[4]),'duplicate_capture')
        self.assertFalse(self.s.summary((T+timedelta(seconds=60)).isoformat())['current_ha_set_valid'])
    def test_live_plan_blocks_bad_b1_without_zeroing(self):
        a=sample();a[0]['sensor.example_b1_status']['state']='B_STATUS_FAULT';self.s.observe(a[0],a[2],a[4])
        r=plan(*a,building_profile={'ready':True,'power_w':300},input_safety=self.s.summary(a[2]))
        self.assertEqual(r['status'],'BLOCKED_INPUT');self.assertEqual(r['building_decisions'],[])
        self.assertFalse(r['control_enabled']);self.assertIn('FAULT_B1',r['input_safety']['last']['reasons'])

class HandoverTests(unittest.TestCase):
    def setUp(self):self.c=sqlite3.connect(':memory:',isolation_level=None);self.h=HandoverDryRun(self.c)
    def tearDown(self):self.c.close()
    def test_legacy_on_unknown_and_nonquiescent_block(self):
        for states,q in ((['on'],True),(['unknown'],True),(['off'],False),([],True)):
            self.assertEqual(self.h.take('battery','test',states,True,q),'BLOCKED')
        self.assertEqual(self.c.execute('select count(*) from dry_leases').fetchone()[0],0)
    def test_single_owner_duplicate_return_and_no_co(self):
        self.assertEqual(self.h.take('battery','one',['off'],True,True),'SIMULATED_ONLY')
        self.assertEqual(self.h.take('battery','one',['off'],True,True),'ALREADY_COMMITTED')
        self.assertEqual(self.h.take('battery','two',['off'],True,True),'BUSY')
        self.assertEqual(self.h.take('cwu','cwu',['off'],True,True),'SIMULATED_ONLY')
        with self.assertRaises(ValueError):self.h.take('co','bad',['off'],True,True)
        self.h.give_back('battery','return');self.h.give_back('battery','return')
        self.assertEqual(self.c.execute("select owner from dry_leases where device='cwu'").fetchone()[0],'SIMULATED_EMS')
    def test_write_failure_does_not_grant(self):
        self.c.execute('pragma query_only=ON')
        with self.assertRaises(sqlite3.Error):self.h.take('battery','one',['off'],True,True)
        self.assertEqual(self.c.execute('select count(*) from dry_audit').fetchone()[0],0)
    def test_audit_failure_rolls_back_lease(self):
        self.c.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON dry_audit BEGIN SELECT RAISE(ABORT,'synthetic_write_failure'); END")
        with self.assertRaises(sqlite3.Error):self.h.take('battery','one',['off'],True,True)
        self.assertEqual(self.c.execute('select count(*) from dry_leases').fetchone()[0],0)
        self.assertEqual(self.c.execute('select count(*) from dry_audit').fetchone()[0],0)
    def test_two_processes_cannot_hold_same_device(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'leases.sqlite';c=sqlite3.connect(p,isolation_level=None);HandoverDryRun(c);c.close()
            script="from control_safety import HandoverDryRun;import sqlite3,sys;c=sqlite3.connect(sys.argv[1],isolation_level=None);print(HandoverDryRun(c).take('battery',sys.argv[2],['off'],True,True))"
            children=[subprocess.Popen([sys.executable,'-c',script,str(p),str(i)],stdout=subprocess.PIPE,text=True) for i in range(2)]
            outputs=[c.communicate(timeout=10)[0].strip() for c in children]
            self.assertEqual(sorted(outputs),['BUSY','SIMULATED_ONLY'])
            c=sqlite3.connect(p);self.assertEqual(c.execute('pragma integrity_check').fetchone()[0],'ok')
            self.assertEqual(c.execute('select count(*) from dry_leases').fetchone()[0],1);c.close()
    def test_ambiguous_commit_reopens_without_second_owner(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'leases.sqlite'
            script="from control_safety import HandoverDryRun;import sqlite3,sys,os;c=sqlite3.connect(sys.argv[1],isolation_level=None);h=HandoverDryRun(c);h.take('battery','one',['off'],True,True);os._exit(9)"
            self.assertEqual(subprocess.run([sys.executable,'-c',script,str(p)]).returncode,9)
            c=sqlite3.connect(p,isolation_level=None);h=HandoverDryRun(c)
            self.assertEqual(c.execute('pragma integrity_check').fetchone()[0],'ok')
            self.assertEqual(h.take('battery','one',['off'],True,True),'ALREADY_COMMITTED')
            self.assertEqual(h.take('battery','two',['off'],True,True),'BUSY')
            self.assertEqual(c.execute('select count(*) from dry_audit').fetchone()[0],1);c.close()

if __name__=='__main__':unittest.main()
