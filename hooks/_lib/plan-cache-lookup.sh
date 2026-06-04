#!/usr/bin/env bash
# plan-cache-lookup helpers (Slice B MISS-only + Slice C HIT path).
# Plan: pipeline-state/plan-cache-agentic/plan.md.
#
# Slice B (MISS only):
#   _plan_cache_mode, _plan_cache_dir, _plan_cache_lookup, _plan_cache_emit_miss.
# Slice C (HIT path):
#   _plan_cache_write_pending, _plan_cache_flip_outcome,
#   _plan_cache_write_resume_stub, _plan_cache_validate_plan,
#   _plan_cache_jsonl_append, _plan_cache_finalize.

_PLAN_CACHE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./project-hash.sh
source "$_PLAN_CACHE_LIB_DIR/project-hash.sh"
# shellcheck source=./repo-hash.sh
source "$_PLAN_CACHE_LIB_DIR/repo-hash.sh"
# Note: pipeline-state-paths.sh (_psp_find_active_pipelines) is sourced and
# invoked by the orchestrator at lookup time to discover task_id; the lib
# itself takes (task_class, tier, critical) and does not need that import.

_plan_cache_mode() {
  # Slice F: default flipped off → shadow (LOW-eng-3 satisfied — slices B-E
  # have shipped; partial-merge subset without F now stays in shadow which is
  # cache-observable but not HIT-serving).
  case "${CLAUDE_PLAN_CACHE_MODE:-shadow}" in
    off|shadow|on) printf '%s\n' "${CLAUDE_PLAN_CACHE_MODE:-shadow}" ;;
    *) printf 'off\n' ;;
  esac
}

_plan_cache_dir() {
  local hash="${CLAUDE_PROJECT_HASH:-}"
  [[ -z "$hash" ]] && hash=$(_project_hash --fallback "$(basename "$(pwd)")")
  printf '%s/learning/%s/plans\n' "${HOME:-$PWD}" "$hash"
}

# _plan_cache_lookup task_class tier critical -> JSON verdict on stdout.
# task_id is discovered from the active pipeline via _psp_find_active_pipelines.
_plan_cache_lookup() {
  local task_class="$1" tier="$2" critical="$3"
  local mode key dir
  mode=$(_plan_cache_mode)
  [[ "$mode" == "off" ]] && { _plan_cache_emit_miss disabled ""; return; }
  key=$(_plan_cache_key "$task_class" "$(_repo_hash)" "$tier" "$critical") || return 1
  dir=$(_plan_cache_dir)
  [[ -f "$dir/$key.md" ]] || { _plan_cache_emit_miss no-template "$key"; return; }
  # Slice C: HIT dispatch is in place but driven by the orchestrator wiring
  # (Slice D — orchestrator/parallel-dispatch-details.md § Stage 0) calling
  # _plan_cache_write_pending / _plan_cache_write_resume_stub / spawn-adapter /
  # _plan_cache_finalize directly. This lookup entry covers off + shadow only;
  # on-mode key-present reaches the HIT helpers via the skill body, not here.
  _plan_cache_emit_miss shadow-mode "$key"
}

_plan_cache_emit_miss() {
  local reason="$1" key="$2"
  printf '[PlanCacheLookup] {"verdict":"PLAN_CACHE_MISS","reason":"%s","cache_key":"%s"}\n' \
    "$reason" "$key"
  _plan_cache_status_line MISS "$reason"
}

# Slice F — verbatim Status Line Copy (plan.md § Status Line Copy).
# One-line, user-facing console output that rides alongside the JSON audit
# marker. `disabled` is intentionally silent (no output).
_plan_cache_status_line() {
  local verdict="$1" reason="$2"
  case "$verdict:$reason" in
    MISS:shadow-mode) printf '[plan-cache] shadow-mode active (cache observable, not serving) — recon+architect running as normal\n' ;;
    MISS:no-template) printf '[plan-cache] no cached plan for this task signature — recon+architect running as normal\n' ;;
    MISS:adapter-rejected) printf '[plan-cache] adapter output rejected by validator — falling through to recon+architect in this pipeline (Iron Law 6)\n' ;;
    HIT:*) _plan_cache_hit_status_line ;;
  esac
}

