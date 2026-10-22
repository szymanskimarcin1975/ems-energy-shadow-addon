#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "${1:-}" = status ]; then exec python3 "$ROOT/manual_ack_watchdog.py" status; fi
[ "$#" = 2 ] || { echo USE_ACK_OPERATION12_CHALLENGE12_AFTER_MCP_CHECKS; exit 1; }
exec python3 "$ROOT/manual_ack_watchdog.py" ack "$1" "$2"
