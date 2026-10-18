"""Regression tests: never grant physical battery control from partial evidence.

Offline tests only. No Home Assistant connection or device dispatch is possible.
Run from ems_shadow: python -m unittest discover -s tests -p 'test_handover_fail_closed_20261018.py'
"""
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from battery_executor import Executor, Policy


class NoDeviceAccess:
    def __init__(self):
        self.calls = 0

    def state(self, *_):
        self.calls += 1
        raise AssertionError("unexpected live HA read")

    def dispatch(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("unexpected battery dispatch")


class Ownership:
    def __init__(self, *, owner="EMS2", epoch=7, permitted=True, fenced=True):
        self.data = {
            "owner": owner, "epoch": epoch,
            "commands_permitted": permitted, "external_fence_verified": fenced,
        }

    def state(self):
        return dict(self.data)


class HandoverFailClosedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ha = NoDeviceAccess()
        self.good_policy = Policy(
            enabled=True, soc_min=30, soc_max=90,
            soc_bounds_approved=True, handover_verified=True,
            no_export_verified=True, fallback_verified=True,
        )

    def executor(self, policy=None, ownership=None, epoch=7):
        return Executor(
            self.ha, policy if policy is not None else self.good_policy,
            Path(self.tmp.name) / "commands.sqlite",
            Path(self.tmp.name) / "executor.lock",
            old_writers=["automation.legacy"],
            soc_entity="sensor.soc", mode_entity="select.command",
            power_entities=("number.charge", "number.discharge"),
            owner_entity="input_select.owner",
            control_entity="select.control",
            bms_sources={
                role: "sensor." + role
                for role in ("status", "max_charge", "peak_charge",
                             "max_discharge", "peak_discharge")
            },
            ownership=ownership if ownership is not None else Ownership(),
            expected_epoch=epoch,
        )

    def attempt(self, executor):
        return executor.execute(
            "regression-1", "Charge from Solar Power",
            datetime.now(timezone.utc) + timedelta(seconds=30),
            maximum_power_w=1000, plan_id="a" * 64,
        )

    def assert_no_side_effects(self):
        self.assertEqual(self.ha.calls, 0)
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_read_only_never_opens_database_or_ha(self):
        self.assertEqual(self.attempt(self.executor(Policy())), "DISABLED")
        self.assert_no_side_effects()

    def test_planning_soc_bounds_are_not_safety_approval(self):
        p = replace(self.good_policy, soc_min=0, soc_max=100,
                    soc_bounds_approved=False)
        self.assertEqual(self.attempt(self.executor(p)), "UNAPPROVED_SAFETY")
        self.assert_no_side_effects()

    def test_missing_fallback_proof_blocks(self):
        p = replace(self.good_policy, fallback_verified=False)
        self.assertEqual(self.attempt(self.executor(p)), "UNAPPROVED_SAFETY")
        self.assert_no_side_effects()

    def test_missing_no_export_proof_blocks(self):
        p = replace(self.good_policy, no_export_verified=False)
        self.assertEqual(self.attempt(self.executor(p)), "UNAPPROVED_SAFETY")
        self.assert_no_side_effects()

    def test_unfenced_external_writers_block(self):
        self.assertEqual(self.attempt(self.executor(
            ownership=Ownership(fenced=False))), "OWNERSHIP_UNCONFIRMED")
        self.assert_no_side_effects()

    def test_wrong_epoch_blocks(self):
        self.assertEqual(self.attempt(self.executor(
            ownership=Ownership(epoch=8))), "OWNERSHIP_UNCONFIRMED")
        self.assert_no_side_effects()

    def test_legacy_owner_blocks(self):
        self.assertEqual(self.attempt(self.executor(
            ownership=Ownership(owner="LEGACY"))), "OWNERSHIP_UNCONFIRMED")
        self.assert_no_side_effects()


if __name__ == "__main__":
    unittest.main()
