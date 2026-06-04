#!/usr/bin/env bash
# mutation-tooling-guard — PreToolUse:Bash hook.
#
# When CWD == REPO_ROOT AND CLAUDE_WORKTREE_PATH is set (a worktree session is
# active), denies mutation tooling commands that could contaminate the root
# working tree while verifiers should be running inside their isolated worktree.
#
# Matched patterns (justified by forensics-instinct-injector-edit.md Anomaly 2):
#   - mutmut (any invocation) — mutation testing tool; found in incident at root
#   - sed -i / sed --in-place targeting source-extension files (.py, .ts, .js,
#     .sh, .rb, .go, .rs, .java, .c, .cpp, .h, .tsx, .jsx, .vue, .svelte)
#     NB: /tmp/*, /var/*, ~/.* paths are excluded (not tracked source)
#   - pytest with --mutate, -m mutation, or similar explicit mutation flags
#     (plain pytest, --lf, --cache-clear are NOT flagged — they do not mutate
#     the source tree)
#
# Ships in ADVISORY-LOG mode: log + stderr warn, exit 0 (never blocks).
# Promotion criterion: flip to enforcing (exit 2) once N=10 sessions confirm
# zero false-positive blocks. One-line promotion marker below.
#
# Escape hatch: CLAUDE_DISABLE_MUTATION_TOOLING_GUARD=1 suppresses all checks.
#
# enforces: CLAUDE.md § Runtime State Location (worktree isolation)
# protects: root working tree from mutation tooling contamination
# references: forensics-instinct-injector-edit.md Anomalies 1, 2
# if-broken-look-at: $HARNESS_DATA/metrics/{session}/mutation-tooling-advisory.jsonl

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
# log.sh sourced from deployed location; fails open when not available (e.g. test env)
# shellcheck source=/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh" 2>/dev/null || {
    _log_hook_start() { :; }; _log_hook_trigger() { :; }; log_hook_event() { :; }
}
_log_hook_start
_log_hook_trigger "PreToolUse:Bash"
trap 'log_hook_event $?' EXIT

set -uo pipefail

# Escape hatch (per-session)
[[ "${CLAUDE_DISABLE_MUTATION_TOOLING_GUARD:-0}" == "1" ]] && exit 0

INPUT=$(cat)
TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" == "Bash" ]] || exit 0

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
[[ -z "$COMMAND" ]] && exit 0

# Only applies when an active worktree session is declared
[[ -n "${CLAUDE_WORKTREE_PATH:-}" ]] || exit 0

# Only applies when CWD is the repo root (not inside a worktree).
# Canonicalize both paths to handle macOS /var -> /private/var symlinks.
_mtg_is_root_cwd() {
    local toplevel canon_top canon_pwd
    toplevel=$(git rev-parse --show-toplevel 2>/dev/null) || return 1
    # Canonicalize both to resolve symlinks
    canon_top=$(cd "$toplevel" 2>/dev/null && pwd -P) || return 1
    canon_pwd=$(pwd -P 2>/dev/null) || return 1
    [[ "$canon_top" == "$canon_pwd" ]] || return 1
    # Allow if CWD is itself a worktree
    [[ "$canon_pwd" == *"/.claude/worktrees/agent-"* ]] && return 1
    # Allow if the canonicalized CWD matches the canonicalized CLAUDE_WORKTREE_PATH.
    # Comparing raw env var vs $PWD caused /var vs /private/var mismatches on macOS.
    if [[ -n "${CLAUDE_WORKTREE_PATH:-}" ]]; then
        local canon_wt
        canon_wt=$(cd "${CLAUDE_WORKTREE_PATH}" 2>/dev/null && pwd -P) || true
        [[ -n "$canon_wt" && "$canon_pwd" == "$canon_wt" ]] && return 1
    fi
    return 0
}

_mtg_is_root_cwd || exit 0

# ---------------------------------------------------------------------------
# Pattern detectors
# ---------------------------------------------------------------------------

# mutmut: any invocation is flagged (mutation testing framework)
_mtg_is_mutmut() {
    [[ "$1" =~ (^|[[:space:]])mutmut([[:space:]]|$) ]]
}

