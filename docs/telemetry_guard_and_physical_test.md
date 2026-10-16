# Observation.24: transport guard and physical validation proposal

No physical test is authorized by publication of this document.
Production remains READ_ONLY, shared owner LEGACY, execution authorization off.
The unchanged observer, planning SOC 0-100%, legacy ledger and fingerprint are
outside the change. Blocking a new command DOES NOT cancel an active command.

## Guard contract

`battery_service` reads configured M1 power, B1 power and SOC in one HA template.
It reports quality even in READ_ONLY, using only read requests. `Executor`
requires the same guard before journalling and again immediately before sending.
Missing mapping, failed read, unavailable/nonfinite values, incorrect units,
future/naive timestamps, HA writes older than 180 seconds or snapshot skew over
5 seconds reject new commands. Missing guard also fails closed.
No software guard substitutes for physical fallback or external writer fencing.

The 180-second limit retains the existing conservative limit: it allows a
declared 120-second cycle plus up to 60 seconds for acquisition jitter, while
rejecting a missed full cycle. A short measured changing-M1 history showed
approximately 121-second intervals. Unchanged B1/SOC Recorder values do not
establish physical sampling cadence. Atomic HA writes are not device clocks.
The 5-second skew check is a conservative HA-snapshot constraint, not a measured
physical synchronization guarantee. Both thresholds remain unapproved for ACTIVE
until longer real observations and physical timing evidence are available.

Private runtime configuration adds `telemetry_sources` keys `m1_power`,
`b1_power`, `soc`. There are no built-in private entity names or implicit fallbacks.
Missing mapping blocks ACTIVE and is visible in READ_ONLY diagnostics.

## Proposed physical session: SE10K-RWB48BFN4, firmware 4.25.11

### Preconditions and authorization

Obtain separate explicit authorization for the physical session. A qualified
installer must provide an on-site recovery path with verified access to local
inverter settings; an unavailable installer interface is not a recovery plan.
Do not modify hardware protections, planning SOC or operational power ceilings.
Verify fresh backup, exact legacy/gateway configuration and ability to restore
only code/configuration without restoring old measurement databases.
Inventory all write clients first, including Scheduler, EMHASS, cloud/manual
controllers and direct Modbus clients. Disable writes only in the approved
maintenance window, preserving their configurations and unrelated protections.
New executor remains READ_ONLY and unauthorized throughout this validation.

Use an existing naturally required command distinct from the default mode.
Do not create charging/discharging demand for the test, especially at full SOC.
If no suitable natural command exists, postpone the expiry observation.

### Measurements

Record an independent bidirectional grid meter and battery-side power at a rate
and accuracy approved by the installer for detecting the prohibited export.
The existing 120-second HA polling alone cannot bound short export transients.
Record PV/inverter AC, SOC, BMS status and power ceilings, device communication
health, command/default mode, timeout, plus all command writes and timestamps.
Use instrument uncertainty to distinguish battery export from PV export; total
grid export alone is not evidence of battery export.

### Sequence

1. Capture stable baseline and last naturally issued command. Reconcile any
   queued/in-flight HA request; ambiguous delivery stops the test.
2. Fence renewal by approved legacy writers without sending a replacement
   command. Keep default MSC and the configured 3600-second timeout unchanged.
3. Observe at least the full timeout from the last verified relevant write,
   plus documented device/readback latency. A wall-clock hour without proof of
   the last write is insufficient. Record actual transition and physical flows.
4. Test controller communication loss only by a separately approved reversible
   isolation of the EMS-to-inverter control path, not by disconnecting mains,
   CAN, battery cabling or all HA communications. Observe fallback and recovery.
5. Loss of the physical M1 measurement is a separate higher-risk subtest. Do not
   unplug an energized meter or change wiring. Execute only using a
   manufacturer-approved fault-injection procedure and qualified installer.
   Without that procedure, mark meter-loss fallback UNCONFIRMED and do not run.
6. Restore communication, verify fresh telemetry and device state; do not replay
   pending/UNKNOWN commands. Restore exactly one authorized legacy writer only
   after the installer confirms the safe local state and no competing controller.

### Abort and recovery

Abort on measured battery export exceeding agreed instrument uncertainty,
unexpected charge/discharge, BMS alarm, changed limits, stale independent
measurements, unexpected writes, failure to revert, or loss of local recovery.
Blocking further API commands is not emergency stopping. On-site installer must
use the previously verified manufacturer-approved local safe mode/recovery
procedure. If this cannot be prepared, the physical session is NO-GO.
Do not automatically issue another battery mode or restore an old SQLite.

### Acceptance and later handover

PASS requires observed expiry, default behavior, controller-loss behavior,
meter-loss behavior (or manufacturer evidence covering this exact system), no
unintended battery export, and successful local recovery. Document exact model,
firmware, instruments, uncertainty and timestamps; do not fill proof flags from
simulation alone. Failure/unconfirmed result retains LEGACY and READ_ONLY.

After separate GO: unauthorized EMS2; fence legacy; drain gateway; reconcile
device command; set transitional UNKNOWN; atomically reconcile durable owner
epoch with HA owner; authorize only EMS2; issue only a naturally required safe
command; verify ACK and physical response. On failure, unauthorized EMS2 first,
reconcile its last command and establish safe local mode, then restore LEGACY.
Never overlap writers or automatically revive legacy after uncertain delivery.
