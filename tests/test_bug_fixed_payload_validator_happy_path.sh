#!/usr/bin/env bash
# BUG_FIXED with full {path, red_evidence, green_evidence} → exit 0 in strict mode.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/bug-fixed-payload-validator.sh"
TMP_METRICS=$(mktemp -d)
trap 'rm -rf "$TMP_METRICS"' EXIT

PAYLOAD=$(cat <<'EOF'
{"subagent_type":"software-engineer","session_id":"sess-test","cwd":"/tmp","stop_hook_active":false,"transcript":"verdict: BUG_FIXED\nreproducer_artifact:\n  path: tests/test_repro.py\n  red_evidence: |\n    AssertionError: expected True\n    1 failed in 0.04s\n  green_evidence: |\n    1 passed in 0.04s\n"}
EOF
)

OUT=$(echo "$PAYLOAD" | CLAUDE_BUGFIX_VALIDATOR_MODE=strict CLAUDE_CONFIG_DIR="$REPO_ROOT" CLAUDE_METRICS_DIR="$TMP_METRICS" bash "$HOOK" 2>&1)
RC=$?

NAME="happy_path_strict_passes"
if [[ "$RC" -eq 0 ]]; then
  echo "PASS: $NAME"
  exit 0
else
  echo "FAIL: $NAME: rc=$RC out=$OUT"
  exit 1
fi
