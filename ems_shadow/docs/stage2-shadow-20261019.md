# Stage 2 candidate — 2026-10-19

Base: prepare/adapter42-disabled, 245df7d94eb335fec9cc75f9bfcddc87a901053e.
No production deployment, HA writes, inverter commands or authorization changes.

## Changes

- Recognise B_STATUS_POWER_SAVING in advisory snapshot validation only when
  battery power is exactly zero. Missing, invalid and nonzero power still reject
  the snapshot. FAULT, unknown status and all freshness/skew checks remain.
  This does not add the status to any actuation/BMS approval list.
- Freshness continues to use last_reported, not the time the value changed.
  Regression tests cover unchanged values with old last_updated/last_changed,
  stale/future/missing/malformed last_reported, and no device-clock assertion.
- Compute the planning fingerprint from configuration and approved SOC policy,
  excluding only the runtime result applied_to_simulation. Input/policy changes
  still change the digest. Executor mismatch/missing/invalid pins remain blocked.
  This intentionally changes the fingerprint format; no automatic pin update.

## Validation

117 weather/planning tests and 383 observer/executor tests passed locally,
including six new regression tests (with parameterised cases).
Privacy check: privacy_patterns_clear; observer_hashes_match.
No Docker build, Supervisor lifecycle or physical-device validation performed.

## Remaining work before any later deployment

Review this candidate and run container CI. Verify the candidate against the
actually installed .42 source before release. After a separately authorised
release, compare the fingerprint computed from the exact production planning
configuration, approved SOC policy, observation options and legacy source map;
explicitly pin that reviewed value in the executor configuration. Never copy
an arbitrary report hash automatically or disable the equality check.
The old 84c2633e / eaefc4ce mismatch is not repaired in production by this commit.

Continue separately with adapter preparation in READ_ONLY / authorization OFF,
120-second command-lifecycle evidence, external writer exclusion, physical
fallback and battery no-export evidence. No ACTIVE transition is included.
Preserve actual SOC 0%; never substitute a reserve value for telemetry.
