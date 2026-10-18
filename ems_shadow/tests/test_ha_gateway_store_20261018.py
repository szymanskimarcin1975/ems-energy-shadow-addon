"""Synthetic-only durable gateway tests; no HA, SolarEdge or live services."""
from __future__ import annotations

import concurrent.futures
import importlib.util
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "custom_components" / "ems_epoch_gateway" / "gate_store.py"
SPEC = importlib.util.spec_from_file_location("ems_gate_store_isolated", MODULE)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def request(**changes):
    data = dict(
        caller="EMS2", operation="dispatch", request_id="example_request_1",
        plan_id="a" * 64, owner_epoch=0, option="Charge from Solar Power",
        power_w=1200, expires_at=time.time() + 45,
    )
    data.update(changes)
    return data


class DurableGatewaySafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ha-gate.sqlite"
        self.gate = GATE.EpochStore(self.path)
        self.gate.initialize()

    def test_default_legacy_has_no_actuation_authority(self):
        status = self.gate.status()
        self.assertEqual(status["status"], "BLOCKED_SAFE")
        self.assertEqual(status["trusted_owner"], "LEGACY")
        self.assertEqual(status["trusted_epoch"], 0)
        self.assertFalse(status["physical_dispatch_supported"])
        self.assertFalse(status["external_writer_fence_verified"])

    def test_valid_dispatch_records_rejected_before_any_write(self):
        reply = self.gate.dispatch_rejected(request())
        self.assertEqual(reply["status"], "REJECTED")
        self.assertEqual(reply["reason"], "TRUSTED_PHYSICAL_FENCE_UNVERIFIED")
        self.assertFalse(reply["writes_started"])
        self.assertFalse(reply["device_execution_confirmed"])
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT state,owner_epoch FROM requests").fetchone()
        self.assertEqual(row, ("REJECTED", 0))

    def test_duplicate_same_request_rejected_after_restart(self):
        initial = request()
        self.gate.dispatch_rejected(initial)
        reopened = GATE.EpochStore(self.path)
        reply = reopened.dispatch_rejected(initial)
        self.assertEqual(reply["reason"], "DUPLICATE_REJECTED")
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 1)

    def test_changed_identity_conflict_on_same_request_id(self):
        original = request()
        self.gate.dispatch_rejected(original)
        for variant in (
            dict(plan_id="b" * 64),
            dict(power_w=700),
            dict(option="Discharge to Minimize Import"),
            dict(owner_epoch=1),
            dict(expires_at=original["expires_at"] + 1),
        ):
            with self.subTest(variant=variant):
                reply = self.gate.dispatch_rejected(request(**{
                    **original, **variant
                }))
                self.assertEqual(reply["reason"], "REQUEST_ID_CONFLICT")

    def test_pending_crash_is_not_replayed(self):
        original = request()
        verdict, normalized = GATE.validate(original)
        self.assertEqual(verdict, "VALID")
        self.assertEqual(self.gate.reserve(normalized), "RESERVED_BEFORE_TRANSPORT")
        restarted = GATE.EpochStore(self.path)
        self.assertEqual(restarted.dispatch_rejected(original)["reason"],
                         "UNKNOWN_REQUIRES_RECONCILIATION")
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT state FROM requests").fetchone()[0], "PENDING")

    def test_epoch_mismatch_rejected_without_new_reservation(self):
        reply = self.gate.dispatch_rejected(request(owner_epoch=8))
        self.assertEqual(reply["reason"], "TRUSTED_EPOCH_MISMATCH")
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 0)

    def test_corrupt_owner_fails_closed(self):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE trusted_owner SET owner='EMS2',physical_enabled=1")
        self.assertEqual(self.gate.status()["status"], "GATE_INTEGRITY_UNKNOWN")
        self.assertEqual(self.gate.dispatch_rejected(request())["reason"],
                         "DURABLE_GATE_UNAVAILABLE_NO_RETRY")

    def test_concurrent_reserve_only_one_winner(self):
        original = request()
        verdict, normalized = GATE.validate(original)
        self.assertEqual(verdict, "VALID")
        def worker(_):
            return GATE.EpochStore(self.path).reserve(normalized)
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(worker, range(30)))
        self.assertEqual(results.count("RESERVED_BEFORE_TRANSPORT"), 1)
        self.assertEqual(results.count("UNKNOWN_REQUIRES_RECONCILIATION"), 29)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 1)

    def test_missing_database_not_treated_as_trusted(self):
        missing = GATE.EpochStore(Path(self.temp.name) / "not_initialized.sqlite")
        self.assertEqual(missing.status()["status"], "GATE_INTEGRITY_UNKNOWN")
        self.assertEqual(missing.dispatch_rejected(request())["reason"],
                         "DURABLE_GATE_UNAVAILABLE_NO_RETRY")

    def test_invalid_values_fail_closed_without_reservation(self):
        for variant in (
            dict(power_w=float("nan")), dict(power_w=float("inf")),
            dict(power_w=True), dict(power_w=0), dict(power_w=5001),
            dict(owner_epoch=True), dict(plan_id="bad"),
            dict(request_id="../escape"), dict(expires_at=time.time() - 1),
            dict(option="Discharge to Maximize Export"),
        ):
            with self.subTest(variant=variant):
                reply = self.gate.dispatch_rejected(request(**variant))
                self.assertEqual(reply["status"], "REJECTED")
                self.assertFalse(reply["writes_started"])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 0)

    def test_no_transport_interface_or_owner_transition(self):
        self.assertFalse(hasattr(self.gate, "send"))
        self.assertFalse(hasattr(self.gate, "transition"))
        self.assertFalse(hasattr(self.gate, "enable"))
        self.assertFalse(hasattr(self.gate, "select_option"))


if __name__ == "__main__":
    unittest.main()
