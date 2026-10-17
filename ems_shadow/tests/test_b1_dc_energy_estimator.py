import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
from b1_dc_energy_estimator import EnergyEstimator
def stamp(n):
    from datetime import datetime,timedelta,timezone
    return (datetime(2026,10,17,16,tzinfo=timezone.utc)+timedelta(seconds=n)).isoformat()
class Tests(unittest.TestCase):
    def test_discharge(self):
        e=EnergyEstimator();e.observe(stamp(0),-2400)
        x=e.observe(stamp(120),-2400)
        self.assertAlmostEqual(x["discharge_dc_kwh_estimated"],.08)
        self.assertEqual(x["charge_dc_kwh_estimated"],0)
    def test_charge(self):
        e=EnergyEstimator();e.observe(stamp(0),1000)
        self.assertAlmostEqual(e.observe(stamp(120),1000)["charge_dc_kwh_estimated"],1/30,places=5)
    def test_gap_skipped(self):
        e=EnergyEstimator();e.observe(stamp(0),2000)
        self.assertEqual(e.observe(stamp(300),2000)["status"],"GAP_SKIPPED")
        self.assertEqual(e.observe(stamp(420),2000)["accepted_intervals"],1)
        self.assertEqual(e.report("X")["skipped_gaps"],1)
    def test_duplicate(self):
        e=EnergyEstimator();e.observe(stamp(0),-1000)
        self.assertEqual(e.observe(stamp(0),-1000)["status"],"DUPLICATE_OR_OUT_OF_ORDER")
    def test_out_of_order_does_not_advance(self):
        e=EnergyEstimator();e.observe(stamp(120),1000)
        e.observe(stamp(0),1000)
        self.assertEqual(e.observe(stamp(240),1000)["accepted_intervals"],1)
    def test_crossing_zero(self):
        e=EnergyEstimator();e.observe(stamp(0),1000)
        x=e.observe(stamp(120),-1000)
        self.assertAlmostEqual(x["charge_dc_kwh_estimated"],1/120,places=6)
        self.assertAlmostEqual(x["discharge_dc_kwh_estimated"],1/120,places=6)
    def test_bad_values(self):
        e=EnergyEstimator();self.assertEqual(e.observe(stamp(0),float("nan"))["status"],"EVIDENCE_GAP_REBASELINED")
        self.assertEqual(e.observe(stamp(0),True)["status"],"EVIDENCE_GAP_REBASELINED")
    def test_invalid_sample_breaks_continuity(self):
        e=EnergyEstimator()
        e.observe(stamp(0),-2400)
        e.observe(stamp(120),float("nan"))
        self.assertEqual(e.observe(stamp(240),-2400)["status"],"BASELINE")
        self.assertEqual(e.report("X")["accepted_intervals"],0)
    def test_unavailable_ha_snapshot_breaks_continuity(self):
        e=EnergyEstimator()
        e.observe(stamp(0),-2400)
        self.assertEqual(e.invalidate_continuity()["status"],"EVIDENCE_GAP_REBASELINED")
        self.assertEqual(e.observe(stamp(120),-2400)["status"],"BASELINE")
    def test_restart_resets_estimates(self):
        e=EnergyEstimator();e.observe(stamp(0),-1000);e.observe(stamp(120),-1000)
        self.assertEqual(EnergyEstimator().report("BASELINE")["discharge_dc_kwh_estimated"],0)
if __name__=="__main__":unittest.main()
