#!/usr/bin/env bash
# Plan-cache audit — PostToolUse sibling in the universal block (HIGH-eng-2).
# Writes one JSONL line per /plan-cache-lookup invocation to
# metrics/{session}/plan-cache.jsonl. On [PlanValidationOutcome] markers it
# writes pv_outcome back into the most recent HIT/MISS line of this session.
# NEVER blocks (exit 0 on every path); mirrors hooks/intake-fingerprint-audit.sh.
#
# enforces: pipeline-state/plan-cache-agentic/plan.md § Slice slice-e
# protects: pipeline, forensics

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" 2>/dev/null && check_hook_profile "standard" || exit 0

INPUT=$(cat 2>/dev/null || printf '')
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null)
[[ "$TOOL" != "Skill" ]] && exit 0

RESPONSE=$(printf '%s' "$INPUT" | jq -r '.tool_response // ""' 2>/dev/null)

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SID_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SID="${SID_RAW//[^A-Za-z0-9_-]/}"
[[ -z "$SID" ]] && SID="local-$$"
METRICS_DIR="${CLAUDE_HOOK_LOG_DIR:-$HOME/.claude/metrics}/$SID"
CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

_dispatch_pv() {
  local pv_verdict
  pv_verdict=$(printf '%s' "$RESPONSE" \
    | grep -oE '\[PlanValidationOutcome\] verdict: [A-Z_]+' \
    | tail -1 | sed 's/^.*verdict: //')
  [[ "$pv_verdict" =~ ^(PLAN_APPROVED|PLAN_HOLES|ROUTING_UPSHIFTED)$ ]] || return 0
  python3 "${HOOK_DIR}/_lib/plan-cache-audit-emit.py" \
    pv "$METRICS_DIR" "$SID" "$pv_verdict" 2>/dev/null || true
}

_dispatch_lookup() {
  local payload verdict cache_key miss_reason task_id
  payload=$(printf '%s' "$RESPONSE" \
    | grep -oE '\[PlanCacheLookup\] \{[^}]*\}' \
    | tail -1 | sed 's/^\[PlanCacheLookup\] //')
  [[ -n "$payload" ]] || return 0
  verdict=$(printf '%s' "$payload" | jq -r '.verdict // ""' 2>/dev/null)
  cache_key=$(printf '%s' "$payload" | jq -r '.cache_key // ""' 2>/dev/null)
  miss_reason=$(printf '%s' "$payload" | jq -r '.reason // ""' 2>/dev/null)
  task_id="${CLAUDE_PLAN_CACHE_TASK_ID:-<unknown>}"
  if [[ ! "$task_id" =~ ^[A-Za-z0-9._-]+$ ]]; then task_id="<unknown>"; fi
  python3 "${HOOK_DIR}/_lib/plan-cache-audit-emit.py" \
    lookup "$METRICS_DIR" "$TS" "$task_id" "$SID" \
    "$verdict" "$cache_key" "$miss_reason" \
    "${CLAUDE_PLAN_CACHE_ADAPTER_TOKENS:-0}" "$CONFIG_DIR" 2>/dev/null || true
}

if printf '%s' "$RESPONSE" | grep -q '\[PlanValidationOutcome\]'; then
  _dispatch_pv
elif printf '%s' "$RESPONSE" | grep -q '\[PlanCacheLookup\]'; then
  _dispatch_lookup
fi
exit 0
