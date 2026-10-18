"""Candidate actuator journal. Shares trusted_owner with the SHADOW gateway.

No transport here. Reservations and owner transitions serialize across processes.
Opening this store never authorizes physical writes or resumes after a restart.
"""
from contextlib import closing
import json
import sqlite3
import time
from .gate_store import EpochStore, request_hash


class ControlStore(EpochStore):
    @staticmethod
    def _owner(db):
        return ControlStore.control_owner(db)[:2]

    def initialize(self):
        with closing(self._connect()) as db:
            db.execute('CREATE TABLE IF NOT EXISTS control_owner_events(epoch INTEGER PRIMARY KEY,owner TEXT NOT NULL,previous_owner TEXT NOT NULL,at REAL NOT NULL,reference TEXT NOT NULL)')
        super().initialize()
        self.initialize_control()

    def initialize_control(self):
        with closing(self._connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS control_owner_events(epoch INTEGER PRIMARY KEY,owner TEXT NOT NULL,previous_owner TEXT NOT NULL,at REAL NOT NULL,reference TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS control_commands(request_id TEXT PRIMARY KEY,payload_sha256 TEXT NOT NULL,owner_epoch INTEGER NOT NULL,state TEXT NOT NULL,writes_started INTEGER NOT NULL,result TEXT NOT NULL,updated_at REAL NOT NULL)')
            # A process that disappeared between reservation and completion cannot replay.
            db.execute("UPDATE control_commands SET state='UNKNOWN' WHERE state IN ('RESERVED','SENDING','WAITING_EFFECT','WAITING_STOP')")
            db.execute('UPDATE trusted_owner SET physical_enabled=0 WHERE id=1')
            self.control_owner(db)
            db.commit()

    @staticmethod
    def control_owner(db):
        rows = db.execute('SELECT owner,epoch,physical_enabled FROM trusted_owner WHERE id=1').fetchall()
        if len(rows) != 1:
            raise ValueError('OWNER_INTEGRITY_UNKNOWN')
        owner, epoch, enabled = rows[0]
        if owner not in ('LEGACY', 'EMS2') or type(epoch) is not int or epoch < 0 or enabled not in (0, 1):
            raise ValueError('OWNER_INTEGRITY_UNKNOWN')
        if (owner, epoch, enabled) == ('LEGACY', 0, 0):
            return rows[0]
        event = db.execute('SELECT owner FROM control_owner_events WHERE epoch=?', (epoch,)).fetchone()
        if event != (owner,) or (owner == 'LEGACY' and enabled):
            raise ValueError('OWNER_AUDIT_MISMATCH')
        return rows[0]

    def control_status(self):
        with closing(self._connect()) as db:
            db.execute('BEGIN')
            owner, epoch, enabled = self.control_owner(db)
            unresolved = db.execute("SELECT COUNT(*) FROM control_commands WHERE state NOT IN ('REJECTED','ENDED')").fetchone()[0]
            stop = self._emergency_status(db)
            db.commit()
        return dict(trusted_owner=owner, trusted_epoch=epoch, physical_authorized=bool(enabled),
                    unresolved_requests=unresolved, emergency_stop=stop,
                    automatic_resume=False, physical_dispatch_supported=bool(enabled),
                    status="AUTHORIZED_PENDING_PREFLIGHT" if enabled else "BLOCKED_SAFE",
                    physical_adapter_implemented=True)

    def transition_owner(self, expected_epoch, target, reference):
        if type(expected_epoch) is not int or target not in ('LEGACY', 'EMS2') or not isinstance(reference, str) or not reference.strip():
            raise ValueError('INVALID_TRANSITION')
        with closing(self._connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            owner, epoch, _ = self.control_owner(db)
            if epoch != expected_epoch:
                raise ValueError('OWNER_EPOCH_CHANGED')
            if db.execute("SELECT 1 FROM control_commands WHERE state NOT IN ('REJECTED','ENDED')").fetchone():
                raise ValueError('ACTIVE_OR_UNKNOWN_COMMAND')
            if db.execute("SELECT 1 FROM requests WHERE state IN ('PENDING','UNKNOWN')").fetchone():
                raise ValueError('SHADOW_REQUEST_UNRESOLVED')
            if target == 'EMS2' and self._emergency_status(db)['latched']:
                raise ValueError('EMERGENCY_STOP_LATCHED')
            epoch += 1
            db.execute('INSERT INTO control_owner_events VALUES(?,?,?,?,?)', (epoch, target, owner, time.time(), reference))
            db.execute('UPDATE trusted_owner SET owner=?,epoch=?,physical_enabled=? WHERE id=1', (target, epoch, int(target == 'EMS2')))
            db.commit()
        return epoch

    def reserve_control(self, request):
        with closing(self._connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            owner, epoch, enabled = self.control_owner(db)
            row = db.execute('SELECT payload_sha256,state,writes_started FROM control_commands WHERE request_id=?', (request['request_id'],)).fetchone()
            if row:
                if row[0] != request_hash(request):
                    return 'REQUEST_ID_CONFLICT'
                return 'DUPLICATE_REJECTED' if row[1] == 'REJECTED' else 'UNKNOWN_NO_REPLAY'
            if db.execute('SELECT 1 FROM requests WHERE request_id=?', (request['request_id'],)).fetchone():
                return 'SHADOW_ID_ALREADY_RESERVED'
            if owner != 'EMS2' or not enabled or epoch != request['owner_epoch']:
                return 'OWNER_OR_EPOCH_NOT_AUTHORIZED'
            if self._emergency_status(db)['latched']:
                return 'EMERGENCY_STOP_LATCHED'
            if db.execute("SELECT 1 FROM control_commands WHERE state NOT IN ('REJECTED','ENDED')").fetchone():
                return 'ACTIVE_OR_UNKNOWN_COMMAND'
            db.execute('INSERT INTO control_commands VALUES(?,?,?,\'RESERVED\',0,\'{}\',?)',
                       (request['request_id'], request_hash(request), epoch, time.time()))
            db.commit()
        return 'RESERVED'

    def record(self, request_id, state, started, result, expected_state=None):
        if state not in ('SENDING', 'WAITING_EFFECT', 'WAITING_STOP', 'ACK_ACTIVE', 'UNKNOWN', 'REJECTED', 'ENDED'):
            raise ValueError('INVALID_COMMAND_STATE')
        payload = json.dumps(result, allow_nan=False, sort_keys=True)
        with closing(self._connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT state,writes_started,result FROM control_commands WHERE request_id=?', (request_id,)).fetchone()
            if row is None or row[0] in ('REJECTED', 'ENDED'):
                raise ValueError('REQUEST_NOT_ACTIVE')
            if expected_state is not None and row[0] != expected_state:
                raise ValueError('COMMAND_STATE_CHANGED')
            if json.loads(row[2]).get('stop_attempted') and not result.get('stop_attempted'):
                raise ValueError('STOP_ALREADY_RESERVED')
            if state == 'REJECTED' and (started or row[1]):
                raise ValueError('CANNOT_REJECT_AFTER_WRITE')
            db.execute('UPDATE control_commands SET state=?,writes_started=?,result=?,updated_at=? WHERE request_id=?',
                       (state, int(started or row[1]), payload, time.time(), request_id))
            db.commit()

    def reserve_stop(self, request_id):
        """Cross-process one-shot STOP claim, committed before any transport."""
        with closing(self._connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT state,writes_started,result FROM control_commands WHERE request_id=?', (request_id,)).fetchone()
            if row is None or row[0] not in ('ACK_ACTIVE', 'WAITING_EFFECT', 'UNKNOWN'):
                return None
            result = json.loads(row[2])
            if result.get('stop_attempted'):
                return None
            result['stop_attempted'] = True
            db.execute("UPDATE control_commands SET state='UNKNOWN',result=?,updated_at=? WHERE request_id=?",
                       (json.dumps(result, allow_nan=False, sort_keys=True), time.time(), request_id))
            db.commit()
            return dict(state='UNKNOWN', writes_started=bool(row[1]), result=result)

    def active(self, request_id):
        with closing(self._connect()) as db:
            row = db.execute('SELECT state,writes_started,result FROM control_commands WHERE request_id=?', (request_id,)).fetchone()
        return None if row is None else dict(state=row[0], writes_started=bool(row[1]), result=json.loads(row[2]))

    def current_request(self):
        with closing(self._connect()) as db:
            rows = db.execute("SELECT request_id FROM control_commands WHERE state NOT IN ('REJECTED','ENDED')").fetchall()
        if len(rows) > 1:
            raise ValueError('MULTIPLE_ACTIVE_REQUESTS')
        return rows[0][0] if rows else None
