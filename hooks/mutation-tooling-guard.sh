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
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/check-bypass-gate.sh"
# log.sh sourced from deployed location; fails open when not available (e.g. test env)
# shellcheck source=/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh" 2>/dev/null || {
    _log_hook_start() { :; }; _log_hook_trigger() { :; }; log_hook_event() { :; }
}
_log_hook_start
_log_hook_trigger "PreToolUse:Bash"
trap 'log_hook_event $?' EXIT

set -uo pipefail

# Escape hatch (per-session) — writes audit record before exiting so forensics
# can identify sessions that bypassed this advisory guard (Gap 5).
if check_bypass_gate "CLAUDE_DISABLE_MUTATION_TOOLING_GUARD"; then
    _sid="${CLAUDE_SESSION_ID:-local-$$}"; _sid="${_sid//[^a-zA-Z0-9_.-]/}"
    _dir="${HARNESS_DATA:-${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}}/metrics/${_sid}"
    mkdir -p "$_dir" 2>/dev/null && \
        printf '{"timestamp":"%s","session_id":"%s","guard":"mutation-tooling-guard","action":"escaped"}\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$_sid" \
            >> "$_dir/guard-escapes.jsonl" 2>/dev/null || true
    exit 0
fi

INPUT=$(cat)
TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" == "Bash" ]] || exit 0

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
[[ -z "$COMMAND" ]] && exit 0

# Routing:
# - WORKTREE_PATH set: standard path — check if CWD is repo root, then detect mutation tooling
# - WORKTREE_PATH unset: Gap 3 heuristic — if active worktrees exist AND CWD looks like repo
#   root, emit a reduced-confidence advisory (worktree context could not be verified)
_MTG_WORKTREE_PATH_SET=0
[[ -n "${CLAUDE_WORKTREE_PATH:-}" ]] && _MTG_WORKTREE_PATH_SET=1

