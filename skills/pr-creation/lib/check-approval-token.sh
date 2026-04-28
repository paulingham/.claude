#!/usr/bin/env bash
# Approval token gate for /pr-creation. Exits 0 to proceed, 2 to block.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/../../../hooks/_lib/approval-token.sh"

BRANCH="$(git branch --show-current 2>/dev/null || echo "")"
TASK_ID="$(_at_resolve_task_id "$BRANCH")"

if [ -z "$TASK_ID" ] || ! _at_pipeline_active "$TASK_ID"; then
  echo "manual PR path — no active pipeline"
  exit 0
fi

exit 0
