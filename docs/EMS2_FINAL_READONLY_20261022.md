# Consolidated read-only candidate, 22 October 2026

Production remains addon .43, owner LEGACY, authorization OFF. No commissioning evidence is manufactured by this PR. Version .44 remains the separately reviewed forward recovery to original .42; it is not reused here.

## Scope

Reuse the disabled adapter bindings from PR22 without merging PR22–24. Preserve the production planner fingerprint. No POWER_SAVING or fingerprint-format change is introduced while the current contract agrees. Fix only the identified adapter lifecycle defects and expose the reason for the new planning storage guard failure. No database deletion, limit increase, VACUUM, migration or production write is performed.

## Admission versus monitoring

Initial mode5 admission requires confirmed import headroom and live BMS ceilings. Once discharge supplies the home, residual grid import is no longer the initial demand: monitoring retains the BMS ceiling and refuses observed grid export, without reconstructing AC demand from battery DC power. This is conservative aggregate telemetry supervision, not proof of physical no-export on every phase or between 120-second polls.

Admission must preserve valid STOP and writer-fence evidence for the full device command lease, transport budget and STOP observation window. HOLD remains no new command; it does not cancel an existing inverter command. UNKNOWN is durable and never automatically replayed.

## Production integration evidence

At 17:00 CEST the actual whole-boiler meter `sensor.0x286847fffef5f4e9_power` reported 1372 W and energy 275.37 kWh. Individual phases are asynchronously updated (1330/13/0 W in that snapshot); they must not be summed as a synchronized reference. The heat-pump submeter is a subset and must not be added to the whole-boiler total. This reading identifies available sources; it does not independently prove the installed observer options. CWU automation remained ON. No CWU, CO or G13 setting is changed.

At 17:01 CEST production .43 reported `PLANNING_STORAGE_LIMIT`, stage observe, planning_runtime.py:185. Thus earlier ready plans do not establish current continuous readiness. The old guard conflates database+WAL+SHM >=256 MiB and free disk <64 MiB. Obtain bounded sizes/free-space diagnostics before selecting recovery. Do not delete history, silently raise thresholds, copy live SQLite with cp, or treat this as a sensor failure.

## Disabled installation acceptance (separate operation)

1. Verify a current usable backup of addon data and EMS config, source hashes, and an independent recovery path. Backup 2ff31f67 is the known pre-.43 backup; verify its continuing availability before installation.
2. Verify exact single-attempt SolarEdge 4.0.4+ems.1 companion and entry opt-in. Keep 120-second polling, no second client.
3. Install reviewed gateway code and disabled YAML only after approval of the exact package. Validate HA configuration. A Core restart is needed to load YAML, and is not performed by this PR.
4. Read status after restart: adapter implemented, LEGACY, authorization OFF, no unresolved requests, zero new physical writes. Observe two natural complete polls. Do not dispatch or STOP for disabled acceptance.
5. If loading fails, restore copied code/YAML and approved restart. Do not restore old SQLite over current ownership/request history.

## Controlled commissioning: not executed or authorized by this PR

All writer paths must be fenced, including external clients, not merely disabled four HA automations. Record current owner/epoch, pending work, exact device identity and complete live M1/B1/SOC/BMS/thermal data. The operational range is 5–95%; undocumented internal numeric BMS SOC bounds are not an additional requirement.

First independently qualify the neutral STOP/local self-consumption operation under explicit physical-test approval and local recovery availability. Do not certify it by editing evidence. Preserve prior settings and single-writer control; avoid needless identical writes. Confirm two natural post-write complete polls at the unchanged 120s cadence. A service return, zero power or elapsed 3600s alone does not confirm termination.

Only after STOP/fallback, phase policy/no-export, single-attempt transport and writer exclusion are actually confirmed may a separate approval permit transition. Freeze old writes, establish verified termination, reserve a new durable owner epoch, enable EMS2 through the same serialized gateway, then execute one bounded device test. During WAITING/UNKNOWN block new commands and owner changes.

Rollback is not an immediate second writer: block new EMS2 admission, execute only the commissioned termination procedure, verify device termination and no unresolved request, then transition epoch/owner and enable the preserved LEGACY paths. If termination is UNKNOWN, keep the fence and use the confirmed local recovery procedure; do not automatically reactivate LEGACY.

## Remaining physical evidence

- STOP/local fallback and behavior after lost HA/Modbus/M1 on this firmware.
- Mode5 phase policy and actual battery no-export while allowing PV export. Aggregate 120s telemetry cannot exclude short transients.
- Actual directional BMS permissions and confirmed thermal envelope; zero/missing limits remain fail-closed.
- Exclusion of external writers, companion single-attempt patch and reviewed flash-write policy.

No ACTIVE readiness is claimed from simulated tests alone.
