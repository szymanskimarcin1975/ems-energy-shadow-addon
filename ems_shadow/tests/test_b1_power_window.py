import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
from b1_power_window import window_mean_abs_power
def row(t,p): return {"timestamp":"2026-10-17T16:"+t+":00+00:00","watts":p}
class PowerWindowTests(unittest.TestCase):
    def test_weighted(self):
        rows=[row("00",1000),row("02",2000),row("04",0),row("06",0)]
        self.assertAlmostEqual(window_mean_abs_power(rows,rows[0]["timestamp"],rows[-1]["timestamp"]),1000)
    def test_long_gap_unknown(self):
        rows=[row("00",2000),row("04",2000)]
        self.assertIsNone(window_mean_abs_power(rows,rows[0]["timestamp"],rows[-1]["timestamp"]))
    def test_missing_window_boundary(self):
        rows=[row("01",1000),row("03",1000)]
        self.assertIsNone(window_mean_abs_power(rows,row("00",0)["timestamp"],rows[-1]["timestamp"]))
    def test_duplicate_time(self):
        rows=[row("00",100),row("00",100),row("02",100)]
        self.assertIsNone(window_mean_abs_power(rows,rows[0]["timestamp"],rows[-1]["timestamp"]))
    def test_nonfinite_unknown(self):
        rows=[row("00",float("nan")),row("02",500)]
        self.assertIsNone(window_mean_abs_power(rows,rows[0]["timestamp"],rows[-1]["timestamp"]))
    def test_reverse_power_absolute(self):
        rows=[row("00",-1000),row("02",-1000),row("04",1000)]
        self.assertAlmostEqual(window_mean_abs_power(rows,rows[0]["timestamp"],rows[-1]["timestamp"]),1000)
if __name__=="__main__":unittest.main()
