# Actuation gateway candidate — issue #9 / comment 6248775724

This PR is for independent code review, **not installation or activation approval**.
Production remains .39, LEGACY / READ_ONLY / authorization off. No hardware test
or HA production change is part of this PR. No change to G13, PV forecasting, CWU,
CO, operational SOC 5–95%, old ledgers or the historical SQLite checks.

## Implemented candidate

- ACTIVE dispatch requires HA administrator/internal service authority. The gateway
  independently verifies current household plan, fingerprint, slot, request/plan IDs
  and control approval; a syntactically valid caller-supplied hash grants no authority.
- ACTIVE and SHADOW use `ems_epoch_gateway.dispatch`. An omitted execution mode
  is READ_ONLY; ACTIVE must be explicit. Default integration setup still uses
  the existing non-actuating journal and exposes no hardware authority.
- Optional YAML `ems_epoch_gateway.actuation_candidate` loads the candidate only
  with `enabled: true`; `physical_authorized` is independently false by default.
  Do not enable it in production from this PR. No edits to `.storage` are needed.
- The HA adapter uses only registered SolarEdge entity services: command mode,
  storage charge/discharge limit and command timeout. It checks platform,
  config entry, unique-ID suffix and inverter device binding. It never writes
  raw Modbus registers, Export Limit, control/default mode or network settings.
- SQLite `trusted_owner` remains the authority. Owner transitions are CAS on
  expected epoch, serialize with durable command reservations, require prior
  command reconciliation and reject unresolved requests. Both old and new
  journals reject reused request IDs. Reconciliation evidence must postdate
  quiescence of known HA writers; an absent termination observer blocks even
  owner transition, not merely command execution. Restart disarms and preserves UNKNOWN;
  ACK means active, not ended. A DB transaction cannot atomically change a HA
  helper or exclude a direct external Modbus client: failure leaves execution
  blocked. Helpers are informational and additional negative interlocks.
- Known HA writers must be off/current=0. External writers require separate,
  device-bound, expiring commissioning evidence; a helper or caller assertion
  cannot provide this proof. No service automatically disables/enables LEGACY.
- Directional SOC: no charge at/above 95%, no discharge at/below 5%; actual SOC
  100% is preserved and can theoretically move inward. BMS status, current zero
  directional power, missing data and alarms still refuse commands.
- A successful HA service call is only transport acknowledgement. A later full
  Modbus poll must show correlated mode/power settings and actual B1 response.
  Timeout, cancellation, partial write, wrong identity or missing confirmation
  persist UNKNOWN with no replay. Commands are monitored; stale/invalid inputs
  or expired plans latch STOP. No automatic resume or automatic LEGACY restart.

## Read provenance and upstream evidence

Reviewed upstream SolarEdge Modbus Multi **v4.0.4**, commit
`d38d890887684ddd7938c4bce5223d387b24c6a7`:
https://github.com/WillCodeForCats/solaredge-modbus-multi/tree/v4.0.4

- `hub.py::async_refresh_modbus_data` reads inverter, meter and battery in a
  completed poll; errors propagate. The coordinator is a
  `TimestampDataUpdateCoordinator`. The candidate copies raw values in its
  completion listener, without forcing refresh or opening a second client.
- An unchanged B1 `last_updated` alone **does not prove two hours without device
  reads**: a constant value need not change HA state timestamps. This PR does
  not diagnose a device outage from that timestamp. Poll completion proves a
  successful register read, **not** an internal BMS sample clock. The whole poll
  window uses its conservative timeout bound; without an acceptable bound or
  successful poll, writes are refused. No invented device timestamp.
- Existing entity controls are implemented by `select.py::StorageCommandMode`
  and `number.py::StorageChargeLimit/StorageDischargeLimit/StorageCommandTimeout`.
  Modes from upstream: PV charge=2, solar+grid=3, minimize import=5, self use=7.
- v4.0.4 retries uncertain writes three times. The .40 follow-up provides an
  offline, exact-source companion patch scoped to an explicit entry allowlist and
  StorageControl only. It pins the lower transport and checks its capability.
  See [installation candidate and hardware protocol](installation_candidate_40.md).

## STOP and fallback

HOLD never cancels an active command. The connected .40 observer watches the
reviewed command7 -> control1 local-autoconsumption procedure after one durable
STOP attempt. Two complete post-write polls are required; HA ACK, mode7 alone and
elapsed3600s are insufficient. A device-specific commissioning witness is still
required before ACTIVE; synthetic tests never create such evidence.

UNKNOWN remains blocked across restart and repeated STOP cannot retry. Software
observation establishes local-authority readback under a commissioned procedure,
not physical proof of timer expiry or transient battery no-export. See the .40
protocol for fast measurements, abort criteria and independent code recovery.

## Before any installation / first hardware test

1. Independently review this PR and CI. Install only with the actuator unconfigured
   or disabled; retain .39 and original gateway backup for code-only rollback.
2. Confirm entity bindings and a successful complete Modbus read of M1/B1, with
   explicit read window, latency and current BMS limits. Do not infer freshness
   from a repeated template event or `last_changed` alone.
3. Review the pinned, entry-scoped companion and transport CI evidence. Its
   installation is separate from the default READ_ONLY addon update.
4. Inventory/fence all actual writers including direct external clients. Record
   quiescence and confirm end of the old command after quiescence. Merely waiting
   3600 seconds, seeing SOC 100%, mode 7 or 0 W is not termination proof.
5. Commission a device-specific stop/termination observer and fallback; prove
   battery no-export for mode 5 with synchronized physical measurements. PV
   export remains allowed. The margin and simulator cannot prove transient
   no-export with 120-second telemetry. No general site export limit is changed.
6. Owner explicitly approves a direction, limited power and short duration only
   after these prerequisites. Record pre-state and local recovery access. Never
   test charge when SOC >=95%, BMS charge limit is 0 W or status is unapproved.
7. In an isolated environment first: LEGACY writes fenced, old command ended,
   CAS owner epoch, helper sync, explicit physical authorization, one request,
   ACK + device response, verified termination, then rollback. Any ambiguity:
   UNKNOWN + blocked, no duplicate command, no concurrent LEGACY restart.

The temperature envelope is device-evidence-based, not invented. Operating SOC
5–95% is not a statement about internal BMS protection thresholds. Missing
physical evidence is listed here, not replaced with a simulation PASS.
