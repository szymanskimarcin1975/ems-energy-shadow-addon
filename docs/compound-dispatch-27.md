# Observation .27: compound power/mode and durable command lifecycle

Production stays READ_ONLY and LEGACY-owned. No cancellation or physical fault
experiment is introduced. Existing observer files and legacy source schema remain
unchanged. Temperature response remains disabled.

Planned grid charge is explicitly supported, never relabelled as solar-only.
Executor transport sends one `dispatch` operation through the existing queued HA
gateway. The EMS2 branch rechecks ownership, authorization, quiescent legacy writers,
SOC, status, fault code, units, HA freshness/skew and dynamic BMS direction limits.
It clamps positive requested watts to 5000 W and the live max/peak direction caps.
SOC ceiling and zero direction limit are rejection conditions, not clamp targets.
Power then mode are two device writes in ONE queued script run; they are not a
hardware-atomic transaction. A safety change between writes returns PARTIAL/UNKNOWN
and prevents the mode write. There is no direct-service fallback in the add-on.

The original LEGACY sequence is retained as an unchanged suffix after a new EMS2
branch. New gate configuration is separately backed up and verified. Template tests
use synthetic Jinja states/actions in CI, not the production inverter. READ_ONLY
container tests assert zero command and lifecycle records.

A SQLite transaction records PENDING plus the active-command identity before
transport. ACK means fresh HA mode AND power readback, never physical completion.
Identical IDs do not send again. Expired/late ACK, transport failure and partial
writes become UNKNOWN and require reconciliation. A database failure after the
write leaves the already committed PENDING marker, never permission to replay.

HOLD and stale/missing plans send no new command, but report termination-required
if an EMS2 command remains active or unknown. Neither 3600 seconds elapsed nor zero
battery watts is accepted as termination proof. Different requests are blocked until
separately verified, request-correlated device-inactive evidence is recorded. The
explicit evidence interface is NOT automatically fed production assumptions.
No manufacturer-verified cancellation/status method for the target firmware has
been established; active takeover therefore remains blocked. CHARGE/HOLD/DISCHARGE
transition tests use synthetic termination evidence and are labelled accordingly.

Rollback retains all databases: restore previous gateway configuration and code,
with EMS2 READ_ONLY and owner LEGACY. Never restore old SQLite merely to revert code.
New lifecycle tables are in the independent execution database only. Physical BMS
bounds, external-client exclusivity, prior-command reconciliation, fail-safe and
no-battery-export behaviour remain separate mandatory preconditions for ACTIVE.
