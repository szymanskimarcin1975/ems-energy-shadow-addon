"""Read-only control readiness and per-device handover dry runs.

No HA service client or actuator. A local lease cannot fence external writers;
production takeover remains blocked until that external fence is implemented.
"""
import hashlib
import json
from statistics import median
from datetime import timedelta
from weather_demand import stamp, number


def channels(options):
    s = options['observation']['solar_sources']
    return {'ac': (s['ac_power'], 'W'), 'm1': (options['sources']['grid_kw'], 'kW'),
            'b1': (s['b1_power'], 'W'), 'soc': (s['b1_soc'], '%'),
            'status': (s['b1_status'], None)}


class Safety:
    def __init__(self, connection):
        self.c = connection
        self.c.executescript('''
            CREATE TABLE IF NOT EXISTS safety_metadata(key PRIMARY KEY,value);
            CREATE TABLE IF NOT EXISTS safety_samples(id PRIMARY KEY,captured,role,reported,record);
            CREATE TABLE IF NOT EXISTS safety_checks(id PRIMARY KEY,record);
        ''')

    def observe(self, states, at, options):
        roles = channels(options)
        digest = hashlib.sha256(json.dumps(roles, sort_keys=True).encode()).hexdigest()
        reasons, times, records = [], [], []
        values = {}
        for role, (entity, unit) in roles.items():
            raw = states.get(entity, {})
            row = {k: raw.get(k) for k in ('state', 'last_reported', 'last_updated', 'last_changed', 'timestamp_origin')}
            row.update(role=role, captured_at=at, device_measured_at=None)
            try:
                if unit is not None and raw.get('attributes', {}).get('unit_of_measurement') != unit:
                    raise ValueError('UNIT')
                if role == 'status':
                    if raw.get('state') not in ('B_STATUS_OFF', 'B_STATUS_STANDBY', 'B_STATUS_INIT', 'B_STATUS_CHARGE', 'B_STATUS_DISCHARGE', 'B_STATUS_FAULT', 'B_STATUS_PRESERVE_CHARGE', 'B_STATUS_IDLE'):
                        raise ValueError('STATUS')
                    if raw['state'] == 'B_STATUS_FAULT': reasons.append('FAULT_B1')
                else:
                    values[role] = number(raw['state'])
                    if role == 'soc' and not 0 <= values[role] <= 100: raise ValueError('RANGE')
            except (ValueError, KeyError, TypeError) as exc:
                reasons.append('VALUE_OR_UNIT_' + role.upper())
            try:
                t = stamp(raw['last_reported']); age = (stamp(at) - t).total_seconds()
                row['ha_age_seconds'] = age
                times.append(t)
                if age < 0: reasons.append('FUTURE_' + role.upper())
                elif age > 240: reasons.append('STALE_' + role.upper())
                row['reported'] = t.isoformat()
            except (ValueError, KeyError, TypeError):
                row['reported'] = None; reasons.append('TIMESTAMP_' + role.upper())
            records.append(row)
        skew = (max(times) - min(times)).total_seconds() if len(times) == len(roles) else None
        if skew is not None and skew > 2: reasons.append('HA_SET_SKEW')
        if values.get('b1', 0) > 0 and states.get(roles['status'][0], {}).get('state') == 'B_STATUS_DISCHARGE': reasons.append('B1_SIGN_STATUS_CONFLICT')
        if values.get('b1', 0) < 0 and states.get(roles['status'][0], {}).get('state') == 'B_STATUS_CHARGE': reasons.append('B1_SIGN_STATUS_CONFLICT')
        result = {'captured_at': at, 'valid_until': (stamp(at) + timedelta(seconds=45)).isoformat(),
                  'ha_set_valid': not reasons, 'reasons': sorted(set(reasons)), 'ha_skew_seconds': skew,
                  'device_synchronisation_confirmed': False, 'control_enabled': False,
                  'timestamp_semantics': 'HA_STATE_MACHINE_NOT_DEVICE_MEASUREMENT'}
        self.c.execute('BEGIN IMMEDIATE')
        try:
            old = self.c.execute("SELECT value FROM safety_metadata WHERE key='sources'").fetchone()
            if old and old[0] != digest: raise ValueError('separate_safety_ledger_required')
            self.c.execute("INSERT OR IGNORE INTO safety_metadata VALUES('sources',?)", (digest,))
            if self.c.execute('SELECT 1 FROM safety_checks WHERE id=?', (at,)).fetchone():
                self.c.execute('ROLLBACK'); return 'duplicate_capture'
            for row in records:
                if row['reported'] is None: continue
                key = hashlib.sha256((digest + row['role'] + row['reported']).encode()).hexdigest()
                existing = self.c.execute('SELECT record FROM safety_samples WHERE id=?', (key,)).fetchone()
                if existing and json.loads(existing[0])['state'] != row['state']:
                    result['reasons'].append('SAME_TIMESTAMP_CHANGED_VALUE_' + row['role'].upper())
                    result['ha_set_valid'] = False
                elif not existing:
                    latest = self.c.execute('SELECT reported FROM safety_samples WHERE role=? ORDER BY reported DESC LIMIT 1', (row['role'],)).fetchone()
                    if latest and stamp(row['reported']) < stamp(latest[0]):
                        result['reasons'].append('OUT_OF_ORDER_' + row['role'].upper()); result['ha_set_valid'] = False
                    self.c.execute('INSERT INTO safety_samples VALUES(?,?,?,?,?)', (key, at, row['role'], row['reported'], json.dumps(row, allow_nan=False)))
            self.c.execute('INSERT INTO safety_checks VALUES(?,?)', (at, json.dumps(result, allow_nan=False)))
            self.c.execute('COMMIT')
        except Exception:
            if self.c.in_transaction: self.c.execute('ROLLBACK')
            raise
        return result

    def summary(self, at):
        since = (stamp(at) - timedelta(minutes=30)).isoformat()
        reports = [json.loads(r[0]) for r in self.c.execute('SELECT record FROM safety_checks WHERE id>=? AND id<=? ORDER BY id', (since, at))]
        intervals = {}
        for role in ('ac', 'm1', 'b1', 'soc', 'status'):
            rows = self.c.execute('SELECT reported FROM safety_samples WHERE captured>=? AND captured<=? AND role=? ORDER BY reported', (since, at, role)).fetchall()
            delta = [(stamp(b[0]) - stamp(a[0])).total_seconds() for a, b in zip(rows, rows[1:])]
            delta = [v for v in delta if v > 0]
            intervals[role] = {'distinct_ha_reports': len(rows), 'intervals': len(delta),
                               'min_median_max_seconds': [min(delta), median(delta), max(delta)] if delta else None,
                               'device_cycle_confirmed': False}
        reasons = {}
        for r in reports:
            for reason in set(r['reasons']): reasons[reason] = reasons.get(reason, 0) + 1
        last = reports[-1] if reports else None
        fresh = bool(last and 0 <= (stamp(at) - stamp(last['captured_at'])).total_seconds() <= 45)
        return {'generated_at': at, 'last': last, 'current_ha_set_valid': bool(fresh and last['ha_set_valid']),
                'checks_30m': len(reports), 'valid_checks_30m': sum(r['ha_set_valid'] for r in reports),
                'rejection_reasons_30m': reasons, 'ha_reporting_intervals': intervals,
                'real_device_reporting_coverage': None, 'control_enabled': False,
                'external_writer_fence_installed': False,
                'handover_status': 'BLOCKED_NO_EXTERNAL_WRITER_FENCE'}


