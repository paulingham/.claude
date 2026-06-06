#!/usr/bin/env bash
# Story 1 (dynamic-model-router): cost record enriched with four router-training
# signals. Drives a real non-zero-token SubagentStop envelope through
# cost-feed.sh and asserts on the written costs.jsonl line.
#
# New costs.jsonl keys (additive):
#   complexity_budget : int | null  (sentinel null)  — active intake.md
#   prior_error_count : int         (sentinel 0)     — default
#   graph_depth       : int | null  (sentinel null)  — $CLAUDE_SUBAGENT_DEPTH
#   router_decision   : string      (sentinel "none")— literal until Story 2
#
# Run: bash hooks/tests/test-cost-feed-router-signals.sh
# Exit 0 = all pass; Exit 1 = any failure.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COST_FEED="$HOOKS_DIR/cost-feed.sh"
COST_HELPERS="$HOOKS_DIR/_lib/cost-helpers.sh"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1"; FAIL=$(( FAIL + 1 )); }

# Non-zero-token SubagentStop envelope — passes the cost-emit token gate.
ENVELOPE='{"subagent_type":"software-engineer","model":"claude-sonnet-4-6","usage":{"input_tokens":1000,"output_tokens":500,"cache_read_input_tokens":200,"cache_creation_input_tokens":0}}'

# fresh_data_dir — make an isolated HARNESS_DATA with empty metrics + state.
fresh_data_dir() {
  local d; d=$(mktemp -d)
  mkdir -p "$d/metrics" "$d/pipeline-state"
  echo "$d"
}

# write_active_pipeline <data_dir> <task> — fixture pipeline.md so
# _psp_find_active_pipelines resolves this task as the active pipeline.
write_active_pipeline() {
  local d="$1" task="$2"
  mkdir -p "$d/pipeline-state/$task"
  printf -- '---\ntask_id: %s\nverdict: in_progress\n---\n' "$task" \
    > "$d/pipeline-state/$task/pipeline.md"
}

# drive <data_dir> — run cost-feed.sh with ENVELOPE; echo costs.jsonl path.
drive() {
  local d="$1"; shift
  echo "$ENVELOPE" | \
    CLAUDE_PLUGIN_DATA="$d" \
    CLAUDE_PLUGIN_ROOT="$HOOKS_DIR/.." \
    "$@" \
    bash "$COST_FEED" >/dev/null 2>&1
  echo "$d/metrics/costs.jsonl"
}

# jq_field <costs_file> <key> — last record's value (raw).
jq_field() { tail -1 "$1" | jq -r ".$2"; }

echo "=== Cost Feed Router Signals (Story 1) ==="
echo ""

# ── AC1: record_has_four_new_keys ───────────────────────────────────────────
echo "-- AC1: record_has_four_new_keys --"
D=$(fresh_data_dir)
write_active_pipeline "$D" "router-fixture"
printf -- '---\ncomplexity_budget:\n  total: 13\n---\n' \
  > "$D/pipeline-state/router-fixture/intake.md"
CF=$(drive "$D" env CLAUDE_SUBAGENT_DEPTH=1)
if [[ -f "$CF" ]]; then
  KEYS_OK=$(tail -1 "$CF" | jq -e \
    'has("complexity_budget") and has("prior_error_count") and has("graph_depth") and has("router_decision") and has("timestamp") and has("session_id") and has("pipeline_id") and has("agent_role") and has("model") and has("total_cost_usd") and has("input_tokens") and has("output_tokens") and has("cached_tokens") and has("rate_version")' \
    >/dev/null 2>&1 && echo yes || echo no)
  [[ "$KEYS_OK" == "yes" ]] && pass "all 4 new + 10 existing keys present" \
    || fail "missing keys in record: $(tail -1 "$CF")"
else
  fail "no costs.jsonl written"
fi
rm -rf "$D"
echo ""

