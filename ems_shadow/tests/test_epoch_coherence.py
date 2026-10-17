"""No Home Assistant or inverter calls; real temporary SQLite and restart tests."""
import sqlite3,tempfile,unittest
from pathlib import Path
from epoch_coherence import inspect

class Cases(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.p=Path(self.t.name)/"owner.sqlite"
        with sqlite3.connect(self.p) as db:
            db.execute("CREATE TABLE owner(id INTEGER PRIMARY KEY,name TEXT NOT NULL,epoch INTEGER NOT NULL)")
            db.execute("INSERT INTO owner VALUES(1,'LEGACY',0)")
    def call(self,owner="LEGACY",authorized=False,epoch=0):
        return inspect(self.p,owner,authorized,epoch)
    def test_coherent_legacy(self):self.assertEqual(self.call()["status"],"COHERENT_ADVISORY_ONLY")
    def test_never_authorizes(self):self.assertFalse(self.call()["may_dispatch"])
    def test_mismatch(self):self.assertEqual(self.call(owner="EMS2")["status"],"OWNER_MISMATCH")
    def test_stale_epoch(self):self.assertEqual(self.call(epoch=1)["status"],"EPOCH_MISMATCH")
    def test_invalid_epoch(self):self.assertEqual(self.call(epoch=True)["status"],"INVALID_EXPECTED_EPOCH")
    def test_wrong_authorization(self):self.assertEqual(self.call(authorized=True)["status"],"AUTHORIZATION_OWNER_CONFLICT")
    def test_missing_db(self):self.assertEqual(inspect(str(self.p)+"missing","LEGACY",False,0)["status"],"DURABLE_OWNER_UNAVAILABLE")
    def test_restart_then_transfer(self):
        with sqlite3.connect(self.p) as db:db.execute("UPDATE owner SET name='TRANSFER_PENDING',epoch=1 WHERE id=1")
        self.assertEqual(self.call()["status"],"OWNER_MISMATCH")
        self.assertEqual(self.call(owner="TRANSFER_PENDING",epoch=1)["status"],"COHERENT_ADVISORY_ONLY")
        self.assertFalse(self.call(owner="TRANSFER_PENDING",epoch=1)["may_dispatch"])

if __name__=="__main__": unittest.main()
