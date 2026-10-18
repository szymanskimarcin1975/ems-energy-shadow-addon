"""Durable, fail-closed HA-side owner epoch and request journal.

No hardware dispatch exists in this module. HA helpers are NOT trusted
ownership evidence. A committed PENDING reservation is never replayed.
"""
from __future__ import annotations

import hashlib
from contextlib import closing
import json
import math
import re
import sqlite3
import time
from pathlib import Path

CONTRACT = "EMS2_COMPOUND_V28"
OPTIONS = {
    "Charge from Solar Power",
    "Charge from Solar Power and Grid",
    "Discharge to Minimize Import",
}
REQUEST_RE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
PLAN_RE = re.compile(r"[a-f0-9]{64}\Z")


def validate(request: dict, now: float | None = None) -> tuple[str, dict | None]:
    """Normalize and bind all safety-relevant fields before DB reservation."""
    if not isinstance(request, dict):
        return "INVALID_REQUEST", None
    now = time.time() if now is None else now
    try:
        if request.get("caller") != "EMS2" or request.get("operation") != "dispatch":
            return "INVALID_CALLER_OR_OPERATION", None
        request_id, plan_id = request["request_id"], request["plan_id"]
        owner_epoch, option = request["owner_epoch"], request["option"]
        power_w, expires_at = request["power_w"], request["expires_at"]
        if not isinstance(request_id, str) or not REQUEST_RE.fullmatch(request_id):
            return "INVALID_REQUEST_ID", None
        if not isinstance(plan_id, str) or not PLAN_RE.fullmatch(plan_id):
            return "INVALID_PLAN_ID", None
        if type(owner_epoch) is not int or owner_epoch < 0:
            return "INVALID_OWNER_EPOCH", None
        if option not in OPTIONS:
            return "INVALID_COMMAND_MODE", None
        if type(power_w) not in (int, float) or not math.isfinite(power_w) or not 0 < power_w <= 5000:
            return "INVALID_POWER", None
        if type(expires_at) not in (int, float) or not math.isfinite(expires_at) or not now < expires_at <= now + 60:
            return "EXPIRED_OR_INVALID_DEADLINE", None
    except (KeyError, TypeError, ValueError):
        return "INVALID_REQUEST", None
    normalized = {
        "caller": "EMS2", "operation": "dispatch", "request_id": request_id,
        "plan_id": plan_id, "owner_epoch": owner_epoch, "option": option,
        "power_w": float(power_w), "expires_at": float(expires_at),
    }
    return "VALID", normalized


