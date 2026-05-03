#!/usr/bin/env bash
# Slice B — intake-reminder finds new-layout pipeline file when batch keyword used.
# AC #4. Stub: batch_keyword_passes_when_new_layout_pipeline_exists.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/intake-reminder.sh"
[[ -x "$HOOK" ]] || { echo "FAIL: hook not executable: $HOOK"; exit 1; }

PASS=0; FAIL=0
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.claude"; ln -s "$REPO_ROOT/hooks" "$TMP/.claude/hooks"
mkdir -p "$TMP/.claude/pipeline-state/t1"
printf -- '---\ntask_id: t1\nverdict: in_progress\n---\n' > "$TMP/.claude/pipeline-state/t1/pipeline.md"

PAYLOAD=$(jq -nc '{prompt:"start wave 4 build"}')

echo "Test batch_keyword_passes_when_new_layout_pipeline_exists"
HOME="$TMP" CLAUDE_HOOK_PROFILE=standard bash "$HOOK" <<<"$PAYLOAD" >/dev/null 2>&1
RC=$?
if [[ "$RC" -eq 0 ]]; then
  echo "  ok: batch keyword + new-layout pipeline = no block"; PASS=$((PASS + 1))
else
  echo "  FAIL: hook blocked despite new-layout pipeline (rc=$RC)"; FAIL=$((FAIL + 1))
fi

# Sanity: legacy pipeline still passes
rm -rf "$TMP/.claude/pipeline-state"
mkdir -p "$TMP/.claude/pipeline-state"
printf -- '---\ntask_id: t1\nverdict: in_progress\n---\n' > "$TMP/.claude/pipeline-state/t1-pipeline.md"
HOME="$TMP" CLAUDE_HOOK_PROFILE=standard bash "$HOOK" <<<"$PAYLOAD" >/dev/null 2>&1
LRC=$?
if [[ "$LRC" -eq 0 ]]; then
  echo "  ok: batch keyword + legacy pipeline = no block (sanity)"; PASS=$((PASS + 1))
else
  echo "  FAIL: legacy form regressed (rc=$LRC)"; FAIL=$((FAIL + 1))
fi

# Negative: no pipeline state at all should block
rm -rf "$TMP/.claude/pipeline-state"
mkdir -p "$TMP/.claude/pipeline-state"
HOME="$TMP" CLAUDE_HOOK_PROFILE=standard bash "$HOOK" <<<"$PAYLOAD" >/dev/null 2>&1
NRC=$?
if [[ "$NRC" -eq 2 ]]; then
  echo "  ok: empty pipeline-state still blocks (sanity)"; PASS=$((PASS + 1))
else
  echo "  FAIL: empty state did not block (rc=$NRC) — test plumbing broken"; FAIL=$((FAIL + 1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
