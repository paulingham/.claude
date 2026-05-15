#!/usr/bin/env bash
# task_id with newline-injection attempt must be sanitized to literal "unknown"
# in the JSONL line; output must remain exactly one JSON line (no injection split).
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/bug-fixed-payload-validator.sh"
TMP_METRICS=$(mktemp -d)
trap 'rm -rf "$TMP_METRICS"' EXIT

# Craft task_id with an embedded newline.
EVIL_TASK=$(printf 'evil\nx')

PAYLOAD=$(jq -cn --arg tid "$EVIL_TASK" '{
  subagent_type:"software-engineer",
  session_id:"sess-task-sanitize",
  task_id:$tid,
  cwd:"/tmp",
  stop_hook_active:false,
  transcript:"verdict: BUG_FIXED\nreproducer_artifact: tests/test_repro.py\n"
}')

OUT=$(echo "$PAYLOAD" | CLAUDE_BUGFIX_VALIDATOR_MODE=log CLAUDE_CONFIG_DIR="$REPO_ROOT" CLAUDE_METRICS_DIR="$TMP_METRICS" bash "$HOOK" 2>&1)
RC=$?

NAME="task_id_sanitized_single_line"
JSONL_FILE="$TMP_METRICS/sess-task-sanitize/bug-fixed-payload.jsonl"

if [[ "$RC" -ne 0 ]]; then
  echo "FAIL: $NAME: rc=$RC out=$OUT"; exit 1
fi
if [[ ! -f "$JSONL_FILE" ]]; then
  echo "FAIL: $NAME: jsonl not written; out=$OUT"; exit 1
fi

# Exactly one line — no injection-induced split.
LINE_COUNT=$(wc -l < "$JSONL_FILE" | tr -d ' ')
if [[ "$LINE_COUNT" -ne 1 ]]; then
  echo "FAIL: $NAME: expected 1 line, got $LINE_COUNT — contents:"
  cat "$JSONL_FILE"
  exit 1
fi

# task_id sanitized to literal "unknown".
if ! grep -q '"task_id":"unknown"' "$JSONL_FILE"; then
  echo "FAIL: $NAME: task_id not sanitized to unknown — contents:"
  cat "$JSONL_FILE"
  exit 1
fi

echo "PASS: $NAME"
exit 0
