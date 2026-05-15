#!/usr/bin/env bash
# Table-driven sanitization check: malformed session_id values land in
# $TMP_METRICS/unknown/; valid allow-list values land in their own bucket.
# Defense-in-depth before strict-mode flip (MEDIUM security finding).
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/bug-fixed-payload-validator.sh"
TMP_METRICS=$(mktemp -d)
trap 'rm -rf "$TMP_METRICS"' EXIT

NAME="session_id_defense_in_depth"

run_case() {
  local label="$1" sid="$2" expected_bucket="$3"
  local payload
  payload=$(jq -cn --arg sid "$sid" '{
    subagent_type:"software-engineer",
    session_id:$sid,
    cwd:"/tmp",
    stop_hook_active:false,
    transcript:"verdict: BUG_FIXED\nreproducer_artifact: tests/test_repro.py\n"
  }')
  local out rc
  out=$(echo "$payload" | CLAUDE_BUGFIX_VALIDATOR_MODE=log CLAUDE_CONFIG_DIR="$REPO_ROOT" CLAUDE_METRICS_DIR="$TMP_METRICS" bash "$HOOK" 2>&1)
  rc=$?
  if [[ "$rc" -ne 0 ]]; then
    echo "FAIL: $NAME[$label]: rc=$rc out=$out"; exit 1
  fi
  local expected_file="$TMP_METRICS/$expected_bucket/bug-fixed-payload.jsonl"
  if [[ ! -f "$expected_file" ]]; then
    echo "FAIL: $NAME[$label]: expected jsonl at $expected_file"
    echo "Tree:"; find "$TMP_METRICS" -type f
    exit 1
  fi
}

# Empty string → unknown
run_case "empty" "" "unknown"

# Numeric "123" → passes allow-list, lands under 123/
run_case "numeric" "123" "123"

# Shell-injection attempt → unknown
run_case "semicolon_rm" ";rm -rf /tmp" "unknown"

# Command substitution syntax → unknown (contains `$`, `(`, `)`)
run_case "cmd_subst" "\$(whoami)" "unknown"

# Newline-embedded (use printf to inject a real newline) → unknown
NL_SID=$(printf 'foo\nbar')
run_case "newline_embedded" "$NL_SID" "unknown"

# Ensure nothing was written outside TMP_METRICS — collect every regular file
# created during the test and check each path is rooted at TMP_METRICS.
STRAY=0
while IFS= read -r f; do
  case "$f" in
    "$TMP_METRICS"/*) ;;  # ok
    *) echo "STRAY: $f"; STRAY=1 ;;
  esac
done < <(find "$TMP_METRICS" -type f)
if [[ "$STRAY" -ne 0 ]]; then
  echo "FAIL: $NAME: files materialized outside TMP_METRICS"; exit 1
fi

echo "PASS: $NAME"
exit 0
