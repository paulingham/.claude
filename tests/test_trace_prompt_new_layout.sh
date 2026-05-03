#!/usr/bin/env bash
# Slice B — trace-prompt resolves task_id from new-layout fixture.
# AC #4. Stub: trace_prompt_resolves_task_id_from_new_layout.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/trace-prompt.sh"
[[ -x "$HOOK" ]] || { echo "FAIL: hook not executable: $HOOK"; exit 1; }

PASS=0; FAIL=0
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.claude"; ln -s "$REPO_ROOT/hooks" "$TMP/.claude/hooks"
mkdir -p "$TMP/.claude/pipeline-state/t-trace"
cat > "$TMP/.claude/pipeline-state/t-trace/pipeline.md" <<'EOF'
---
task_id: t-trace
phase: build
verdict: in_progress
---
EOF

PAYLOAD=$(jq -nc '{tool_name:"Agent", tool_input:{subagent_type:"software-engineer", prompt:"hello"}}')

echo "Test trace_prompt_resolves_task_id_from_new_layout"
HOME="$TMP" CLAUDE_ENABLE_TRACE=1 CLAUDE_SESSION_ID=test-sess \
  bash "$HOOK" <<<"$PAYLOAD" >/dev/null 2>&1
TRACE_DIR="$TMP/.claude/metrics/test-sess/trace"
TRACE_FILE=""
if [[ -d "$TRACE_DIR" ]]; then
  TRACE_FILE=$(rtk proxy find "$TRACE_DIR" -name '*t-trace*' -type f 2>/dev/null | head -1)
fi
if [[ -n "$TRACE_FILE" ]] && grep -q "^task_id: t-trace$" "$TRACE_FILE"; then
  echo "  ok: trace file has task_id=t-trace from new layout"; PASS=$((PASS + 1))
else
  echo "  FAIL: task_id not resolved from new-layout fixture"; FAIL=$((FAIL + 1))
  [[ -d "$TRACE_DIR" ]] && rtk proxy find "$TRACE_DIR" -type f 2>/dev/null
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
