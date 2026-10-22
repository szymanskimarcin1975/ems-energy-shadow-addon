"""Exact proposed production bindings, simulated HA only; no network or device."""
import importlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'ems_shadow/tests'))
import test_actuation_candidate as f
Adapter=f.Adapter
CONFIG=ROOT/'deployment/adapter42/actuation_candidate.yaml'

class PreparedAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture=f.AdapterTests('test_successful_poll_uses_raw_bms_not_unchanged_entity_time')
        await self.fixture.asyncSetUp()
        self.c=json.loads(CONFIG.read_text())
        self.hass=self.fixture.adapter.hass
        self.hass.data['solaredge_modbus_multi'][self.c['solaredge_entry_id']]=self.hass.data['solaredge_modbus_multi']['entry']
        suffixes=importlib.import_module(f.PKG+'.ha_adapter').CONTROL_SUFFIXES
        registry={e:NS(platform='solaredge_modbus_multi',config_entry_id=self.c['solaredge_entry_id'],device_id='same-inverter',disabled_by=None,unique_id='actual-binding'+suffixes[k][1]) for k,e in self.c['entities'].items()}
        async def owner():return dict(trusted_owner='LEGACY',trusted_epoch=0,physical_authorized=False,emergency_stop={'latched':False})
        self.a=Adapter(self.hass,self.c,owner,NS(async_get=registry.get))
    async def asyncTearDown(self):
        self.a.unsubscribe()
        self.assertEqual(self.fixture.calls,[], 'Prepared configuration must never issue HA device services')
    async def test_instantiation_and_binding_have_no_writes(self):
        self.a.check_bindings()
        self.assertEqual(self.a.poll_interval_s,120)
        self.assertIsNone(self.a.sample) # Must wait for a complete natural poll.
    async def test_preflight_authorization_off(self):
        with self.assertRaisesRegex(ValueError,'PHYSICAL_AUTHORIZATION_OFF'):
            await self.a.preflight(f.request())
    async def test_apply_without_journal_refuses(self):
        with self.assertRaisesRegex(ValueError,'DURABLE_SETTING_JOURNAL_REQUIRED'):
            await self.a.apply(f.request(),100)
    async def test_apply_authorization_off(self):
        async def reserve(*args):pass
        async def finish(*args):pass
        self.a.bind_write_journal(reserve,finish)
        with self.assertRaisesRegex(ValueError,'PHYSICAL_AUTHORIZATION_OFF'):
            await self.a.apply(f.request(),100)
    async def test_stop_cannot_touch_legacy_owner(self):
        with self.assertRaisesRegex(ValueError,'STOP_OWNER_NOT_EMS2'):
            await self.a.request_local_mode('never-dispatch')
    async def test_no_fabricated_commissioning_evidence(self):
        for name in self.c['verified_evidence']:
            with self.assertRaisesRegex(ValueError,'UNVERIFIED'):self.a.evidence(name)
    async def test_no_arbitrary_write_budget_or_import_margin(self):
        self.assertIsNone(self.c['write_policy'])
        self.assertIsNone(self.c['import_margin_w'])
    async def test_operational_soc_direction_guards(self):
        guard=importlib.import_module(f.PKG+'.actuation').direction_guard
        self.assertEqual(guard('Charge from Solar Power',100,5,95),'SOC_CEILING')
        self.assertEqual(guard('Discharge to Minimize Import',2.22,5,95),'SOC_RESERVE')
        self.assertIsNone(guard('Charge from Solar Power',2.22,5,95))
    async def test_json_is_exact_config_subtree_not_whole_ha_config(self):
        self.assertTrue(self.c['enabled'])
        self.assertIs(self.c['physical_authorized'],False)
        self.assertNotIn('homeassistant',self.c)
        self.assertEqual(set(self.c['entities']),{'mode','control','default','timeout','charge','discharge'})
    async def test_restart_keeps_legacy_and_disarms(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'isolated.sqlite'
            store=f.Store(path);store.initialize();store.initialize()
            state=store.control_status()
            self.assertEqual((state['trusted_owner'],state['trusted_epoch'],state['physical_authorized']),('LEGACY',0,False))
            self.assertTrue(state['physical_adapter_implemented'])
            self.assertFalse(state['physical_dispatch_supported'])
            with sqlite3.connect(path) as db:self.assertEqual(db.execute('pragma integrity_check').fetchone()[0],'ok')

if __name__=='__main__':unittest.main()
