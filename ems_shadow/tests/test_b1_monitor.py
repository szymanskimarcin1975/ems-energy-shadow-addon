import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
from b1_monitor import Monitor
def states(minute,kw=2,imp=10,exp=13):
    stamp="2026-10-17T16:%02d:00+00:00"%minute
    return {key:{"state":str(val),"last_reported":stamp} for key,val in [
        ("sensor.solaredge_i1_b1_dc_power",kw*1000),
        ("sensor.solaredge_i1_b1_energy_import",imp),
        ("sensor.solaredge_i1_b1_energy_export",exp)]}
class B1MonitorTests(unittest.TestCase):
    def test_stationary_with_active_power(self):
        m=Monitor()
        for i in (0,2,4): m.observe(states(i))
        self.assertEqual(m.observe(states(6))["status"],"STATIONARY_WITH_ACTIVE_POWER")
    def test_dedup(self):
        m=Monitor();m.observe(states(0))
        self.assertEqual(m.observe(states(0))["status"],"WAITING_FOR_NEW_HA_REPORT")
    def test_reset(self):
        m=Monitor();m.observe(states(0))
        self.assertEqual(m.observe(states(2,exp=12))["status"],"COUNTER_DECREASED")
    def test_missing_channel(self):
        m=Monitor()
        self.assertEqual(m.observe({})["status"],"UNAVAILABLE_OR_INVALID_HA_INPUT")
    def test_no_power_evidence_with_gap(self):
        m=Monitor();m.observe(states(0))
        self.assertEqual(m.observe(states(6))["status"],"STATIONARY_UNCONFIRMED")
    def test_no_actuation_authority(self):
        m=Monitor()
        self.assertTrue(m.observe(states(0))["advisory_only"])
if __name__=="__main__":unittest.main()
