"""Durability and replay tests for the executor-side dispatch reservation."""
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dispatch_reservations import reserve, set_status


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "dispatch.sqlite"
        self.now = datetime.now(timezone.utc)
        self.expires = self.now + timedelta(seconds=30)

    def open(self):
        db = sqlite3.connect(self.path, timeout=2, isolation_level=None, check_same_thread=False)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY, mode TEXT, status TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS command_identity(request_id TEXT PRIMARY KEY, plan_id TEXT, owner_epoch INTEGER, requested_power_w REAL)")
        return db

    def do_reserve(self, db, request_id="r1", plan_id="a"*64, epoch=0, power=1000):
        return reserve(db, request_id=request_id, plan_id=plan_id, owner_epoch=epoch,
                       option="Charge from Solar Power", power_w=power,
                       expires_at=self.expires, now=self.now)

    def test_commit_then_restart_rejects_same_id(self):
        db = self.open()
        db.execute("BEGIN IMMEDIATE")
        self.assertEqual(self.do_reserve(db), "RESERVED")
        set_status(db, "r1", "PENDING", self.now)
        db.commit(); db.close()
        db = self.open()
        self.assertEqual(self.do_reserve(db), "DUPLICATE_PENDING")
        self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        db.close()

    def test_payload_or_epoch_conflict(self):
        db = self.open(); db.execute("BEGIN IMMEDIATE")
        self.assertEqual(self.do_reserve(db), "RESERVED"); db.commit()
        self.assertEqual(self.do_reserve(db, power=1200), "REQUEST_CONFLICT")
        self.assertEqual(self.do_reserve(db, epoch=1), "REQUEST_CONFLICT")
        db.close()

    def test_refreshed_deadline_is_same_request_identity(self):
        db = self.open()
        db.execute("BEGIN IMMEDIATE")
        self.assertEqual(self.do_reserve(db), "RESERVED")
        db.commit()
        refreshed = self.now + timedelta(seconds=45)
        self.assertEqual(
            reserve(db, request_id="r1", plan_id="a"*64, owner_epoch=0,
                    option="Charge from Solar Power", power_w=1000,
                    expires_at=refreshed, now=self.now),
            "DUPLICATE_RESERVED",
        )
        db.close()

    def test_uncommitted_reservation_rolls_back(self):
        db = self.open(); db.execute("BEGIN IMMEDIATE")
        self.assertEqual(self.do_reserve(db), "RESERVED")
        db.rollback(); db.close()
        db = self.open()
        self.assertEqual(self.do_reserve(db), "RESERVED")
        db.rollback(); db.close()

    def test_concurrent_connections_serialize(self):
        first = self.open(); second = self.open()
        first.execute("BEGIN IMMEDIATE")
        self.assertEqual(self.do_reserve(first), "RESERVED")
        started = threading.Event(); result = []
        def contender():
            started.set()
            second.execute("BEGIN IMMEDIATE")
            result.append(self.do_reserve(second))
            second.commit()
        thread = threading.Thread(target=contender)
        thread.start(); started.wait(timeout=1)
        first.commit(); thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, ["DUPLICATE_RESERVED"])
        self.assertEqual(first.execute("SELECT COUNT(*) FROM dispatch_reservations").fetchone()[0], 1)
        first.close(); second.close()

    def test_old_schema_request_cannot_be_replayed(self):
        db = self.open()
        db.execute("INSERT INTO commands VALUES('r1','Charge from Solar Power','ACK')")
        self.assertEqual(self.do_reserve(db), "LEGACY_REQUEST_ALREADY_RECORDED")
        db.close()


if __name__ == "__main__":
    unittest.main()
