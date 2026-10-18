"""Actual HA 2026.10.0 service registry/permissions, isolated temp SQLite.
No device integration, production credentials, network or physical dispatch.
"""
import asyncio
import importlib
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant, Context
from homeassistant.exceptions import Unauthorized

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

async def main():
    assert __version__ == '2026.10.0', __version__
    component = importlib.import_module('custom_components.ems_epoch_gateway')
    with tempfile.TemporaryDirectory() as directory:
        hass = HomeAssistant(directory)
        hass.auth = SimpleNamespace(async_get_user=AsyncMock(return_value=SimpleNamespace(is_admin=False)))
        try:
            assert await component.async_setup(hass, {})
            assert hass.services.has_service('ems_epoch_gateway','dispatch')
            assert hass.services.has_service('ems_epoch_gateway','transition_owner')
            assert hass.services.has_service('ems_epoch_gateway','stop_command')
            from custom_components.ems_epoch_gateway.gate_store import EpochStore
            store=EpochStore(Path(directory)/'test.sqlite'); await hass.async_add_executor_job(store.initialize)
            hass.data['ems_epoch_gateway']['store']=store
            import time
            payload=dict(caller='EMS2',operation='dispatch',request_id='isolated_ha_request',plan_id='a'*64,
                         owner_epoch=0,option='Charge from Solar Power',power_w=100,expires_at=time.time()+30)
            reply=await hass.services.async_call('ems_epoch_gateway','dispatch',payload,blocking=True,return_response=True)
            assert reply['status']=='REJECTED' and reply['writes_started'] is False
            # Explicit ACTIVE cannot actuate an unconfigured runtime either.
            reply=await hass.services.async_call('ems_epoch_gateway','dispatch',dict(payload,execution_mode='ACTIVE'),blocking=True,return_response=True)
            assert reply['writes_started'] is False
            try:
                await hass.services.async_call('ems_epoch_gateway','transition_owner',
                    dict(expected_epoch=0,target='EMS2',reference='synthetic'),blocking=True,return_response=True,context=Context(user_id='nonadmin'))
            except Unauthorized:
                pass
            else:
                raise AssertionError('non-admin handover accepted')
            hass.auth.async_get_user.return_value=SimpleNamespace(is_admin=True)
            reply=await hass.services.async_call('ems_epoch_gateway','transition_owner',
                dict(expected_epoch=0,target='EMS2',reference='synthetic'),blocking=True,return_response=True,context=Context(user_id='admin'))
            assert reply['reason']=='ACTUATION_CANDIDATE_NOT_CONFIGURED'
            try:
                hass.auth.async_get_user.return_value=SimpleNamespace(is_admin=False)
                await hass.services.async_call('ems_epoch_gateway','dispatch',payload,
                    blocking=True,return_response=True,context=Context(user_id='nonadmin'))
            except Unauthorized:
                pass
            else:
                raise AssertionError('non-admin dispatch accepted')
            # Real HA service dispatcher -> production engine -> simulated device.
            sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'ems_shadow/tests'))
            from test_actuation_candidate import Device
            from custom_components.ems_epoch_gateway.control_store import ControlStore
            from custom_components.ems_epoch_gateway.actuation import ActuationGateway
            candidate=ControlStore(Path(directory)/'candidate.sqlite')
            await hass.async_add_executor_job(candidate.initialize)
            await hass.async_add_executor_job(candidate.transition_owner,0,'EMS2','synthetic-device-fence')
            device=Device()
            engine=ActuationGateway(candidate,device,hass.async_add_executor_job)
            hass.data['ems_epoch_gateway']['actuation_engine']=engine
            hass.data['ems_epoch_gateway']['store']=candidate
            active=dict(payload,request_id='isolated_active',owner_epoch=1,execution_mode='ACTIVE')
            result=await hass.services.async_call('ems_epoch_gateway','dispatch',active,blocking=True,return_response=True)
            assert result['status']=='SERVICE_COMPLETED' and result['device_execution_confirmed'] is True
            assert len(device.calls)==1
            result=await hass.services.async_call('ems_epoch_gateway','dispatch',active,blocking=True,return_response=True)
            assert result['status']=='UNKNOWN' and len(device.calls)==1
            await component.async_unload_entry(hass,None)
            assert 'actuation_engine' not in hass.data['ems_epoch_gateway']
            assert store.status()['trusted_owner']=='LEGACY'
            assert not hass.services.has_service('select','select_option')
            print('HA2026.10.0_SERVICE_REGISTRATION_PERMISSION_AND_DEFAULT_NO_WRITE_PASS')
        finally:
            await hass.async_stop(force=True)

asyncio.run(main())
