# Autonomous SolarEdge PREPARE over existing authenticated MCP

PREPARED OFFLINE ONLY. No production installation, restart or backup performed.

Transport remains Nabu Casa -> /api/mcp_http -> existing OAuth -> existing
verified_identity/require_admin. Add two tools, not a shell:
- ems_admin_solaredge_prepare(operation_id): fixed component copy and SHA256.
- ems_admin_solaredge_prepare_status(operation_id): verify same backup after an
  interrupted connection. UNKNOWN must never be retried with a new operation ID.

No command string, arbitrary path, token, URL, Modbus, subprocess, service call,
SQL, .storage, configuration change, installation, restoration or restart API.
Existing bounded MCP log-reading tools remain separate. Do NOT route the new
operation through generic call_service: the reviewed generic wrapper does not
forward the authenticated user's HA Context. The dedicated tool uses the
existing verified OAuth admin ContextVar, then checks active HA admin again.

HA Core's current OS permissions suffice: read ONLY
/config/custom_components/solaredge_modbus_multi and create/read ONLY
/config/ems_prepare_backups/<32-hex-operation-id>. No new account/password,
Supervisor token, public port or broad filesystem permission is requested.
Current MCP has no such operation; agent cannot bootstrap its own new capability
through an absent command tool or by using YAML/template/path traversal tricks.

Implementation: Python filesystem APIs with directory FDs/O_NOFOLLOW, regular
files only, no hardlinks, bounded size/count/depth and snapshot work, private
backup directory0700/files0600. Source hub/manifest SHA must match reviewed4.0.4
before backup creation. All component code/translation files copied and hashed;
cache ignored, SQL/unknown file types rejected. Original files never written.
Durable intent, COMPLETE manifest and SHA verification; incomplete existing
operation stays UNKNOWN. No secrets/file contents returned, only hash metadata.
It is a LOCAL code backup, not independently stored off-server disaster recovery.

## Candidate package / deployment method

build_package.py uses a COPY of the current MCP component as input, verifies
EVERY file against base_sha256.json (reviewed1.18.0+ems.1), then makes a full
candidate1.18.0+ems.2 and matching code-only recoveryZIP, with SHA256SUMS.
Any actual installed deviation must be reviewed; no blind replacement.
Relative OAuth, auth, HTTP, config-flow and existing tools code is preserved.
Only adds prepare_operations.py / tools/ems_prepare.py and changes the tool
import list + manifest version. No new API endpoint or credentials.

The local reference package was built and SHA-checked; this is NOT a backup of
production. New filesystem/refusal tests use isolated files and simulated auth
boundaries, not a full live MCP/OAuth acceptance test. That integration test is
required before deployment; existing OAuth tests are not claimed as this test.

Shortest bootstrap is ONE approved component update in the existing server
terminal/file manager, not eight repeated PREPARE commands: first obtain actual
MCP source backup/hash, assemble/verify the matching update+recovery package,
apply in an approved Core maintenance window and restart/reconnect once.
The current MCP/files API cannot safely install .py files by itself. No Windows
or direct LAN connectivity is needed, but the owner must perform/enable this
initial server-side installation until a supported deployment tool is available.
Do not claim HACS support for this private MCP patch unless its repository and
package are actually configured. Do not overwrite .storage/OAuth registrations.

After installation, tools/list/client refresh must expose both tools. Verify
admin-only status and unauthorized refusal, then the agent can invoke PREPARE
with one fresh operation ID, verify same ID, and report actual source/backups
SHA256. No owner/authorization/battery changes are part of this rollout.

Rollback: restore the pre-update MCP CODE only through the existing server
terminal and approved Core restart; keep OAuth/.storage/Recorder/EMS databases.
No rollback service is exposed by these new tools. After an interrupted PREPARE,
inspect the same ID before considering any further action.
