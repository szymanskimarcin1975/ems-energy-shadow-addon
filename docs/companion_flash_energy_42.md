# .42 / gateway0.2.0-rc.3: reviewed companion delivery, bounded writes, energy integrity

Implements issue9 comment6249978069. No production component change, restart,
owner switch or physical inverter command is performed by preparing these artifacts.
The fixed120s interval, G13, CWU/CO, inverter network and BMS safeguards stay unchanged.

## Flash facts and remaining device-specific fact

Checked2026-10-18:
* Upstream Multi4.0.4 hub.py `_async_init_solaredge` emits the Storage Control flash
  warning. It is not a measurement of remaining flash life or evidence of damage.
* SolarEdge's [TerraMax technical note](https://knowledge-center.solaredge.com/sites/kc/files/se-modbus-interface-for-solaredge-terramax-inverter-technical-note.pdf)
  p19 warns about periodic parameter changes. This is a different inverter family;
  do not turn it into a numerical endurance rating for SE10K-RWB48BFN4 fw4.25.11.
* [Official HA Modbus documentation](https://www.home-assistant.io/integrations/solaredge_modbus/#supported-functionality)
  likewise warns against continuous writes to settings. It documents a different
  integration; it is not a firmware-specific classification of our registers.
* [Upstream maintainer explanation](https://github.com/WillCodeForCats/solaredge-modbus-multi/discussions/926)
  identifies Active Power Limit/CosPhi as dynamic exceptions. It does NOT establish
  that StorageControl fields have the same non-persistent behavior.

No checked source provides a verified per-register persistence map, wear levelling
or permitted writes/day for this exact model/firmware. Treat the following as
potential nonvolatile writes, without claiming all are proven flash writes:

| Existing Multi4.0.4 field | Address from source, not a new direct-write path |
|---|---:|
| control_mode |57348|
| default_mode (not written by EMS2) |57354|
| command_timeout |57355|
| command_mode |57357|
| charge_limit |57358|
| discharge_limit |57360|

Use event-driven schedule boundaries with fixed limits/timeout where possible,
not120s refresh commands or continuous limit tracking. Identical desired state is
not rewritten to refresh a timer; if there is no change the request is refused as
IDENTICAL_SETTINGS_NO_WRITE_NO_TIMEOUT_RENEWAL. Elapsed timeout is still not proof
of cancellation. Do not replace Storage Control with Active Power Limit/CosPhi:
those control a different quantity and do not solve battery no-export.

Exact missing technical confirmation, if endurance must be established: identify
which of57348,57355,57357,57358,57360 persist on SE10K-RWB48BFN4 fw4.25.11, whether
identical-value writes are coalesced, which writes refresh the Remote timer, and
permitted sustained event rate/flash endurance. No contact with the manufacturer
was made. A short hardware test cannot certify years of flash life.

## Implemented local write protection

* Compare fresh complete poll raw settings to desired values; skip identical
  timeout/limit/mode/control values. No extra poll, Modbus client or direct register.
* Reserve the WHOLE ordinary settings batch atomically in the existing gateway
  SQLite before its first write. A rejected local budget cannot partially apply it.
* Persist per-setting value, role, request ID, emergency flag, time and state:
  RESERVED_UNKNOWN → ATTEMPTED_UNKNOWN → SERVICE_RETURNED or UNKNOWN;
  unchanged settings recorded SKIPPED_READBACK. SERVICE_RETURNED is not physical ACK.
* Pending/unknown journal rows count as possible writes, even after restart; no
  release of budget merely because an ACK is absent. Repeated batch/role refuses.
* Require an explicitly configured local policy. Example for independent review:

```yaml
write_policy:
  basis: LOCAL_EMS_WRITE_BUDGET_NOT_MANUFACTURER_LIMIT
  minimum_interval_s: 900
  maximum_writes_per_24h: 24
```

These numbers are an EMS proposal, NOT SolarEdge specifications or proof of safe
flash life. No policy is enabled on production by this PR. Missing/invalid policy
blocks ordinary dispatch before writes. Counter counts changed setting writes,
not planner cycles; several fields may be necessary in one command batch.
* STOP bypasses the economic interval/budget but retains owner, external-writer
  fence, commissioned procedure and durable one-attempt checks. STOP itself is
  audited; it is not delayed for wear savings. No retry of UNKNOWN.

The120s effect/STOP state machine remains intact. No simulated result claims
physical STOP, instantaneous no-export, or device endurance certification.

## Counter evidence and safe accounting

Owner's actual warnings: import10098→3004Wh and export13270→1873Wh. Read-only HA
check still showed10.098/13.27kWh: Multi4.0.4 restores its last native values and
rejects lower raw values when allow_battery_energy_reset is false. This explains
why UI can stay at the prior maximum, NOT why raw firmware counters went backwards.

Exact source definitions are uint64, little word order, Wh at57718(export) and
57722(import). UI kWh is a unit conversion, not evidence for changing raw scaling.
A hardware counter reset, firmware behavior or endpoint/history mismatch remain
unresolved without before/after raw values tied to the same actual serial/endpoint.
Do not reset HA statistics, change allow_battery_energy_reset, alter scaling or
rewrite historical databases to make the graph look monotonic.

New separate `battery-energy-integrity.sqlite` preserves intervals and segment
boundaries. Any decrease has null usable energy deltas, raw negative diagnostic
deltas kept separately, usable_for_cost=false and cause UNCONFIRMED. Gaps rebaseline;
restart preserves boundaries. No cross-reset energy or false negative costs.
HA restore-filtered values are explicitly NOT independent raw-counter proof and
are not approved for cost/efficiency calculations by this ledger.

HA currently exposes one visible logical B1 maximum-energy entity9.2kWh. Two
physical modules do not justify B1×2. The aggregation helper only sums distinct,
explicitly inventoried BMS endpoints once, with the same interval and complete
valid evidence. No new B2 is invented. If another endpoint is found later, verify
its serial/coverage before changing aggregation. These checks do not assert the
absence of disabled/hidden B2 or deduce individual module capacity from one sensor.

## Practical companion installation — existing Windows SSH, no long commands

Artifact `ems-companion-windows-installer.zip` contains a PowerShell installer and
exact patched hub/manifest payload. It does NOT download latest upstream or4.0.8.
Uses built-in Windows PowerShell/OpenSSH and the already authorized SSH key.
No new HA tools, credentials, .storage editing or authentication bypass.
No ExecutionPolicy bypass is included; review/trust the downloaded GitHub
artifact per Windows policy before running it.

1. Download/extract the CI artifact; compare SHA256SUMS with the reviewed commit.
   Pause automatic HACS updates for this component via its supported UI before
   the maintenance operation. Do not add another HACS repository with the same
   domain or select4.0.8. The alternative is ordinary custom-component code
   deployment over authorized SSH, preserving domain, config entry and entities.
2. In the extracted installer folder run the short command:

```powershell
.\EMS-Companion.ps1
```

   Default is Prepare. It asks only SSH host and completed full-backup slug. For
   this operation verify a052cf15. Catalog check found it661.4MB, backed_up/idle;
   catalog presence is NOT archive integrity or proof of full content. Installer
   independently requires Supervisor full-backup metadata before proceeding.
3. Prepare verifies exact installed4.0.4 hub/manifest hashes, copies the ACTUAL
   installed component to `/config/ems_companion_backups/<timestamp>`, computes
   per-file SHA256, downloads this code backup to Windows and verifies every file.
   It refuses a differing source. No installation/reload/restart. Keep its
   prepared.json and the independent Windows copy. Do not publish those backups.
4. Apply only in the approved Core maintenance window after inverter state,
   writer exclusivity, recovery access and CWU schedule interruption are reviewed.
   Script never stops/starts Core and refuses Apply while Core is running:

```powershell
.\EMS-Companion.ps1 -Mode Apply
```

   It verifies backup again and transfers just reviewed hub.py/manifest.json,
   preserving file permissions and verifying installed hashes. All other
   component files, entity registry, options, /data and SQLite remain untouched.
   Manifest pins the already reviewed dependency versions; no Core library files
   are overwritten. Candidate/entry opt-in and physical authorization stay OFF.
5. After reviewed Core start, verify4.0.4+ems.1, existing entity IDs/normal120s polls,
   candidate still READ_ONLY, owner unchanged and physical commands0. Enabling
   `ems_single_attempt_entries` is a separate reviewed configuration action;
   deploying files alone does not grant write authority.
6. If code recovery is required, through independent SSH/Windows with Core stopped:

```powershell
.\EMS-Companion.ps1 -Mode Rollback
```

   It verifies the actual saved code backup, preserves failed code, restores the
   complete original component and checks hashes. It does not restore .storage,
   Recorder or any SQLite, and does not re-enable LEGACY. Supervisor must remain
   reachable for the stopped-Core guard; local code recovery is independent of MCP.
   If Supervisor itself fails, do not improvise live replacement or claim this
   script can safely manage a running Core without a state check.

CI validates PowerShell syntax and exercises Prepare/independent-download hash
verification plus live-Core/partial-backup refusals with MOCKED SSH. It is not a
production SSH installation test. Actual on-server per-file backup has NOT been
made by this agent because current MCP does not expose that filesystem.

## First device test — unchanged approval boundary

After review/install/real backup, retain ownerLEGACY and authorizationOFF until the
complete commissioning protocol is accepted. First neutral command7/control1
procedure under ONE operator/writer, preserve original settings, observe two
natural120s polls. Fresh dedup may skip already correct values. Do not send an
energy command merely to test audit or flash writes.

Only after neutral STOP/recovery is proven: separately approved low-power charge
while SOC<95% and positive actual BMS cap;100W, timeout300s, normally one natural
poll120–150s then explicit STOP, confirmation up to390s. At current reportedSOC100%
and preserve-charge status, charging is NOT permitted. Discharge/no-export requires
its own applicable evidence; sparse120s samples cannot exclude short transients.

Abort on fault, stale/ambiguous data, direction cap0, SOC bound, competing writer,
unknown write outcome or sampled unintended battery export. Use only commissioned
STOP/local recovery; no automatic LEGACY restart or blind retry. Restore recorded
settings only after confirmed safe local state, by the sole authorized writer.
No physical test, owner switch, flash endurance experiment or artificial outage
is performed by this PR.
