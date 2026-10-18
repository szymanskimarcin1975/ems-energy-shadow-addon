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

STOP_SCHEMA = vol.Schema({
    vol.Required("reason"): cv.string,
    vol.Optional("request_id"): cv.string,
    vol.Optional("owner_epoch"): int,
    vol.Optional("evidence", default={}): dict,
}, extra=vol.PREVENT_EXTRA)

DISPATCH_SCHEMA = vol.Schema({
    vol.Required("caller"): cv.string,
    vol.Required("operation"): cv.string,
    vol.Required("request_id"): cv.string,
    vol.Required("plan_id"): cv.string,
    vol.Required("owner_epoch"): vol.Any(int, cv.string),
    vol.Required("option"): cv.string,
    vol.Required("power_w"): vol.Any(int, float, cv.string),
    vol.Required("expires_at"): vol.Any(int, float, cv.string),
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

    async def emergency_stop(call: ServiceCall) -> dict:
        store: EpochStore | None = hass.data.get(DOMAIN, {}).get(DATA_GATE)
        if store is None:
            return {"status": "STOP_NOT_CONFIRMED", "reason": "TRUSTED_GATE_NOT_LOADED",
                    "new_commands_blocked": True, "active_command_state": "UNKNOWN_ACTIVE_COMMAND",
                    "active_command_canceled": False, "automatic_resume": False}
        result = await hass.async_add_executor_job(
            store.trip_emergency_stop,
            call.data["reason"],
            call.data.get("request_id"),
            call.data.get("owner_epoch"),
            call.data.get("evidence", {}),
        )
        _LOGGER.error("EMS emergency stop latched: %s", result.get("reason"))
        try:
            await hass.services.async_call(
                "persistent_notification", "create",
                {"title": "EMS2 Emergency STOP",
                 "message": "EMS2 został zatrzymany i blokuje nowe żądania. Przyczyna: "
                            + str(result.get("reason"))
                            + ". Aktywna komenda falownika nie została anulowana; jej stan może wymagać ręcznej weryfikacji.",
                 "notification_id": "ems2_emergency_stop"},
                blocking=False,
            )
        except Exception:
            _LOGGER.warning("EMS emergency stop latched; persistent notification unavailable")
        return result

    hass.services.async_register(DOMAIN, "status", status,
                                 supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "emergency_stop", emergency_stop,
                                 schema=STOP_SCHEMA,
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
