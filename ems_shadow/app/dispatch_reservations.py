"""Durable, one-shot request reservations for EMS2 dispatch.

This is an add-on-side idempotency ledger, not a replacement for the HA-side
trusted owner fence. A reservation is committed before transport; after that,
any ambiguous outcome remains non-retryable across process restarts.
"""
import hashlib
import json
import math
import sqlite3


def initialise(db):
    db.execute(
        """CREATE TABLE IF NOT EXISTS dispatch_reservations(
            request_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            owner_epoch INTEGER NOT NULL,
            payload_digest TEXT NOT NULL,
            status TEXT NOT NULL,
            reserved_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS dispatch_reservations_status_idx "
        "ON dispatch_reservations(status)"
    )


def payload_digest(*, request_id, plan_id, owner_epoch, option, power_w, expires_at=None):
    if type(owner_epoch) is not int or owner_epoch < 0:
        raise ValueError("invalid_owner_epoch")
    if type(power_w) not in (int, float) or not math.isfinite(power_w) or power_w <= 0:
        raise ValueError("invalid_power")
    record = {
        "request_id": request_id,
        "plan_id": plan_id,
        "owner_epoch": owner_epoch,
        "option": option,
        "power_w": float(power_w),
        # The deadline governs whether dispatch may start, not what request
        # the ID represents. The planner refreshes short-lived deadlines on
        # each poll; binding the digest to that deadline would turn a retry
        # of an already completed/unknown request into an ID conflict.
    }
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def reserve(db, *, request_id, plan_id, owner_epoch, option, power_w, expires_at=None, now):
    """Reserve once inside caller's SQLite transaction; never starts transport."""
    initialise(db)
    digest = payload_digest(
        request_id=request_id,
        plan_id=plan_id,
        owner_epoch=owner_epoch,
        option=option,
        power_w=power_w,
        expires_at=expires_at,
    )
    row = db.execute(
        "SELECT plan_id,owner_epoch,payload_digest,status FROM dispatch_reservations WHERE request_id=?",
        (request_id,),
    ).fetchone()
    if row:
        same = row[:3] == (plan_id, owner_epoch, digest)
        return "DUPLICATE_" + row[3] if same else "REQUEST_CONFLICT"
    # Older executor records are conservatively reserved too. They may not be
    # replayed merely because an older schema lacked this explicit table.
    if db.execute("SELECT 1 FROM commands WHERE id=?", (request_id,)).fetchone():
        return "LEGACY_REQUEST_ALREADY_RECORDED"
    db.execute(
        "INSERT INTO dispatch_reservations VALUES(?,?,?,?,?,?,?)",
        (request_id, plan_id, owner_epoch, digest, "RESERVED", now.isoformat(), now.isoformat()),
    )
    return "RESERVED"


def inspect(db, *, request_id, plan_id, owner_epoch, option, power_w, expires_at=None):
    """Read-only duplicate/conflict check; safe before live HA reads."""
    initialise(db)
    digest = payload_digest(
        request_id=request_id,
        plan_id=plan_id,
        owner_epoch=owner_epoch,
        option=option,
        power_w=power_w,
        expires_at=expires_at,
    )
    row = db.execute(
        "SELECT plan_id,owner_epoch,payload_digest,status FROM dispatch_reservations WHERE request_id=?",
        (request_id,),
    ).fetchone()
    if row:
        return "DUPLICATE_" + row[3] if row[:3] == (plan_id, owner_epoch, digest) else "REQUEST_CONFLICT"
    if db.execute("SELECT 1 FROM commands WHERE id=?", (request_id,)).fetchone():
        return "LEGACY_REQUEST_ALREADY_RECORDED"
    return None


def set_status(db, request_id, status, now):
    allowed = {"PENDING", "ACK", "REJECTED", "UNKNOWN"}
    if status not in allowed:
        raise ValueError("invalid_reservation_status")
    row = db.execute(
        "SELECT status FROM dispatch_reservations WHERE request_id=?", (request_id,)
    ).fetchone()
    if not row or row[0] not in {"RESERVED", "PENDING"}:
        raise ValueError("reservation_transition_invalid")
    db.execute(
        "UPDATE dispatch_reservations SET status=?,updated_at=? WHERE request_id=?",
        (status, now.isoformat(), request_id),
    )

