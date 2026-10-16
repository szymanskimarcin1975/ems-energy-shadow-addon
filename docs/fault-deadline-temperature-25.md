# Observation .25: fault gate, workday deadline and local temperature

No ownership or hardware settings change. READ_ONLY remains required in production.
The legacy observer and its source fingerprint are unchanged.

## Fault gate

The executor now requires healthy inverter status and vendor status from explicit
private source mappings. Missing mapping, FAULT, nonzero vendor error, stale,
future, out-of-order or ambiguous readings block new EMS2 commands. Readiness
requires three distinct HA publication pairs spanning at least 240 seconds;
repeated retrieval cannot advance readiness. Each source must be within 180
seconds and pair skew within five seconds. These are HA publication checks,
not proof of physical measurement time or inverter fallback.

Readiness is invalidated on worker restart and after a fault or communication gap.
State is stored only in the independent execution SQLite. The gate is checked
again in the production execution path before any command transport. Blocking
new commands does not cancel an already active inverter command. Hardware
fallback, export protection, BMS operating limits and external-writer fencing
remain separate mandatory evidence gates.

## Advisory deadline

The household scenario now minimises workday SOC shortfall at 16:00, then
estimated import cost. The target is applied at the END of the 15:00 slot,
not at the end of 16:00. Exact capacity is a reachable discretisation endpoint.
A zero BMS charge ceiling leaves the deadline explicitly unreachable; no energy
is invented. Future workday and nonworkday scenarios remain separate. A partial
current hour is not modelled and that limitation is reported. Prices, capacity,
efficiencies and household load remain advisory assumptions, not authority to
control devices. No accepted boiler integration logic is changed.

## Temperature input

The demand worker forwards the fresh real local temperature into the forecasting
feature pipeline. For leads up to two hours, experimental temperature persistence
uses that local measurement; for later hours the separate weather forecast is
used. This is not a permanent forecast correction. The existing seven independent
training-day gate and no-extrapolation rule remain. Insufficient training uses
actual register-based persistence, explicitly without an identified temperature
response. No fabricated training data, CO attribution or forecast accuracy claim.

## Rollback

Retain the previous release code. Restore code only through the supported add-on
update procedure; never overwrite current databases with older copies. New tables
are in the execution database only and are ignored by the previous code. Restoring
previous code removes this additional fault gate, so EMS2 must remain READ_ONLY.
Do not change owner, authorization, BMS settings, legacy ledger or its seven sources.
Container tests are not Supervisor rollback or physical fail-safe tests.
