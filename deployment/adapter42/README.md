# .42 adapter binding — PREPARED ONLY, no production change

Base: main 2427748fae954e4724d6a14219e81963a9475207, addon .42,
gateway 0.2.0-rc.3. No runtime code, version, tariff or planner changes.

## Root cause verified 2026-10-19 15:58 Europe/Warsaw

Production configuration.yaml has no `ems_epoch_gateway.actuation_candidate`.
`async_setup_entry` therefore instantiates EpochStore, not HASolarEdgeAdapter /
ActuationGateway / ControlStore. The existing six services being registered does
not prove that the actuator engine is running. Current `status` has no
`physical_adapter_implemented` and reports `trusted_epoch_transition_implemented=false`.

Important: `physical_dispatch_supported=false` is ALSO correct when an adapter
is loaded but authorization is OFF. After a disabled installation, require
`physical_adapter_implemented=true`; do NOT expect physical dispatch to turn true.

## Prepared, not installed

`actuation_candidate.yaml` is JSON syntax valid as YAML. The content is the
subtree for the following proposed addition to configuration.yaml:

```yaml
ems_epoch_gateway:
  actuation_candidate: !include ems_shadow/actuation_candidate.yaml
```

Do not duplicate an existing domain block. No script in this change writes HA.
Read-only HA observations supplied the entry ID, six exact control entity IDs,
inverter model/firmware/serial, B1-reported serial and existing 3600s timeout.
I1/B1/M1 numeric endpoint IDs follow the existing names; complete-poll identity
and registry binding must still be checked when loaded, before commissioning.
The matching reported inverter and B1 serial does not identify each physical
battery module separately.

Safeguards in the prepared subtree:
- `enabled=true` loads the engine only; `physical_authorized=false` remains OFF.
- Existing owner helper LEGACY, authorization helper OFF; do not change either.
- EMS operating envelope 5–95%, not BMS protection limits. Current SOC below 5%
  does not prove a BMS fault; EMS discharge is refused, charge still requires
  every other guard. Factory self-consumption is not changed by this file.
- Natural complete polls only, cadence 120s unchanged, no second Modbus client.
- 180s maximum poll age / 30s maximum complete read-window are existing software
  admission caps, NOT a change to the read frequency. A longer real read window
  is a blocker, not a reason to falsify the cap.
- `verified_evidence` entries all false, no forged dates/device confirmations.
- `write_policy=null`, `import_margin_w=null`: no invented flash lifetime or
  untested import margin. Must be explicitly reviewed before physical activation.
- 3600s is the read existing setting, not proof of command expiry or safe fallback.
- Existing planner fingerprint/scenario must match the live report at installation.

## Existing .42 runtime behaviour retained

The adapter already implements service writes to the bound SolarEdge entities,
SOC/directional BMS limits/FAULT/complete-poll admission, persistent reservations,
no retry of UNKNOWN, deduplication and write audit. STOP is separate from HOLD:
one-shot command mode 7 plus control mode 1 revokes Remote Control authority,
then two completed natural post-write polls are required. WAITING_STOP timeout
is 390s; uncertainty stays UNKNOWN and never transfers ownership automatically.
A service return is not physical confirmation. Merely enabling the engine does
not authorize services, commission STOP, enable the addon or change the owner.

## Concrete approval scope: disabled installation only

1. Confirm a current usable backup and independent SSH code/config rollback.
   Copy the actual configuration.yaml and gateway source with SHA-256. Do not
   copy active SQLite files as ordinary files. Confirm no unresolved requests;
   schedule outside required CWU actions. Existing automations stay as they are.
2. Confirm the reviewed single-attempt SolarEdge 4.0.4+ems.1 companion is actually
   installed and opted in for this config entry. Its status is not established
   by the present MCP reads. Do not install 4.0.8, change poll interval or blindly
   enable an integration option. If missing, handle companion separately with
   its already reviewed backup/hash installer and approved maintenance window.
3. Install only this file under /config/ems_shadow/ and the include above after
   HA configuration validation. No actuation runtime patch is needed.
4. A short approved Core restart is needed to ingest this YAML (`async_setup`),
   not merely an integration reload. Owner/auth remain LEGACY/OFF. Initialization
   adds control tables to the existing journal and disarms physical_enabled;
   it does not restore or delete request history. Abort if unresolved work exists.
5. Read status: adapter implemented true, owner LEGACY, epoch 0, physical false,
   no unresolved commands, no device writes. Observe two natural complete polls;
   verify bindings, identity, poll duration and healthy telemetry. Do not invoke
   dispatch/STOP/transition_owner/EMERGENCY STOP for this acceptance.
6. On loading failure, restore the copied YAML/code via independent SSH and
   approved restart. Never restore older SQLite/.storage to roll back this code.

Estimated disabled configuration installation: 10–15 min after backup/access
and maintenance checks. Observe at least two natural 120s polls (up to ~5 min).
No production changes have been made by preparing this proposal.

## Separate first device STOP commissioning — not authorized by this change

A circular prerequisite must NOT be solved by setting `device_test_passed=true`.
The first neutral operation must be an explicitly approved, supervised manual
operation through the existing SolarEdge integration, under one exclusive writer
with an independent recovery path. The candidate's first STOP remains gated.

Before approving that test: all writer paths fenced (not just four automation
states), current healthy I1/M1/B1 and limits, known local recovery, installer
single-attempt transport verified; owner present and continuous local monitoring.
No intentional charge or discharge, no M1 disconnect, no network fault injection.
Record the actual existing modes. If command mode is already 7, do not rewrite it.
The proposed neutral step is returning control to local Maximize Self Consumption
(control 1); this is a physical write requiring separate approval and validation
on this inverter, not a behaviour already proven by this document.

Observe two complete post-write polls at natural 120s cadence: control 1,
command/default 7, healthy status, SOC and M1/B1/PV, no contradictory writer.
Budget 5–7 min for observation, 15–20 min including supervised preparation.
An ambiguous reply/readback means UNKNOWN: do not repeat or automatically start
LEGACY/EMS2; use the separately confirmed local recovery procedure.
This test proves neither natural timeout behaviour nor loss-of-M1 behaviour.
It also cannot prove absence of short battery-export transients at 120s cadence.

## No-export / remaining commissioning evidence

Current M1 A/B/C are available but the .42 admission/STOP observer uses TOTAL M1.
An aggregate import can coexist with export on one phase. A claim of zero battery
export on each phase is therefore NOT validated by current software/120s sampling.
Do not enable general Export Limit (PV export must remain possible), do not
shorten polling or open another client. Discharge mode5 is only a candidate;
require device-specific proof of its actual phase policy and response/fallback
before commissioning. Missing physical no-export, fallback and writer-fence
proofs remain false. No internal undocumented BMS SOC threshold is demanded.
Thermal permitted envelope and real direction permission also remain required.
