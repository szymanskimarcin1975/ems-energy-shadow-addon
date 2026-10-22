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
    deferred_confirmation = True
    poll_interval_s = 120
    def __init__(self, hass, config, owner_status, registry, clock=time.time, termination_observer=None):
        self.hass, self.config, self.owner_status, self.registry, self.clock = hass, copy.deepcopy(config), owner_status, registry, clock
        self.termination_observer = termination_observer or self.observe_local_authority
        self.poll_history = []
        self.stop_started = {}
        self.reserve_writes = None
        self.finish_write = None
        self.prepared_writes = {}
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
                device=dict(model=inverter.inverter_common.C_Model,
                            firmware=inverter.inverter_common.C_Version,
                            inverter_serial=inverter.inverter_common.C_SerialNumber,
                            battery_serial=battery.serial),
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
            self.poll_history = (self.poll_history + [copy.deepcopy(self.sample)])[-12:]
            self.poll_event.set()
        except Exception:
            self.poll_history = []
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
        stop = self.evidence('stop_procedure')
        if stop.get('method') != 'remote_to_local_self_consumption' or stop.get('device_test_passed') is not True:
            raise ValueError('STOP_METHOD_NOT_VERIFIED')
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
        sample = self.sample
        if sample is None or self.coordinator.last_update_success is not True:
            raise ValueError('COMPLETE_MODBUS_POLL_UNCONFIRMED')
        age = self.config.get('max_poll_age_s', 0)
        if not finite(age) or not 0 < age <= 180 or not 0 <= self.clock() - sample['poll_completed_at'] <= age:
            raise ValueError('MODBUS_POLL_STALE')
        def firmware(value):
            text = str(value)
            return tuple(int(x) for x in text.split('.')) if all(x.isdecimal() for x in text.split('.')) else text
        expected = self.config.get('device', {})
        actual = sample.get('device', {})
        if (not all(expected.get(k) and actual.get(k) == expected[k] for k in ('model','inverter_serial','battery_serial')) or
                firmware(actual.get('firmware')) != firmware(expected.get('firmware'))):
            raise ValueError('PHYSICAL_DEVICE_IDENTITY_MISMATCH')
        if sample['inverter_status'] not in (4, 5, 8) or sample['bms_status'] not in (1, 3, 4, 7):
            raise ValueError('FAULT_OR_BMS_STATUS_NOT_APPROVED')
        # This verifies configured HA writers only. External exclusion needs separate evidence.
        if target not in ('EMS2', 'LEGACY'):
            raise ValueError('INVALID_OWNER')

    def write_retry_count(self):
        # Capability comes from the reviewed entry-scoped companion patch.
        # Pin the transport inspected/tested for ambiguous-outcome no-retry.
        from importlib.metadata import version
        if (getattr(self.hub, 'ems_storage_single_attempt', False) is True and
                version('modbus-connection') == '4.10.0' and version('tmodbus') == '0.6.1'):
            return 1
        return 0

    async def preflight(self, request, *, monitoring=False):
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
        plan_until = await self.validate_plan(request, monitoring=True) if monitoring else await self.validate_plan(request)
        if not monitoring:
            # Do not admit a lease that can outlive the evidence needed to STOP.
            timeout = self.config.get('command_timeout_s')
            if type(timeout) is not int or not 1 <= timeout <= 3600 or not finite(plan_until):
                raise ValueError('COMMAND_LEASE_UNCONFIRMED')
            stop_until = self.clock() + 30 + timeout + 390
            for name in ('external_writer_fence', 'stop_procedure'):
                if self.evidence(name)['valid_until'] <= stop_until:
                    raise ValueError('STOP_EVIDENCE_EXPIRES_BEFORE_LEASE_END')
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
        sample['plan_valid_until'] = plan_until
        sample['direction_limit_w'] = min(limits)
        if direction == 'discharge':
            # Positive M1 is export; never infer demand by clipping a bad balance.
            margin = self.config.get('import_margin_w')
            if not finite(margin) or margin <= 0:
                raise ValueError('IMPORT_MARGIN_UNVERIFIED')
            if monitoring:
                # Mode 5 is a power ceiling, not a fixed discharge demand. Once
                # active it reduces measured grid import itself. DC battery W
                # cannot safely reconstruct AC load without verified losses.
                # Keep BMS ceilings and reject observed export; do not treat
                # residual import as the original available household demand.
                if sample['m1_w'] > 0:
                    raise ValueError('OBSERVED_GRID_EXPORT_DURING_DISCHARGE')
            else:
                if sample['m1_w'] >= -margin:
                    raise ValueError('NO_CONFIRMED_IMPORT_HEADROOM')
                sample['direction_limit_w'] = min(sample['direction_limit_w'], -sample['m1_w'] - margin)
        return sample

    async def monitor_preflight(self, request):
        return await self.preflight(request, monitoring=True)

    async def validate_plan(self, request, monitoring=False):
        return await self.hass.async_add_executor_job(read_approved_request,
            self.hass.config.path('ems_shadow/planning_report.yaml'),
            self.config.get('planner', {}), request, datetime.now(timezone.utc), monitoring)

    def bind_write_journal(self, reserve, finish):
        self.reserve_writes,self.finish_write=reserve,finish

    def _changes(self, commands):
        # Raw register values from a fresh, successful complete poll. No forced read.
        sample=self.sample
        fresh=(sample is not None and self.coordinator.last_update_success is True and
               0<=self.clock()-sample['poll_completed_at']<=180)
        modes={'Charge from Solar Power':2,'Charge from Solar Power and Grid':3,
               'Discharge to Minimize Import':5,'Maximize Self Consumption':7}
        changes=[]
        for domain,service,role,value in commands:
            desired=(1 if role=='control' else modes[value]) if domain=='select' else value
            changes.append(dict(domain=domain,service=service,role=role,value=value,
                                required=not(fresh and sample.get(role)==desired)))
        return changes

    async def prepare_apply(self, request, power):
        if self.reserve_writes is None:raise ValueError('DURABLE_SETTING_JOURNAL_REQUIRED')
        direction='charge' if request['option'] in CHARGES else 'discharge'
        timeout=self.config.get('command_timeout_s')
        if type(timeout) is not int or not 1<=timeout<=3600:raise ValueError('COMMAND_TIMEOUT_UNVERIFIED')
        commands=[('number','set_value','timeout',timeout),('number','set_value',direction,power),
                  ('select','select_option','mode',request['option'])]
        changes=self._changes(commands)
        await self.reserve_writes(request['request_id'],changes,self.config.get('write_policy'),self.clock(),False)
        self.prepared_writes[request['request_id']]=changes

    async def _setting_service(self, request_id, row, emergency):
        if not row['required']:return
        role=row['role']
        await self.finish_write(request_id,role,emergency,'ATTEMPTED_UNKNOWN')
        try:
            async with asyncio.timeout(10):
                await self.hass.services.async_call(row['domain'],row['service'],
                    {'entity_id':self.config['entities'][role],
                     'value' if row['domain']=='number' else 'option':row['value']},blocking=True)
        except BaseException:
            await asyncio.shield(self.finish_write(request_id,role,emergency,'UNKNOWN'))
            raise
        await self.finish_write(request_id,role,emergency,'SERVICE_RETURNED')

    async def apply(self, request, power):
        if request['request_id'] not in self.prepared_writes:await self.prepare_apply(request,power)
        changes=self.prepared_writes.pop(request['request_id'])
        for row in changes:
            sample=await self.preflight(request)
            if power>sample['direction_limit_w'] or self.clock()>=request['expires_at']:
                raise ValueError('GUARD_CHANGED_DURING_COMPOUND_WRITE')
            await self._setting_service(request['request_id'],row,False)

    async def confirm_effect(self, request, power, *, after=None):
        # Non-blocking observation of a natural 120-second poll. No refresh/I/O.
        s = copy.deepcopy(self.sample)
        after = self.clock() if after is None else after
        if s is None or s['poll_completed_at'] - s['poll_window_bound_s'] <= after:
            return dict(pending_confirmation=True)
        s = await self.monitor_preflight(request)
        expected = {'Charge from Solar Power': 2, 'Charge from Solar Power and Grid': 3, 'Discharge to Minimize Import': 5}[request['option']]
        direction = 'charge' if request['option'] in CHARGES else 'discharge'
        tolerance = self.config.get('power_readback_tolerance_w', 0)
        if not finite(tolerance) or not 0 <= tolerance <= 500:
            return {}
        effect = (s['b1_w'] > 0 if direction == 'charge' else s['b1_w'] < 0) and abs(s['b1_w']) <= power + tolerance
        mode_ok = s['mode'] == expected and s[direction] == power and s['timeout'] == self.config['command_timeout_s']
        if direction == 'discharge' and s['m1_w'] > 0:
            effect = False
        return dict(request_id=request['request_id'], plan_id=request['plan_id'], owner_epoch=request['owner_epoch'],
                    observed_at=s['poll_completed_at'], physical_effect_confirmed=bool(effect and mode_ok),
                    b1_w=s['b1_w'], m1_w=s['m1_w'], ac_w=s['ac_w'],
                    poll_window_bound_s=s['poll_window_bound_s'], no_export_physically_proven=False)

    async def verify_stop_procedure(self, request_id):
        current = await self.owner_status()
        if current['trusted_owner'] != 'EMS2':
            raise ValueError('STOP_OWNER_NOT_EMS2')
        self.evidence('external_writer_fence')
        owner = self.hass.states.get(self.config['owner_entity'])
        if owner is None or owner.state != 'EMS2':
            raise ValueError('STOP_SHARED_OWNER_AMBIGUOUS')
        for entity in self.config.get('legacy_writers', []):
            state = self.hass.states.get(entity)
            if state is None or state.state != 'off' or state.attributes.get('current') != 0:
                raise ValueError('STOP_WRITER_CONFLICT')
        procedure = self.evidence('stop_procedure')
        if (procedure.get('method') != 'remote_to_local_self_consumption' or
                procedure.get('device_test_passed') is not True):
            raise ValueError('STOP_METHOD_NOT_VERIFIED')
        if self.write_retry_count() != 1:
            raise ValueError('INTEGRATION_WRITE_RETRIES_UNSAFE')
        # STOP revokes Remote authority; it must not wait for fresh telemetry.
        # Unknown transport result is latched; no automatic retry is permitted.
        self.check_bindings()

    async def request_local_mode(self, request_id):
        # Separate emergency batch bypasses economic rate/budget, never the
        # owner/fence/commissioned-procedure checks or durable one-shot reservation.
        await self.verify_stop_procedure(request_id)
        if self.reserve_writes is None:raise ValueError('DURABLE_SETTING_JOURNAL_REQUIRED')
        changes=self._changes([('select','select_option','mode','Maximize Self Consumption'),
                               ('select','select_option','control','Maximize Self Consumption')])
        await self.reserve_writes(request_id,changes,{},self.clock(),True)
        for row in changes:
            await self.verify_stop_procedure(request_id)
            await self._setting_service(request_id,row,True)
        self.stop_started[request_id]=self.clock()

    async def observe_local_authority(self, request_id, *, after=None):
        started = self.stop_started.get(request_id) if after is None else after
        if started is None:
            return dict(request_id=request_id, active_command_ended=False,
                        safe_local_mode_confirmed=False, reason='STOP_NOT_OBSERVED')
        # Poll cadence and duration are different. Exclude reads that may have
        # started before the last STOP write; constant HA states are not a clock.
        samples = [s for s in self.poll_history
                   if s['poll_completed_at'] - s['poll_window_bound_s'] > started]
        if len(samples) >= 2:
            a, b = samples[-2:]
            bound = self.config.get('max_poll_window_s', 0)
            valid = (self.coordinator.last_update_success is True and
                a['poll_completed_at'] < b['poll_completed_at'] and
                b['poll_completed_at'] - a['poll_completed_at'] <= 150 and
                0 <= self.clock() - b['poll_completed_at'] <= 180 and
                finite(bound) and 0 < bound <= 30 and
                all(s['control'] == 1 and s['mode'] == 7 and s['default'] == 7 and
                    s['inverter_status'] in (4, 5, 8) and s['bms_status'] in (1, 3, 4, 7) and
                    finite(s['poll_window_bound_s']) and 0 < s['poll_window_bound_s'] <= bound and
                    all(finite(s[k]) for k in ('b1_w', 'm1_w', 'soc')) and
                    not (s['b1_w'] < 0 and s['m1_w'] > 0) for s in (a, b)))
            if valid:
                return dict(request_id=request_id, active_command_ended=True,
                    safe_local_mode_confirmed=True, observed_at=b['poll_completed_at'],
                    basis='REMOTE_AUTHORITY_REVOKED_TWO_COMPLETE_POLLS',
                    timeout_expiry_confirmed=False, no_export_physically_proven=False, samples=[a, b])
        return dict(request_id=request_id, pending_confirmation=True,
                    active_command_ended=False, safe_local_mode_confirmed=False)

    async def confirm_termination(self, request_id, *, after=None):
        if self.termination_observer == self.observe_local_authority:
            return await self.observe_local_authority(request_id, after=after)
        if self.termination_observer is not None:
            return await self.termination_observer(request_id)
        return dict(request_id=request_id, active_command_ended=False,
                    safe_local_mode_confirmed=False, reason='DEVICE_TERMINATION_OBSERVER_UNAVAILABLE')
