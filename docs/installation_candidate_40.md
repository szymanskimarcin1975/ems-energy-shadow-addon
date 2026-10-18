# Installation candidate .40 / gateway 0.2.0-rc.1 — ACTIVE OFF

Scope: PR #19 comment 6249286752. Extends that review; no second actuation PR,
no owner switch, no production installation or battery command.

## What is shipped

* Addon `0.1.4-observation.40`, gateway `0.2.0-rc.1`. Candidate stays opt-in,
  `physical_authorized` stays false, no automatic owner transition. Existing
  SHADOW remains usable without enabling the companion or any physical code.
* Offline builder `tools/installation/prepare_candidate.py` verifies exact upstream
  v4.0.4 hub/manifest hashes from commit `d38d890887684ddd7938c4bce5223d387b24c6a7`.
  Produces separate gateway, reviewed SolarEdge companion, pristine upstream
  recovery archives and SHA256SUMS. Does not access HA, credentials or SQLite.
* Companion `4.0.4+ems.1`: optional YAML `solaredge_modbus_multi:
  {ems_single_attempt_entries: ["REVIEWED_CONFIG_ENTRY_ID"]}`. Only exact
  StorageControl component writes for that entry bypass the integration's
  three-attempt loop. Other entries, component writes and read retries unchanged.
  Dependencies pinned to inspected/tested modbus-connection 4.10.0/tmodbus 0.6.1.
  Lower transport reconnect is disabled and does not retry ambiguous timeout,
  disconnect or malformed response; explicit device-busy refusals can be retried
  internally and are not proof of a write. No runtime monkey patch or second client.
* STOP: one durable attempt, command mode 7 then control mode 1 (local self
  consumption), through existing select services. Failure of either stage remains
  UNKNOWN; no retry, no automatic LEGACY. This is revocation of Remote authority,
  not deletion of a command register or observation of timer expiry.
* Connected observer checks two distinct complete post-write polls, local control
  1 / command 7 / default 7, non-FAULT states, finite telemetry and no sampled
  concurrent battery discharge/export. A failed poll resets witness history.
  Requires bounded read window <=5 s and confirmation within 30 s. Slow 120 s
  polling cannot pass; no forced polling or configuration change is performed.
* ACTIVE preflight still requires a device-specific, dated commissioning witness
  for this STOP method (`method=remote_to_local_self_consumption`,
  `device_test_passed=true`), writer exclusion, fallback and battery no-export.
  Test fixtures are not valid production evidence. Observer returns
  `timeout_expiry_confirmed=false`, `no_export_physically_proven=false`.

## CWU dependency — separate review, no production change

Read-only HA check during preparation found the dedicated CWU controller ON,
main combined LEGACY OFF, cached target and temperature 50 C. This does not prove
fresh ACK or physical morning heating. Turning the combined automation OFF may
remove its 04:00 check; do not recreate a second temperature writer.
`blueprints/automation/ems2/cwu_weekday_review.yaml` is a proposed read-only
checkpoint at 02:30/04:00/07:00 on configured workdays. It logs cached observations,
never sets a target or heats, never writes the battery, and does not change weekends.
Before deploying any heating schedule change, review the existing dedicated
controller against start 02:30, 50 C by 04:00 and hold to 07:00. No such change is
included or deployed here.

## Installation and code-only recovery after independent review

1. Keep owner/helper LEGACY, EMS2 READ_ONLY, authorization OFF. Check actual state;
   do not re-enable old battery writers that the owner intentionally stopped.
2. Back up the actual installed gateway and actual installed SolarEdge component
   outside `custom_components`, with per-file hashes, using independent SSH.
   CI's upstream recovery is NOT a substitute for a backup of installed files.
   Preserve .storage, addon /data and all live SQLite. Do not copy live databases.
3. Review SHA256SUMS and source commit; install addon .40 only by Supervisor, and
   HA gateway/companion only by the approved custom-component procedure. No script
   here performs installation. Companion is optional for READ_ONLY installation;
   leave its entry opt-in absent and candidate disabled until separate review.
