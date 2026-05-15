#!/usr/bin/env bash
# Emit a named-deviation reflect token.
#
# Usage: reflect-token-emit.sh <deviation_id>
# Writes: $HOME/.claude/metrics/$CLAUDE_SESSION_ID/reflect-tokens/<deviation_id>.json
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

DEVIATION_ID="${1:-}"
if [[ -z "$DEVIATION_ID" ]]; then
  echo "reflect-token-emit: deviation_id required" >&2
  exit 2
fi

SESSION_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SESSION="${SESSION_RAW//[^A-Za-z0-9_-]/_}"
[[ -z "$SESSION" || "$SESSION" =~ ^_+$ ]] && SESSION="local-$$"
DIR="$HOME/.claude/metrics/$SESSION/reflect-tokens"
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
