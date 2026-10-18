"""Fail-closed tests for the durable owner/epoch journal.

All operations use a temporary SQLite database; no Home Assistant API calls.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from ownership import Ownership


class OwnerJournalIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "owner.sqlite"
        self.sources = {"soc": "sensor.example_battery"}

    def open(self):
        return Ownership(self.path, self.sources)

    def assert_blocked(self, owner):
        state = owner.state()
        self.assertEqual(state["owner"], "BLOCKED")
        self.assertEqual(state["epoch"], -1)
        self.assertFalse(state["local_durable_fence"])
        self.assertFalse(state["commands_permitted"])
        self.assertFalse(state["external_fence_verified"])

    def test_clean_legacy_and_restart(self):
        owner = self.open()
        self.assertEqual((owner.state()["owner"], owner.state()["epoch"]), ("LEGACY", 0))
        owner.close()
        owner = self.open()
        self.assertEqual(owner.state()["epoch"], 0)
        owner.close()

    def test_valid_pending_chain_survives_restart(self):
        owner = self.open()
        self.assertEqual(owner.transition("r-1", 0, "TRANSFER_PENDING"), "COMMITTED")
        owner.close()
        owner = self.open()
        state = owner.state()
        self.assertEqual((state["owner"], state["epoch"]), ("TRANSFER_PENDING", 1))
        self.assertFalse(state["commands_permitted"])
        owner.close()

    def test_owner_forged_without_audit_is_blocked(self):
        owner = self.open()
        owner.c.execute("UPDATE owner SET name='EMS2', epoch=2 WHERE id=1")
        self.assert_blocked(owner)
        with self.assertRaisesRegex(ValueError, "ownership_head_audit_mismatch"):
            owner.transition("r-2", 2, "BLOCKED")
        owner.close()

    def test_deleted_journal_is_blocked(self):
        owner = self.open()
        owner.transition("r-1", 0, "TRANSFER_PENDING")
        owner.c.execute("DELETE FROM audit")
        self.assert_blocked(owner)
        with self.assertRaises(ValueError):
            owner.transition("r-2", 1, "BLOCKED")
        owner.close()

    def test_wrong_journal_predecessor_is_blocked(self):
        owner = self.open()
        owner.transition("r-1", 0, "TRANSFER_PENDING")
        owner.c.execute("UPDATE audit SET previous='EMS2' WHERE request_id='r-1'")
        self.assert_blocked(owner)
        owner.close()

    def test_duplicate_epoch_entry_is_blocked(self):
        owner = self.open()
        owner.transition("r-1", 0, "TRANSFER_PENDING")
        owner.c.execute(
            "INSERT INTO audit VALUES('r-2','TRANSFER_PENDING','BLOCKED',1)"
        )
        self.assert_blocked(owner)
        owner.close()

    def test_missing_epoch_entry_is_blocked(self):
        owner = self.open()
        owner.transition("r-1", 0, "TRANSFER_PENDING")
        owner.c.execute(
            "INSERT INTO audit VALUES('r-2','TRANSFER_PENDING','BLOCKED',3)"
        )
        owner.c.execute("UPDATE owner SET name='BLOCKED', epoch=3 WHERE id=1")
        self.assert_blocked(owner)
        owner.close()

    def test_replay_cannot_bypass_integrity_check(self):
        owner = self.open()
        owner.transition("r-1", 0, "TRANSFER_PENDING")
        owner.c.execute("UPDATE owner SET epoch=50 WHERE id=1")
        with self.assertRaises(ValueError):
            owner.transition("r-1", 0, "TRANSFER_PENDING")
        self.assert_blocked(owner)
        owner.close()

    def test_corrupt_database_fails_reopen_not_silently_accept(self):
        owner = self.open()
        owner.close()
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE owner SET name='EMS2',epoch=1 WHERE id=1")
        with self.assertRaises(ValueError):
            self.open()


if __name__ == "__main__":
    unittest.main()