# ── AC5: complexity_budget_equals_active_state (nested total:) ───────────────
echo "-- AC5: complexity_budget_equals_active_state --"
D=$(fresh_data_dir)
write_active_pipeline "$D" "router-fixture"
printf -- '---\ncomplexity_budget:\n  total: 13\n---\n' \
  > "$D/pipeline-state/router-fixture/intake.md"
CF=$(drive "$D" env CLAUDE_SUBAGENT_DEPTH=1)
CB=$(jq_field "$CF" complexity_budget 2>/dev/null)
[[ "$CB" == "13" ]] && pass "nested complexity_budget.total: 13 -> 13" \
  || fail "expected 13, got '$CB'"
rm -rf "$D"
echo ""

# ── AC5: complexity_budget_flat_shape (flat complexity_budget: 9) ────────────
echo "-- AC5: complexity_budget_flat_shape --"
D=$(fresh_data_dir)
write_active_pipeline "$D" "router-fixture"
printf -- '---\ncomplexity_budget: 9\n---\n' \
  > "$D/pipeline-state/router-fixture/intake.md"
CF=$(drive "$D" env CLAUDE_SUBAGENT_DEPTH=1)
CB=$(jq_field "$CF" complexity_budget 2>/dev/null)
[[ "$CB" == "9" ]] && pass "flat complexity_budget: 9 -> 9" \
  || fail "expected 9, got '$CB'"
rm -rf "$D"
echo ""

# ── AC1: graph_depth_from_env ───────────────────────────────────────────────
echo "-- AC1: graph_depth_from_env --"
D=$(fresh_data_dir)
write_active_pipeline "$D" "router-fixture"
printf -- '---\ncomplexity_budget: 9\n---\n' \
  > "$D/pipeline-state/router-fixture/intake.md"
CF=$(drive "$D" env CLAUDE_SUBAGENT_DEPTH=2)
GD=$(jq_field "$CF" graph_depth 2>/dev/null)
[[ "$GD" == "2" ]] && pass "CLAUDE_SUBAGENT_DEPTH=2 -> graph_depth 2" \
  || fail "expected 2, got '$GD'"
rm -rf "$D"
echo ""

# ── AC2: nonzero_tokens_emit_exactly_one_record ─────────────────────────────
echo "-- AC2: nonzero_tokens_emit_exactly_one_record --"
D=$(fresh_data_dir)
write_active_pipeline "$D" "router-fixture"
printf -- '---\ncomplexity_budget: 9\n---\n' \
  > "$D/pipeline-state/router-fixture/intake.md"
CF="$D/metrics/costs.jsonl"
BEFORE=0; [[ -f "$CF" ]] && BEFORE=$(wc -l < "$CF")
drive "$D" env CLAUDE_SUBAGENT_DEPTH=1 >/dev/null
AFTER=0; [[ -f "$CF" ]] && AFTER=$(wc -l < "$CF")
DELTA=$(( AFTER - BEFORE ))
[[ "$DELTA" -eq 1 ]] && pass "exactly one record appended (delta=1)" \
  || fail "expected delta 1, got $DELTA"
rm -rf "$D"
echo ""

# ── AC3: absent_signals_default_to_sentinels ────────────────────────────────
echo "-- AC3: absent_signals_default_to_sentinels --"
D=$(fresh_data_dir)   # no active pipeline, no intake.md
CF=$(echo "$ENVELOPE" | env -u CLAUDE_SUBAGENT_DEPTH \
  CLAUDE_PLUGIN_DATA="$D" CLAUDE_PLUGIN_ROOT="$HOOKS_DIR/.." \
  bash "$COST_FEED" >/dev/null 2>&1; echo "$D/metrics/costs.jsonl")
if [[ -f "$CF" ]]; then
  SENT_OK=$(tail -1 "$CF" | jq -e \
    '.complexity_budget == null and .graph_depth == null and .prior_error_count == 0 and .router_decision == "none"' \
    >/dev/null 2>&1 && echo yes || echo no)
  [[ "$SENT_OK" == "yes" ]] && pass "all sentinels emitted, keys present" \
    || fail "sentinels wrong: $(tail -1 "$CF")"
