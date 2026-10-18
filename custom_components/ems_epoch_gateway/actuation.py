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
                await self.run_db(self.store.record, request['request_id'], 'SENDING', True, {})
                started = True  # Conservative: the next await may have partially written.
                await self.adapter.apply(request, power)
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
            if current is None or current['state'] not in ('ACK_ACTIVE', 'UNKNOWN'):
                return dict(status='STOP_NOT_CONFIRMED', active_command_canceled=False)
            # Persist attempt before transport: a timeout/restart may never repeat it.
            if current['result'].get('stop_attempted'):
                return dict(status='UNKNOWN_ACTIVE_COMMAND', active_command_canceled=False, automatic_retry=False)
            result = dict(current['result'], stop_attempted=True)
            await self.run_db(self.store.record, request_id, 'UNKNOWN', current['writes_started'], result)
            try:
                await self.adapter.verify_stop_procedure(request_id)
                await self.adapter.request_local_mode(request_id)
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

    async def monitor_once(self):
        """Monitor only this gateway's active command; never interfere with LEGACY."""
        request_id = await self.run_db(self.store.current_request)
        if request_id is None:
            return
        state = await self.run_db(self.store.active, request_id)
        try:
            if state['state'] != 'ACK_ACTIVE':
                raise ValueError('UNKNOWN_ACTIVE_COMMAND')
            request = state['result']['request']
            if self.clock() >= request['expires_at']:
                raise ValueError('ACTIVE_PLAN_EXPIRED')
            await self.adapter.preflight(request)
        except Exception:
            status = await self.run_db(self.store.control_status)
            if not status['emergency_stop']['latched']:
                await self.run_db(self.store.trip_emergency_stop, 'ACTIVE_COMMAND_SAFETY_LOST', request_id, status['trusted_epoch'], {})
            await self.stop(request_id)
