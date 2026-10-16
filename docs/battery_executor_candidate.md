# Battery executor candidate — not an activated controller

The new module is an importable real Home Assistant API actuator, not a scheduled runtime. No release version or gateway entrypoint changed. Defaults: enabled=false, soc_min=null, soc_max=null, soc_bounds_approved=false. Disabled calls never access HA, SQLite or lock files.

Rated energy 9200 Wh and configured power ceilings 5000 W are not BMS SOC limits or proof of current dynamic power allowance. Operating SOC limits need explicit operator approval and manufacturer compatibility verification.

The command journal is separate from observer ledgers. Intent is committed before an API write. PENDING or UNKNOWN survive restart and block new commands pending external reconciliation; never automatically retry ambiguous operations. Fresh mode state is an acknowledgement of the HA entity only, not proof of physical battery response.

Local flock serializes this module only. Reading old automation state off/current=0 is necessary but does not provide a persistent external fence against manual calls or re-enabling other automations. handover_verified must remain false until a real ownership/fencing mechanism and recovery are independently tested. No code automatically disables or resumes the old controller.

Only Charge from Solar Power and Discharge to Minimize Import are allowed. Discharge to Maximize Export is forbidden. A mode allowlist alone is not a verified hardware no-export guarantee, especially during stale measurement or timeout transitions. no_export_verified and fallback_verified must remain false pending validation.

Remote timeout/default-mode configuration must be read and independently verified on the actual inverter. Do not deliberately let a live command expire while another controller owns the battery. No protection claims against unvalidated fallback behavior, arbitrary privileged writers, host failures, or BMS limits not exposed by HA.

Activation NO-GO: runtime scheduling/guard watchdog, durable external ownership, real fallback validation and explicit SOC approval are not complete. Container CI is not a Supervisor handover test. Current observers and CWU remain unaffected. Rollback before activation is code-only because candidate is not imported by runtime. No historical SQLite restoration is required.