else
  fail "no costs.jsonl written for sentinel case"
fi
rm -rf "$D"
echo ""

# ── AC4: extraction_error_exits_zero_shape_intact ───────────────────────────
echo "-- AC4: extraction_error_exits_zero_shape_intact --"
D=$(fresh_data_dir)
write_active_pipeline "$D" "router-fixture"
# Corrupt/unreadable intake.md (no read permission).
printf -- 'garbage no budget here\n' \
  > "$D/pipeline-state/router-fixture/intake.md"
chmod 000 "$D/pipeline-state/router-fixture/intake.md"
echo "$ENVELOPE" | env CLAUDE_SUBAGENT_DEPTH=1 \
  CLAUDE_PLUGIN_DATA="$D" CLAUDE_PLUGIN_ROOT="$HOOKS_DIR/.." \
  bash "$COST_FEED" >/dev/null 2>&1
RC=$?
chmod 644 "$D/pipeline-state/router-fixture/intake.md" 2>/dev/null || true
CF="$D/metrics/costs.jsonl"
SHAPE_OK=no
if [[ -f "$CF" ]]; then
  SHAPE_OK=$(tail -1 "$CF" | jq -e \
    'has("timestamp") and has("session_id") and has("pipeline_id") and has("agent_role") and has("model") and has("total_cost_usd") and has("input_tokens") and has("output_tokens") and has("cached_tokens") and has("rate_version")' \
    >/dev/null 2>&1 && echo yes || echo no)
fi
if [[ "$RC" -eq 0 && "$SHAPE_OK" == "yes" ]]; then
  pass "corrupt intake.md: exit 0 + 10 original keys valid JSON intact"
else
  fail "exit=$RC shape_ok=$SHAPE_OK line=$( [[ -f "$CF" ]] && tail -1 "$CF" )"
fi
rm -rf "$D"
echo ""

# ── AC4: each_extractor_returns_sentinel_on_error (unit) ─────────────────────
echo "-- AC4: each_extractor_returns_sentinel_on_error --"
# Source helpers in an isolated subshell with no active pipeline so the
# budget extractor must fall to its null sentinel; depth unset -> null.
SENT=$(
  env -u CLAUDE_SUBAGENT_DEPTH CLAUDE_PLUGIN_DATA="$(fresh_data_dir)" \
    CLAUDE_PLUGIN_ROOT="$HOOKS_DIR/.." bash -c "
      set -uo pipefail
      source '$HOOKS_DIR/_lib/harness-paths.sh'
      source '$COST_HELPERS'
      printf '%s|%s|%s|%s\n' \
        \"\$(_cf_complexity_budget)\" \
        \"\$(_cf_graph_depth)\" \
        \"\$(_cf_prior_error_count)\" \
        \"\$(_cf_router_decision)\"
    " 2>/dev/null
)
RC=$?
[[ "$SENT" == "null|null|0|none" && "$RC" -eq 0 ]] \
  && pass "extractors return null|null|0|none under no-source, exit 0" \
  || fail "got '$SENT' rc=$RC (expected 'null|null|0|none')"
echo ""

# ── Mutation guard: graph_depth non-numeric -> null (not the raw token) ──────
echo "-- mutation: graph_depth non-numeric env -> null --"
GD=$(
  env CLAUDE_SUBAGENT_DEPTH=abc bash -c "
    source '$COST_HELPERS'
    _cf_graph_depth
  " 2>/dev/null
)
[[ "$GD" == "null" ]] && pass "non-numeric CLAUDE_SUBAGENT_DEPTH -> null" \
  || fail "expected null, got '$GD'"
echo ""

# ── Summary ─────────────────────────────────────────────────────────────────
TOTAL=$(( PASS + FAIL ))
echo "=== Results: $PASS/$TOTAL passed ==="
if [[ $FAIL -gt 0 ]]; then
  echo "FAIL: $FAIL test(s) failed"
  exit 1
fi
exit 0
