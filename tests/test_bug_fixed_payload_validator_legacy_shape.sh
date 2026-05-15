#!/usr/bin/env bash
# Strict mode + flat (legacy) `reproducer_artifact: <path>` line → exit 2 with
# the legacy-form rejection message.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/bug-fixed-payload-validator.sh"
TMP_METRICS=$(mktemp -d)
trap 'rm -rf "$TMP_METRICS"' EXIT

PAYLOAD=$(cat <<'EOF'
{"subagent_type":"software-engineer","session_id":"sess-test-legacy","cwd":"/tmp","stop_hook_active":false,"transcript":"verdict: BUG_FIXED\nreproducer_artifact: tests/test_repro.py\n"}
EOF
)

OUT=$(echo "$PAYLOAD" | CLAUDE_BUGFIX_VALIDATOR_MODE=strict CLAUDE_CONFIG_DIR="$REPO_ROOT" CLAUDE_METRICS_DIR="$TMP_METRICS" bash "$HOOK" 2>&1)
RC=$?

NAME="legacy_shape_strict_rejects"
if [[ "$RC" -eq 2 ]] && echo "$OUT" | grep -q "missing required key: red_evidence (legacy string form deprecated)"; then
  echo "PASS: $NAME"
  exit 0
else
  echo "FAIL: $NAME: rc=$RC out=$OUT"
  exit 1
fi
