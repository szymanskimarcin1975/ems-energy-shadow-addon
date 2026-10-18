# .41 / gateway0.2.0-rc.2 — fixed120s Modbus lifecycle

PR19 is merged. This change supersedes its30s confirmation window and any
recommendation to accelerate Modbus reads. The existing120s interval is immutable:
no update_interval change, forced refresh, additional connection or client.
No CWU/CO/G13 configuration changes. No production install or physical command.

## Lifecycle and exact bounds

| Phase | Persistent gateway state | Action |
|---|---|---|
| Admission | RESERVED → SENDING | Validate current plan, owner/epoch, registry and BMS. Admission deadline<=60s. |
| Sent, not physically observed | WAITING_EFFECT | Reply WAITING_CONFIRMATION immediately; no service call waits120s. |
| Natural post-write read | ACK_ACTIVE | Request/plan/epoch, readback and directional B1 effect all required. |
| Explicit safety STOP | UNKNOWN during reserved transport → WAITING_STOP | Actually request command7 then control1 now, once; never equate HOLD with STOP. |
| Two post-STOP reads | ENDED | Local-authority readback under the independently commissioned procedure. |
| Partial/failed/ambiguous write or missing confirmation | UNKNOWN | No replay, owner switch, automatic resume or LEGACY restart. |

An admission deadline is not a physical command lease. The command is bounded by
its device timeout and the approved plan validity. Monitoring independently checks
the current matching household plan; a refreshed matching plan may extend the
plan lease only within the original device timeout, without another write. A
changed/expired plan or lost guard invokes a separately journaled STOP attempt.
Neither expiry nor STOP service success is proof the device stopped.

* Confirm effect by natural read within270s (two120s opportunities +30s budget).
* Confirm STOP within390s (three opportunities +30s), requiring two distinct full
  post-write polls, consecutive completion gap<=150s. A failed poll clears history.
* Freshness ceiling remains180s (120s cadence +60s tolerance); no stale measurement
  authorizes a new energy command. A poll's read-window bound is distinct from its
  cadence and remains explicitly checked (<=configured bound, maximum30s).
* Exclude any poll whose read may have started before the final command/STOP write:
  use completed_at minus conservative whole-poll bound. No inferred BMS sample clock.
* While WAITING_EFFECT or WAITING_STOP, new requests and owner changes are blocked
  by SQLite, across instances. Read-only command_status requests do not dispatch.
* Restart disarms authorization and converts interrupted/waiting states to UNKNOWN.
  It never resends energy commands. A previously reserved STOP cannot be repeated.
  Unknown active energy command may trigger only the separately verified one-shot
  STOP procedure. If unavailable/uncertain, preserve UNKNOWN and require the operator.
* STOP is permitted to attempt verified revocation even when telemetry is stale;
  it must not wait for another120s sample. Loss of transport can make that operation
  UNKNOWN: software cannot guarantee delivery during physical communication loss.

The addon persists WAITING, polls only the read-only HA outcome for reserved IDs,
and records ACK/ENDED/UNKNOWN without redispatch. This reconciliation is limited
to new asynchronous requests; it does not reinterpret old ACK records. A failed
outcome read latches UNKNOWN and cannot later resume automatically.

## Retry and exclusivity

The reviewed4.0.4+ems.1 companion remains unchanged: entry-specific single attempt
for StorageControl, exact upstream source hashes, pinned transport. CI exercises
actual loopback TCP timeout/disconnect/malformed replies and sees one frame, no
ambiguous replay. Explicit device-busy refusals may be retried by the lower layer.

Gateway request/STOP claims are SQLite-atomic and share owner/epoch authority.
Known writers must be OFF/current0 and externally fenced before activation. This
code cannot exclude an unknown LAN Modbus writer or an independently authorized
HA client by looking at helper values. Retain the explicit external-fence evidence;
do not declare it established merely because this PR merges.

## Install and code-only rollback — after independent review

1. Preserve existing owner LEGACY, EMS2 READ_ONLY and physical authorization OFF.
   Do not re-enable battery automations already disabled by the owner. Do not
   change CWU, CO, tariff, Export Limit, device safeguards or120s read interval.
2. Back up the actual installed gateway and SolarEdge component via existing SSH;
   record per-file SHA256. Retain addon backups and current data. No cp of live
   SQLite, no restore of .storage or older databases.
