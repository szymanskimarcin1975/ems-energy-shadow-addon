"""Actual HA setup/entry/status with the proposed .42 configuration.
SolarEdge coordinator is simulated. No transport, no installed HA or credentials.
"""
import asyncio
import importlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

async def main():
    assert __version__=='2026.10.0'
    component=importlib.import_module('custom_components.ems_epoch_gateway')
    config=json.loads((ROOT/'deployment/adapter42/actuation_candidate.yaml').read_text())
    callbacks=[];listeners=[]
    with tempfile.TemporaryDirectory() as root:
        hass=HomeAssistant(root)
        try:
            # No device services/client/network are registered in this environment.
            hass.states.async_set(config['owner_entity'],'LEGACY')
            hass.states.async_set(config['authorization_entity'],'off')
            coordinator=NS(last_update_success=False,async_add_listener=lambda callback:(listeners.append(callback) or (lambda:None)))
            hass.data['solaredge_modbus_multi']={config['solaredge_entry_id']:{'hub':NS(),'coordinator':coordinator}}
            full={'ems_epoch_gateway':{'actuation_candidate':config}}
            component.CONFIG_SCHEMA(full)
            assert await component.async_setup(hass,full)
            entry=NS(async_on_unload=callbacks.append)
            assert await component.async_setup_entry(hass,entry)
            result=await hass.services.async_call('ems_epoch_gateway','status',{},blocking=True,return_response=True)
            assert result['physical_adapter_implemented'] is True
            assert result['physical_dispatch_supported'] is False
            assert result['trusted_owner']=='LEGACY' and result['trusted_epoch']==0
            assert result['physical_authorized'] is False and result['unresolved_requests']==0
            assert result['ha_authorization_helper']=='off'
            assert len(listeners)==1
            engine=hass.data['ems_epoch_gateway']['actuation_engine']
            assert engine.adapter.sample is None
            assert engine.adapter.poll_interval_s==120
            assert not hass.services.has_service('number','set_value')
            assert not hass.services.has_service('select','select_option')
            # No dispatch, STOP or transition invocation, even in the isolated API.
            for cancel in callbacks:cancel()
            await component.async_unload_entry(hass,entry)
            assert 'actuation_engine' not in hass.data['ems_epoch_gateway']
            print('HA2026.10.0_ADAPTER42_EXACT_CONFIG_ENTRY_LOAD_LEGACY_DISARMED_NO_DISPATCH_PASS')
        finally:
            await hass.async_stop(force=True)

asyncio.run(main())
