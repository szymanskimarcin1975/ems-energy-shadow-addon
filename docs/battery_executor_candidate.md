# Battery executor candidate — not an activated controller

The executor module is an importable Home Assistant API actuator, not an activated actuator runtime. Observation.13 and later schedule a separate supervised battery_runtime.py readiness worker. That worker has its own GET-only transport, never constructs the actuator transport, never opens an observer ledger, and publishes battery_executor_report.yaml in the existing private report directory. It cannot send device commands. Defaults: enabled=false, soc_min=null, soc_max=null, soc_bounds_approved=false. Disabled calls never access HA, SQLite or lock files.

Rated energy 9200 Wh and configured power ceilings 5000 W are not BMS SOC limits or proof of current dynamic power allowance. Operating SOC limits need explicit operator approval and manufacturer compatibility verification.

The command journal is separate from observer ledgers. Intent is committed before an API write. PENDING or UNKNOWN survive restart and block new commands pending external reconciliation; never automatically retry ambiguous operations. Fresh mode state is an acknowledgement of the HA entity only, not proof of physical battery response.

Local flock serializes this module only. Reading old automation state off/current=0 is necessary but does not provide a persistent external fence against manual calls or re-enabling other automations. handover_verified must remain false until a real ownership/fencing mechanism and recovery are independently tested. No code automatically disables or resumes the old controller.

Only Charge from Solar Power and Discharge to Minimize Import are allowed. Discharge to Maximize Export is forbidden. A mode allowlist alone is not a verified hardware no-export guarantee, especially during stale measurement or timeout transitions. no_export_verified and fallback_verified must remain false pending validation.

Remote timeout/default-mode configuration must be read and independently verified on the actual inverter. Do not deliberately let a live command expire while another controller owns the battery. No protection claims against unvalidated fallback behavior, arbitrary privileged writers, host failures, or BMS limits not exposed by HA.

Active-control NO-GO: actuator scheduling/guard watchdog, durable external ownership, real fallback validation and explicit SOC approval are not complete. The read-only readiness worker is supervised by the existing identity/progress guard. SetApp access is not required for read-only installation; manufacturer-specific limits not exposed by HA must be obtained from documented device interfaces or the installer before active control. Container CI is not a Supervisor handover test. Current observers and CWU remain unaffected. Rollback before activation is code-only because candidate is not imported by runtime. No historical SQLite restoration is required.
 
## Observation.14
Readiness compares serialized REST timestamps with direct in-memory State properties obtained by a fixed read-only /api/template request. Both are retained; neither is declared a device measurement timestamp. Unavailable values remain rejected even when HA recently wrote them. Reports expire after 60 seconds.

The new battery-ownership.sqlite is separate from all energy ledgers. Initialization preserves LEGACY ownership. Compare-and-swap epochs, audit records and request IDs are transactionally durable. TRANSFER_PENDING and BLOCKED survive restart and do not auto-resume a controller. This is a LOCAL protocol only: the old HA automation is not yet routed through it. external_fence_verified remains false and commands_permitted remains false. Installing the readiness worker must not be reported as a completed global single-writer handover.

Source explanation: HA Core 2026.10.0 StateMachine.async_set mutates last_reported for unchanged state/attributes without rebuilding the cached JSON representation used by APIStatesView. No HA Core modification is included.
