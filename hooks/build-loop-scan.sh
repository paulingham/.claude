#!/usr/bin/env bash
# Build-Loop Scan — PreToolUse:Bash hook.
#
# Shift-left scan gate: fires on `git commit` inside an agent worktree, scans the
# STAGED DIFF and HARD-BLOCKS (exit 2) an introduced secret before the commit
# object is created. SAST/dependency findings are surfaced advisory (exit 0).
# The secret HARD-BLOCK floor is regex-based (canonical patterns in
# hooks/_lib/build_loop_scan.py) so it is tool-independent — a missing scanner
# never silently disables the secret block. This is a FIRST-pass gate; the
# security-review phase remains the authoritative second-pass gate (Iron Law 5).
#
# Bypass: CLAUDE_DISABLE_BUILD_LOOP_SCAN=1.
#
# enforces: protocols/engineering-invariants.md:Security Baseline
# protects: security-review, build-implementation

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/harness-paths.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:${TOOL_NAME:-Bash}"
trap 'log_hook_event $?' EXIT

set -uo pipefail

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

# TASK_ID: use live pipeline task id when available; stable fallback for solo-hook runs.
TASK_ID="${CLAUDE_TASK_ID:-inline-build-scan-gate}"

is_caller_in_worktree() {
    local toplevel
    [[ -n "${CLAUDE_WORKTREE_PATH:-}" && "$CLAUDE_WORKTREE_PATH" == *"/.claude/worktrees/agent-"* ]] && return 0
    toplevel=$(git rev-parse --show-toplevel 2>/dev/null)
    [[ "$toplevel" == *"/.claude/worktrees/agent-"* ]] || [[ "$PWD" == *"/.claude/worktrees/agent-"* ]]
}

# _cmd_has_commit_subcommand: true when the command is `git [global-flags...] commit [flags...]`.
# Matches: git commit, git -c k=v commit, git --no-pager commit, git commit --amend.
# Does NOT match: git log --grep=commit, git log --format='...commit...'.
# Strategy: strip the leading `git` token and any global flags (-c k=v, --flag, -f)
# until we find a non-flag token; the subcommand must be `commit`.
_cmd_has_commit_subcommand() {
    local cmd="$1"
    # Must start with `git` (with optional whitespace before global flags)
    [[ "$cmd" =~ ^[[:space:]]*git[[:space:]] ]] || return 1
    # Drop the `git` token, then walk remaining tokens.
    local rest="${cmd#*git}"
    set -f        # noglob: prevent glob expansion of $rest (e.g. core.pager=*.txt)
    set -- $rest
    set +f        # restore globbing
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -c)      shift 2; continue ;;  # -c key=value: skip two tokens
            --*)     shift;   continue ;;  # --no-pager, --git-dir=..., etc.
            -[!-]*)  shift;   continue ;;  # single-dash short flags (-C, -p)
            commit)  return 0 ;;           # subcommand found
            *)       return 1 ;;           # other subcommand (log, push, etc.)
        esac
    done
    return 1
}

is_git_commit() {
    _cmd_has_commit_subcommand "$1"
}

staged_file_count() {
    git diff --cached --name-only 2>/dev/null | grep -c . || true
}

detect_sast_tool() {
    command -v semgrep >/dev/null 2>&1 && { echo "semgrep"; return; }
    command -v bearer >/dev/null 2>&1 && { echo "bearer"; return; }
    echo ""
}

staged_dep_manifest() {
    git diff --cached --name-only 2>/dev/null \
        | grep -m1 -E '(package\.json|requirements\.txt|Gemfile|Gemfile\.lock)$' || true
}

count_sast_findings() {
    # $1 = tool name. Advisory scan of staged files; returns a finding count.
    local tool="$1"
    [[ -z "$tool" ]] && { echo 0; return; }
    if [[ "$tool" == "semgrep" ]]; then
        # NUL-delimited filenames (-z / xargs -0) prevent word-splitting on
        # spaces; -- terminates the semgrep option list so filenames starting
        # with - cannot be parsed as flags (argument-injection defence).
        git diff --cached --name-only -z 2>/dev/null \
            | xargs -0 semgrep scan --config auto --severity ERROR --json -- 2>/dev/null \
            | jq -r '.results | length' 2>/dev/null || echo 0
        return
    fi
    echo 0
}

count_dep_findings() {
    # Advisory npm-audit when an npm manifest is staged; 0 otherwise.
    [[ -z "$1" ]] && { echo 0; return; }
    command -v npm >/dev/null 2>&1 || { echo 0; return; }
    npm audit --json 2>/dev/null \
        | jq -r '.metadata.vulnerabilities.total // 0' 2>/dev/null || echo 0
}

