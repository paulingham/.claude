#!/usr/bin/env bash
# Invalid payload in mode=log → exit 0 AND JSONL line appended (safe rollout path).
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/bug-fixed-payload-validator.sh"
TMP_METRICS=$(mktemp -d)
trap 'rm -rf "$TMP_METRICS"' EXIT

PAYLOAD=$(cat <<'EOF'
{"subagent_type":"software-engineer","session_id":"sess-test-log","cwd":"/tmp","stop_hook_active":false,"transcript":"verdict: BUG_FIXED\nreproducer_artifact: tests/test_repro.py\n"}
EOF
)

OUT=$(echo "$PAYLOAD" | CLAUDE_BUGFIX_VALIDATOR_MODE=log CLAUDE_CONFIG_DIR="$REPO_ROOT" CLAUDE_METRICS_DIR="$TMP_METRICS" bash "$HOOK" 2>&1)
RC=$?

NAME="log_mode_invalid_payload_no_block"
JSONL_FILE="$TMP_METRICS/sess-test-log/bug-fixed-payload.jsonl"

if [[ "$RC" -ne 0 ]]; then
  echo "FAIL: $NAME: exit must be 0 in log mode, got rc=$RC out=$OUT"; exit 1
fi
if [[ ! -f "$JSONL_FILE" ]]; then
  echo "FAIL: $NAME: jsonl audit file not written at $JSONL_FILE; out=$OUT"; exit 1
fi
if ! grep -q '"action":"log-only"' "$JSONL_FILE"; then
  echo "FAIL: $NAME: jsonl missing action=log-only: $(cat "$JSONL_FILE")"; exit 1
fi

echo "PASS: $NAME"
exit 0
