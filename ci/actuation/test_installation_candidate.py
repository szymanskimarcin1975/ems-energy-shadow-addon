"""New paths only: offline source patch, STOP witness and review-only CWU."""
import ast
import asyncio
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'ems_shadow/tests'))
import test_actuation_candidate as fixtures
Adapter=fixtures.Adapter
spec=importlib.util.spec_from_file_location('package_builder',ROOT/'tools/installation/prepare_candidate.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class StopWitnessTests(fixtures.AdapterTests):
    # Inherit existing exact fixture; each new case drives actual adapter methods.
    async def test_default_observer_is_connected(self):
        self.assertTrue(callable(Adapter(self.adapter.hass,self.config,self.adapter.owner_status,self.adapter.registry).termination_observer))

    async def test_local_stop_services_and_two_poll_witness(self):
        self.adapter.termination_observer=self.adapter.observe_local_authority
        await self.adapter.request_local_mode('stop')
        self.assertEqual([x[2]['entity_id'] for x in self.calls],
                         [self.config['entities']['control']])
        after=self.adapter.stop_started['stop']
        self.assertTrue((await self.adapter.confirm_termination('stop'))['pending_confirmation'])
        c=self.hub.inverters[0].storage_control_data;c.control_mode=1;c.command_mode=7
        self.now=after+120;self.adapter.clock=lambda:self.now;self.adapter.capture_poll()
        self.assertTrue((await self.adapter.confirm_termination('stop'))['pending_confirmation'])
        self.now=after+240;self.adapter.capture_poll()
        result=await self.adapter.confirm_termination('stop')
        self.assertTrue(result['active_command_ended'])
        self.assertFalse(result['timeout_expiry_confirmed'])
        self.assertFalse(result['no_export_physically_proven'])

    async def test_command_mode_alone_never_proves_stop(self):
        self.adapter.stop_started['stop']=time.time()-1
        self.adapter.poll_history=[dict(self.adapter.sample,poll_completed_at=time.time())]*2
        result=await self.adapter.observe_local_authority('stop')
        self.assertFalse(result['active_command_ended'])

    async def test_uncommissioned_stop_has_zero_calls(self):
        self.adapter.config['verified_evidence']['stop_procedure']['device_test_passed']=False
        with self.assertRaisesRegex(ValueError,'STOP_METHOD_NOT_VERIFIED'):
            await self.adapter.request_local_mode('stop')
        self.assertEqual(self.calls,[])

    async def test_second_stop_write_timeout_propagates_without_retry(self):
        async def call(domain,service,data,blocking):
            self.calls.append(data)
            if len(self.calls)==2:raise TimeoutError()
        self.adapter.hass.services.async_call=call
        self.adapter.sample['mode']=2
        with self.assertRaises(TimeoutError):await self.adapter.request_local_mode('stop')
        self.assertEqual(len(self.calls),2)

    async def test_unknown_stop_request_does_not_infer_expiry(self):
        self.assertFalse((await self.adapter.observe_local_authority('unknown'))['active_command_ended'])

    async def test_fault_export_and_remote_readback_do_not_confirm_stop(self):
        from unittest.mock import patch
        async def no_more_polls(awaitable, timeout):
            awaitable.close()
            raise TimeoutError()
        for changes in ({'inverter_status':6}, {'bms_status':6},
                        {'control':4}, {'b1_w':-250,'m1_w':100},
                        {'poll_window_bound_s':120}, {'soc':float('nan')}):
            now=time.time();self.adapter.stop_started['stop']=now-1
            good=dict(self.adapter.sample,control=1,mode=7,default=7)
            self.adapter.poll_history=[dict(good,poll_completed_at=now-.2),
                dict(good,poll_completed_at=now-.1,**changes)]
            with patch('asyncio.wait_for',no_more_polls):
                result=await self.adapter.observe_local_authority('stop')
            self.assertFalse(result['active_command_ended'],changes)

    async def test_failed_poll_clears_termination_witness(self):
        self.assertTrue(self.adapter.poll_history)
        self.coordinator.last_update_success=False;self.adapter.capture_poll()
        self.assertEqual(self.adapter.poll_history,[])



class PackagingTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_patched_component_write_single_attempt(self):
        import os
        source=Path(os.environ.get('SOLAREDGE_SOURCE','/workspace/scratch/700f4f124b09/solaredge-404-reference/custom_components/solaredge_modbus_multi'))
        if not source.exists():self.skipTest('exact upstream source provided by CI')
        patched=builder.companion(source)
        tree=ast.parse(patched['hub.py'])
        cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='SolarEdgeModbusMultiHub')
        selected=[x for x in cls.body if getattr(x,'name','') in ('component_write','ems_storage_single_attempt')]
        class Failure(Exception):pass
        async def retry(component,field,value):
            for _ in range(3):
                try:return await component.write(field,value)
                except Failure:pass
            raise Failure()
        ns=dict(async_write_with_retry=retry,ModbusConnectionError=Failure,ModbusProtocolError=Failure,
                ModbusTimeoutError=Failure,IllegalFunctionError=Failure,IllegalDataAddressError=Failure,
                IllegalDataValueError=Failure,ModbusExceptionError=Failure,HomeAssistantError=Failure,
                _LOGGER=NS(debug=lambda *a:None),WRITE_SETTLE_CYCLES=2)
        # Exact patched methods without importing HA or replacing their bodies.
        exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='Hub',bases=[],keywords=[],body=selected,decorator_list=[])],type_ignores=[])), '<patched-upstream>', 'exec'),ns)
        h=ns['Hub']();h.sleep_after_write=0;h._entry_id='allowed';h._yaml_config={'ems_single_attempt_entries':['allowed']}
        class Component:
            attempts=0
            async def write(self,*a):self.attempts+=1;raise Failure()
        c=Component();h.inverters=[NS(storage_control_data=c)]
        with self.assertRaises(Failure):await h.component_write(1,c,'command_mode',5)
        self.assertEqual(c.attempts,1)
        h._entry_id='not-allowed';c.attempts=0
        with self.assertRaises(Failure):await h.component_write(1,c,'command_mode',5)
        self.assertEqual(c.attempts,3)
        h._entry_id='allowed';other=Component()
        with self.assertRaises(Failure):await h.component_write(1,other,'unrelated',1)
        self.assertEqual(other.attempts,3)

    async def test_unreviewed_source_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'hub.py').write_text('changed')
            with self.assertRaisesRegex(ValueError,'UNREVIEWED'):builder.companion(p)

    async def test_artifact_versions_match_actual_source(self):
        import os,zipfile
        source=Path(os.environ.get('SOLAREDGE_SOURCE','/workspace/scratch/700f4f124b09/solaredge-404-reference/custom_components/solaredge_modbus_multi'))
        if not source.exists():self.skipTest('exact upstream source not supplied')
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'candidate'
            builder.build(source,out,ROOT)
            state=json.loads((out/'INSTALLATION-STATE.json').read_text())
            version=state['addon_version'];gateway=state['gateway_version']
            with zipfile.ZipFile(out/f'ems-shadow-{version}-source.zip') as z:
                self.assertIn('version: '+version,z.read('ems_shadow/config.yaml').decode())
            with zipfile.ZipFile(out/f'ems-epoch-gateway-{gateway}.zip') as z:
                self.assertEqual(json.loads(z.read('custom_components/ems_epoch_gateway/manifest.json'))['version'],gateway)
            self.assertFalse((out/'ems-shadow-0.1.4-observation.42-source.zip').exists())

    async def test_disabled_installation_defaults(self):
        config=(ROOT/'ems_shadow/config.yaml').read_text()
        self.assertIn('0.1.4-observation.45',config)
        self.assertIn('io.hass.version="0.1.4-observation.45"',(ROOT/'ems_shadow/Dockerfile').read_text())
        source=(ROOT/'custom_components/ems_epoch_gateway/__init__.py').read_text()
        self.assertIn('candidate.get("enabled") is True',source)
        self.assertNotIn('transition_owner(', (ROOT/'tools/installation/prepare_candidate.py').read_text())

    async def test_cwu_review_contains_no_actuation(self):
        text=(ROOT/'blueprints/automation/ems2/cwu_weekday_review.yaml').read_text()
        for t in ('02:30:00','04:00:00','07:00:00'):self.assertIn(t,text)
        for forbidden in ('number.set_value','select.select_option','climate.','ems_epoch_gateway.dispatch'):
            self.assertNotIn(forbidden,text)
        self.assertIn('logbook.log',text)

if __name__=='__main__':unittest.main()
