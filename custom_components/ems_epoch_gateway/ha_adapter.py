"""HA binding for existing SolarEdge Modbus Multi entity services only.

Version-scoped read adapter: upstream v4.0.4 d38d890887684ddd7938c4bce5223d387b24c6a7.
No second Modbus client, register writes, forced poll or upstream monkey patch.
"""
import asyncio
import copy
import math
import time
from datetime import datetime, timezone
from .plan_guard import read_approved_request
from .actuation import CHARGES, direction_guard, finite

DOMAIN = 'solaredge_modbus_multi'
CONTROL_SUFFIXES = {
    'mode': ('select', '_storage_command_mode'),
    'control': ('select', '_storage_control_mode'),
    'default': ('select', '_storage_default_mode'),
    'timeout': ('number', '_storage_command_timeout'),
    'charge': ('number', '_storage_charge_limit'),
    'discharge': ('number', '_storage_discharge_limit'),
}


class HASolarEdgeAdapter:
    def __init__(self, hass, config, owner_status, registry, clock=time.time, termination_observer=None):
        self.hass, self.config, self.owner_status, self.registry, self.clock = hass, copy.deepcopy(config), owner_status, registry, clock
        self.termination_observer = termination_observer
        self.sample = None
        self.poll_event = asyncio.Event()
        self.entry_id = config['solaredge_entry_id']
        data = hass.data[DOMAIN][self.entry_id]
        self.hub, self.coordinator = data['hub'], data['coordinator']
        self.unsubscribe = self.coordinator.async_add_listener(self.capture_poll)
        # Do not bootstrap physical freshness from HA entity timestamps/cache.

    def evidence(self, name):
        value = self.config.get('verified_evidence', {}).get(name, {})
        now = self.clock()
        if (not isinstance(value, dict) or value.get('verified') is not True or
                value.get('device') != self.config.get('device') or
                not isinstance(value.get('reference'), str) or not value['reference'].strip() or
                not finite(value.get('verified_at')) or not finite(value.get('valid_until')) or
                not value['verified_at'] <= now < value['valid_until'] or
                not 0 < value['valid_until'] - value['verified_at'] <= 86400):
            raise ValueError(name.upper() + '_UNVERIFIED')
        return value

    def check_bindings(self):
        devices = set()
        for role, (domain, suffix) in CONTROL_SUFFIXES.items():
            entity = self.config['entities'][role]
            entry = self.registry.async_get(entity)
            if (not entity.startswith(domain + '.') or entry is None or
                    entry.platform != DOMAIN or entry.config_entry_id != self.entry_id or
                    entry.disabled_by is not None or not entry.unique_id.endswith(suffix)):
                raise ValueError('CONTROL_ENTITY_BINDING_UNVERIFIED')
            devices.add(entry.device_id)
        if len(devices) != 1 or None in devices:
            raise ValueError('CONTROL_DEVICE_MISMATCH')

    def capture_poll(self):
        """Listener runs after the integration's complete read cycle; no new I/O."""
        try:
            if self.coordinator.last_update_success is not True:
                raise ValueError('POLL_FAILED')
            t = self.coordinator.last_update_success_time.timestamp()
            if self.sample is not None and t <= self.sample['poll_completed_at']:
                return
            unit = self.config['inverter_unit_id']
            inverter, = [x for x in self.hub.inverters if x.inverter_unit_id == unit]
            battery, = [x for x in self.hub.batteries if x.inverter_unit_id == unit and x.battery_id == self.config['battery_id']]
            meter, = [x for x in self.hub.meters if x.inverter_unit_id == unit and x.meter_id == self.config['meter_id']]
            b, i, m, c = battery.battery_data, inverter.inverter_data, meter.meter_data, inverter.storage_control_data
            self.sample = dict(
                poll_completed_at=t, poll_window_bound_s=self.hub.coordinator_timeout,
                provenance='successful_complete_Modbus_read_not_device_sample_clock',
                device_sample_time_known=False, soc=b.B_SOE, b1_w=b.B_DC_Power,
                temperature_c=b.B_Temp_Average, bms_status=b.B_Status,
                max_charge=b.B_MaxChargePower, peak_charge=b.B_MaxChargePeakPower,
                max_discharge=b.B_MaxDischargePower, peak_discharge=b.B_MaxDischargePeakPower,
                inverter_status=i.I_Status,
                m1_w=m.AC_Power * 10 ** m.AC_Power_SF,
                ac_w=i.AC_Power * 10 ** i.AC_Power_SF,
                mode=c.command_mode, control=c.control_mode, default=c.default_mode,
                timeout=c.command_timeout, charge=c.charge_limit, discharge=c.discharge_limit,
            )
            self.poll_event.set()
        except Exception:
            self.sample = None
            self.poll_event.set()

    async def verify_handover(self, target):
        if self.config.get('physical_authorized') is not True:
            raise ValueError('PHYSICAL_AUTHORIZATION_OFF')
        self.evidence('external_writer_fence')
        ended = self.evidence('previous_command_ended')
        if ended.get('inverter_command_inactive_confirmed') is not True:
            raise ValueError('PREVIOUS_COMMAND_NOT_RECONCILED')
        if self.termination_observer is None:
            raise ValueError('DEVICE_TERMINATION_OBSERVER_UNAVAILABLE')
        if self.write_retry_count() != 1:
            raise ValueError('INTEGRATION_WRITE_RETRIES_UNSAFE')
        self.evidence('fallback')
        self.evidence('battery_no_export')
        self.check_bindings()
        writers = self.config.get('legacy_writers')
        if not isinstance(writers, list) or not writers:
            raise ValueError('WRITER_INVENTORY_MISSING')
        for entity in writers:
            state = self.hass.states.get(entity)
            if (not isinstance(entity, str) or not entity.startswith(('automation.', 'script.')) or state is None or
                    state.state != 'off' or state.attributes.get('current') != 0):
                raise ValueError('LEGACY_WRITER_NOT_FENCED')
            changed = getattr(state, 'last_changed', None)
            if changed is None or ended['verified_at'] < changed.timestamp():
                raise ValueError('TERMINATION_EVIDENCE_PREDATES_WRITER_QUIESCENCE')
        # This verifies configured HA writers only. External exclusion needs separate evidence.
        if target not in ('EMS2', 'LEGACY'):
            raise ValueError('INVALID_OWNER')

    @staticmethod
    def write_retry_count():
        from custom_components.solaredge_modbus_multi.const import RetrySettings
        return RetrySettings.RequestRetries

    async def preflight(self, request):
        await self.verify_handover('EMS2')
        current = await self.owner_status()
        if current['trusted_owner'] != 'EMS2' or current['trusted_epoch'] != request['owner_epoch'] or not current['physical_authorized'] or current['emergency_stop']['latched']:
            raise ValueError('OWNER_OR_EPOCH_NOT_AUTHORIZED')
        owner = self.hass.states.get(self.config['owner_entity'])
        auth = self.hass.states.get(self.config['authorization_entity'])
        if owner is None or owner.state != 'EMS2' or auth is None or auth.state != 'on':
            raise ValueError('SHARED_AUTHORIZATION_OFF')
        # v4.0.4 retries Modbus writes internally. An EMS no-retry policy cannot
        # override that by pretending a single HA service call is one device write.
        if self.write_retry_count() != 1:
            raise ValueError('INTEGRATION_WRITE_RETRIES_UNSAFE')
        if self.termination_observer is None:
            raise ValueError('DEVICE_TERMINATION_OBSERVER_UNAVAILABLE')
        await self.validate_plan(request)
        sample = copy.deepcopy(self.sample)
        if sample is None or self.coordinator.last_update_success is not True:
            raise ValueError('COMPLETE_MODBUS_POLL_UNCONFIRMED')
        max_age = self.config.get('max_poll_age_s', 0)
        window = self.config.get('max_poll_window_s', 0)
        if not finite(max_age) or not 0 < max_age <= 180 or not 0 <= self.clock() - sample['poll_completed_at'] <= max_age:
            raise ValueError('MODBUS_POLL_STALE')
        if not finite(window) or not 0 < window <= 30 or not finite(sample['poll_window_bound_s']) or not 0 < sample['poll_window_bound_s'] <= window:
            raise ValueError('MODBUS_READ_WINDOW_UNVERIFIED')
        if not all(finite(sample[k]) for k in ('soc', 'm1_w', 'b1_w', 'ac_w', 'temperature_c')):
            raise ValueError('NONFINITE_TELEMETRY')
        if sample['inverter_status'] not in (4, 5, 8) or sample['bms_status'] not in (1, 3, 4, 7):
            raise ValueError('FAULT_OR_BMS_STATUS_NOT_APPROVED')
        if sample['control'] != 4 or sample['default'] != 7:
            raise ValueError('REMOTE_OR_DEFAULT_MODE_UNCONFIRMED')
        thermal = self.evidence('battery_temperature_envelope')
        low, high = thermal.get('minimum_c'), thermal.get('maximum_c')
        if not finite(low) or not finite(high) or not low < high or not low <= sample['temperature_c'] <= high:
            raise ValueError('BATTERY_TEMPERATURE_UNCONFIRMED')
        reason = direction_guard(request['option'], sample['soc'], self.config.get('soc_min', 5), self.config.get('soc_max', 95))
        if reason:
            raise ValueError(reason)
        direction = 'charge' if request['option'] in CHARGES else 'discharge'
        limits = [sample['max_' + direction], sample['peak_' + direction]]
        if not all(finite(v) and 0 <= v <= 5000 for v in limits):
            raise ValueError('BMS_LIMIT_UNCONFIRMED')
        if min(limits) <= 0:
            raise ValueError('BMS_DIRECTION_LIMIT_ZERO')
        sample['direction_limit_w'] = min(limits)
        if direction == 'discharge':
            # Positive M1 is export; never infer demand by clipping a bad balance.
            margin = self.config.get('import_margin_w')
            if not finite(margin) or margin <= 0:
                raise ValueError('IMPORT_MARGIN_UNVERIFIED')
            if sample['m1_w'] >= -margin:
                raise ValueError('NO_CONFIRMED_IMPORT_HEADROOM')
            sample['direction_limit_w'] = min(sample['direction_limit_w'], -sample['m1_w'] - margin)
        return sample

    async def validate_plan(self, request):
        await self.hass.async_add_executor_job(read_approved_request,
            self.hass.config.path('ems_shadow/planning_report.yaml'),
            self.config.get('planner', {}), request, datetime.now(timezone.utc))

    async def apply(self, request, power):
        direction = 'charge' if request['option'] in CHARGES else 'discharge'
        commands = [('number', 'set_value', 'timeout', self.config['command_timeout_s']),
                    ('number', 'set_value', direction, power),
                    ('select', 'select_option', 'mode', request['option'])]
        timeout = self.config.get('command_timeout_s')
        if type(timeout) is not int or not 1 <= timeout <= 3600:
            raise ValueError('COMMAND_TIMEOUT_UNVERIFIED')
        for domain, service, role, value in commands:
            sample = await self.preflight(request)
            if power > sample['direction_limit_w'] or self.clock() >= request['expires_at']:
                raise ValueError('GUARD_CHANGED_DURING_COMPOUND_WRITE')
            key = 'value' if domain == 'number' else 'option'
            async with asyncio.timeout(min(10, max(0, request['expires_at'] - self.clock()))):
                await self.hass.services.async_call(domain, service,
                    {'entity_id': self.config['entities'][role], key: value}, blocking=True)

    async def confirm_effect(self, request, power):
        before = self.sample['poll_completed_at'] if self.sample else self.clock()
        self.poll_event.clear()
        remaining = min(30, request['expires_at'] - self.clock())
        if remaining <= 0:
            return {}
        try:
            await asyncio.wait_for(self.poll_event.wait(), timeout=remaining)
        except TimeoutError:
            return {}
        s = await self.preflight(request)
        expected = {'Charge from Solar Power': 2, 'Charge from Solar Power and Grid': 3, 'Discharge to Minimize Import': 5}[request['option']]
        direction = 'charge' if request['option'] in CHARGES else 'discharge'
        # These checks demonstrate response, not battery-origin export attribution.
        tolerance = self.config.get('power_readback_tolerance_w', 0)
        if not finite(tolerance) or not 0 <= tolerance <= 500:
            return {}
        effect = (s['b1_w'] > 0 if direction == 'charge' else s['b1_w'] < 0) and abs(s['b1_w']) <= power + tolerance
        mode_ok = s['mode'] == expected and s[direction] == power and s['timeout'] == self.config['command_timeout_s']
        if direction == 'discharge' and s['m1_w'] > 0:
            effect = False
        return dict(request_id=request['request_id'], plan_id=request['plan_id'], owner_epoch=request['owner_epoch'],
                    observed_at=s['poll_completed_at'], physical_effect_confirmed=bool(effect and mode_ok and s['poll_completed_at'] > before),
                    b1_w=s['b1_w'], m1_w=s['m1_w'], ac_w=s['ac_w'],
                    poll_window_bound_s=s['poll_window_bound_s'], no_export_physically_proven=False)

    async def verify_stop_procedure(self, request_id):
        current = await self.owner_status()
        if current['trusted_owner'] != 'EMS2':
            raise ValueError('STOP_OWNER_NOT_EMS2')
        self.evidence('external_writer_fence')
        procedure = self.evidence('stop_procedure')
        if procedure.get('method') != 'command_mode_maximize_self_consumption':
            raise ValueError('STOP_METHOD_NOT_VERIFIED')
        if self.write_retry_count() != 1:
            raise ValueError('INTEGRATION_WRITE_RETRIES_UNSAFE')
        if self.sample is None or not 0 <= self.clock() - self.sample['poll_completed_at'] <= 30:
            raise ValueError('STOP_STATE_UNKNOWN')
        self.check_bindings()

    async def request_local_mode(self, request_id):
        # A verified installation procedure may request this mode. A select ACK
        # does not itself terminate/reconcile the preceding device command.
        async with asyncio.timeout(10):
            await self.hass.services.async_call('select', 'select_option',
                {'entity_id': self.config['entities']['mode'], 'option': 'Maximize Self Consumption'}, blocking=True)

    async def confirm_termination(self, request_id):
        # v4.0.4 has no correlated inactive-command status. Never manufacture one.
        if self.termination_observer is not None:
            return await self.termination_observer(request_id)
        return dict(request_id=request_id, active_command_ended=False,
                    safe_local_mode_confirmed=False, reason='DEVICE_TERMINATION_OBSERVER_UNAVAILABLE')
