#!/usr/bin/env bash
# Slice B — subagent-stop-trajectory.sh writes to new-layout trajectory.jsonl
# AND tightens task_id sanitization to drop '.' (rejects '..' traversal).
# AC #4 + R10. Stubs: trajectory_writes_to_new_layout, trajectory_rejects_dotdot_task_id_under_new_layout.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/subagent-stop-trajectory.sh"
[[ -x "$HOOK" ]] || { echo "FAIL: hook not executable: $HOOK"; exit 1; }

PASS=0; FAIL=0
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.claude"; ln -s "$REPO_ROOT/hooks" "$TMP/.claude/hooks"

mkdir -p "$TMP/.claude/pipeline-state/t1"
cat > "$TMP/.claude/pipeline-state/t1/pipeline.md" <<'EOF'
---
task_id: t1
verdict: in_progress
---
EOF

echo "Test trajectory_writes_to_new_layout"
PAYLOAD=$(jq -nc '{subagent_type:"software-engineer", subagent_id:"test-sid"}')
HOME="$TMP" bash "$HOOK" <<<"$PAYLOAD" >/dev/null 2>&1
NEW_PATH="$TMP/.claude/pipeline-state/t1/trajectory.jsonl"
if [[ -f "$NEW_PATH" ]] && grep -q '"task_id":"t1"' "$NEW_PATH"; then
  echo "  ok: trajectory written to new-layout path"; PASS=$((PASS + 1))
else
  echo "  FAIL: trajectory not at $NEW_PATH"; FAIL=$((FAIL + 1))
fi

echo "Test trajectory_rejects_dotdot_task_id_under_new_layout"
PAYLOAD2=$(jq -nc '{subagent_type:"software-engineer", subagent_id:"test-sid"}')
rm -rf "$TMP/.claude/pipeline-state"
mkdir -p "$TMP/.claude/pipeline-state"
HOME="$TMP" CLAUDE_PIPELINE_TASK_ID=".." \
  bash "$HOOK" <<<"$PAYLOAD2" >/dev/null 2>&1
RC=$?
TRAVERSAL_FILE="$TMP/.claude/pipeline-state/../trajectory.jsonl"
LITERAL_DOTDOT="$TMP/.claude/pipeline-state/../-trajectory.jsonl"
if [[ "$RC" -eq 0 ]] && [[ ! -f "$TRAVERSAL_FILE" ]] && [[ ! -f "$LITERAL_DOTDOT" ]]; then
  echo "  ok: '..' task_id sanitized — no traversal write"; PASS=$((PASS + 1))
else
  echo "  FAIL: traversal allowed (rc=$RC, file=$TRAVERSAL_FILE)"; FAIL=$((FAIL + 1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
