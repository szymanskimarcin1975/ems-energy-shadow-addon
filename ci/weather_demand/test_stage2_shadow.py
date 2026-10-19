"""Synthetic regression: no HA client, secrets or device transport."""
import copy
import sqlite3
import unittest
from datetime import timedelta
from test_control_safety import sample
from test_planning import T
from control_safety import Safety
from planning_runtime import plan, planning_fingerprint
from plan_bridge import build

class Stage2(unittest.TestCase):
    def observe(self, args):
        with sqlite3.connect(':memory:', isolation_level=None) as c:
            guard = Safety(c)
            guard.observe(args[0], args[2], args[4])
            return guard.summary(args[2])

    def sleeping(self):
        a = sample()
        a[0]['sensor.example_b1_status']['state'] = 'B_STATUS_POWER_SAVING'
        a[0]['sensor.example_b1_power']['state'] = '0'
        a[0]['sensor.example_b1_soc']['state'] = '0'
        return a

    def test_power_saving_zero_soc_is_advisory_only(self):
        a = self.sleeping()
        safety = self.observe(a)
        self.assertTrue(safety['current_ha_set_valid'])
        r = plan(*a, input_safety=safety)
        self.assertNotEqual(r['status'], 'BLOCKED_INPUT')
        self.assertEqual(r['battery']['soc_percent'], 0)
        self.assertFalse(r['control_enabled'])
        self.assertFalse(r['active_control_readiness']['ready'])

    def test_sleeping_nonzero_power_and_unknown_status_rejected(self):
        for watts in ('1', '-1', 'unavailable'):
            a = self.sleeping()
            a[0]['sensor.example_b1_power']['state'] = watts
            self.assertFalse(self.observe(a)['current_ha_set_valid'])
        for status in ('unknown', 'unavailable', 'B_STATUS_FAULT'):
            a = self.sleeping()
            a[0]['sensor.example_b1_status']['state'] = status
            self.assertFalse(self.observe(a)['current_ha_set_valid'])

    def test_fresh_reports_do_not_require_changed_values(self):
        a = self.sleeping()
        for row in a[0].values():
            row['last_updated'] = (T-timedelta(hours=2)).isoformat()
            row['last_changed'] = row['last_updated']
        s = self.observe(a)
        self.assertTrue(s['current_ha_set_valid'])
        self.assertFalse(s['last']['device_synchronisation_confirmed'])
        self.assertFalse(s['control_enabled'])

    def test_bad_reported_time_never_replaced_by_fresh_updated(self):
        for reported in (None, 'bad', (T-timedelta(seconds=241)).isoformat(),
                         (T+timedelta(seconds=1)).isoformat()):
            a = self.sleeping()
            a[0]['sensor.example_b1_soc'].update(last_reported=reported, last_updated=a[2])
            self.assertFalse(self.observe(a)['current_ha_set_valid'])

    def test_fingerprint_stable_across_runtime_quality_and_key_order(self):
        a = self.sleeping()
        p = {'soc_min':5, 'soc_max':95, 'owner_approved':True, 'scope':'planning_only',
             'bms_safety_confirmed':False, 'applied_to_simulation':False}
        first = planning_fingerprint(a[3], p, a[4])
        p['applied_to_simulation'] = True
        self.assertEqual(first, planning_fingerprint(dict(reversed(list(a[3].items()))), p, a[4]))
        for key, value in (('soc_max',90), ('owner_approved',False)):
            changed = dict(p, **{key:value})
            self.assertNotEqual(first, planning_fingerprint(a[3], changed, a[4]))
        changed = copy.deepcopy(a[3]); changed['simulation_charge_eff'] = .8
        self.assertNotEqual(first, planning_fingerprint(changed, p, a[4]))

    def test_mismatch_missing_or_bad_pin_still_blocks(self):
        a = self.sleeping()
        fp = planning_fingerprint(a[3], {}, a[4])
        for pin in (None, '', 'a'*64, fp.upper()):
            r = build({'generated_at':T.isoformat(), 'valid_until':(T+timedelta(seconds=360)).isoformat(), 'status':'ADVISORY_HOUSEHOLD_SCHEDULE_READY', 'current_plan_usable_for_simulation':True, 'input_safety':{'current_ha_set_valid':True}, 'planning_config_fingerprint':fp}, {'enabled':True,'expected_fingerprint':pin}, T, 0)
            self.assertEqual(r['status'], 'PLAN_FINGERPRINT_UNCONFIRMED')
            self.assertIsNone(r['pending_request'])