write_artifact() {
    # $1 verdict  $2 secret_categories  $3 sast_count  $4 dep_count
    #   $5 tools_present  $6 staged_count
    local dir="$HARNESS_DATA/pipeline-state/${TASK_ID}/build-artifacts"
    mkdir -p "$dir" 2>/dev/null || return 0
    jq -nc \
        --arg verdict "$1" \
        --arg cats "$2" \
        --argjson sast "$3" \
        --argjson dep "$4" \
        --arg tools "$5" \
        --argjson staged "$6" \
        '{verdict:$verdict,
          secret_categories:(if $cats=="" then [] else ($cats|split(",")) end),
          sast_findings_count:$sast, dep_findings_count:$dep,
          tools_present:(if $tools=="" then [] else ($tools|split(",")) end),
          staged_file_count:$staged}' \
        > "$dir/build-loop-scan-report.json" 2>/dev/null || return 0
}

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[[ "$TOOL_NAME" != "Bash" ]] && exit 0
is_git_commit "$COMMAND" || exit 0
is_caller_in_worktree || exit 0

if [[ "${CLAUDE_DISABLE_BUILD_LOOP_SCAN:-0}" == "1" ]]; then
    echo "BUILD-LOOP-SCAN BYPASSED via CLAUDE_DISABLE_BUILD_LOOP_SCAN=1 — security-review (second-pass) still gates." >&2
    printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/build_loop_scan_cli.py" >/dev/null 2>&1 || true
    write_artifact "BYPASSED" "" 0 0 "" "$(staged_file_count)"
    exit 0
fi

STAGED_COUNT="$(staged_file_count)"
SAST_TOOL="$(detect_sast_tool)"
DEP_MANIFEST="$(staged_dep_manifest)"
TOOLS_PRESENT="$SAST_TOOL"
[[ -n "$DEP_MANIFEST" ]] && command -v npm >/dev/null 2>&1 && TOOLS_PRESENT="${TOOLS_PRESENT:+$TOOLS_PRESENT,}npm"

# Capture verdict and CLI exit status; a crash/exception must fail-closed.
DECISION=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/build_loop_scan_cli.py")
CLI_EXIT=$?
VERDICT=$(printf '%s\n' "$DECISION" | sed -n '1p')
CATEGORIES=$(printf '%s\n' "$DECISION" | sed -n '2p')

# Fail-closed: non-zero CLI exit or unrecognised verdict blocks conservatively.
verdict_is_valid() { case "$1" in PASSED|FINDINGS|SKIPPED|BYPASSED|BLOCKED) return 0 ;; esac; return 1; }
if [[ $CLI_EXIT -ne 0 ]] || ! verdict_is_valid "$VERDICT"; then
    echo 'BUILD-LOOP-SCAN: scan could not run — blocking conservatively (set CLAUDE_DISABLE_BUILD_LOOP_SCAN=1 only if you accept the risk).' >&2
    exit 2
fi

# Secret block wins outright — assert it before spending cycles on SAST/dep.
if [[ "$VERDICT" == "BLOCKED" ]]; then
    write_artifact "BLOCKED" "$CATEGORIES" 0 0 "$TOOLS_PRESENT" "$STAGED_COUNT"
    cat >&2 <<EOF
BUILD-LOOP-SCAN BLOCKED: secret detected [${CATEGORIES}] in staged diff.
Remediate before commit — never commit a secret. Move the literal to an env var
or secret store. Set CLAUDE_DISABLE_BUILD_LOOP_SCAN=1 ONLY for a confirmed false positive.
EOF
    exit 2
fi

if [[ -z "$TOOLS_PRESENT" ]]; then
    write_artifact "SKIPPED" "" 0 0 "" "$STAGED_COUNT"
    echo "BUILD-LOOP-SCAN SKIPPED: no SAST/dep scan tools present (secret regex floor still active)." >&2
    exit 0
fi

# SAST/dep are advisory: a finding surfaces FINDINGS (exit 0), never a block.
SAST_COUNT="$(count_sast_findings "$SAST_TOOL")"
DEP_COUNT="$(count_dep_findings "$DEP_MANIFEST")"

if [[ "$SAST_COUNT" -gt 0 || "$DEP_COUNT" -gt 0 ]]; then
    write_artifact "FINDINGS" "" "$SAST_COUNT" "$DEP_COUNT" "$TOOLS_PRESENT" "$STAGED_COUNT"
    echo "BUILD-LOOP-SCAN FINDINGS: ${SAST_COUNT} SAST, ${DEP_COUNT} dependency. Auto-fix if mechanical per SKILL Step 2c; else security-review (second-pass) gates. (advisory — commit proceeds)" >&2
    exit 0
fi

write_artifact "PASSED" "" 0 0 "$TOOLS_PRESENT" "$STAGED_COUNT"
exit 0
