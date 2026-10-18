"""Review candidate: serial, durable device adapter orchestration.

Disabled by default. A HA service ACK is never physical execution/termination.
The adapter must supply independently verified installation evidence and actual
Modbus poll provenance. Request data cannot grant itself safety authority.
"""
import asyncio
import math
import time
from .gate_store import CONTRACT, validate

CHARGES = {'Charge from Solar Power', 'Charge from Solar Power and Grid'}


def finite(v):
    return type(v) in (int, float) and math.isfinite(v)


def direction_guard(option, soc, minimum=5, maximum=95):
    if not all(finite(v) for v in (soc, minimum, maximum)) or not 0 <= minimum < maximum <= 100 or not 0 <= soc <= 100:
        return 'SOC_INVALID'
    if option in CHARGES and soc >= maximum:
        return 'SOC_CEILING'
    if option == 'Discharge to Minimize Import' and soc <= minimum:
        return 'SOC_RESERVE'
    return None  # Above ceiling: HOLD/discharge; below reserve: HOLD/charge.


class ActuationGateway:
    def __init__(self, store, adapter, run_db, clock=time.time):
        self.store, self.adapter, self.run_db, self.clock = store, adapter, run_db, clock
        self.lock = asyncio.Lock()
        if hasattr(adapter, 'bind_write_journal'):
            adapter.bind_write_journal(
                lambda *args:self.run_db(store.reserve_setting_batch,*args),
                lambda *args:self.run_db(store.finish_setting_write,*args))

    async def transition(self, expected_epoch, target, reference):
        # Same lock as dispatch and STOP. DB CAS also excludes a second process.
        async with self.lock:
            await self.adapter.verify_handover(target)
            epoch = await self.run_db(self.store.transition_owner, expected_epoch, target, reference)
            # HA helper is informational; never authority. No automatic legacy restart.
            return dict(owner=target, owner_epoch=epoch, legacy_resumed=False)

    async def dispatch(self, raw):
        if not isinstance(raw, dict):
            raw = {}
        if raw.get('execution_mode', 'READ_ONLY') == 'READ_ONLY':
            return await self.run_db(self.store.dispatch_rejected, raw)
        if raw.get('execution_mode') != 'ACTIVE':
            return dict(status='REJECTED', reason='INVALID_EXECUTION_MODE', writes_started=False,
                        device_execution_confirmed=False, physical_dispatch_supported=False)
        reason, request = validate(raw, self.clock())
        if request is not None:
            request['execution_mode'] = 'ACTIVE'
        reply = dict(gateway_contract=CONTRACT, status='REJECTED', reason=reason,
                     writes_started=False, device_execution_confirmed=False,
                     physical_dispatch_supported=False, request_id=raw.get('request_id', ''),
                     plan_id=raw.get('plan_id', ''), owner_epoch=raw.get('owner_epoch', -1))
        if request is None:
            return reply
        async with self.lock:
            reserved = False
            started = False
            try:
                await self.adapter.preflight(request)
                if self.clock() >= request['expires_at']:
                    raise ValueError('REQUEST_EXPIRED')
                outcome = await self.run_db(self.store.reserve_control, request)
                if outcome != 'RESERVED':
                    reply.update(reason=outcome)
                    if outcome in ('UNKNOWN_NO_REPLAY', 'REQUEST_ID_CONFLICT', 'ACTIVE_OR_UNKNOWN_COMMAND'):
                        reply.update(status='UNKNOWN', writes_started=None)
                    return reply
                reserved = True
                # Repeat the guards after DB reservation and immediately before transport.
                sample = await self.adapter.preflight(request)
                cap = min(request['power_w'], sample['direction_limit_w'], 5000)
                power = math.floor(cap)
                if power <= 0:
                    raise ValueError('BMS_DIRECTION_LIMIT_ZERO')
                if self.clock() >= request['expires_at']:
                    raise ValueError('REQUEST_EXPIRED')
                if hasattr(self.adapter, 'prepare_apply'):
                    await self.adapter.prepare_apply(request, power)
                await self.run_db(self.store.record, request['request_id'], 'SENDING', True, dict(reply, request=request))
                started = True  # Conservative: the next await may have partially written.
                await self.adapter.apply(request, power)
                completed = self.clock()
                if getattr(self.adapter, 'deferred_confirmation', False):
                    # Admission expires_at only admits a write. Ongoing control is
                    # bounded independently by the validated plan and device timeout.
                    plan_until = sample.get('plan_valid_until', request['expires_at'])
                    if not finite(plan_until):
                        raise ValueError('PLAN_LEASE_UNCONFIRMED')
                    active_until = min(plan_until, completed + self.adapter.config['command_timeout_s'])
                    reply.update(status='WAITING_CONFIRMATION', reason='AWAITING_NATURAL_MODBUS_POLL',
                        writes_started=True, physical_dispatch_supported=True, device_execution_confirmed=False,
                        owner='EMS2', option=request['option'], applied_power_w=power, request=request,
                        writes_completed_at=completed, confirmation_deadline=completed+270,
                        active_until=active_until, device_until=completed+self.adapter.config['command_timeout_s'], automatic_retry=False)
                    await self.run_db(self.store.record, request['request_id'], 'WAITING_EFFECT', True, reply)
                    return reply
                evidence = await self.adapter.confirm_effect(request, power)
                # Fresh physical evidence must be request-correlated, not just a select state.
                confirmed = (evidence.get('request_id') == request['request_id'] and
                             evidence.get('plan_id') == request['plan_id'] and
                             evidence.get('owner_epoch') == request['owner_epoch'] and
                             evidence.get('physical_effect_confirmed') is True and
                             finite(evidence.get('observed_at')) and
                             sample['poll_completed_at'] < evidence['observed_at'] <= self.clock() and
                             self.clock() < request['expires_at'])
                await self.adapter.preflight(request)
                owner = await self.run_db(self.store.control_status)
                confirmed = confirmed and owner['trusted_owner'] == 'EMS2' and owner['trusted_epoch'] == request['owner_epoch'] and owner['physical_authorized'] and not owner['emergency_stop']['latched']
                reply.update(status='SERVICE_COMPLETED' if confirmed else 'UNKNOWN',
                             reason='PHYSICAL_EFFECT_CONFIRMED' if confirmed else 'DEVICE_EFFECT_UNCONFIRMED',
                             writes_started=True, physical_dispatch_supported=True,
                             device_execution_confirmed=confirmed, owner='EMS2',
                             option=request['option'], applied_power_w=power, evidence=evidence, request=request)
                await self.run_db(self.store.record, request['request_id'], 'ACK_ACTIVE' if confirmed else 'UNKNOWN', True, reply)
            except BaseException as exc:
                # Cancellation is an unknown outcome once any write may have started.
                reply.update(request=request, status='UNKNOWN' if started else 'REJECTED',
                             reason='ACTUATION_OUTCOME_UNKNOWN' if started else (str(exc) if isinstance(exc, ValueError) else 'PREFLIGHT_UNCONFIRMED'),
                             writes_started=started, physical_dispatch_supported=started)
                if reserved:
                    await asyncio.shield(self.run_db(self.store.record, request['request_id'], 'UNKNOWN' if started else 'REJECTED', started, reply))
                if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                    raise
            return reply

    async def stop(self, request_id):
        """Separate, one-shot stop attempt, never HOLD and never automatic LEGACY."""
        async with self.lock:
            current = await self.run_db(self.store.active, request_id)
            if current is None or current['state'] not in ('ACK_ACTIVE', 'WAITING_EFFECT', 'WAITING_STOP', 'UNKNOWN'):
                return dict(status='STOP_NOT_CONFIRMED', active_command_canceled=False)
            if current['state'] == 'WAITING_STOP':
                return await self._observe_stop(request_id, current)
            # Persist attempt before transport: a timeout/restart may never repeat it.
            if current['result'].get('stop_attempted'):
                return dict(status='UNKNOWN_ACTIVE_COMMAND', active_command_canceled=False, automatic_retry=False)
            claimed = await self.run_db(self.store.reserve_stop, request_id)
            if claimed is None:
                return dict(status='UNKNOWN_ACTIVE_COMMAND', active_command_canceled=False, automatic_retry=False)
            result = dict(claimed['result'])
            try:
                await self.adapter.verify_stop_procedure(request_id)
                await self.adapter.request_local_mode(request_id)
                if getattr(self.adapter, 'deferred_confirmation', False):
                    completed = self.clock()
                    result.update(status='WAITING_STOP', stop_writes_completed_at=completed,
                                  stop_confirmation_deadline=completed+390, request_id=request_id)
                    await self.run_db(self.store.record, request_id, 'WAITING_STOP', current['writes_started'], result)
                    return dict(status='WAITING_STOP', active_command_canceled=False, automatic_retry=False)
                evidence = await self.adapter.confirm_termination(request_id)
                if (evidence.get('request_id') != request_id or
                        evidence.get('active_command_ended') is not True or
                        evidence.get('safe_local_mode_confirmed') is not True or
                        not finite(evidence.get('observed_at')) or
                        not 0 <= self.clock() - evidence['observed_at'] <= 30):
                    raise ValueError('TERMINATION_NOT_CONFIRMED')
                result.update(status='ENDED', termination_evidence=evidence)
                await self.run_db(self.store.record, request_id, 'ENDED', current['writes_started'], result)
                return dict(status='ENDED', active_command_canceled=True, legacy_resumed=False)
            except Exception as exc:
                result.update(status='UNKNOWN_ACTIVE_COMMAND', stop_reason=
                    str(exc) if isinstance(exc, ValueError) else 'STOP_TRANSPORT_OR_OBSERVER_UNKNOWN')
                await self.run_db(self.store.record, request_id, 'UNKNOWN', current['writes_started'], result)
                return dict(status='UNKNOWN_ACTIVE_COMMAND', active_command_canceled=False, automatic_retry=False, legacy_resumed=False)

    async def command_status(self, request_id):
        """Read only. Querying an outcome cannot issue or repeat a command."""
        row = await self.run_db(self.store.active, request_id)
        if row is None:
            return dict(gateway_contract=CONTRACT, request_id=request_id, status='NOT_FOUND', automatic_retry=False)
        result = dict(row['result'])
        result.update(gateway_contract=CONTRACT, request_id=request_id,
                      command_state=row['state'], automatic_retry=False)
        if row['state'] == 'UNKNOWN':
            result.update(status='UNKNOWN', device_execution_confirmed=False)
        return result

    async def _observe_stop(self, request_id, current):
        result = dict(current['result'])
        if self.clock() >= result['stop_confirmation_deadline']:
            result.update(status='UNKNOWN_ACTIVE_COMMAND', stop_reason='STOP_CONFIRMATION_TIMEOUT')
            await self.run_db(self.store.record, request_id, 'UNKNOWN', current['writes_started'], result, 'WAITING_STOP')
            return dict(status='UNKNOWN_ACTIVE_COMMAND', active_command_canceled=False, automatic_retry=False)
        evidence = await self.adapter.confirm_termination(request_id, after=result['stop_writes_completed_at'])
        if (evidence.get('request_id') == request_id and evidence.get('active_command_ended') is True and
                evidence.get('safe_local_mode_confirmed') is True and finite(evidence.get('observed_at')) and
                result['stop_writes_completed_at'] < evidence['observed_at'] <= self.clock() and
                self.clock()-evidence['observed_at'] <= 180):
            result.update(status='ENDED', termination_evidence=evidence)
            await self.run_db(self.store.record, request_id, 'ENDED', current['writes_started'], result, 'WAITING_STOP')
            return dict(status='ENDED', active_command_canceled=True, legacy_resumed=False)
        return dict(status='WAITING_STOP', active_command_canceled=False, automatic_retry=False)

    async def monitor_once(self):
        """Advance durable waiting states using natural polls, never a new dispatch."""
        stop_id = None
        async with self.lock:
            request_id = await self.run_db(self.store.current_request)
            if request_id is None:
                return
            state = await self.run_db(self.store.active, request_id)
            if state['state'] == 'WAITING_STOP':
                await self._observe_stop(request_id, state)
                return
            try:
                result = dict(state['result'])
                if state['state'] not in ('ACK_ACTIVE', 'WAITING_EFFECT'):
                    raise ValueError('UNKNOWN_ACTIVE_COMMAND')
                request = result['request']
                if self.clock() >= result.get('active_until', request['expires_at']):
                    raise ValueError('ACTIVE_PLAN_OR_DEVICE_LEASE_EXPIRED')
                if getattr(self.adapter, 'deferred_confirmation', False):
                    sample = await self.adapter.monitor_preflight(request)
                    if result['applied_power_w'] > sample['direction_limit_w']:
                        raise ValueError('ACTIVE_POWER_EXCEEDS_CURRENT_BMS_OR_IMPORT_HEADROOM')
                    lease = sample.get('plan_valid_until')
                    if finite(lease):
                        updated_until = min(lease, result['device_until'])
                        if updated_until <= self.clock():
                            raise ValueError('CURRENT_PLAN_EXPIRED')
                        if updated_until != result['active_until']:
                            result['active_until'] = updated_until
                            await self.run_db(self.store.record, request_id, state['state'], True, result, state['state'])
                    if state['state'] == 'WAITING_EFFECT':
                        if self.clock() >= result['confirmation_deadline']:
                            raise ValueError('EFFECT_CONFIRMATION_TIMEOUT')
                        evidence = await self.adapter.confirm_effect(request, result['applied_power_w'],
                                                                    after=result['writes_completed_at'])
                        if evidence.get('pending_confirmation') is True:
                            return
                        if not (evidence.get('request_id') == request_id and
                                evidence.get('plan_id') == request['plan_id'] and
                                evidence.get('owner_epoch') == request['owner_epoch'] and
                                evidence.get('physical_effect_confirmed') is True and
                                finite(evidence.get('observed_at')) and
                                result['writes_completed_at'] < evidence['observed_at'] <= self.clock()):
                            raise ValueError('DEVICE_EFFECT_UNCONFIRMED')
                        result.update(status='SERVICE_COMPLETED', reason='PHYSICAL_EFFECT_CONFIRMED',
                                      device_execution_confirmed=True, evidence=evidence)
                        await self.run_db(self.store.record, request_id, 'ACK_ACTIVE', True, result, 'WAITING_EFFECT')
                else:
                    await self.adapter.preflight(request)
            except Exception as exc:
                status = await self.run_db(self.store.control_status)
                if not status['emergency_stop']['latched']:
                    await self.run_db(self.store.trip_emergency_stop, 'ACTIVE_COMMAND_SAFETY_LOST',
                        request_id, status['trusted_epoch'], {'reason':str(exc) if isinstance(exc,ValueError) else 'MONITOR_UNKNOWN'})
                stop_id = request_id
        # STOP has its own same-instance lock and cross-process SQLite reservation.
        if stop_id is not None:
            await self.stop(stop_id)
