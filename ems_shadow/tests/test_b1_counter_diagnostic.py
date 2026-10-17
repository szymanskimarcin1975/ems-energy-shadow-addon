import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
from b1_counter_diagnostic import evaluate
BASE={"timestamp":"2026-10-17T16:00:00+00:00","import_kwh":10.0,"export_kwh":13.0}
def sample(**kwargs):
    return {**BASE,**kwargs}
class B1CounterTests(unittest.TestCase):
    def test_stationary_active(self):
        self.assertEqual(evaluate(BASE,sample(timestamp="2026-10-17T16:10:00+00:00"),mean_abs_watts=1500)["status"],"STATIONARY_WITH_ACTIVE_POWER")
    def test_stationary_unknown(self):
        self.assertEqual(evaluate(BASE,sample(timestamp="2026-10-17T16:10:00+00:00"))["status"],"STATIONARY_UNCONFIRMED")
    def test_advance(self):
        self.assertEqual(evaluate(BASE,sample(timestamp="2026-10-17T16:10:00+00:00",import_kwh=10.3))["status"],"COUNTERS_ADVANCING")
    def test_decrease(self):
        self.assertEqual(evaluate(BASE,sample(timestamp="2026-10-17T16:10:00+00:00",export_kwh=12.5))["status"],"COUNTER_DECREASED")
    def test_short_window(self):
        self.assertEqual(evaluate(BASE,sample(timestamp="2026-10-17T16:02:00+00:00"),mean_abs_watts=1500)["status"],"INSUFFICIENT_WINDOW")
    def test_naive_time(self):
        self.assertEqual(evaluate(BASE,sample(timestamp="2026-10-17T16:10:00"))["status"],"INVALID_TIMESTAMPS")
    def test_backwards_time(self):
        self.assertEqual(evaluate(BASE,sample(timestamp="2026-10-17T15:59:00+00:00"))["status"],"INVALID_ORDER")
    def test_nan(self):
        self.assertEqual(evaluate(BASE,sample(timestamp="2026-10-17T16:10:00+00:00",export_kwh=float("nan")))["status"],"INVALID_EVIDENCE")
    def test_nan_power(self):
        self.assertEqual(evaluate(BASE,sample(timestamp="2026-10-17T16:10:00+00:00"),mean_abs_watts=float("nan"))["status"],"INVALID_POWER_EVIDENCE")
if __name__=="__main__":
    unittest.main()
