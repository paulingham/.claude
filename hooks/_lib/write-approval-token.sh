#!/usr/bin/env bash
# Wrapper: writes a product-acceptance approval token. Args: --task-id ID --verdict V
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/approval-token.sh"

TASK_ID="" VERDICT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --task-id) TASK_ID="$2"; shift 2 ;;
    --verdict) VERDICT="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -n "$TASK_ID" ] && [ -n "$VERDICT" ] || { echo "missing --task-id or --verdict" >&2; exit 2; }
_at_write_token "$TASK_ID" "$VERDICT"
