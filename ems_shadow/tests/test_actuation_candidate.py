"""Review candidate tests. Synthetic HA services and device polls; no network."""
import asyncio
import concurrent.futures
import importlib
import sqlite3
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[2]
PKG = 'ems_candidate_under_test'
if PKG not in sys.modules:
    package = types.ModuleType(PKG)
    package.__path__ = [str(ROOT / 'custom_components/ems_epoch_gateway')]
    sys.modules[PKG] = package
Store = importlib.import_module(PKG + '.control_store').ControlStore
Engine = importlib.import_module(PKG + '.actuation').ActuationGateway
Adapter = importlib.import_module(PKG + '.ha_adapter').HASolarEdgeAdapter
direction_guard = importlib.import_module(PKG + '.actuation').direction_guard


def request(**changes):
    value = dict(caller='EMS2', operation='dispatch', execution_mode='ACTIVE', request_id='test_request', plan_id='a'*64,
                 owner_epoch=1, option='Charge from Solar Power', power_w=1200, expires_at=time.time()+50)
    value.update(changes)
    return value


class Device:
    def __init__(self):
        self.calls = []
        self.error = None
        self.verified = True
        self.can_stop = True
        self.ended = True
        self.delay = 0
    async def verify_handover(self, target):
        if self.error: raise ValueError(self.error)
    async def preflight(self, req):
        if self.error: raise ValueError(self.error)
        return dict(direction_limit_w=900, poll_completed_at=time.time()-1)
    async def apply(self, req, power):
        self.calls.append((req['option'], power))
        if self.delay: await asyncio.sleep(self.delay)
        if self.error == 'AFTER_WRITE': raise TimeoutError()
    async def confirm_effect(self, req, power):
        return dict(request_id=req['request_id'], plan_id=req['plan_id'], owner_epoch=req['owner_epoch'],
                    observed_at=time.time(), physical_effect_confirmed=self.verified)
    async def verify_stop_procedure(self, request_id):
        if not self.can_stop: raise ValueError('NO_STOP_PROOF')
    async def request_local_mode(self, request_id): self.calls.append(('STOP', request_id))
    async def confirm_termination(self, request_id):
        return dict(request_id=request_id, active_command_ended=self.ended, safe_local_mode_confirmed=self.ended, observed_at=time.time())


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'gate.sqlite'
        self.store = Store(self.path); self.store.initialize()
        self.device = Device()
        async def db(fn, *args): return await asyncio.to_thread(fn, *args)
        self.db = db; self.engine = Engine(self.store, self.device, db)
        self.store.transition_owner(0, 'EMS2', 'synthetic-fence-and-termination-proof')
    async def test_full_path_clamps_and_retains_active_command(self):
        r = await self.engine.dispatch(request())
        self.assertEqual(r['status'], 'SERVICE_COMPLETED'); self.assertTrue(r['device_execution_confirmed'])
        self.assertEqual(self.device.calls, [('Charge from Solar Power', 900)])
        self.assertEqual(self.store.active('test_request')['state'], 'ACK_ACTIVE')
    async def test_default_request_is_shadow_even_with_authorized_owner(self):
        r = request(); r.pop('execution_mode')
        result = await self.engine.dispatch(r)
        self.assertEqual(result['status'], 'REJECTED'); self.assertFalse(result['writes_started']); self.assertEqual(self.device.calls, [])
    async def test_readonly_is_durable_and_never_calls_adapter(self):
        r = await self.engine.dispatch(request(execution_mode='READ_ONLY'))
        with sqlite3.connect(self.path) as db: self.assertEqual(db.execute('select state from requests').fetchone()[0], 'REJECTED')
        self.assertFalse(r['physical_dispatch_supported']); self.assertFalse(self.device.calls)
    async def test_legacy_owner_rejects_without_write(self):
        self.store.transition_owner(1, 'LEGACY', 'synthetic-ended')
        r = await self.engine.dispatch(request(owner_epoch=2))
        self.assertEqual(r['status'], 'REJECTED'); self.assertFalse(self.device.calls)
    async def test_preflight_failure_no_write(self):
        for reason in ('BMS_DIRECTION_LIMIT_ZERO','SOC_CEILING','FAULT','STALE_B1','LEGACY_NOT_FENCED'):
            self.device.error = reason
            r = await self.engine.dispatch(request(request_id=reason))
            self.assertEqual(r['status'], 'REJECTED'); self.assertFalse(self.device.calls)
    async def test_ack_without_device_effect_is_unknown(self):
        self.device.verified = False
        r = await self.engine.dispatch(request())
        self.assertEqual(r['status'], 'UNKNOWN'); self.assertTrue(r['writes_started'])
        r = await self.engine.dispatch(request(request_id='another'))
        self.assertEqual(r['status'], 'UNKNOWN'); self.assertEqual(len(self.device.calls), 1)
    async def test_wrong_device_correlation_unknown(self):
        original = self.device.confirm_effect
        async def wrong(req, power):
            result = await original(req, power); result['request_id']='other'; return result
        self.device.confirm_effect=wrong
        self.assertEqual((await self.engine.dispatch(request()))['status'], 'UNKNOWN')
    async def test_partial_write_timeout_is_unknown_and_no_replay(self):
        async def partial(req, power): self.device.calls.append(('timeout', power)); raise TimeoutError()
        self.device.apply=partial; r=request()
        self.assertEqual((await self.engine.dispatch(r))['status'], 'UNKNOWN')
        self.assertEqual((await self.engine.dispatch(r))['status'], 'UNKNOWN'); self.assertEqual(len(self.device.calls), 1)
    async def test_restart_disarms_and_retains_unknown(self):
        self.device.verified=False; await self.engine.dispatch(request())
        reopened=Store(self.path); reopened.initialize()
        self.assertFalse(reopened.control_status()['physical_authorized'])
        self.assertEqual(reopened.active('test_request')['state'],'UNKNOWN')
        with self.assertRaises(ValueError): reopened.transition_owner(1,'EMS2','retry')
    async def test_cancellation_durable_no_double_execution(self):
        self.device.delay=10; r=request(); task=asyncio.create_task(self.engine.dispatch(r))
        while not self.device.calls: await asyncio.sleep(.001)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(self.store.active(r['request_id'])['state'], 'UNKNOWN')
        self.assertEqual((await self.engine.dispatch(r))['status'],'UNKNOWN'); self.assertEqual(len(self.device.calls),1)
    async def test_owner_transition_blocked_during_active_command(self):
        await self.engine.dispatch(request())
        with self.assertRaises(ValueError): await self.engine.transition(1,'LEGACY','return')
    async def test_stop_attempt_and_confirm_are_separate(self):
        await self.engine.dispatch(request()); self.device.ended=False
        result=await self.engine.stop('test_request')
        self.assertFalse(result['active_command_canceled']); self.assertEqual(result['status'],'UNKNOWN_ACTIVE_COMMAND')
        await self.engine.stop('test_request'); self.assertEqual([x[0] for x in self.device.calls].count('STOP'),1)
    async def test_unverified_stop_never_sends_local_mode(self):
        await self.engine.dispatch(request()); self.device.can_stop=False
        self.assertFalse((await self.engine.stop('test_request'))['active_command_canceled'])
        self.assertEqual(len(self.device.calls),1)
    async def test_confirmed_stop_allows_rollback_without_starting_legacy(self):
        await self.engine.dispatch(request())
        self.assertTrue((await self.engine.stop('test_request'))['active_command_canceled'])
        r=await self.engine.transition(1,'LEGACY','confirmed-ended')
        self.assertEqual(r['owner'],'LEGACY'); self.assertFalse(r['legacy_resumed'])
    async def test_monitor_failure_latches_without_automatic_resume(self):
        await self.engine.dispatch(request()); self.device.error='FAULT'; self.device.can_stop=False
        await self.engine.monitor_once()
        self.assertTrue(self.store.control_status()['emergency_stop']['latched'])
        self.assertFalse(self.store.control_status()['automatic_resume']); self.assertEqual(len(self.device.calls),1)
    async def test_competing_instances_one_physical_write(self):
        self.device.delay=.02
        other=Engine(self.store,self.device,self.db)
        a,b=await asyncio.gather(self.engine.dispatch(request(request_id='one')),other.dispatch(request(request_id='two')))
        self.assertEqual(len(self.device.calls),1)
        self.assertIn('UNKNOWN', (a['status'],b['status']))
    async def test_changed_request_identity_not_replayed(self):
        r=request(); await self.engine.dispatch(r)
        result=await self.engine.dispatch(dict(r,power_w=700))
        self.assertEqual(result['status'],'UNKNOWN'); self.assertEqual(len(self.device.calls),1)
    async def test_corrupt_owner_cannot_pass(self):
        with sqlite3.connect(self.path) as db: db.execute('update trusted_owner set epoch=9')
        r=await self.engine.dispatch(request(owner_epoch=9))
        self.assertEqual(r['status'],'REJECTED'); self.assertFalse(self.device.calls)
    async def test_sqlite_integrity(self):
        await self.engine.dispatch(request())
        with sqlite3.connect(self.path) as db: self.assertEqual(db.execute('pragma integrity_check').fetchone()[0],'ok')


