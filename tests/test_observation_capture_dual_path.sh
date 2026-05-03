#!/usr/bin/env bash
# Slice B — observation-capture extracts phase from new-layout pipeline file.
# AC #4. Stub: observation_capture_extracts_phase_from_new_layout.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/observation-capture.sh"
[[ -x "$HOOK" ]] || { echo "FAIL: hook not executable: $HOOK"; exit 1; }

PASS=0; FAIL=0
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.claude"; ln -s "$REPO_ROOT/hooks" "$TMP/.claude/hooks"
ln -s "$REPO_ROOT/skills" "$TMP/.claude/skills"

mkdir -p "$TMP/.claude/pipeline-state/t1"
# Frontmatter intentionally lacks `verdict: in_progress` so that the FIRST
# `in_progress` line the hook finds is `- Build: in_progress` in the body
# (matches the legacy hook's phase-extraction contract verbatim).
cat > "$TMP/.claude/pipeline-state/t1/pipeline.md" <<'EOF'
---
task_id: t1
phase: build
verdict: PIPELINE_ACTIVE
---

## Phases
- Build: in_progress
EOF

PAYLOAD=$(jq -nc '{tool_name:"Read", tool_input:{file_path:"x.md"}, tool_output:{}}')

echo "Test observation_capture_extracts_phase_from_new_layout"
HOME="$TMP" CLAUDE_HOOK_PROFILE=standard CLAUDE_PROJECT_HASH=test \
  bash "$HOOK" <<<"$PAYLOAD" >/dev/null 2>&1
OBS="$TMP/.claude/learning/test/observations.jsonl"
if [[ -f "$OBS" ]] && grep -q '"phase":"build"' "$OBS"; then
  echo "  ok: extracted phase=build from new-layout fixture"; PASS=$((PASS + 1))
else
  echo "  FAIL: phase not extracted from new-layout fixture"; FAIL=$((FAIL + 1))
  [[ -f "$OBS" ]] && cat "$OBS"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
