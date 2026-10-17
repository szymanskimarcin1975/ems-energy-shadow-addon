import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
from b1_sample_window import B1Window
class B1SamplingTests(unittest.TestCase):
    def setUp(self): self.s=B1Window()
    def test_duplicate_report(self):
        self.assertEqual(self.s.add("2026-10-17T16:00:00+00:00",2000),"ACCEPTED")
        self.assertEqual(self.s.add("2026-10-17T16:00:00+00:00",3000),"DUPLICATE_REPORT")
        self.assertEqual(len(self.s.get()),1)
    def test_accept_same_power_new_time(self):
        self.s.add("2026-10-17T16:00:00+00:00",2000)
        self.assertEqual(self.s.add("2026-10-17T16:02:01+00:00",2000),"ACCEPTED")
    def test_reject_order(self):
        self.s.add("2026-10-17T16:02:01+00:00",2000)
        self.assertEqual(self.s.add("2026-10-17T16:00:00+00:00",2000),"OUT_OF_ORDER")
    def test_reject_naive(self):
        self.assertEqual(self.s.add("2026-10-17T16:00:00",2000),"INVALID_SAMPLE")
    def test_nonfinite(self):
        self.assertEqual(self.s.add("2026-10-17T16:00:00+00:00",float("inf")),"INVALID_SAMPLE")
    def test_rollover(self):
        s=B1Window(max_samples=2)
        for t in ("00","02","04"):
            self.assertEqual(s.add("2026-10-17T16:"+t+":00+00:00",200),"ACCEPTED")
        self.assertEqual(len(s.get()),2)
if __name__=="__main__":unittest.main()
