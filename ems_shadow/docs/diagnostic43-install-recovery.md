# Diagnostic .43: installation gate and code-only recovery

Prepared only. No production change, merge, release installation or Core restart.
Base: 2427748fae954e4724d6a14219e81963a9475207 (.42).
Runtime delta: only observation/demand_runtime.py from PR #26, blob
0f609cfb64c24cea5d32676716975b80caea7354.
No adapter, PR #22/#23/#24, schema migration, options/source/ledger/fingerprint changes.
Existing SQL and database filenames are unchanged. Error reports gain additive
bounded fields; successful report format is unchanged. This does not fix or prove
the unknown production root exception.

## Before approval to install
1. Require full CI on this exact head, including .42 -> .43 -> .42 code transition
   on the same synthetic /data and /ha_config; options byte equality and all SQLite
   integrity checks. This is container evidence, not a real Supervisor restore test.
2. Verify current owner LEGACY, READ_ONLY, authorization OFF, no unresolved command.
3. Create a cold partial Supervisor backup of this exact existing addon
   (backup:cold stops it temporarily for consistency); verify completed ID,
   addon/data inclusion and availability. Also preserve EMS YAML from /config/
   (outside addon /data) via a verified HA/config backup. Do not ordinary-cp live DBs.
4. Record installed .42 identity, addon slug/repository, options, ledger/source digest,
   baseline report timestamps and commands_sent=0.
5. Confirm recovery availability BEFORE installing: recovery/planning-original42-44
   contains exact original .42 application, only config/Docker version=.44.
   Both candidate and recovery must be publishable to the SAME existing Supervisor
   repository/addon slug after separate approval. Do not add a second #branch repo
   as a supposed in-place upgrade: repository identity/data may differ.
   A repository branch alone is NOT a production-ready rollback button.
   Do not rely on unsupported downgrade of the update entity.
6. Never merge other outstanding PRs to obtain this diagnostic version.
   Publication/merge to the existing distribution branch requires separate consent.

## Approved installation (not executed)
Once backup/recovery/publication gates are confirmed, reload the existing store,
verify target .43 exactly, update only the existing EMS Energy SHADOW addon.
Do not reinstall, change options, restore a database, restart Core, enable execution
or touch SolarEdge/G13/CWU/CO. Addon stop/start creates a short observation gap.

## Observe 5-10 minutes
Read fresh planning_report.yaml repeatedly (report TTL 45s, worker cycle ~20s).
If PLANNING_ERROR recurs record generated_at plus error.code, error.stage,
error.exception_type and error.location; never request arbitrary exception text.
Check current_plan_usable_for_simulation=false and empty decisions on failure.
Verify observers/demand timestamps and capture growth, sources_digest/ledger,
LEGACY/READ_ONLY/auth OFF and commands_sent=0. Do not call dispatch or STOP.
Success of diagnosis means a bounded cause is visible, NOT that planning is repaired.
If a usable household plan appears validate it; do not infer success from process UP.

## Abort and code rollback
Abort further work if observers stop progressing, options/source identity changes,
ownership/authorization changes, unexpected commands, DB errors or access loss.
Stop only this addon if needed; preserve newest /data and /config data.
Publish approved recovery .44 through the SAME original repository/slug; refresh
store, verify .44 target, update only this addon. Recovery app content is exactly
.42; metadata says .44 to allow a supported forward update. Do not restore old DBs.
Verify old application content, startup, collection, options, ledger, zero commands.
If Supervisor recovery path is unavailable, do not improvise or uninstall. Installation
must remain blocked until an independently usable recovery path is confirmed.
A full backup restore is disaster recovery, may roll history back, and is NOT this
code-only rollback procedure.

## Evidence limits
No production backup, Supervisor installation or recovery has been executed here.
No physical commands. Existing .42 defect may persist after rollback; recovery
restores previous code rather than promising a valid plan. PR #24 fixes are excluded.
