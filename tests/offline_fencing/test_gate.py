"""Offline-only safety regression. Does not contact Home Assistant or SolarEdge."""
from tempfile import TemporaryDirectory
from pathlib import Path
from gate import CommandFence

with TemporaryDirectory() as p:
    path=Path(p)/"fence.sqlite"
    f=CommandFence(path)
    payload={"mode":"Charge from Solar Power","power_w":1200}
    assert f.decide("a",0,"EMS2",payload)=="REJECTED_STALE_EPOCH_OR_OWNER"
    f.set_owner_for_offline_test(1,"EMS2")
    assert f.decide("a",1,"EMS2",payload)=="RESERVED_NO_DISPATCH"
    assert f.decide("a",1,"EMS2",payload)=="REJECTED_REPLAY"
    assert f.decide("a",1,"EMS2",{"mode":"different"})=="REJECTED_ID_COLLISION"
    assert f.decide("b",0,"EMS2",payload)=="REJECTED_STALE_EPOCH_OR_OWNER"
    g=CommandFence(path)
    assert g.decide("a",1,"EMS2",payload)=="REJECTED_REPLAY"
    g.set_owner_for_offline_test(2,"LEGACY")
    assert g.decide("c",1,"EMS2",payload)=="REJECTED_STALE_EPOCH_OR_OWNER"
    assert g.decide("d",2,"EMS2",payload)=="REJECTED_STALE_EPOCH_OR_OWNER"
print("PASS: 8 offline assertions")
