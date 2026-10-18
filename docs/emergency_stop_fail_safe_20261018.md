# EMS2 Emergency STOP — 2026-10-18

## Implemented in gateway 0.1.1 candidate

The HA-side `ems_epoch_gateway` now provides:
- `ems_epoch_gateway.emergency_stop`: latches a reason code, optional request ID/owner epoch, bounded structured evidence and timestamp in the gateway SQLite database.
- `ems_epoch_gateway.status`: exposes the latch and most recent incident metadata.
- Dispatch reservation returns `EMERGENCY_STOP_LATCHED` while the durable latch is set, including after HA restart.
- There is no automatic-clear or resume operation in this version.
- A persistent HA notification is attempted when the stop service succeeds.

The gateway still has no physical SolarEdge dispatch transport and still rejects all dispatch requests. The STOP latch therefore protects the HA command boundary for new EMS2 requests, but this CI does not prove a physical inverter stop.

## Required semantics

1. A successful latch means only that new gateway reservations are blocked.
2. It does not cancel or neutralize a previously accepted SolarEdge Remote Control command. Its state remains `UNKNOWN_ACTIVE_COMMAND` until separately reconciled.
3. No automatic LEGACY fallback, inverter reset, register write, battery action, or restart is attempted.
4. If HA is unreachable, the call outcome must be treated as UNKNOWN; do not retry an energy command. An operator must confirm the stop state through `ems_epoch_gateway.status`.
5. This candidate has a manual emergency-stop service, but it does not yet install automatic HA triggers for every fault source. Existing executor quality/fault checks continue to block its own new requests; wiring each detection source to the durable HA latch requires a separately validated source mapping and integration test.
6. Resume requires operator-controlled reconciliation: resolve cause, fresh/credible telemetry, coherent owner/epoch, no competing writer, reconcile any active command, and independently verified BMS, fallback and no-battery-export safeguards. This version has deliberately no reset service.

## Verification

Synthetic-only GitHub Actions test checks SQLite persistence across reopen, blocked dispatch after latching, no auto-clear, bounded evidence, and audit event history. No HA host, inverter, BMS or physical command is involved.
