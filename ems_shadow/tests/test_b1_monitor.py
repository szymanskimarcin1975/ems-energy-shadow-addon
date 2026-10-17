import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
from b1_monitor import Monitor
def states(minute,kw=2,imp=10,exp=13):
    stamp="2026-10-17T16:%02d:00+00:00"%minute
    return {key:{"state":str(val),"last_reported":stamp} for key,val in [
        ("sensor.example_b1_dc_power",kw*1000),
        ("sensor.example_b1_energy_import",imp),
        ("sensor.example_b1_energy_export",exp)]}
class B1MonitorTests(unittest.TestCase):
    def test_stationary_with_active_power(self):
        m=Monitor("sensor.example_b1_dc_power")
        for i in (0,2,4): m.observe(states(i))
        self.assertEqual(m.observe(states(6))["status"],"STATIONARY_WITH_ACTIVE_POWER")
    def test_dedup(self):
        m=Monitor("sensor.example_b1_dc_power");m.observe(states(0))
        self.assertEqual(m.observe(states(0))["status"],"WAITING_FOR_NEW_HA_REPORT")
    def test_reset(self):
        m=Monitor("sensor.example_b1_dc_power");m.observe(states(0))
        self.assertEqual(m.observe(states(2,exp=12))["status"],"COUNTER_DECREASED")
    def test_missing_channel(self):
        m=Monitor("sensor.example_b1_dc_power")
        self.assertEqual(m.observe({})["status"],"UNAVAILABLE_OR_INVALID_HA_INPUT")
    def test_no_power_evidence_with_gap(self):
        m=Monitor("sensor.example_b1_dc_power");m.observe(states(0))
        self.assertEqual(m.observe(states(6))["status"],"GAP_REBASELINED")
    def test_no_actuation_authority(self):
        m=Monitor("sensor.example_b1_dc_power")
        self.assertTrue(m.observe(states(0))["advisory_only"])
    def test_restart_requires_new_baseline(self):
        m=Monitor("sensor.example_b1_dc_power")
        m.observe(states(0))
        m.observe(states(2))
        restarted=Monitor("sensor.example_b1_dc_power")
        self.assertEqual(restarted.observe(states(4))["status"],"BASELINE_CAPTURED")
        self.assertEqual(restarted.observe(states(6))["status"],"INSUFFICIENT_WINDOW")
    def test_unchanged_ha_timestamp_does_not_accumulate_power(self):
        m=Monitor("sensor.example_b1_dc_power")
        m.observe(states(0))
        for _ in range(20):
            self.assertEqual(m.observe(states(0))["status"],"WAITING_FOR_NEW_HA_REPORT")
        self.assertEqual(len(m.window.get()),1)
    def test_stale_other_counter_not_considered_same_snapshot(self):
        m=Monitor("sensor.example_b1_dc_power")
        sample=states(0)
        sample["sensor.example_b1_energy_import"]["last_reported"]="2026-10-17T15:56:00+00:00"
        self.assertEqual(m.observe(sample)["status"],"HA_REPORT_SKEW_OR_MISSING")
    def test_gap_rebaselines(self):
        m=Monitor("sensor.example_b1_dc_power")
        m.observe(states(0))
        self.assertEqual(m.observe(states(6))["status"],"GAP_REBASELINED")
        self.assertEqual(m.observe(states(8))["status"],"INSUFFICIENT_WINDOW")
    def test_counter_drop_after_gap_detected(self):
        m=Monitor("sensor.example_b1_dc_power")
        m.observe(states(0))
        m.observe(states(6))
        self.assertEqual(m.observe(states(8,exp=12))["status"],"COUNTER_DECREASED")
if __name__=="__main__":unittest.main()
