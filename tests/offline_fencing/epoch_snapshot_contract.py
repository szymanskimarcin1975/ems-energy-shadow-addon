"""Fail-closed checker for a proposed *read-only* epoch attestation.

Not wired to Home Assistant; caller-provided objects are not trusted by themselves.
A future transport must authenticate the attestation origin and freshness.
"""
from datetime import datetime, timezone

def verify_epoch_snapshot(snapshot, *, request_epoch, ha_owner, authorized, at, max_age_s=15):
    if not isinstance(snapshot, dict) or type(request_epoch) is not int or request_epoch < 0:
        return "REJECT_UNTRUSTED_FORMAT"
    if not isinstance(at, datetime) or at.tzinfo is None:
        return "REJECT_UNTRUSTED_TIME"
    if type(snapshot.get("epoch")) is not int or type(snapshot.get("generated_unix")) not in (int, float):
        return "REJECT_UNTRUSTED_FORMAT"
    if snapshot.get("owner") != "EMS2" or ha_owner != "EMS2" or authorized is not True:
        return "REJECT_OWNER"
    if snapshot.get("epoch") != request_epoch:
        return "REJECT_STALE_EPOCH"
    if snapshot.get("read_only") is not True or snapshot.get("commands_permitted") is not False:
        return "REJECT_UNTRUSTED_SCOPE"
    age=at.timestamp()-snapshot["generated_unix"]
    if not 0<=age<=max_age_s:
        return "REJECT_STALE_SNAPSHOT"
    return "CANDIDATE_MATCH_NOT_AUTHORIZATION"