3. Verify CI commit and artifact SHA256SUMS. Artifacts include addon.41 source,
   gateway0.2.0-rc.2, reviewed companion and pristine upstream recovery. The latter
   is not a substitute for the actual installed component backup.
4. Install addon.41 only through Supervisor. Install gateway custom component in
   the approved maintenance window with candidate disabled/physical auth OFF.
   Companion installation/entry opt-in is separate and unnecessary for READ_ONLY.
   If a Core restart is needed, preserve independent SSH and the established CWU
   recovery; do not infer physical restart safety solely from CI.
5. Confirm versions, ordinary120s polls, observer/plan/executor continuity, owner
   unchanged and physical EMS2 writes0. Isolated owner transfer/rollback is tested;
   no production owner switch is included.
6. On software regression restore ONLY backed-up code through SSH and the approved
   restart/reload procedure. New state strings have no database CHECK restriction;
   older code treats unresolved rows as blocking. Keep authorization OFF. Never
   restore older SQLite or start LEGACY while a command remains UNKNOWN.

## First limited device test — final procedure review still required

Do not fabricate device_test_passed evidence to get through the uncommissioned
production gate. Commission the stop procedure under a separately approved,
single-operator procedure before authorizing the automatic executor.

A. Prerequisites: reviewer approval, physical operator and independent local
recovery available, known/external writers fenced, previous command reconciled,
normal inverter/BMS, current direction cap, temperatures within device limits,
fresh full poll, SOC10–90%. Preserve original control/command/default modes and
power limits. No new Modbus client. No artificial M1 disconnection or FAULT.

B. First validate the neutral STOP procedure under operator supervision from the
existing self-consumption state: command7 then control1 via existing HA integration,
one attempt each. Wait for two complete natural120s post-write reads (up to390s),
verify local-autoconsumption authority and device indications. A select ACK alone
is insufficient. Any partial result is UNKNOWN; do not blindly repeat or swap owner.
Returning to Remote requires a separately reviewed sole-writer step with command7
neutralized and state confirmed. This is not a charging/discharging test.

C. After STOP is commissioned and owner transfer is separately approved, first
energy test: CHARGE FROM GRID capped100W, device timeout300s, no more than one
natural120s confirmation opportunity before requesting STOP (normally120–150s).
Require SOC<95%, positive current charge cap, normal BMS and the approved plan/test
admission. Never charge a full battery or a zero direction limit. If telemetry
cannot establish effect by270s, automatic STOP attempt; no replay. Then allow up
to390s for two STOP-confirmation polls. Small power limits test energy; they do
not certify BMS parameters or physical battery-origin no-export.

D. Separately reviewed mode5 discharge test only after successful STOP/recovery:
cap100W, SOC>10%, positive BMS cap and confirmed import headroom>=1000W. Operator
may use the prepared1500W resistive load after circuit safety review. Do not change
Export Limit. Log all natural M1/B1/AC/PV/load reads with read windows and units.
Use existing independent local indications if needed; never accelerate Modbus.

E. Abort on FAULT, zero BMS limit, SOC envelope boundary, stale/failed data,
competing writer, uncertain ACK, unexpected directional power>200W for this100W
test, or any sampled M1 export while B1 discharges. Perform only the commissioned
one-shot STOP; UNKNOWN requires independent local recovery, not an automatic
controller swap. Do not change hardware safeguards or cut power as a software STOP.

## What120s observations can and cannot establish

They can confirm a bounded sequence of mode readbacks and sampled physical power,
with their actual uncertainty and gaps. They cannot prove the absence of short
battery-export transients between samples or attribute every exported watt to the
battery when PV also produces. No-export assurance must combine the applicable
inverter mode's verified behavior and installation evidence; this PR does not
claim such assurance from sparse samples. If the final procedure cannot establish
that evidence safely, discharge ACTIVE remains gated while other verified work
can proceed. No artificial network/M1 fault test is authorized by this change.

24h evaluation after actual commissioning should correlate existing plan/request
IDs, dispatch and STOP outcomes, SOC/PV/M1/B1, G13 costs and forecast errors.
Economic uncertainty alone is not a device-safety veto; physical guards remain.
