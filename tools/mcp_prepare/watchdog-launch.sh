#!/bin/sh
# Explicit approval is required. No actions on download, unpack or test.
set -eu
[ "${1:-}" = CONFIRM_CORE_RESTART ] || { echo EXPLICIT_RESTART_CONFIRMATION_REQUIRED; exit 1; }
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACK=/config/mcp_prepare_ems2_recovery
for tool in python3 nohup setsid; do command -v "$tool" >/dev/null || { echo "MISSING_TOOL:$tool"; exit 1; }; done
[ -f "$BACK/PREPARED" ] || exit 1
# Python holds the same exclusive OS lock throughout apply and rollback.
nohup setsid python3 "$ROOT/watchdog.py" deploy CONFIRM_CORE_RESTART > "$BACK/watchdog-launch.log" 2>&1 </dev/null &
echo WATCHDOG_QUEUED_VERIFY_EVENT_LOG_NOT_INSTALLATION_SUCCESS
