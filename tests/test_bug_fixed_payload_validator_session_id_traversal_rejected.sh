#!/usr/bin/env bash
# Malicious session_id with path traversal must be sanitized; JSONL must land
# inside $CLAUDE_METRICS_DIR (under "unknown/"), never outside it.
# Defense-in-depth before strict-mode flip (MEDIUM security finding).
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/bug-fixed-payload-validator.sh"
TMP_METRICS=$(mktemp -d)
# Sentinel directory the traversal payload would target if unsanitized.
TMP_SENTINEL=$(mktemp -d)
trap 'rm -rf "$TMP_METRICS" "$TMP_SENTINEL"' EXIT

# Traversal target: ../<basename of TMP_SENTINEL>/evil — would escape TMP_METRICS
# if SESSION_ID interpolation is unsanitized.
SENTINEL_NAME=$(basename "$TMP_SENTINEL")
EVIL_SESSION="../${SENTINEL_NAME}/evil"

PAYLOAD=$(jq -cn --arg sid "$EVIL_SESSION" '{
  subagent_type:"software-engineer",
  session_id:$sid,
  cwd:"/tmp",
  stop_hook_active:false,
  transcript:"verdict: BUG_FIXED\nreproducer_artifact: tests/test_repro.py\n"
}')

OUT=$(echo "$PAYLOAD" | CLAUDE_BUGFIX_VALIDATOR_MODE=log CLAUDE_CONFIG_DIR="$REPO_ROOT" CLAUDE_METRICS_DIR="$TMP_METRICS" bash "$HOOK" 2>&1)
RC=$?

NAME="session_id_traversal_rejected"

if [[ "$RC" -ne 0 ]]; then
  echo "FAIL: $NAME: exit must be 0 in log mode, got rc=$RC out=$OUT"; exit 1
fi

# JSONL MUST be written under the sanitized "unknown" bucket inside TMP_METRICS.
SAFE_JSONL="$TMP_METRICS/unknown/bug-fixed-payload.jsonl"
if [[ ! -f "$SAFE_JSONL" ]]; then
  echo "FAIL: $NAME: expected sanitized jsonl at $SAFE_JSONL; out=$OUT"
  echo "Tree under TMP_METRICS:"; find "$TMP_METRICS" -type f
  exit 1
fi

# Sentinel directory MUST remain empty — no traversal escape.
if [[ -n "$(ls -A "$TMP_SENTINEL" 2>/dev/null)" ]]; then
  echo "FAIL: $NAME: traversal escaped — sentinel dir has contents: $(ls -A "$TMP_SENTINEL")"
  exit 1
fi

# Parent of TMP_METRICS must not have grown any new files in our traversal name.
if [[ -e "$TMP_METRICS/../${SENTINEL_NAME}/evil/bug-fixed-payload.jsonl" ]]; then
  PARENT_HIT=$(ls -la "$TMP_METRICS/../${SENTINEL_NAME}/evil/" 2>/dev/null || true)
  # Only fail if the file actually exists at the traversal target.
  if [[ -f "$TMP_METRICS/../${SENTINEL_NAME}/evil/bug-fixed-payload.jsonl" ]]; then
    echo "FAIL: $NAME: traversal jsonl materialized outside TMP_METRICS: $PARENT_HIT"
    exit 1
  fi
fi

echo "PASS: $NAME"
exit 0
