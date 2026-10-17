"""Synthetic boundary contract: no Home Assistant or device calls."""
import unittest

def mocked_gateway_decision(*, request_epoch, trusted_epoch, request_id, recorded_ids, owner, authorized, operation):
    if operation != "dispatch":
        return "NOT_DISPATCH"
    if owner != "EMS2" or not authorized:
        return "REJECTED_OWNER"
    if type(request_epoch) is not int or type(trusted_epoch) is not int or request_epoch != trusted_epoch:
        return "REJECTED_EPOCH"
    if request_id in recorded_ids:
        return "REJECTED_REPLAY"
    return "ELIGIBLE_FOR_OTHER_SAFETY_CHECKS_NOT_ACTUATION"

class TestTrustedBoundary(unittest.TestCase):
    def test_legacy_reject(self):
        self.assertEqual(mocked_gateway_decision(request_epoch=0,trusted_epoch=0,request_id="r",recorded_ids=set(),owner="LEGACY",authorized=False,operation="dispatch"),"REJECTED_OWNER")
    def test_epoch_mismatch(self):
        self.assertEqual(mocked_gateway_decision(request_epoch=1,trusted_epoch=2,request_id="r",recorded_ids=set(),owner="EMS2",authorized=True,operation="dispatch"),"REJECTED_EPOCH")
    def test_replay(self):
        self.assertEqual(mocked_gateway_decision(request_epoch=2,trusted_epoch=2,request_id="r",recorded_ids={"r"},owner="EMS2",authorized=True,operation="dispatch"),"REJECTED_REPLAY")
    def test_true_boolean_not_valid_epoch(self):
        self.assertEqual(mocked_gateway_decision(request_epoch=True,trusted_epoch=1,request_id="r",recorded_ids=set(),owner="EMS2",authorized=True,operation="dispatch"),"REJECTED_EPOCH")
    def test_diagnostic_not_dispatch(self):
        self.assertEqual(mocked_gateway_decision(request_epoch=0,trusted_epoch=0,request_id="r",recorded_ids=set(),owner="LEGACY",authorized=False,operation="status"),"NOT_DISPATCH")
    def test_match_not_authorization(self):
        self.assertEqual(mocked_gateway_decision(request_epoch=2,trusted_epoch=2,request_id="new",recorded_ids=set(),owner="EMS2",authorized=True,operation="dispatch"),"ELIGIBLE_FOR_OTHER_SAFETY_CHECKS_NOT_ACTUATION")

if __name__=="__main__":
    unittest.main()