class HandoverDryRun:
    """Transaction/replay tests only; cannot activate production control."""
    def __init__(self, c):
        self.c = c
        c.executescript('CREATE TABLE IF NOT EXISTS dry_leases(device PRIMARY KEY,owner,request_id UNIQUE);CREATE TABLE IF NOT EXISTS dry_audit(request_id PRIMARY KEY,device,action);')

    def take(self, device, request_id, legacy_states, gates_ok=False, quiescent=False):
        if device not in ('battery', 'cwu'): raise ValueError('unsupported_device')
        if not isinstance(request_id,str) or not request_id or len(request_id) > 80: raise ValueError('invalid_request')
        if not gates_ok or not quiescent or not legacy_states or any(s != 'off' for s in legacy_states): return 'BLOCKED'
        self.c.execute('BEGIN IMMEDIATE')
        try:
            old = self.c.execute('SELECT device,action FROM dry_audit WHERE request_id=?', (request_id,)).fetchone()
            if old:
                if old != (device, 'TAKE'): raise ValueError('request_conflict')
                self.c.execute('ROLLBACK'); return 'ALREADY_COMMITTED'
            if self.c.execute('SELECT 1 FROM dry_leases WHERE device=?', (device,)).fetchone():
                self.c.execute('ROLLBACK'); return 'BUSY'
            self.c.execute('INSERT INTO dry_leases VALUES(?,?,?)', (device, 'SIMULATED_EMS', request_id))
            self.c.execute('INSERT INTO dry_audit VALUES(?,?,?)', (request_id, device, 'TAKE'))
            self.c.execute('COMMIT'); return 'SIMULATED_ONLY'
        except Exception:
            if self.c.in_transaction: self.c.execute('ROLLBACK')
            raise

    def give_back(self, device, request_id):
        if device not in ('battery', 'cwu'): raise ValueError('unsupported_device')
        if not isinstance(request_id,str) or not request_id or len(request_id)>80: raise ValueError('invalid_request')
        self.c.execute('BEGIN IMMEDIATE')
        try:
            old = self.c.execute('SELECT device,action FROM dry_audit WHERE request_id=?', (request_id,)).fetchone()
            if old and old != (device, 'RETURN'): raise ValueError('request_conflict')
            if not old:
                self.c.execute('DELETE FROM dry_leases WHERE device=?', (device,))
                self.c.execute('INSERT INTO dry_audit VALUES(?,?,?)', (request_id, device, 'RETURN'))
            self.c.execute('COMMIT'); return 'LEGACY_RESTORE_MUST_BE_VERIFIED_SEPARATELY'
        except Exception:
            if self.c.in_transaction: self.c.execute('ROLLBACK')
            raise
