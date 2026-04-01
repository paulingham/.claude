#!/usr/bin/env bash
# backend.sh -- Backend dispatcher: loads correct ticket backend
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

_log() {
  local level="$1"; shift
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [$level] $*" >&2
}

# Load backend implementation
case "$TICKET_BACKEND" in
  jira)   source "$SCRIPT_DIR/jira.sh" ;;
  github) source "$SCRIPT_DIR/github.sh" ;;
  *)
    _log ERROR "Unknown TICKET_BACKEND: $TICKET_BACKEND"
    exit 1
    ;;
esac

# Validate contract
_required_fns="backend_health_check backend_poll_ready_tickets backend_get_ticket backend_claim_ticket backend_post_comment backend_complete_ticket backend_fail_ticket backend_ticket_url"
for fn in $_required_fns; do
  if ! declare -f "$fn" >/dev/null 2>&1; then
    _log ERROR "Backend '$TICKET_BACKEND' missing required function: $fn"
    exit 1
  fi
done

_log INFO "Backend loaded: $TICKET_BACKEND"
