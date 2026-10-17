"""Read-only local epoch coherence observer; advisory only, never a dispatch grant."""
import sqlite3
from pathlib import Path

def inspect(path, ha_owner, ha_authorized, expected_epoch):
    if type(expected_epoch) is not int or expected_epoch < 0:
        return {"status":"INVALID_EXPECTED_EPOCH","may_dispatch":False}
    if not isinstance(path,(str,Path)):
        return {"status":"INVALID_PATH","may_dispatch":False}
    try:
        db=sqlite3.connect("file:"+str(Path(path).resolve())+"?mode=ro",uri=True,timeout=2)
        try:
            db.execute("BEGIN")
            rows=db.execute("SELECT name,epoch FROM owner WHERE id=1").fetchall()
            if len(rows)!=1 or type(rows[0][1]) is not int:
                return {"status":"INVALID_DURABLE_OWNER","may_dispatch":False}
            owner,epoch=rows[0]
            if owner not in ("LEGACY","TRANSFER_PENDING","EMS2","BLOCKED") or epoch<0:
                return {"status":"INVALID_DURABLE_OWNER","may_dispatch":False}
            if owner!=ha_owner:
                status="OWNER_MISMATCH"
            elif epoch!=expected_epoch:
                status="EPOCH_MISMATCH"
            elif owner=="EMS2" and ha_authorized is not True:
                status="AUTHORIZATION_OFF"
            elif owner!="EMS2" and ha_authorized is True:
                status="AUTHORIZATION_OWNER_CONFLICT"
            else:
                status="COHERENT_ADVISORY_ONLY"
            return {"status":status,"durable_owner":owner,"durable_epoch":epoch,"may_dispatch":False}
        finally:
            db.close()
    except (OSError,sqlite3.Error,ValueError):
        return {"status":"DURABLE_OWNER_UNAVAILABLE","may_dispatch":False}
