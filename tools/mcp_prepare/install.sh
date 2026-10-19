#!/bin/sh
# Fixed MCP CODE deployment only. No token, .storage, SQL or inverter commands.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SRC=/config/custom_components/mcp_server_http_transport
BACK=/config/mcp_prepare_ems2_recovery
MODE=${1:-prepare}
for tool in sha256sum unzip cp mv cmp find sort ha nohup env; do command -v "$tool" >/dev/null || { echo "MISSING_TOOL:$tool"; exit 1; }; done
[ "$MODE" = prepare ] || [ "$MODE" = apply ] || [ "$MODE" = rollback ] || exit 1
cd "$ROOT"
sha256sum -c SHA256SUMS
check_source() {
 [ -z "$(find "$SRC" -type l -print -quit)" ] || { echo SOURCE_SYMLINK_REFUSED; exit 1; }
 (cd "$SRC" && sha256sum -c "$ROOT/BASE_SHA256SUMS")
 (cd "$SRC" && find . -type f ! -path '*/__pycache__/*' -print | LC_ALL=C sort) > "$BACK/source-filelist.txt"
 cmp "$BACK/source-filelist.txt" "$ROOT/BASE_FILELIST"
}
if [ "$MODE" = prepare ]; then
 # Never overwrite an existing backup. Repeat requires inspecting that backup.
 mkdir -m 700 "$BACK"
 check_source
 cp -a "$SRC" "$BACK/component"
 (cd "$BACK/component" && sha256sum -c "$ROOT/BASE_SHA256SUMS")
 printf '%s\n' PREPARED > "$BACK/PREPARED"
 echo PREPARE_COMPLETE_CODE_BACKUP_ONLY_NO_RESTART
 exit 0
fi
[ "${2:-}" = CONFIRM_CORE_RESTART ] || { echo EXPLICIT_RESTART_CONFIRMATION_REQUIRED; exit 1; }
[ -f "$BACK/PREPARED" ] || { echo PREPARE_REQUIRED; exit 1; }
# Core restart can disconnect Nabu Casa ingress; keep work in the addon process.
if [ "${EMS_MCP_DETACHED:-0}" != 1 ]; then
 nohup env EMS_MCP_DETACHED=1 sh "$ROOT/install.sh" "$MODE" CONFIRM_CORE_RESTART > "$BACK/$MODE.log" 2>&1 </dev/null &
 echo "QUEUED_SERVER_SIDE: $BACK/$MODE.log"
 exit 0
fi
[ -z "$(find "$BACK/component" -type l -print -quit)" ] || exit 1
(cd "$BACK/component" && sha256sum -c "$ROOT/BASE_SHA256SUMS")
STAMP=$(date -u +%Y%m%dT%H%M%S)
if [ "$MODE" = apply ]; then
 check_source
 STAGE="$BACK/stage-$STAMP"
 mkdir "$STAGE"
 unzip -q "$ROOT/mcp-1.18.0-ems.2-prepare.zip" -d "$STAGE"
 NEW="$STAGE/custom_components/mcp_server_http_transport"
 (cd "$NEW" && sha256sum -c "$ROOT/CANDIDATE_SHA256SUMS")
 ha core check
else
 NEW="$BACK/rollback-$STAMP"
 cp -a "$BACK/component" "$NEW"
 (cd "$NEW" && sha256sum -c "$ROOT/BASE_SHA256SUMS")
fi
# Never start a replacement while Core may still be reading the old component.
ha core stop
OLD="$BACK/pre-$MODE-$STAMP"
if ! mv "$SRC" "$OLD"; then ha core start; exit 1; fi
if ! mv "$NEW" "$SRC"; then mv "$OLD" "$SRC"; ha core start; exit 1; fi
if ! ha core start; then
 echo CORE_START_FAILED_RESTORE_PREVIOUS_CODE
 ha core stop || exit 1
 mv "$SRC" "$BACK/failed-$MODE-$STAMP"
 mv "$OLD" "$SRC"
 ha core start
 exit 1
fi
echo CODE_CHANGE_COMPLETE_VERIFY_MCP_OAUTH_BEFORE_ACCEPTANCE
# A successful CLI start does NOT prove MCP loaded. Verify over the real client.
