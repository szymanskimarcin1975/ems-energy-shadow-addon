# EMS2 ownership / idempotency integration review (2026-10-17)

Status: **BLOCKED FOR PHYSICAL HANDOVER**. Review only. No inverter writes.

## Verified candidate implementation
- `ems_shadow/app/ownership.py`: SQLite WAL + FULL synchronous, monotonic owner epoch, request-id transition audit, crash/reopen checks. `commands_permitted` remains false; external fencing unverified.
- `ems_shadow/app/battery_executor.py`: SQLite `commands` primary-key request ID, `command_identity` with plan_id and expected owner_epoch. On retry, returns duplicate/conflict; pending/unknown blocks fresh commands. Serializes in-process executions using flock.
- `ems_shadow/app/dispatch_lifecycle.py`: transport acknowledgement does not count as device termination.
- `ems_shadow/tests/test_ownership.py` and `test_dispatch_identity.py`: already cover restart, conflict and unknown outcomes.
- `tests/offline_fencing/`: a reference-only prototype, **not** a replacement for existing production database, and must not be wired to device transport.

## Remaining gaps before live handover
1. **Bridge trusted epoch to HA gateway.** HA `script.ems_battery_command_gateway` currently validates owner_epoch *format* and echoes it, but has no independently trusted authoritative epoch for comparison. Echoing a caller-provided epoch is not fencing.
2. **Boundary atomicity.** The executor SQLite identity, HA queued service, and physical Modbus side effect are not a single atomic transaction. Reconcile outcomes explicitly; never retry unknown.
3. **External writer inventory.** HA queue excludes neither installer actions nor other Modbus clients; establish verifiable exclusive-writer control.
4. **Device termination and recovery.** Timeout configuration is not an observed cancellation acknowledgement; physical fallback test must be supervised.
5. **BMS and export.** Approved actuation SOC envelope and no-export verification remain absent.

## Next safe integration test (mock only)
- Start at LEGACY owner epoch 0 and authorization OFF. Expect EMS2 dispatch rejected before writes.
- Simulate durable owner transition only in isolated test DB; compare EMS2 local expected epoch vs HA mocked trusted epoch. Stale epoch rejected, no dispatch.
- Simulate two identical request IDs and one same ID with changed command; no second device call.
- Simulate service-timeout/partial response, restart executor; state remains UNKNOWN and no retry.
- Do not enable gateway EMS2 physical path until all physical preflight blockers are independently closed.

No production HA scripts, automations, inverter or battery settings changed by this document.
