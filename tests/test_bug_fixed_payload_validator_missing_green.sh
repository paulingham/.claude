#!/usr/bin/env bash
# BUG_FIXED payload without green_evidence in strict mode → exit 2 + helpful stderr.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/bug-fixed-payload-validator.sh"
TMP_METRICS=$(mktemp -d)
trap 'rm -rf "$TMP_METRICS"' EXIT

PAYLOAD=$(cat <<'EOF'
{"subagent_type":"software-engineer","session_id":"sess-test","cwd":"/tmp","stop_hook_active":false,"transcript":"verdict: BUG_FIXED\nreproducer_artifact:\n  path: tests/test_repro.py\n  red_evidence: |\n    1 failed\n"}
EOF
)

OUT=$(echo "$PAYLOAD" | CLAUDE_BUGFIX_VALIDATOR_MODE=strict CLAUDE_CONFIG_DIR="$REPO_ROOT" CLAUDE_METRICS_DIR="$TMP_METRICS" bash "$HOOK" 2>&1)
RC=$?

NAME="missing_green_strict_rejects"
if [[ "$RC" -eq 2 ]] && echo "$OUT" | grep -q "missing required key: green_evidence"; then
  echo "PASS: $NAME"
  exit 0
else
  echo "FAIL: $NAME: rc=$RC out=$OUT"
  exit 1
fi
