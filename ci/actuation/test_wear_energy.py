"""Persistent local write-budget and counter discontinuity regression, no device."""
import importlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'ems_shadow/tests'),str(ROOT/'ems_shadow/app')]
import test_actuation_candidate as f
from battery_energy_segments import Ledger
import battery_runtime
write_policy=importlib.import_module(f.PKG+'.write_policy')

class WearTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'wear.sqlite'
        self.policy=dict(basis='LOCAL_EMS_WRITE_BUDGET_NOT_MANUFACTURER_LIMIT',minimum_interval_s=900,maximum_writes_per_24h=3)
        self.changes=[dict(role='timeout',value=3600,required=False),dict(role='charge',value=100,required=True),dict(role='mode',value=3,required=True)]
    def reserve(self,id,now,emergency=False,changes=None):
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            return write_policy.reserve(db,id,changes or self.changes,self.policy,now,emergency)
    def test_only_changed_settings_count(self):
        self.assertEqual(self.reserve('one',1000),2)
        with sqlite3.connect(self.path) as db:self.assertEqual(dict(db.execute('SELECT state,count(*) FROM setting_write_audit GROUP BY state')),{'RESERVED_UNKNOWN':2,'SKIPPED_READBACK':1})
    def test_minimum_interval_blocks_whole_batch(self):
        self.reserve('one',1000)
        with self.assertRaisesRegex(ValueError,'MINIMUM_CHANGE_INTERVAL'):self.reserve('two',1100)
        with sqlite3.connect(self.path) as db:self.assertEqual(db.execute('select count(*) from setting_write_audit').fetchone()[0],3)
    def test_budget_blocks_batch_before_partial_execution(self):
        self.reserve('one',1000)
        with self.assertRaisesRegex(ValueError,'WRITE_BUDGET_EXCEEDED'):self.reserve('two',2000)
    def test_stop_bypasses_budget_and_delay_but_is_durable(self):
        self.reserve('one',1000);self.reserve('one',1001,emergency=True)
        with self.assertRaisesRegex(ValueError,'NO_RETRY'):self.reserve('one',1002,emergency=True)
    def test_budget_survives_reopen_and_does_not_release_unknown(self):
        self.reserve('one',1000)
        with self.assertRaisesRegex(ValueError,'WRITE_BUDGET_EXCEEDED'):self.reserve('two',3000)
    def test_all_identical_is_not_timeout_refresh(self):
        rows=[dict(x,required=False) for x in self.changes]
        with self.assertRaisesRegex(ValueError,'IDENTICAL_SETTINGS'):self.reserve('one',1000,changes=rows)
    def test_missing_policy_refuses_ordinary_not_stop(self):
        self.policy={}
        with self.assertRaisesRegex(ValueError,'NOT_CONFIGURED'):self.reserve('one',1000)
        self.assertEqual(self.reserve('stop',1000,True),2)

class EnergyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'energy.sqlite';self.ledger=Ledger(self.path)
    def read(self,t,imp,exp,source='B1',raw=True,unit='Wh'):
        return self.ledger.observe(source,'2026-10-18T12:%02d:00+00:00'%t,imp,exp,unit,raw)
    def test_reported_reset_has_no_negative_energy_or_cost(self):
        self.read(0,10098,13270);r=self.read(2,3004,1873)
        self.assertEqual(r['quality'],'COUNTER_DISCONTINUITY');self.assertIsNone(r['import_delta_kwh']);self.assertFalse(r['usable_for_cost'])
        self.assertEqual(r['physical_reset_cause'],'UNCONFIRMED')
        self.assertGreater(self.read(4,3014,1883)['import_delta_kwh'],0)
    def test_reset_stays_segmented_after_restart(self):
        self.read(0,10098,13270);self.read(2,3004,1873);self.ledger=Ledger(self.path)
        self.assertEqual(self.read(4,3005,1874)['segment'],1)
    def test_gap_and_duplicate_are_not_energy(self):
        self.read(0,10,20)
        self.assertEqual(self.read(4,15,25)['quality'],'GAP_REBASELINED')
        self.assertFalse(self.read(4,15,25)['usable_for_cost'])
    def test_ha_restore_value_cannot_prove_raw_counter_integrity(self):
        self.read(0,10,20,raw=False);r=self.read(2,11,21,raw=False)
        self.assertTrue(r['ha_restore_filter_may_hide_discontinuity']);self.assertFalse(r['usable_for_cost'])
    def test_two_distinct_endpoints_sum_once_not_twice(self):
        self.read(0,10,20);self.read(0,30,40,source='B2')
        a=self.read(2,20,30);b=self.read(2,50,60,source='B2')
        self.assertAlmostEqual(Ledger.aggregate([a,b],['B1','B2'])['import_delta_kwh'],.03)
        self.assertFalse(Ledger.aggregate([a,a],['B1'])['usable_for_cost'])
        self.assertFalse(Ledger.aggregate([a],['B1','B2'])['usable_for_cost'])
    def test_wh_and_kwh_are_explicit(self):
        self.read(0,1000,2000);self.assertAlmostEqual(self.read(2,1.1,2.2,unit='kWh')['import_delta_kwh'],.1)
        with self.assertRaises(ValueError):self.read(4,1,2,unit='W')
    def test_runtime_requests_counter_units_for_bound_logical_b1(self):
        class API:
            def call(self,method,path,body):
                self.ids=body['variables']['ids'];self.template=body['template'];return []
        api=API();battery_runtime.in_memory_times(api,{'b1_power':'sensor.example_b1_dc_power'})
        self.assertIn('sensor.example_b1_energy_import',api.ids)
        self.assertIn('sensor.example_b1_energy_export',api.ids)
        self.assertIn('unit_of_measurement',api.template)

    def test_integrity_check(self):
        self.read(0,1,2);self.read(2,2,3)
        with sqlite3.connect('file:'+str(self.path)+'?mode=ro',uri=True) as db:self.assertEqual(db.execute('pragma integrity_check').fetchone()[0],'ok')

class RealAdapterJournalTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=f.AdapterTests.asyncSetUp
    async def make_engine(self):
        import asyncio
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=f.Store(Path(self.temp.name)/'control.sqlite');self.store.initialize()
        self.store.transition_owner(0,'EMS2','synthetic-only')
        async def db(fn,*args):return await asyncio.to_thread(fn,*args)
        return f.Engine(self.store,self.adapter,db)
    async def test_actual_adapter_skips_identical_timeout_and_audits_stop(self):
        engine=await self.make_engine()
        self.assertEqual((await engine.dispatch(f.request()))['status'],'WAITING_CONFIRMATION')
        self.assertEqual(len(self.calls),2) # limit + mode; timeout already30s
        self.assertEqual((await engine.stop('test_request'))['status'],'WAITING_STOP')
        self.assertEqual(len(self.calls),3) # command7 already observed, only control1
        with sqlite3.connect(self.store.path) as db:
            states=dict(db.execute('SELECT state,count(*) FROM setting_write_audit GROUP BY state'))
            self.assertEqual(states,{'SERVICE_RETURNED':3,'SKIPPED_READBACK':2})
    async def test_actual_service_timeout_remains_unknown_without_retry(self):
        engine=await self.make_engine()
        async def timeout(*a,**kw):self.calls.append('attempt');raise TimeoutError()
        self.adapter.hass.services.async_call=timeout
        self.assertEqual((await engine.dispatch(f.request()))['status'],'UNKNOWN')
        self.assertEqual((await engine.dispatch(f.request()))['status'],'UNKNOWN')
        self.assertEqual(self.calls,['attempt'])
        with sqlite3.connect(self.store.path) as db:self.assertEqual(db.execute("SELECT state FROM setting_write_audit WHERE role='charge'").fetchone()[0],'UNKNOWN')

if __name__=='__main__':unittest.main()