async def AsyncTermination(request_id):
    return dict(request_id=request_id,active_command_ended=False,safe_local_mode_confirmed=False)


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls=[]; self.states={}; self.now=time.time()
        async def call(domain,service,data,blocking): self.calls.append((domain,service,data))
        self.coordinator=NS(last_update_success=True,last_update_success_time=NS(timestamp=lambda:self.now),async_add_listener=lambda f:lambda:None)
        b=NS(B_SOE=50,B_DC_Power=0,B_Temp_Average=22,B_Status=7,B_MaxChargePower=5000,B_MaxChargePeakPower=5000,B_MaxDischargePower=5000,B_MaxDischargePeakPower=5000)
        c=NS(command_mode=7,control_mode=4,default_mode=7,command_timeout=30,charge_limit=5000,discharge_limit=5000)
        i=NS(I_Status=4,AC_Power=1000,AC_Power_SF=0)
        m=NS(AC_Power=-1500,AC_Power_SF=0)
        self.hub=NS(coordinator_timeout=3,inverters=[NS(inverter_unit_id=1,inverter_data=i,storage_control_data=c)],
                    batteries=[NS(inverter_unit_id=1,battery_id=1,battery_data=b)],meters=[NS(inverter_unit_id=1,meter_id=1,meter_data=m)])
        self.config=dict(physical_authorized=True,solaredge_entry_id='entry',inverter_unit_id=1,battery_id=1,meter_id=1,
                         owner_entity='input_select.example_owner',authorization_entity='input_boolean.example_auth',
                         legacy_writers=['automation.example_legacy'],max_poll_age_s=180,max_poll_window_s=5,
                         import_margin_w=200,command_timeout_s=30,device=dict(model='example_model',firmware='example_fw',inverter_serial='example_inverter',battery_serial='example_battery'))
        suffixes=importlib.import_module(PKG+'.ha_adapter').CONTROL_SUFFIXES
        self.hub.inverters[0].inverter_common=NS(C_Model='example_model',C_Version='example_fw',C_SerialNumber='example_inverter')
        self.hub.batteries[0].serial='example_battery'
        self.config['entities']={k:domain+'.example'+suffix for k,(domain,suffix) in suffixes.items()}
        self.config['verified_evidence']={k:dict(verified=True,device=self.config['device'],reference='synthetic-only',verified_at=self.now-1,valid_until=self.now+60,minimum_c=0,maximum_c=40,inverter_command_inactive_confirmed=True) for k in ('external_writer_fence','previous_command_ended','fallback','battery_no_export','battery_temperature_envelope','stop_procedure')}
        self.states['automation.example_legacy']=NS(state='off',attributes={'current':0},last_changed=__import__('datetime').datetime.fromtimestamp(self.now-2,__import__('datetime').timezone.utc))
        self.states['input_select.example_owner']=NS(state='EMS2',attributes={})
        self.states['input_boolean.example_auth']=NS(state='on',attributes={})
        registry={e:NS(platform='solaredge_modbus_multi',config_entry_id='entry',device_id='device',disabled_by=None,unique_id='example'+suffixes[k][1]) for k,e in self.config['entities'].items()}
        hass=NS(data={'solaredge_modbus_multi':{'entry':{'hub':self.hub,'coordinator':self.coordinator}}},states=NS(get=self.states.get),services=NS(async_call=call))
        async def owner(): return dict(trusted_owner='EMS2',trusted_epoch=1,physical_authorized=True,emergency_stop={'latched':False})
        self.adapter=Adapter(hass,self.config,owner,NS(async_get=registry.get)); self.adapter.write_retry_count=lambda:1
        self.adapter.termination_observer=AsyncTermination
        async def plan_validation(req): pass
        self.adapter.validate_plan=plan_validation
        self.adapter.capture_poll()
    async def test_successful_poll_uses_raw_bms_not_unchanged_entity_time(self):
        self.assertEqual((await self.adapter.preflight(request()))['soc'],50)
        self.assertFalse(self.adapter.sample['device_sample_time_known'])
    async def test_newer_ha_event_does_not_replace_failed_poll(self):
        self.coordinator.last_update_success=False; self.adapter.capture_poll()
        with self.assertRaisesRegex(ValueError,'POLL_UNCONFIRMED'): await self.adapter.preflight(request())
    async def test_stale_poll_blocks(self):
        self.adapter.sample['poll_completed_at']=time.time()-500
        with self.assertRaisesRegex(ValueError,'POLL_STALE'): await self.adapter.preflight(request())
    async def test_internal_modbus_retries_block(self):
        self.adapter.write_retry_count=lambda:3
        with self.assertRaisesRegex(ValueError,'WRITE_RETRIES_UNSAFE'): await self.adapter.preflight(request())
    async def test_zero_bms_blocks_before_services(self):
        self.adapter.sample['peak_charge']=0
        with self.assertRaisesRegex(ValueError,'LIMIT_ZERO'): await self.adapter.apply(request(),100)
        self.assertFalse(self.calls)
    async def test_soc_100_blocks_charge(self):
        self.adapter.sample['soc']=100
        with self.assertRaisesRegex(ValueError,'SOC_CEILING'): await self.adapter.preflight(request())
    async def test_soc_100_allows_directional_discharge_when_all_other_checks_pass(self):
        self.adapter.sample['soc']=100
        self.assertGreater((await self.adapter.preflight(request(option='Discharge to Minimize Import')))['direction_limit_w'],0)
    async def test_preserve_charge_still_blocks_unapproved_status(self):
        self.adapter.sample['soc']=100; self.adapter.sample['bms_status']=6
        with self.assertRaisesRegex(ValueError,'STATUS_NOT_APPROVED'): await self.adapter.preflight(request(option='Discharge to Minimize Import'))
    async def test_discharge_clamps_to_import_headroom(self):
        self.adapter.sample['m1_w']=-500
        self.assertEqual((await self.adapter.preflight(request(option='Discharge to Minimize Import')))['direction_limit_w'],300)
    async def test_export_or_no_import_blocks_discharge_not_pv_export(self):
        self.adapter.sample['m1_w']=500
        with self.assertRaisesRegex(ValueError,'IMPORT_HEADROOM'): await self.adapter.preflight(request(option='Discharge to Minimize Import'))
        await self.adapter.preflight(request())
    async def test_wrong_entity_platform_blocks(self):
        self.adapter.registry.async_get=lambda entity:NS(platform='other',config_entry_id='entry',disabled_by=None)
        with self.assertRaisesRegex(ValueError,'BINDING'): await self.adapter.preflight(request())
    async def test_known_writer_running_blocks(self):
        self.states['automation.example_legacy'].state='on'
        with self.assertRaisesRegex(ValueError,'NOT_FENCED'): await self.adapter.preflight(request())
    async def test_compound_services_exact_and_no_export_limit_write(self):
        await self.adapter.apply(request(),700)
        self.assertEqual([(d,s) for d,s,_ in self.calls],[('number','set_value'),('number','set_value'),('select','select_option')])
        self.assertEqual(self.calls[-1][2]['option'],'Charge from Solar Power')
        self.assertFalse(any('export' in str(x) for x in self.calls))
    async def test_unknown_termination_not_fabricated_from_mode(self):
        r=await self.adapter.confirm_termination('test_request')
        self.assertFalse(r['active_command_ended']); self.assertFalse(r['safe_local_mode_confirmed'])
    async def test_read_window_bound_is_enforced(self):
        self.adapter.sample['poll_window_bound_s']=60
        with self.assertRaisesRegex(ValueError,'WINDOW_UNVERIFIED'): await self.adapter.preflight(request())
    async def test_temperature_requires_verified_envelope(self):
        del self.adapter.config['verified_evidence']['battery_temperature_envelope']
        with self.assertRaisesRegex(ValueError,'TEMPERATURE_ENVELOPE'): await self.adapter.preflight(request())
    async def test_100_and_5_direction_guards(self):
        self.assertEqual(direction_guard('Charge from Solar Power',100),'SOC_CEILING')
        self.assertIsNone(direction_guard('Discharge to Minimize Import',100))
        self.assertEqual(direction_guard('Discharge to Minimize Import',5),'SOC_RESERVE')
        self.assertIsNone(direction_guard('Charge from Solar Power',4))

    async def test_missing_termination_observer_blocks_before_writes(self):
        self.adapter.termination_observer=None
        with self.assertRaisesRegex(ValueError,'TERMINATION_OBSERVER_UNAVAILABLE'):
            await self.adapter.preflight(request())
        self.assertFalse(self.calls)

    async def test_replaced_device_cannot_reuse_commissioning_evidence(self):
        self.adapter.sample['device']['inverter_serial']='different_device'
        with self.assertRaisesRegex(ValueError,'DEVICE_IDENTITY_MISMATCH'):
            await self.adapter.preflight(request())
        self.assertFalse(self.calls)

    async def test_post_write_poll_confirms_mode_and_b1_effect_not_only_ha_ack(self):
        req=request(); power=700
        await self.adapter.apply(req,power)
        task=asyncio.create_task(self.adapter.confirm_effect(req,power))
        await asyncio.sleep(0)
        c=self.hub.inverters[0].storage_control_data
        c.command_mode=2; c.charge_limit=power; c.command_timeout=30
        self.hub.batteries[0].battery_data.B_DC_Power=650
        self.now=time.time(); self.adapter.capture_poll()
        result=await task
        self.assertTrue(result['physical_effect_confirmed'])
        self.assertEqual(result['request_id'],req['request_id'])
        self.assertFalse(result['no_export_physically_proven'])
    async def test_power_above_limit_is_not_confirmed_from_service_success(self):
        req=request(); power=700
        await self.adapter.apply(req,power)
        task=asyncio.create_task(self.adapter.confirm_effect(req,power))
        await asyncio.sleep(0)
        c=self.hub.inverters[0].storage_control_data
        c.command_mode=2; c.charge_limit=power; c.command_timeout=30
        self.hub.batteries[0].battery_data.B_DC_Power=3000
        self.now=time.time(); self.adapter.capture_poll()
        self.assertFalse((await task)['physical_effect_confirmed'])