# Helper isolates HIT-specific env-var reads so _plan_cache_status_line stays
# CC ≤ 5. Placeholders {N} and {cost} interpolate from caller-provided env
# (set by the orchestrator wiring around the adapter spawn).
_plan_cache_hit_status_line() {
  local secs="${CLAUDE_PLAN_CACHE_ADAPT_SECS:-?}"
  local cost="${CLAUDE_PLAN_CACHE_SAVINGS_USD:-?}"
  printf '[plan-cache] cache HIT — Haiku adapted in %ss, estimated savings ~$%s; verify slices against current repo before Build\n' \
    "$secs" "$cost"
}

# Slice F — write-on-MISS path. After Plan Validation emits PLAN_APPROVED,
# the orchestrator caches the current pipeline's plan.md under
# learning/{project-hash}/plans/{key}.md so future pipelines with the same
# task signature get a HIT in mode=on. Atomic (tmp+mv), idempotent.
# Args: PLAN_PATH KEY TASK_CLASS TIER CRITICAL REPO_HASH SOURCE_TASK_ID.
_plan_cache_write_template() {
  local plan="$1" key="$2" task_class="$3" tier="$4" critical="$5"
  local repo_hash="$6" source_task_id="$7"
  local dir tmp out now
  dir=$(_plan_cache_dir)
  mkdir -p "$dir"
  out="$dir/$key.md"
  tmp="$(mktemp -t plan-cache-tmpl-XXXXXX)"
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  _plan_cache_render_template "$plan" "$key" "$task_class" "$tier" \
    "$critical" "$repo_hash" "$source_task_id" "$now" >"$tmp" && mv "$tmp" "$out"
}

# Renders a cached template: frontmatter (per plan.md § On-disk template schema)
# + body copied from the source plan.md without its own frontmatter block.
_plan_cache_render_template() {
  local plan="$1" key="$2" task_class="$3" tier="$4" critical="$5"
  local repo_hash="$6" source_task_id="$7" now="$8"
  printf -- '---\n'
  printf 'cache_key: %s\n' "$key"
  printf 'task_class: %s\n' "$task_class"
  printf 'tier: %s\n' "$tier"
  printf 'critical: %s\n' "$critical"
  printf 'repo_hash: %s\n' "$repo_hash"
  printf 'created_at: %s\n' "$now"
  printf 'hit_count: 0\n'
  printf 'last_adapted_at: null\n'
  printf 'last_adapt_outcome: null\n'
  printf 'source_pipeline: %s\n' "$source_task_id"
  printf -- '---\n'
  _plan_cache_strip_frontmatter "$plan"
}

# Strip a YAML frontmatter block (--- ... ---) from the head of a file.
# Idempotent: files without frontmatter pass through unchanged.
_plan_cache_strip_frontmatter() {
  awk 'BEGIN{drop=0; done=0}
    !done && NR==1 && /^---$/ { drop=1; next }
    drop && /^---$/ { drop=0; done=1; next }
    drop { next }
    { print }' "$1"
}

# Slice C — HIT path helpers.
# State-before-expensive-op (Memory M5): mutate template frontmatter BEFORE
# adapter spawn so a crash mid-adapter leaves last_adapt_outcome=pending.
_plan_cache_write_pending() {
  local template="$1" now tmp
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  tmp="$(mktemp -t plan-cache-mv-XXXXXX)"
  awk -v ts="$now" '
    /^last_adapted_at:/ { print "last_adapted_at: " ts; next }
    /^last_adapt_outcome:/ { print "last_adapt_outcome: pending"; next }
    { print }
  ' "$template" >"$tmp" && mv "$tmp" "$template"
}

