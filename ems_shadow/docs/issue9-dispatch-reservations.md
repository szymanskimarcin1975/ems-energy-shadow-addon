# Issue 9: durable EMS2 request reservations

## Change

The battery executor now reserves each accepted request ID in its own SQLite
table in the executor database. The reservation binds the ID to plan_id,
owner_epoch, option, and requested power. The short-lived request deadline is
validated before dispatch but is not part of request identity, because the
planner refreshes that deadline while polling the same plan slot.

The executor runs SQLite in WAL mode with synchronous=FULL. It commits the
reservation, command identity, and PENDING lifecycle record together before
calling the transport. A crash or ambiguous transport outcome therefore leaves
a durable non-retryable request. A duplicate with the same identity returns the
stored state; a duplicate ID with changed plan, epoch, mode, or power is
rejected as a conflict. Existing command rows from the prior schema are treated
as already reserved and cannot be replayed.

## Safety boundary

This is an add-on-side durable reservation. It does not establish the
independent Home Assistant owner-epoch fence. The HA gateway's existing
TRUSTED_EPOCH_GATE_NOT_ESTABLISHED rejection must remain in place until a
trusted, durable owner and reservation check is enforced at that gateway
boundary and validated against every HA-side writer. EMS2 must remain
READ_ONLY and LEGACY must remain owner until then. No physical battery command
is authorized by this change.

## Data compatibility

The new dispatch_reservations table is created lazily in the executor's
separate database. The legacy energy ledger, its ID, fingerprint, history, and
tables are untouched.

## Verification

Targeted local tests cover commit/reopen duplicate detection, conflict on
payload/epoch changes, rollback before commit, serialization from competing
SQLite connections, old-schema replay refusal, and executor restart/UNKNOWN
non-retry behavior. CI remains the release gate before this code is merged or
installed.