# Only applies when CWD is the repo root (not inside a worktree).
# Canonicalize both paths to handle macOS /var -> /private/var symlinks.
#
# Amendment 2 (slice-1b): REPO_ROOT derived from porcelain first entry via
# `git worktree list --porcelain | awk '/^worktree /{print $2}' | head -1`
# instead of `git rev-parse --show-toplevel`. The porcelain form is CWD-independent
# (always returns the main worktree path regardless of hook CWD), fixing the
# self-denial bug where hook CWD = worktree caused rev-parse to return the worktree
# root as "toplevel", making worktree == REPO_ROOT and blocking legitimate operations.
_mtg_is_root_cwd() {
    local toplevel canon_top canon_pwd
    # CWD-independent REPO_ROOT: first entry of porcelain worktree list = main worktree.
    toplevel=$(git worktree list --porcelain 2>/dev/null \
        | awk '/^worktree /{print $2}' | head -1) || return 1
    [[ -z "${toplevel:-}" ]] && return 1
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

# Standard path (WORKTREE_PATH set): check if CWD is repo root.
# Gap 3 path (WORKTREE_PATH unset): handled below in check section.
if [[ "$_MTG_WORKTREE_PATH_SET" == "1" ]]; then
    _mtg_is_root_cwd || exit 0
fi

# ---------------------------------------------------------------------------
# Gap 3: WORKTREE_PATH-unset heuristic
# When CLAUDE_WORKTREE_PATH is not set, the early-exit at line ~101 has not
# fired (that exit is gated on WORKTREE_PATH being set). If we reach here with
# WORKTREE_PATH unset, this heuristic handles that case: if active linked
# worktrees exist, emit a reduced-confidence advisory.
# The standard path (WORKTREE_PATH set) uses _mtg_is_root_cwd; the heuristic
# path (WORKTREE_PATH unset + active worktrees) is a secondary signal.
# ---------------------------------------------------------------------------
_mtg_has_active_worktrees() {
    # Check for any linked worktrees (tail -n +2 skips main worktree = REPO_ROOT).
    local wt
    while IFS= read -r wt; do
        [[ -n "$wt" ]] && return 0
    done < <(git worktree list --porcelain 2>/dev/null \
        | awk '/^worktree /{print $2}' | tail -n +2)
    return 1
}

# ---------------------------------------------------------------------------
# Command normalizer (_mtg_normalize_command): unwrap bash -c / eval / simple
# $(echo X) substitutions before pattern matching (Gap 2, Amendment 3).
#
# Max unwrap depth: 2. Unwrap condition: leading token must match
# ^[a-zA-Z0-9_/.-]+ and must not start with # (comment) or be inside a
# string literal context (echo/printf "...").
#
# Accepted-risk out-of-contract residuals (not unwrapped; caught by raw-pass):
#   - ANSI-C quoting: bash -c $'mutmut run'  ($'...' form not matched by _re_sq/_re_dq)
#   - Backtick substitution: `bash -c 'mutmut run'`  (backtick not parsed)
#   - Depth > 2: bash -c 'bash -c "bash -c \"mutmut\""'  (depth limit = 2; depth 3+ not unwrapped)
# These forms remain detectable via the raw-pass that follows normalization.
# ---------------------------------------------------------------------------
_mtg_normalize_command() {
    local cmd="$1"
    local depth=0

    while [[ $depth -lt 2 ]]; do
        local leading_token=""
        # Extract leading token (first word after stripping leading whitespace)
        local trimmed="${cmd#"${cmd%%[![:space:]]*}"}"
        leading_token="${trimmed%%[[:space:]]*}"

        # Strip backslashes from leading token to normalize s\ed -> sed
        local normalized_token="${leading_token//\\/}"

        # Regex variables for single/double-quoted string patterns.
        # SQ = single-quote char (workaround for shell quoting in =~ expressions).
        local SQ="'"
        local _re_sq="(bash|sh)[[:space:]]+-c[[:space:]]+${SQ}([^${SQ}]*)${SQ}"
        local _re_dq='(bash|sh)[[:space:]]+-c[[:space:]]+"([^"]*)"'
        local _re_eval_dq='eval[[:space:]]+"([^"]*)"'
        local _re_eval_sq="eval[[:space:]]+${SQ}([^${SQ}]*)${SQ}"

        case "$normalized_token" in
            bash|sh)
                # bash -c '...' or bash -c "..." unwrap
                local inner=""
                if [[ "$cmd" =~ $_re_sq ]]; then
                    inner="${BASH_REMATCH[2]}"
                elif [[ "$cmd" =~ $_re_dq ]]; then
                    inner="${BASH_REMATCH[2]}"
                else
                    break
                fi
                # FP-guard: skip if inner string is inside echo/printf argument
                [[ "$cmd" =~ (echo|printf)[[:space:]]+"[^"]*-c[[:space:]] ]] && break
                # Unwrap condition: inner leading token must be a command word, not a comment
                local inner_trimmed="${inner#"${inner%%[![:space:]]*}"}"
                local inner_first="${inner_trimmed%%[[:space:]]*}"
                [[ "$inner_first" =~ ^# ]] && break
                [[ "$inner_first" =~ ^[a-zA-Z0-9_/.-]+$ ]] || break
                cmd="$inner"
                depth=$((depth + 1))
                ;;
            eval)
                # eval "inner" or eval 'inner'
                local inner=""
                if [[ "$cmd" =~ $_re_eval_dq ]]; then
                    inner="${BASH_REMATCH[1]}"
                elif [[ "$cmd" =~ $_re_eval_sq ]]; then
                    inner="${BASH_REMATCH[1]}"
                else
                    break
                fi
                local inner_trimmed="${inner#"${inner%%[![:space:]]*}"}"
                local inner_first="${inner_trimmed%%[[:space:]]*}"
                [[ "$inner_first" =~ ^# ]] && break
                [[ "$inner_first" =~ ^[a-zA-Z0-9_/.-]+$ ]] || break
                cmd="$inner"
                depth=$((depth + 1))
                ;;
            *)
                break
                ;;
        esac
    done

    # Normalize backslash-escaped command names (s\ed -> sed, m\utmut -> mutmut)
    # Strip single backslash between two alpha characters (BRE: \\ = literal backslash).
    cmd=$(printf '%s' "$cmd" | sed 's/\([a-zA-Z]\)\\\([a-zA-Z]\)/\1\2/g')

    # Resolve simple $(echo X) -> X (single-word form only; conservative)
    cmd=$(printf '%s' "$cmd" | sed 's/\$( *echo  *\([a-zA-Z0-9_-]*\) *)/\1/g')

    printf '%s' "$cmd"
}

# ---------------------------------------------------------------------------
# Pattern detectors
# ---------------------------------------------------------------------------

# mutmut: any invocation is flagged (mutation testing framework)
_mtg_is_mutmut() {
    [[ "$1" =~ (^|[[:space:]])mutmut([[:space:]]|$) ]] && return 0
    # python -m mutmut
    [[ "$1" =~ (^|[[:space:]])python[[:space:]]+-m[[:space:]]+mutmut([[:space:]]|$) ]] && return 0
    return 1
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
# Check — normalize command first (Gap 2: unwrap bash -c, eval, backslash, echo-subst)
# ---------------------------------------------------------------------------

_MTG_NORM_CMD=$(_mtg_normalize_command "$COMMAND")

_mtg_matched=""
if _mtg_is_mutmut "$_MTG_NORM_CMD"; then
    _mtg_matched="mutmut"
elif _mtg_is_sed_inplace_source "$_MTG_NORM_CMD"; then
    _mtg_matched="sed -i on source file"
elif _mtg_is_pytest_mutating "$_MTG_NORM_CMD"; then
    _mtg_matched="pytest with mutation flag"
fi

# Also check original command against all detectors.
# WHY BOTH NORMALIZED AND RAW: The normalizer is deliberately conservative — it only
# unwraps forms it can safely parse (simple single/double-quoted -c args, eval with
# quoted strings, backslash-escaped names, $(echo X) single-word forms). Any form it
# cannot confidently unwrap (nested quoting, variables in the -c arg, process
# substitutions) is left intact. Running detectors on the raw command as well catches
# patterns that the normalizer declines to unwrap but that are still detectable
# directly (e.g. "sh -c mutmut" where mutmut appears verbatim in the raw string).
# Do NOT collapse this into a single pass — doing so would require the normalizer to be
# exhaustive, which increases FP risk.
if [[ -z "$_mtg_matched" ]]; then
    if _mtg_is_mutmut "$COMMAND"; then
        _mtg_matched="mutmut"
    elif _mtg_is_sed_inplace_source "$COMMAND"; then
        _mtg_matched="sed -i on source file"
    elif _mtg_is_pytest_mutating "$COMMAND"; then
        _mtg_matched="pytest with mutation flag"
    fi
fi

# Gap 3: WORKTREE_PATH unset + active worktrees heuristic.
# If WORKTREE_PATH is unset, we only emit advisory when there are active worktrees
# (reduced-confidence signal). If no worktrees exist, exit silently.
if [[ -z "$_mtg_matched" ]]; then
    exit 0
fi

if [[ "$_MTG_WORKTREE_PATH_SET" == "0" ]]; then
    # Gap 3 path: WORKTREE_PATH unset; check for active worktrees as secondary signal.
    # Need to verify CWD is repo root first.
    if ! _mtg_is_root_cwd; then
        exit 0
    fi
    if ! _mtg_has_active_worktrees; then
        exit 0  # No worktrees -> no signal -> silent allow
    fi
    # Reduced-confidence advisory: active worktrees present but WORKTREE_PATH not set
    _mtg_matched="$_mtg_matched (reduced-confidence: CLAUDE_WORKTREE_PATH unset)"
fi

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
# Flip deferred: FP review 2026-06-04 — see guard-hardening-telemetry-fixes plan.md
# Reason: /var/folders sed records (confirmed FP pre-fix) present in advisory log;
#   Gap 3 reduced-confidence pattern records unsoaked (added this pipeline).
#   Re-run FP review after 10+ sessions with updated guard (post slice-1b) pass.
# TODO(mutation-tooling-guard-promote): one-line flip — change to exit 2
exit 0   # <-- SINGLE PROMOTION LINE
