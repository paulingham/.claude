#!/usr/bin/env bash
# Emit a named-deviation reflect token.
#
# Usage: reflect-token-emit.sh <deviation_id>
# Writes: $HARNESS_DATA/metrics/$CLAUDE_SESSION_ID/reflect-tokens/<deviation_id>.json
# Payload: { deviation_id, acknowledged: false, verification_path, timestamp }
#
# Idempotent: if the token already exists with acknowledged=true, the file
# is preserved verbatim — re-emission MUST NOT clobber operator
# acknowledgment. If the token exists with acknowledged=false, the
# timestamp is refreshed but acknowledgment stays false.
#
# enforces: protocols/thinking-defaults.md § Named deviation
# protects: pipeline Reflect gate

set -u

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/gear-gate.sh"
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/session-id.sh"

# Reflect-phase bookkeeping — the Reflect phase only exists in the Pipeline
# gear. CLI-invoked (no stdin JSON): sid resolves via $CLAUDE_SESSION_ID.
check_gear_gate "$(resolve_session_id "")" || exit 0

DEVIATION_ID="${1:-}"
if [[ -z "$DEVIATION_ID" ]]; then
  echo "reflect-token-emit: deviation_id required" >&2
  exit 2
fi
DEVIATION_ID="${DEVIATION_ID//[^A-Za-z0-9_-]/_}"

SESSION_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SESSION="${SESSION_RAW//[^A-Za-z0-9_-]/_}"
[[ -z "$SESSION" || "$SESSION" =~ ^_+$ ]] && SESSION="local-$$"
DIR="$HARNESS_DATA/metrics/$SESSION/reflect-tokens"
TOKEN="$DIR/$DEVIATION_ID.json"
mkdir -p "$DIR" || exit 1

python3 - "$DEVIATION_ID" "$TOKEN" <<'PY'
import json, sys, datetime
deviation_id, path = sys.argv[1], sys.argv[2]
existing = None
try:
    with open(path) as fh:
        existing = json.load(fh)
except (OSError, ValueError):
    existing = None
if existing and existing.get("acknowledged") is True:
    sys.exit(0)  # operator already acknowledged; preserve verbatim
payload = {
    "deviation_id": deviation_id,
    "acknowledged": False,
    "verification_path": f"metrics/{{session}}/reflect-tokens/{deviation_id}.json",
    "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
}
with open(path, "w") as fh:
    json.dump(payload, fh)
PY
