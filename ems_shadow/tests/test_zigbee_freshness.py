import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
from zigbee_freshness import classify
NOW="2026-10-17T18:05:00+00:00"
class TestFreshness(unittest.TestCase):
 def test_fresh(self):
  v=classify(NOW,{"boiler":{"state":"244","last_reported":"2026-10-17T18:04:30+00:00"}})
  self.assertEqual(v["status"],"ALL_FRESH")
  self.assertFalse(v["automatic_restart_permitted"])
 def test_stale(self):
  v=classify(NOW,{"boiler":{"state":"244","last_reported":"2026-10-17T17:55:00+00:00"}})
  self.assertEqual(v["sources"]["boiler"]["status"],"STALE")
 def test_unavailable(self):
  v=classify(NOW,{"boiler":{"state":"unavailable","last_reported":"2026-10-17T18:04:30+00:00"}})
  self.assertEqual(v["sources"]["boiler"]["status"],"UNKNOWN")
 def test_future(self):
  v=classify(NOW,{"boiler":{"state":"244","last_reported":"2026-10-17T18:05:10+00:00"}})
  self.assertEqual(v["sources"]["boiler"]["status"],"UNSETTLED_OR_FUTURE")
 def test_missing_timestamp(self):
  self.assertEqual(classify(NOW,{"boiler":{"state":"244"}})["sources"]["boiler"]["status"],"UNKNOWN")
 def test_independent_sources(self):
  v=classify(NOW,{"main":{"state":"244","last_reported":"2026-10-17T18:04:30+00:00"},"pump":{"state":"6","last_reported":"2026-10-17T17:55:00+00:00"}})
  self.assertEqual(v["status"],"DEGRADED_OR_UNCONFIRMED")
if __name__=="__main__":unittest.main()
