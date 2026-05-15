#!/usr/bin/env bash
# Invalid payload (missing_red) in mode=warn → exit 0, stderr warning emitted,
# JSONL line records action=warn.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/bug-fixed-payload-validator.sh"
TMP_METRICS=$(mktemp -d)
trap 'rm -rf "$TMP_METRICS"' EXIT

PAYLOAD=$(cat <<'EOF'
{"subagent_type":"software-engineer","session_id":"sess-test-warn","cwd":"/tmp","stop_hook_active":false,"transcript":"verdict: BUG_FIXED\nreproducer_artifact:\n  path: tests/test_repro.py\n  green_evidence: |\n    1 passed\n"}
EOF
)

OUT=$(echo "$PAYLOAD" | CLAUDE_BUGFIX_VALIDATOR_MODE=warn CLAUDE_CONFIG_DIR="$REPO_ROOT" CLAUDE_METRICS_DIR="$TMP_METRICS" bash "$HOOK" 2>&1)
RC=$?

NAME="warn_mode_missing_red_no_block"
JSONL_FILE="$TMP_METRICS/sess-test-warn/bug-fixed-payload.jsonl"

if [[ "$RC" -ne 0 ]]; then
  echo "FAIL: $NAME: exit must be 0 in warn mode, got rc=$RC out=$OUT"; exit 1
fi
if ! echo "$OUT" | grep -q "warn: BUG_FIXED payload shape=missing_red"; then
  echo "FAIL: $NAME: stderr missing 'warn: BUG_FIXED payload shape=missing_red'; out=$OUT"; exit 1
fi
if [[ ! -f "$JSONL_FILE" ]]; then
  echo "FAIL: $NAME: jsonl audit file not written at $JSONL_FILE; out=$OUT"; exit 1
fi
if ! grep -q '"action":"warn"' "$JSONL_FILE"; then
  echo "FAIL: $NAME: jsonl missing action=warn: $(cat "$JSONL_FILE")"; exit 1
fi

echo "PASS: $NAME"
exit 0
