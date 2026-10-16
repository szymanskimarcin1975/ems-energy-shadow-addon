# EMS Energy SHADOW 0.1.3-dev.1

## Identity and persistent data

Keep the same repository and addon slug ems_energy_shadow during an update.
Supervisor manages persistent /data. Do not uninstall the addon to update it.
Preserve ledger_id and all seven source options. Defaults remain empty and must
never replace saved settings. SQLite schema and observer computation code are
unchanged from 0.1.2. Observer report addon_version remains 0.1.2 (code version);
Supervisor metadata and Docker label identify the package as 0.1.3-dev.1.

## Disabled export

The option diagnostic_export_enabled defaults to false. The gateway starts the
observer first. A separate lightweight STDIN reader acknowledges rejected export
requests without opening SQLite or creating export directories. No export service
or controller database is opened. The reader only reads /data/options.json.
Its failure does not terminate the observer. No receiver auto-restart or request
replay occurs.

Requests are JSON objects terminated by newline with exactly these keys:
operation (diagnostic_export), request_id (8-64 ASCII letters/digits/_/-), ledger_id,
expires_at (timezone-aware future time, at most 300 seconds), start and end
(timezone-aware instants exactly 24 hours apart, end not in the future).

A received valid request produces a JSON log acknowledgment containing
component=diagnostic_stdin, status=REJECTED, reason=export_disabled, request_id,
received=true, export_enabled=false and repeated. Duplicate requests remain
rejected; repeated tracks only the last 1024 valid IDs in RAM. Invalid/oversized/
incomplete messages have fixed rejection reasons; unvalidated IDs are not echoed.
Maximum message length is 4096 UTF-8 bytes. EOF closes only the reader.

Supervisor/API success alone is not an application acknowledgment. Missing
correlated acknowledgment means an unknown transport/reader outcome. Do not
automatically resend or enable export to investigate a missing acknowledgment.
The first real Supervisor test must leave export disabled.

## Explicitly enabled export (separate decision)

Enabling the option starts an isolated controller, but does not itself export a
ledger. Only a validated explicit request can reserve a diagnostic export. Source
SQLite is opened mode=ro through Online Backup; SQLite read coordination can affect
SHM. No source checkpoint, VACUUM, reset or migration is performed. Full snapshots
stay in private /data/diagnostic_exports; only allowlisted quality aggregates go to
the existing configuration report directory. Tokens are removed from worker env.
Request IDs are persisted, simultaneous exports refused, interrupted requests become
UNKNOWN and block new exports until reviewed; no automatic replay. Export quota
is three lifetime requests in the control ledger, with a 60-second cooldown.

Worker RAM/WAL/disk and observer freshness checks are safeguards, not proof of
negligible impact. Shared container resource exhaustion can still affect collection.
Do not use diagnostic sampled energy as billing or approved training data until
measurement topology and coverage are independently validated.

## Shutdown and updates

SIGTERM/SIGINT signal observer and sidecar process groups together. Cooperative
stop budget is 15 seconds, followed by kill and a 2-second reap check. Supervisor
timeout is 30 seconds. Unconfirmed shutdown produces UNKNOWN and does not spawn a
replacement. Kernel-blocked I/O cannot be guaranteed immediately killable.

Before a controlled update, create and verify a fresh addon backup and retain an
external copy. backup:cold interrupts collection; require explicit permission.
Mark the resulting gap; never backfill it with zero energy. Returning to observer
code 0.1.2 in a separately approved higher-version recovery package is not an exact
old-image restoration. Do not restore older SQLite automatically. Recovery package
0.1.4-recovery.1 is not published by this candidate. Full Supervisor update/recovery
has not been tested; standalone container tests do not replace that prerequisite.


## 0.1.4-observation.28 — correlated dispatch only

The production executor has no `SupervisorHA.select()` transport and rejects
requests without explicit planned power and a SHA-256 plan identifier. All writes
use the queued compound gateway contract `EMS2_COMPOUND_V28`. The EMS2 gateway
branch rejects older scalar operations before writes; LEGACY logic is unchanged.
Responses must match request ID, plan ID, ownership epoch and gateway contract.
Only an explicit matching REJECTED reply with `writes_started: false` is a clean
rejection. Missing, malformed, partial, mismatched or timed-out outcomes persist as
UNKNOWN with no automatic replay. Successful replies also require EMS2 ownership,
matching mode, valid applied power and fresh HA readback; ownership and plan are
checked again after transport. HA ACK does not prove physical device completion.
A separate command_identity table in the new execution database binds deduplication
to plan, epoch and requested power. No old ledger migration is performed.
Install the matching generated gateway branch while EMS2 remains READ_ONLY and
LEGACY owns control. The original LEGACY suffix must compare equal before/after.
Do not enable ACTIVE based only on these tests: device termination, fallback,
M1-loss behaviour, no battery export and BMS safety evidence remain mandatory.
