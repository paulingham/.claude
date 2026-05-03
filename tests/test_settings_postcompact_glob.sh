#!/usr/bin/env bash
# Slice B — settings.json PostCompact command unions BOTH globs (legacy + new).
# AC #4 + R7. Stub: settings_postcompact_command_matches_both_layouts.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SETTINGS="$REPO_ROOT/settings.json"

PASS=0; FAIL=0
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# Extract the PostCompact command from settings.json.
COMMAND=$(jq -r '.hooks.PostCompact[0].hooks[0].command' "$SETTINGS")

# Set up BOTH layouts
mkdir -p "$TMP/.claude/pipeline-state/new-task"
printf '%s' "x" > "$TMP/.claude/pipeline-state/new-task/pipeline.md"
printf '%s' "x" > "$TMP/.claude/pipeline-state/legacy-task-pipeline.md"

# Run the command from a cwd analogous to repo root, but with HOME-isolated state.
echo "Test settings_postcompact_command_matches_both_layouts"
OUT=$(cd "$TMP/.claude" && bash -c "$COMMAND" 2>&1) || true
if echo "$OUT" | grep -q "Pipeline state files found"; then
  echo "  ok: command found state files"; PASS=$((PASS + 1))
else
  echo "  FAIL: command did not find pipeline files: $OUT"; FAIL=$((FAIL + 1))
fi

# Also verify the command's literal text matches both glob patterns.
echo "Test settings_postcompact_command_text_unions_both_globs"
if echo "$COMMAND" | grep -q "\\*-pipeline.md" && echo "$COMMAND" | grep -q "\\*/pipeline.md"; then
  echo "  ok: command unions both globs"; PASS=$((PASS + 1))
else
  echo "  FAIL: command does not union both globs: $COMMAND"; FAIL=$((FAIL + 1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