def request_hash(normalized: dict) -> str:
    """Stable identity including expiry (no silent request mutation)."""
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class EpochStore:
    """Each operation has its own SQLite connection and IMMEDIATE transaction.

    Concurrency across multiple HA worker threads/processes is serialized by SQLite.
    Do not place this DB on NFS. No method enables physical dispatch or changes owner.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=3, isolation_level=None)
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA busy_timeout=3000")
        return db

    @staticmethod
    def _owner(db) -> tuple[str, int]:
        rows = db.execute("SELECT owner,epoch,physical_enabled FROM trusted_owner WHERE id=1").fetchall()
        if len(rows) != 1 or rows[0] != ("LEGACY", 0, 0):
            raise ValueError("TRUSTED_OWNER_INTEGRITY_UNCONFIRMED")
        # v1 has no handover transition operation; any mutation fails closed.
        return rows[0][:2]

    def initialize(self):
        with closing(self._connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS trusted_owner(
                id INTEGER PRIMARY KEY CHECK(id=1),
                owner TEXT NOT NULL,epoch INTEGER NOT NULL,
                physical_enabled INTEGER NOT NULL CHECK(physical_enabled IN (0,1))
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS requests(
                request_id TEXT PRIMARY KEY,
                payload_sha256 TEXT NOT NULL,
                owner_epoch INTEGER NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('PENDING','UNKNOWN','REJECTED')),
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS emergency_latch(
                id INTEGER PRIMARY KEY CHECK(id=1),
                latched INTEGER NOT NULL CHECK(latched IN (0,1)),
                first_event_id INTEGER,
                last_event_id INTEGER
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS emergency_events(
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                reason TEXT NOT NULL,
                request_id TEXT,
                owner_epoch INTEGER,
                created_at REAL NOT NULL,
                evidence_json TEXT NOT NULL
            )""")
            db.execute("INSERT OR IGNORE INTO emergency_latch VALUES(1,0,NULL,NULL)")
            db.execute("INSERT OR IGNORE INTO trusted_owner VALUES(1,'LEGACY',0,0)")
            self._owner(db)
            db.commit()

    def status(self) -> dict:
        try:
            with closing(self._connect()) as db:
                db.execute("BEGIN")
                owner, epoch = self._owner(db)
                pending = db.execute("SELECT COUNT(*) FROM requests WHERE state IN ('PENDING','UNKNOWN')").fetchone()[0]
                db.commit()
            emergency = self._emergency_status(db)
            return {
                "status": "EMERGENCY_STOP_LATCHED" if emergency["latched"] else "BLOCKED_SAFE",
                "emergency_stop": emergency,
                "trusted_owner": owner, "trusted_epoch": epoch,
                "unresolved_requests": pending,
                "durable_request_journal": True,
                "trusted_epoch_transition_implemented": False,
                "external_writer_fence_verified": False,
                "physical_dispatch_supported": False,
                "writes_started": False,
            }
        except (sqlite3.Error, ValueError, OSError):
            return {
                "status": "GATE_INTEGRITY_UNKNOWN", "trusted_owner": "UNKNOWN",
                "trusted_epoch": -1, "durable_request_journal": False,
                "physical_dispatch_supported": False, "writes_started": False,
            }

    @staticmethod
    def _emergency_status(db) -> dict:
        row = db.execute("SELECT latched,first_event_id,last_event_id FROM emergency_latch WHERE id=1").fetchone()
        if row is None:
            raise ValueError("EMERGENCY_LATCH_MISSING")
        last = None
        count = 0
        if row[2] is not None:
            last = db.execute("SELECT reason,request_id,owner_epoch,created_at FROM emergency_events WHERE event_id=?",
                              (row[2],)).fetchone()
            count = db.execute("SELECT COUNT(*) FROM emergency_events").fetchone()[0]
        return {
            "latched": bool(row[0]),
            "first_event_id": row[1],
            "last_event_id": row[2],
            "last_reason": last[0] if last else None,
            "last_request_id": last[1] if last else None,
            "last_owner_epoch": last[2] if last else None,
            "last_at": last[3] if last else None,
            "event_count": count,
            "automatic_resume": False,
            "active_device_command_canceled": False,
        }

    def emergency_status(self) -> dict:
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            result = self._emergency_status(db)
            db.commit()
            return result

    def trip_emergency_stop(self, reason: str, request_id=None, owner_epoch=None, evidence=None) -> dict:
        """Durably latch a stop and append the cause; there is intentionally no auto-clear."""
        if not isinstance(reason, str) or not STOP_REASON_RE.fullmatch(reason):
            raise ValueError("INVALID_STOP_REASON")
        if request_id is not None and (not isinstance(request_id, str) or not REQUEST_RE.fullmatch(request_id)):
            raise ValueError("INVALID_REQUEST_ID")
        if owner_epoch is not None and (type(owner_epoch) is not int or owner_epoch < 0):
            raise ValueError("INVALID_OWNER_EPOCH")
        if evidence is None:
            evidence = {}
        if not isinstance(evidence, dict):
            raise ValueError("INVALID_EVIDENCE")
        safe_evidence = {}
        for key, value in evidence.items():
            if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,48}", key):
                raise ValueError("INVALID_EVIDENCE_KEY")
            if not isinstance(value, (str, int, float, bool, type(None))) or (isinstance(value, float) and not math.isfinite(value)):
                raise ValueError("INVALID_EVIDENCE_VALUE")
            safe_evidence[key] = value
        payload = json.dumps(safe_evidence, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(payload) > 4096:
            raise ValueError("EVIDENCE_TOO_LARGE")
        now = time.time()
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            latch = db.execute("SELECT latched,first_event_id FROM emergency_latch WHERE id=1").fetchone()
            if latch is None:
                raise ValueError("EMERGENCY_LATCH_MISSING")
            cur = db.execute(
                "INSERT INTO emergency_events(reason,request_id,owner_epoch,created_at,evidence_json) VALUES(?,?,?,?,?)",
                (reason, request_id, owner_epoch, now, payload),
            )
            event_id = cur.lastrowid
            first = latch[1] if latch[0] else event_id
            db.execute("UPDATE emergency_latch SET latched=1,first_event_id=?,last_event_id=? WHERE id=1",
                       (first, event_id))
            db.commit()
        return {
            "status": "LATCHED",
            "reason": reason,
            "event_id": event_id,
            "new_commands_blocked": True,
            "active_command_state": "UNKNOWN_ACTIVE_COMMAND",
            "active_command_canceled": False,
            "automatic_resume": False,
        }

    def reserve(self, normalized: dict) -> str:
        """Commit durable PENDING *before* any possible transport.

        This version has no transport. It records denied requests at the HA boundary
        to exercise reboot/crash-safe deduplication without actuator authority.
        """
        digest = request_hash(normalized)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            stop = db.execute("SELECT latched FROM emergency_latch WHERE id=1").fetchone()
            if stop is None or stop[0] != 0:
                db.commit()
                return "EMERGENCY_STOP_LATCHED"
            owner, epoch = self._owner(db)
            row = db.execute("SELECT payload_sha256,state FROM requests WHERE request_id=?",
                             (normalized["request_id"],)).fetchone()
            if row is not None:
                if row[0] != digest:
                    db.commit()
                    return "REQUEST_ID_CONFLICT"
                db.commit()
                return "DUPLICATE_REJECTED" if row[1] == "REJECTED" else "UNKNOWN_REQUIRES_RECONCILIATION"
            if normalized["owner_epoch"] != epoch:
                db.commit()
                return "TRUSTED_EPOCH_MISMATCH"
            db.execute(
                "INSERT INTO requests VALUES(?,?,?,'PENDING',?,?)",
                (normalized["request_id"], digest, epoch, time.time(), time.time()),
            )
            db.commit()
            return "RESERVED_BEFORE_TRANSPORT"

    def finish_without_write(self, normalized: dict) -> str:
        """Confirm rejection only for the exact committed request identity."""
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            self._owner(db)
            row = db.execute("SELECT payload_sha256,state FROM requests WHERE request_id=?",
                             (normalized["request_id"],)).fetchone()
            if row != (request_hash(normalized), "PENDING"):
                db.commit()
                return "UNKNOWN_REQUIRES_RECONCILIATION"
            db.execute("UPDATE requests SET state='REJECTED',updated_at=? WHERE request_id=?",
                       (time.time(), normalized["request_id"]))
            db.commit()
            return "TRUSTED_PHYSICAL_FENCE_UNVERIFIED"

    def dispatch_rejected(self, request: dict) -> dict:
        """No device calls. Never infer hardware safety from HA helper states."""
        reason, normalized = validate(request)
        reply = {
            "gateway_contract": CONTRACT,
            "status": "REJECTED", "writes_started": False,
            "device_execution_confirmed": False, "physical_dispatch_supported": False,
            "request_id": normalized["request_id"] if normalized else "",
            "plan_id": normalized["plan_id"] if normalized else "",
            "owner_epoch": normalized["owner_epoch"] if normalized else -1,
        }
        if normalized is None:
            reply["reason"] = reason
            return reply
        try:
            outcome = self.reserve(normalized)
            if outcome == "EMERGENCY_STOP_LATCHED":
                reply["reason"] = outcome
                reply["emergency_stop_latched"] = True
                return reply
            if outcome == "RESERVED_BEFORE_TRANSPORT":
                outcome = self.finish_without_write(normalized)
            reply["reason"] = outcome
        except (sqlite3.Error, ValueError, OSError):
            reply["reason"] = "DURABLE_GATE_UNAVAILABLE_NO_RETRY"
        return reply