# Flip last_adapt_outcome to a terminal state (success|failed) post-validation.
_plan_cache_flip_outcome() {
  local template="$1" outcome="$2" tmp
  tmp="$(mktemp -t plan-cache-mv-XXXXXX)"
  awk -v o="$outcome" '
    /^last_adapt_outcome:/ { print "last_adapt_outcome: " o; next }
    { print }
  ' "$template" >"$tmp" && mv "$tmp" "$template"
}

# Resume-safety stub (AC C8): write architect-context.md BEFORE adapter spawn.
# /pipeline-resume readers don't stall on missing recon output.
# Skill callers may not have sourced harness-paths.sh; resolve HARNESS_DATA inline.
_plan_cache_write_resume_stub() {
  # Reject hostile task-id values before constructing the mkdir path.
  [[ "$1" =~ ^[A-Za-z0-9_-]+$ ]] || return 1
  [[ -n "${HARNESS_DATA:-}" ]] || HARNESS_DATA="${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}"
  local dir="${HARNESS_DATA}/pipeline-state/$1"
  mkdir -p "$dir"
  printf '<!-- cache_hit: true, recon-skipped -->\n' >"$dir/architect-context.md"
}

# Structural validator (AC C2, C5): plan must contain all four required H2
# sections plus the `cache_hit: true` marker. Returns 0 on accept, 1 on reject.
# Stays ≤20 LOC per plan.md § Module Boundaries (Cohesion Plan).
_plan_cache_validate_plan() {
  local plan="$1"
  [[ -f "$plan" ]] || return 1
  grep -qF '## Slices' "$plan" || return 1
  grep -qF '## Alternatives Considered' "$plan" || return 1
  grep -qF '## Codebase Ground-Truth Citations' "$plan" || return 1
  grep -qF '## Pre-Mortem' "$plan" || return 1
  grep -qE '^cache_hit:[[:space:]]*true$' "$plan" || return 1
  return 0
}

# Append one JSON line to metrics/{session}/plan-cache.jsonl.
_plan_cache_jsonl_append() {
  local line="$1" session="${CLAUDE_SESSION_ID:-unknown}" dir
  dir="metrics/$session"
  mkdir -p "$dir"
  printf '%s\n' "$line" >>"$dir/plan-cache.jsonl"
}

# Finalize post-adapter: validate plan; on pass → outcome=success, emit HIT;
# on fail → DELETE plan, outcome=failed, emit MISS reason=adapter-rejected
# plus the FALLTHROUGH trace line (AC C7 two-observable). No retry.
# Signature: TEMPLATE PLAN KEY. Caller has task_id/class/tier/critical context;
# this function only needs the template path (to flip outcome), the plan path
# (to validate or delete), and the cache key (for the emitted verdicts).
_plan_cache_finalize() {
  local template="$1" plan="$2" key="$3"
  local session="${CLAUDE_SESSION_ID:-unknown}"
  if _plan_cache_validate_plan "$plan"; then
    _plan_cache_flip_outcome "$template" success
    printf '[PlanCacheLookup] {"verdict":"PLAN_CACHE_HIT","cache_key":"%s"}\n' "$key"
    _plan_cache_status_line HIT served
    return 0
  fi
  rm -f "$plan"
  _plan_cache_flip_outcome "$template" failed
  _plan_cache_jsonl_append \
    "{\"verdict\":\"PLAN_CACHE_MISS\",\"reason\":\"adapter-rejected\",\"session_id\":\"$session\",\"cache_key\":\"$key\"}"
  _plan_cache_jsonl_append \
    "{\"event\":\"PLAN_CACHE_FALLTHROUGH\",\"session_id\":\"$session\",\"reason\":\"adapter-rejected\"}"
  _plan_cache_emit_miss adapter-rejected "$key"
}
