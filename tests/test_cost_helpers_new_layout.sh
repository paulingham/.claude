#!/usr/bin/env bash
# Slice B — cost-helpers _cf_pipeline_id finds new-layout pipeline.
# AC #4. Stub: cost_helpers_pipeline_id_finds_new_layout.
set -uo pipefail

LIB="${BASH_SOURCE%/*}/../hooks/_lib/cost-helpers.sh"
[[ -f "$LIB" ]] || { echo "FAIL: lib missing: $LIB"; exit 1; }

PASS=0; FAIL=0
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.claude/pipeline-state/cost-task"
printf -- '---\ntask_id: cost-task\nverdict: in_progress\n---\n' \
  > "$TMP/.claude/pipeline-state/cost-task/pipeline.md"

echo "Test cost_helpers_pipeline_id_finds_new_layout"
ACTUAL=$(HOME="$TMP" bash -c "source '$LIB'; _cf_pipeline_id")
if [[ "$ACTUAL" == "cost-task" ]]; then
  echo "  ok: _cf_pipeline_id returned cost-task"; PASS=$((PASS + 1))
else
  echo "  FAIL: expected 'cost-task', got '$ACTUAL'"; FAIL=$((FAIL + 1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
