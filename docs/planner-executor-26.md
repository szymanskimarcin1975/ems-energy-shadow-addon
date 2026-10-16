# Observation .26: planner-to-pending-request bridge

Production remains READ_ONLY, owner LEGACY, no device writes. Temperature response
is explicitly held disabled; measurements and training collection continue.

The independent battery worker reads the bounded atomic planning report. An
explicit private scenario selection and exact planning configuration fingerprint
are required. Only a current, unique, contiguous active slot from a fresh,
quality-qualified report can prepare pending_request. Future slots are never
executed early. Household schedules can include the partial current hour and
end after exactly 24 hours. The 16:00 workday target is at the end of the 15:00
slot, including a partial slot when planning at 15:30.

Requests carry source plan digest, fingerprint, validity, slot bounds, mode and
maximum planned watts. Identity is stable within a UTC hour for identical mode,
watts and ownership epoch. Independent SQLite journals previews; the existing
commands journal remains the idempotency authority for attempted dispatch.
UNKNOWN is never retried automatically. Schedule validity is checked again in
the actual execution path before transport. Manual and planner intents conflict
rather than silently overriding each other.

READ_ONLY prepares and records preview intents only. It does not enqueue HA
services or alter ownership. An advisory plan never grants actuation authority.
Existing ownership, SOC, BMS, telemetry, inverter fault, hardware evidence and
fresh readback checks remain mandatory. A fresh HA readback ACK is not physical
energy-delivery confirmation.

## Explicit capability boundaries

The current production gateway and executor allow only Solar Charge and Discharge
to Minimize Import for EMS2. Grid-charge intents are represented accurately but
rejected as unsupported, never silently replaced with solar-only charge. Likewise,
if the existing inverter power ceiling exceeds the planned ceiling, execution is
rejected; this release does not add power-setting commands. A HOLD slot creates
no new command and cannot cancel an earlier Remote Control command. These are
remaining actuation-adapter and device-handover conditions, not a complete ACTIVE
battery-dispatch approval. No automatic LEGACY shutdown, no physical fallback or
no-export certification is introduced.

## Verification and rollback

Synthetic tests cover forecast, solver, intent, ownership gate, executor and fresh
HA ACK, plus SOC ceiling, BMS zero, stale telemetry, FAULT, LEGACY, expired/replaced
plan, unsupported grid charge, excess remote power and UNKNOWN/deduplication.
Isolated ownership transfer and rollback preserve audit/epoch through reopen.
Container smoke uses a synthetic API and proves READ_ONLY journal writes without
actuator requests. These tests do not replace Supervisor rollback or inverter tests.

Rollback is code/configuration only. Keep current SQLite databases and all legacy
source settings. New planner_requests exists solely in the independent execution
database and can be ignored by previous code. Restore the backed-up planner and
executor configuration if needed, retaining READ_ONLY and LEGACY. Never restore
an older production database merely to revert code.