4. Any Core reload/restart requires its own safe maintenance window; do not infer
   that installer artifacts make a restart physically safe. Confirm independent
   SSH access and existing CWU handling before scheduling it.
5. Check version, successful full polls, SHADOW write continuity, owner unchanged,
   auth OFF, physical EMS2 writes 0. Candidate enabling is a separate operation.
6. On software regression disable candidate authorization first (does NOT cancel
   any physical command), restore ONLY backed-up code via SSH and reload/restart
   under the same maintenance controls. Do not restore older .storage or SQLite.
   If any physical command is UNKNOWN, no automatic owner change or LEGACY restart.

## Exact first hardware-test protocol — NOT EXECUTED

The commissioning test itself is a separately approved exception to normal ACTIVE
preflight, run by an operator through one controlled writer. Do not fabricate a
`device_test_passed` record to make the uncommissioned production gate send it.

1. Preconditions: independent reviewer approval; physical operator present;
   restored code/mode procedure available; no CWU/CO change due; full writer audit
   and all old battery writers OFF/current=0, no scheduled pending run, no external
   Modbus/EMHASS/AppDaemon/Scheduler writer left unaccounted for. Validate actual
   registry bindings, SOC within 10–90%, BMS direction cap >=250 W, normal status,
   temperature within documented envelope and no FAULT. No second Modbus client.
2. Instrumentation: an approved fast path on the existing connection or independent
   local meter must record M1, B1, inverter AC and independently measured/derived
   PV/load at <=1 s, bounded timestamp skew <=1 s; retain raw signs, units and read
   windows. Do not infer a subsecond absence of export from 120 s HA samples.
   Distinguish AC inverter total from PV; do not double count battery power.
3. Record baseline >=30 s. First test direction CHARGE FROM GRID, cap 250 W,
   timeout 30 s, at most 10 s forced operation; SOC<95%, current charge cap>0.
   This validates command/readback/STOP, not discharge no-export. Do not send a
   charge at full battery. Reconcile any previous Remote command FIRST.
4. STOP via reviewed command 7 -> control 1 sequence. Confirm both control readback
   and two full fresh polls plus local physical observations. If a write times out
   or readback is ambiguous: UNKNOWN_ACTIVE_COMMAND, no retry/no controller swap.
   On confirmed local return record witness tied to device/firmware and timestamps.
5. Only after successful STOP, separately approve mode 5 discharge test: 250 W,
   <=10 s, positive import headroom >=1000 W, SOC>10%, fresh discharge cap>=250 W.
   Operator may switch a prepared 1500 W resistive load only under this supervised
   protocol; verify rating/circuit safety first. Observe a downward load step only
   if baseline headroom and STOP recovery are confirmed. PV surplus periods do
   not establish battery-origin export without synchronized attribution.
6. Abort immediately on FAULT, BMS limit0, stale/skewed telemetry, competing write,
   loss of import headroom, unexpected power >350 W for the 250 W test, or M1 export
   while B1 discharges (even one observed sample). Execute ONLY the validated STOP;
   if its result is UNKNOWN, latch block and use the operator's documented local
   recovery. Do not assume a software block stops an already active command.
7. Observe >=60 s after return. Do not restart LEGACY until Remote authority ended,
   physical state is clear and the previous controller can be reintroduced alone.
   Loss-of-M1/disconnect is NOT part of this test. Do not create artificial FAULT.

## Remaining device evidence and writer limits

The prepared software cannot prove absence of unknown network clients. Required
inventory includes automations/scripts, entity service callers, Scheduler,
EMHASS, AppDaemon and external Modbus hosts. HA locks serialize this gateway only;
external writers require operational/network exclusion evidence. Capture the
inventory, disabled state, current runs and exclusions before commissioning.

Mode 5 semantics must be confirmed for SE10K-RWB48BFN4 firmware4.25.11 by the above
bounded test; Export Limit remains OFF so PV surplus may export. Sampled no-export
is not an instantaneous hardware guarantee. M1 loss/fallback and actual timeout
expiry require device-specific documentation or a separately assessed physical
test, not elapsed time or the mode register alone. No physical test was run here.
SOC5–95 remains an EMS operating envelope, not a statement about hidden BMS limits.