class PlanAuthorityTests(unittest.TestCase):
    def setUp(self):
        from test_plan_bridge import report, CFG, NOW
        from plan_bridge import build
        self.report=report(); self.config=CFG.copy(); self.now=NOW
        intent=build(self.report,self.config,self.now,1)['pending_request']
        self.request=dict(request_id=intent['request_id'],plan_id=intent['plan_id'],owner_epoch=1,
                          option=intent['option'],power_w=700,expires_at=self.now.timestamp()+30)
        self.guard=importlib.import_module(PKG+'.plan_guard').approved_request
    def test_existing_plan_bridge_identity_accepted_with_lower_safe_power(self):
        self.guard(self.report,self.config,self.request,self.now)
    def test_wrong_plan_and_request_identity_refused(self):
        for key,value in (('plan_id','b'*64),('request_id','forged'),('owner_epoch',2),('power_w',5001)):
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.guard(self.report,self.config,dict(self.request,**{key:value}),self.now)
    def test_unapproved_advisory_plan_refused(self):
        self.report['whole_building_schedule_approved']=False
        with self.assertRaisesRegex(ValueError,'NOT_CONTROL_APPROVED'):
            self.guard(self.report,self.config,self.request,self.now)
    def test_expired_plan_refused(self):
        from datetime import timedelta
        with self.assertRaisesRegex(ValueError,'EXPIRED'):
            self.guard(self.report,self.config,self.request,self.now+timedelta(seconds=361))
    def test_wrong_fingerprint_refused(self):
        self.report['planning_config_fingerprint']='b'*64
        with self.assertRaisesRegex(ValueError,'FINGERPRINT'):
            self.guard(self.report,self.config,self.request,self.now)
    def test_top_level_boiler_plan_is_never_used(self):
        self.report['decisions']=[{'unexpected':'boiler'}]
        self.guard(self.report,self.config,self.request,self.now)
