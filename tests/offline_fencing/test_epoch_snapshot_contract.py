"""Pure local tests. Never call HA or SolarEdge."""
import unittest
from datetime import datetime,timezone,timedelta
from epoch_snapshot_contract import verify_epoch_snapshot

class Tests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,17,15,48,tzinfo=timezone.utc)
        self.snapshot={"owner":"EMS2","epoch":2,"generated_unix":self.now.timestamp(),"read_only":True,"commands_permitted":False}
    def check(self, **changes):
        s=dict(self.snapshot);s.update(changes.pop("snapshot",{}))
        return verify_epoch_snapshot(s,request_epoch=changes.pop("request_epoch",2),ha_owner=changes.pop("ha_owner","EMS2"),authorized=changes.pop("authorized",True),at=changes.pop("at",self.now))
    def test_current_not_authorized(self):self.assertEqual(self.check(),"CANDIDATE_MATCH_NOT_AUTHORIZATION")
    def test_stale_epoch(self):self.assertEqual(self.check(request_epoch=1),"REJECT_STALE_EPOCH")
    def test_wrong_owner(self):self.assertEqual(self.check(ha_owner="LEGACY"),"REJECT_OWNER")
    def test_auth_off(self):self.assertEqual(self.check(authorized=False),"REJECT_OWNER")
    def test_bad_timestamp(self):self.assertEqual(self.check(snapshot={"generated_unix":self.now.timestamp()-40}),"REJECT_STALE_SNAPSHOT")
    def test_future_timestamp(self):self.assertEqual(self.check(snapshot={"generated_unix":self.now.timestamp()+1}),"REJECT_STALE_SNAPSHOT")
    def test_invalid_epoch(self):self.assertEqual(self.check(snapshot={"epoch":True}),"REJECT_UNTRUSTED_FORMAT")
    def test_readonly_scope(self):self.assertEqual(self.check(snapshot={"commands_permitted":True}),"REJECT_UNTRUSTED_SCOPE")

if __name__=="__main__":unittest.main()
