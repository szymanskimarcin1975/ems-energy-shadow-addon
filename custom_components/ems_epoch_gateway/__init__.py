"""EMS Epoch Gateway: non-actuating by default; optional review-only actuator.

Physical dispatch remains disabled by default. The optional review candidate
requires separate commissioning evidence and explicit authorization.
"""
from __future__ import annotations

import logging
import asyncio
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.service import async_register_admin_service

from .gate_store import CONTRACT, EpochStore

DOMAIN = "ems_epoch_gateway"
_LOGGER = logging.getLogger(__name__)
DATA_GATE = "store"
DATA_ENGINE = "actuation_engine"
CONFIG_SCHEMA = vol.Schema({vol.Optional(DOMAIN): vol.Schema({
    vol.Optional("actuation_candidate"): dict,
})}, extra=vol.ALLOW_EXTRA)

STOP_SCHEMA = vol.Schema({
    vol.Required("reason"): cv.string,
    vol.Optional("request_id"): cv.string,
    vol.Optional("owner_epoch"): int,
    vol.Optional("evidence", default={}): dict,
}, extra=vol.PREVENT_EXTRA)

DISPATCH_SCHEMA = vol.Schema({
    vol.Optional("execution_mode", default="READ_ONLY"): vol.In(["READ_ONLY", "ACTIVE"]),
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

    hass.data.setdefault(DOMAIN, {})["candidate_config"] = config.get(DOMAIN, {}).get("actuation_candidate", {})

    async def status(_call: ServiceCall) -> dict:
        store: EpochStore | None = hass.data.get(DOMAIN, {}).get(DATA_GATE)
        if store is None:
            return {"status": "INTEGRATION_NOT_LOADED",
                    "physical_dispatch_supported": False, "writes_started": False}
        result = await hass.async_add_executor_job(store.control_status if hass.data[DOMAIN].get(DATA_ENGINE) else store.status)
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
        engine = hass.data[DOMAIN].get(DATA_ENGINE)
        if engine is not None:
            # Never fall through to the old transport after a candidate exception.
            try:
                return await engine.dispatch(request)
            except Exception:
                return {"gateway_contract": CONTRACT, "status": "UNKNOWN",
                        "reason": "ACTUATION_RUNTIME_UNKNOWN_NO_RETRY", "writes_started": None,
                        "device_execution_confirmed": False,
                        "request_id": request.get("request_id", ""),
                        "plan_id": request.get("plan_id", ""), "owner_epoch": request.get("owner_epoch", -1)}
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
        engine = hass.data[DOMAIN].get(DATA_ENGINE)
        if engine is not None:
            request_id = call.data.get("request_id") or await hass.async_add_executor_job(store.current_request)
            if request_id:
                result["device_stop_attempt"] = await engine.stop(request_id)
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
    async_register_admin_service(hass, DOMAIN, "dispatch", dispatch,
                                 schema=DISPATCH_SCHEMA,
                                 supports_response=SupportsResponse.ONLY)
    async def transition_owner(call: ServiceCall) -> dict:
        engine = hass.data.get(DOMAIN, {}).get(DATA_ENGINE)
        if engine is None:
            return {"status": "REJECTED", "reason": "ACTUATION_CANDIDATE_NOT_CONFIGURED"}
        result = await engine.transition(call.data["expected_epoch"], call.data["target"], call.data["reference"])
        try:
            await hass.services.async_call("input_select", "select_option",
                {"entity_id": engine.adapter.config["owner_entity"], "option": result["owner"]}, blocking=True)
            result["helper_sync"] = "COMPLETED"
        except Exception:
            result["helper_sync"] = "UNKNOWN_BLOCKED"
        return result

    async def command_status(call: ServiceCall) -> dict:
        engine = hass.data.get(DOMAIN, {}).get(DATA_ENGINE)
        if engine is None:
            return {"status": "ACTUATION_CANDIDATE_NOT_CONFIGURED", "writes_started": False}
        return await engine.command_status(call.data["request_id"])

    async_register_admin_service(hass, DOMAIN, "command_status", command_status,
        schema=vol.Schema({vol.Required("request_id"): cv.string}), supports_response=SupportsResponse.ONLY)

    async def stop_command(call: ServiceCall) -> dict:
        engine = hass.data.get(DOMAIN, {}).get(DATA_ENGINE)
        if engine is None:
            return {"status": "STOP_NOT_CONFIRMED", "active_command_canceled": False}
        return await engine.stop(call.data["request_id"])

    async_register_admin_service(hass, DOMAIN, "transition_owner", transition_owner,
        schema=vol.Schema({vol.Required("expected_epoch"): int,
                           vol.Required("target"): vol.In(["LEGACY", "EMS2"]),
                           vol.Required("reference"): cv.string}), supports_response=SupportsResponse.ONLY)
    async_register_admin_service(hass, DOMAIN, "stop_command", stop_command,
        schema=vol.Schema({vol.Required("request_id"): cv.string}), supports_response=SupportsResponse.ONLY)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialize SQLite under HA config; refuse inconsistent owner state."""
    candidate = hass.data.get(DOMAIN, {}).get("candidate_config", {})
    if candidate.get("enabled") is True:
        from .control_store import ControlStore
        store = ControlStore(hass.config.path(".storage/ems_epoch_gateway.sqlite"))
    else:
        store = EpochStore(hass.config.path(".storage/ems_epoch_gateway.sqlite"))
    try:
        await hass.async_add_executor_job(store.initialize)
    except Exception:
        _LOGGER.exception("EMS epoch journal failed initialization; dispatch stays blocked")
        return False
    hass.data.setdefault(DOMAIN, {})[DATA_GATE] = store
    if candidate.get("enabled") is True:
        from .actuation import ActuationGateway
        from .ha_adapter import HASolarEdgeAdapter
        async def owner_status():
            return await hass.async_add_executor_job(store.control_status)
        adapter = HASolarEdgeAdapter(hass, candidate, owner_status, er.async_get(hass))
        entry.async_on_unload(adapter.unsubscribe)
        engine = ActuationGateway(store, adapter, hass.async_add_executor_job)
        hass.data[DOMAIN][DATA_ENGINE] = engine
        async def monitor():
            while True:
                await asyncio.sleep(1)
                try:
                    await engine.monitor_once()
                except Exception:
                    # Persistent storage unavailable: writes cannot be authorized.
                    _LOGGER.error("EMS actuator monitor unavailable; operator reconciliation required")
        task = hass.async_create_background_task(monitor(), "EMS2 command safety monitor")
        entry.async_on_unload(task.cancel)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Unload never sends a stop/restore command or starts LEGACY.
    hass.data.get(DOMAIN, {}).pop(DATA_ENGINE, None)
    hass.data.get(DOMAIN, {}).pop(DATA_GATE, None)
    return True
