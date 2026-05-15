#!/usr/bin/env bash
# BUG_FIXED with env-only → exit 2 in strict mode (asymmetry — only DEBUG_RESOLVED allows env-only).
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/bug-fixed-payload-validator.sh"
TMP_METRICS=$(mktemp -d)
trap 'rm -rf "$TMP_METRICS"' EXIT

PAYLOAD=$(cat <<'EOF'
{"subagent_type":"software-engineer","session_id":"sess-test","cwd":"/tmp","stop_hook_active":false,"transcript":"verdict: BUG_FIXED\nreproducer_artifact: env-only\n"}
EOF
)

OUT=$(echo "$PAYLOAD" | CLAUDE_BUGFIX_VALIDATOR_MODE=strict CLAUDE_CONFIG_DIR="$REPO_ROOT" CLAUDE_METRICS_DIR="$TMP_METRICS" bash "$HOOK" 2>&1)
RC=$?

NAME="env_only_rejected_for_bug_fixed"
if [[ "$RC" -eq 2 ]] && echo "$OUT" | grep -q "env-only"; then
  echo "PASS: $NAME"
  exit 0
else
  echo "FAIL: $NAME: rc=$RC out=$OUT"
  exit 1
fi