# sed -i / sed --in-place targeting source-extension files.
# Safe paths (/tmp/, /var/folders/, /private/var/folders/, $TMPDIR-prefixed) are excluded.
# Protected source extensions: .py .ts .js .sh .rb .go .rs .java .c .cpp .h .tsx .jsx .vue .svelte
_mtg_is_sed_inplace_source() {
    local cmd="$1"
    # Must be sed with -i or --in-place
    [[ "$cmd" =~ sed[[:space:]]+(-i|--in-place) ]] || return 1
    # Must target a source-extension file
    [[ "$cmd" =~ \.(py|ts|js|sh|rb|go|rs|java|c|cpp|h|tsx|jsx|vue|svelte)([^a-zA-Z0-9]|$) ]] || return 1
    # Exclude safe/non-repo paths.
    # Patterns covered: /tmp/ (Linux), /var/folders/ and /private/var/folders/ (macOS
    # TMPDIR = /var/folders/...; canonical form = /private/var/folders/...), and any
    # path prefixed by $TMPDIR (handles both forms without hardcoding the expansion).
    local src_ext='\.(py|ts|js|sh|rb|go|rs|java|c|cpp|h|tsx|jsx|vue|svelte)'
    # Build list of safe prefixes to strip before checking for remaining source targets.
    local stripped="$cmd"
    stripped=$(printf '%s' "$stripped" | sed 's|/tmp/[^[:space:]]*||g')
    stripped=$(printf '%s' "$stripped" | sed 's|/var/folders/[^[:space:]]*||g')
    stripped=$(printf '%s' "$stripped" | sed 's|/private/var/folders/[^[:space:]]*||g')
    # Strip $TMPDIR-prefixed paths if TMPDIR is set (handles runtime expansion).
    if [[ -n "${TMPDIR:-}" ]]; then
        local tmpdir_esc
        tmpdir_esc=$(printf '%s' "${TMPDIR}" | sed 's|[]\[^$.*/\\+?{}()|]|\\&|g')
        stripped=$(printf '%s' "$stripped" | sed "s|${tmpdir_esc}[^[:space:]]*||g")
    fi
    # If no source-extension target remains after stripping safe paths, allow.
    [[ "$stripped" =~ $src_ext([^a-zA-Z0-9]|$) ]] || return 1
    return 0
}

# pytest with explicit mutation flags (not plain pytest, --lf, --cache-clear)
# We only flag invocations that explicitly mutate the source tree:
# --mutate, -m mutation (pytest-mutagen), --mutation (various plugins)
# Plain pytest, --lf, --cache-clear, -x, -v are NOT flagged.
_mtg_is_pytest_mutating() {
    local cmd="$1"
    [[ "$cmd" =~ (^|[[:space:]])pytest([[:space:]]|$) ]] || return 1
    [[ "$cmd" =~ --mutate[[:space:]=] ]] && return 0
    [[ "$cmd" =~ --mutation[[:space:]=] ]] && return 0
    return 1
}

# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------

_mtg_matched=""
if _mtg_is_mutmut "$COMMAND"; then
    _mtg_matched="mutmut"
elif _mtg_is_sed_inplace_source "$COMMAND"; then
    _mtg_matched="sed -i on source file"
elif _mtg_is_pytest_mutating "$COMMAND"; then
    _mtg_matched="pytest with mutation flag"
fi

[[ -z "$_mtg_matched" ]] && exit 0

# ---------------------------------------------------------------------------
# Advisory log
# ---------------------------------------------------------------------------

_mtg_log_advisory() {
    local sid="${CLAUDE_SESSION_ID:-local-$$}"
    sid="${sid//[^a-zA-Z0-9_.-]/}"
    local dir="$HARNESS_DATA/metrics/${sid}"
    mkdir -p "$dir" 2>/dev/null || return 0
    jq -nc \
        --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg sid "$sid" \
        --arg wt "${CLAUDE_WORKTREE_PATH:-}" \
        --arg cmd "$COMMAND" \
        --arg pat "$_mtg_matched" \
        '{timestamp:$ts,session_id:$sid,worktree_path:$wt,command:$cmd,matched_pattern:$pat,action:"advisory"}' \
        >> "$dir/mutation-tooling-advisory.jsonl" 2>/dev/null || true
}

_mtg_log_advisory

cat >&2 <<EOF
[mutation-tooling-guard] ADVISORY: mutation tooling detected at REPO_ROOT while a worktree session is active.
  Matched pattern : $_mtg_matched
  Command         : $COMMAND
  Worktree path   : ${CLAUDE_WORKTREE_PATH:-<see CLAUDE_WORKTREE_PATH>}
  Action required : Run verification commands inside your worktree, not at REPO_ROOT.
  (advisory mode — command NOT blocked; promote to enforcing once 10 sessions confirm zero false positives)
EOF

# ADVISORY MODE — log + warn, exit 0 (spawn NOT blocked).
# PROMOTION CRITERION: flip exit 0 to exit 2 on the SINGLE LINE below once
#   N=10 distinct sessions have generated advisory events with ZERO confirmed
#   false-positive blocks. Check:
#     jq -r '.session_id' "$HARNESS_DATA"/metrics/*/mutation-tooling-advisory.jsonl \
#       2>/dev/null | sort -u | wc -l
# TODO(mutation-tooling-guard-promote): one-line flip — change to exit 2
exit 0   # <-- SINGLE PROMOTION LINE
