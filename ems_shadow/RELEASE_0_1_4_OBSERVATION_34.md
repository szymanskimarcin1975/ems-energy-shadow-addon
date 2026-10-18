# EMS Energy SHADOW 0.1.4-observation.34 — staged safety candidate

This is a non-actuating candidate. Publishing a branch or passing CI is not a
Home Assistant Supervisor installation and does not prove physical safety.

## Runtime change

- Validate the complete durable ownership audit (LEGACY epoch 0 through current
  owner/epoch) before trusting the local owner row or accepting a transition.
- Reject missing, duplicated, skipped or inconsistent ownership epochs.
- Reject even an idempotent replay if journal integrity is uncertain.
- Fail closed: BLOCKED, commands_permitted false, external_fence_verified false.
- Add isolated tests for ownership corruption and all unapproved handovers.
- Preserve all existing observation inputs and the persistent SQLite ledger.

## Device control remains locked

This release does NOT implement the independently trusted gateway epoch match,
persistent gateway request reservation, physical command termination/cancellation,
manufacturer-validated fallback, or externally verified no-battery-export.
The live HA gateway currently rejects EMS2 dispatch. Never change the gateway
rejection solely to deploy this candidate. Do not disable LEGACY or authorize EMS2.

## Before any Supervisor update

1. Confirm the exact currently installed add-on version and its data location.
2. Take a fresh, verified add-on backup and retain a second copy independently.
   This add-on declares `backup: cold`: collection will pause during backup.
3. Preserve the existing add-on slug, ledger_id, all source entity bindings,
   and /data; update in place, never uninstall/reinstall to upgrade.
4. Confirm the local owner journal is valid; a historically inconsistent ledger
   will fail closed and may require a supervised recovery (never fabricate audit).
5. Plan a rollback as a separately versioned package: do not restore older
   SQLite files automatically or silently backfill observation gaps.

## Acceptance after a separately approved installation

- Installed version and container label both report 0.1.4-observation.34.
- Battery readiness report continues updating, with mode READ_ONLY,
  commands_enabled false and commands_sent zero.
- LEGACY remains the owner, EMS2 authorization off, and no battery writes
  originate from EMS2.
- Observation and planning reports continue producing valid snapshots.
- On any outage or owner-audit mismatch, preserve evidence and revert by a
  separately verified procedure, never bypass the fence.
