"""Offline reference fence. No Home Assistant service calls or device dispatch."""
import hashlib
import json
import sqlite3

class CommandFence:
    def __init__(self, database):
        self.db = sqlite3.connect(database, isolation_level=None, timeout=5)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS state (singleton INTEGER PRIMARY KEY CHECK(singleton=1), epoch INTEGER NOT NULL, owner TEXT NOT NULL)")
        self.db.execute("INSERT OR IGNORE INTO state VALUES(1,0,'LEGACY')")
        self.db.execute("CREATE TABLE IF NOT EXISTS requests (request_id TEXT PRIMARY KEY, epoch INTEGER NOT NULL, digest TEXT NOT NULL, verdict TEXT NOT NULL)")

    def decide(self, request_id, epoch, owner, payload):
        if not isinstance(request_id, str) or not request_id or len(request_id)>64 or not isinstance(epoch,int) or isinstance(epoch,bool) or epoch<0 or owner!='EMS2':
            return "REJECTED_INVALID"
        digest = hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            state = self.db.execute("SELECT epoch,owner FROM state WHERE singleton=1").fetchone()
            prev = self.db.execute("SELECT epoch,digest FROM requests WHERE request_id=?", (request_id,)).fetchone()
            if prev:
                verdict = "REJECTED_REPLAY" if prev==(epoch,digest) else "REJECTED_ID_COLLISION"
            elif state != (epoch, owner):
                verdict = "REJECTED_STALE_EPOCH_OR_OWNER"
            else:
                self.db.execute("INSERT INTO requests VALUES(?,?,?,?)",(request_id,epoch,digest,"RESERVED_NO_DISPATCH"))
                verdict = "RESERVED_NO_DISPATCH"
            self.db.execute("COMMIT")
            return verdict
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def set_owner_for_offline_test(self, epoch, owner):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            prior=self.db.execute("SELECT epoch FROM state WHERE singleton=1").fetchone()[0]
            if epoch!=prior+1 or owner not in ("LEGACY","EMS2"):
                raise ValueError("nonmonotonic epoch or invalid owner")
            self.db.execute("UPDATE state SET epoch=?,owner=? WHERE singleton=1",(epoch,owner))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
