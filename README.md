# EMS Energy SHADOW

Home Assistant addon repository for diagnostic energy observation.

The 0.1.3-dev.1 candidate is available only on a preparation branch. Main remains
unchanged until an explicit release approval. This is experimental software:
container tests do not establish Home Assistant Supervisor update/rollback safety.

The observer keeps a private SQLite ledger, validates source quality and records
measurement gaps without inventing consumption. All seven source entity IDs and
ledger_id must be configured explicitly; no installation-specific defaults exist.

Diagnostic export is disabled by default. Starting with the default option does
not open the export controller database or perform any diagnostic backup. The
observer necessarily opens its own ledger for normal collection. See
ems_shadow/DOCS.md for STDIN acknowledgments and separate export authorization.

No built Docker images or measurement data are published by CI.
