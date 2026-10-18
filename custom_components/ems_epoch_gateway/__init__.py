"""EMS Epoch Gateway: persistent, HA-side, non-actuating dispatch fence.

A deliberate staged integration: every dispatch is rejected. Physical writer
exclusivity, manufacturer fallback and safety bounds must be independently
proven before a separately reviewed release can add hardware dispatch.
"""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv

from .gate_store import CONTRACT, EpochStore

DOMAIN = "ems_epoch_gateway"
_LOGGER = logging.getLogger(__name__)
DATA_GATE = "store"

DISPATCH_SCHEMA = vol.Schema({
    vol.Required("caller"): cv.string,
    vol.Required("operation"): cv.string,
    vol.Required("request_id"): cv.string,
    vol.Required("plan_id"): cv.string,
    vol.Required("owner_epoch"): vol.Any(vol.Coerce(int), cv.string),
    vol.Required("option"): cv.string,
    vol.Required("power_w"): vol.Any(vol.Coerce(float), cv.string),
    vol.Required("expires_at"): vol.Any(vol.Coerce(float), cv.string),
}, extra=vol.PREVENT_EXTRA)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register services even before the integration config entry is created."""

    async def status(_call: ServiceCall) -> dict:
        store: EpochStore | None = hass.data.get(DOMAIN, {}).get(DATA_GATE)
        if store is None:
            return {"status": "INTEGRATION_NOT_LOADED",
                    "physical_dispatch_supported": False, "writes_started": False}
        result = await hass.async_add_executor_job(store.status)
        result["ha_owner_helper"] = hass.states.get("input_select.ems_battery_control_owner").state if hass.states.get("input_select.ems_battery_control_owner") else "UNKNOWN"
        result["ha_authorization_helper"] = hass.states.get("input_boolean.ems_battery_execution_authorized").state if hass.states.get("input_boolean.ems_battery_execution_authorized") else "UNKNOWN"
        result["ha_helpers_are_trusted_authority"] = False
        return result

    async def dispatch(call: ServiceCall) -> dict:
        request = dict(call.data)
        store: EpochStore | None = hass.data.get(DOMAIN, {}).get(DATA_GATE)
        if store is None:
            return {
                "gateway_contract": CONTRACT, "status": "REJECTED",
                "reason": "TRUSTED_GATE_NOT_LOADED", "writes_started": False,
                "device_execution_confirmed": False,
                "request_id": request.get("request_id", ""),
                "plan_id": request.get("plan_id", ""),
                "owner_epoch": request.get("owner_epoch", -1),
            }
        try:
            return await hass.async_add_executor_job(store.dispatch_rejected, request)
        except Exception:
            # No device transport exists in this integration, even on exception.
            _LOGGER.exception("Durable gateway rejected request due to internal error")
            return {
                "gateway_contract": CONTRACT, "status": "REJECTED",
                "reason": "DURABLE_GATE_INTERNAL_ERROR_NO_RETRY",
                "writes_started": False, "device_execution_confirmed": False,
                "request_id": request.get("request_id", ""),
                "plan_id": request.get("plan_id", ""),
                "owner_epoch": request.get("owner_epoch", -1),
            }

    hass.services.async_register(DOMAIN, "status", status,
                                 supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "dispatch", dispatch,
                                 schema=DISPATCH_SCHEMA,
                                 supports_response=SupportsResponse.ONLY)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialize SQLite under HA config; refuse inconsistent owner state."""
    store = EpochStore(hass.config.path(".storage/ems_epoch_gateway.sqlite"))
    try:
        await hass.async_add_executor_job(store.initialize)
    except Exception:
        _LOGGER.exception("EMS epoch journal failed initialization; dispatch stays blocked")
        return False
    hass.data.setdefault(DOMAIN, {})[DATA_GATE] = store
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Dropping the in-memory handle never changes persisted ownership."""
    hass.data.setdefault(DOMAIN, {}).pop(DATA_GATE, None)
    return True
