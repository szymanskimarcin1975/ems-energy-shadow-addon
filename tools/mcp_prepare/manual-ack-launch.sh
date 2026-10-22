#!/bin/sh
set -eu
[ "${1:-}" = CONFIRM_CORE_RESTART ] || { echo EXPLICIT_RESTART_APPROVAL_REQUIRED; exit 1; }
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACK=/config/mcp_prepare_ems2_recovery
for tool in python3 nohup setsid ha; do command -v "$tool" >/dev/null || { echo "MISSING_TOOL:$tool"; exit 1; }; done
[ -f "$BACK/PREPARED" ] || exit 1
nohup setsid python3 "$ROOT/manual_ack_watchdog.py" deploy CONFIRM_CORE_RESTART > "$BACK/manual-watchdog-launch.log" 2>&1 </dev/null &
echo QUEUED_NOT_INSTALLED_VERIFY_STATUS
