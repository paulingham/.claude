#!/usr/bin/env bash
# Intake Backstop — PreToolUse hook for BOTH Bash and Agent matchers.
#
# enforces: protocols/work-class-routing.md:Intake gate
# protects: intake, pipeline
#
# Closes the gap where the orchestrator starts doing work (installing deps,
# running tests, building, deploying, mutating files/git, spawning specialized
# build/review agents) WITHOUT first running /intake to classify and route the
# request through the pipeline. The hook branches on the tool name from stdin:
#   - Bash:  FAIL-OPEN block-list — exit 2 only for clear work detectors W1-W8.
#   - Agent: FAIL-CLOSED allow-list — exit 2 for specialized roles, allow
#            architect + non-specialized.
#
# SHARED short-circuits (all fail-open / exit 0): wrong hook profile, escape
# env, subagent caller, in-worktree caller, intake marker present. Every error
# path defaults to ALLOW so a buggy detector or a missing lib never wedges the
# session.
#
# SID DEPENDENCY (read this before trusting the marker): the marker round-trip
# between intake-fingerprint-audit.sh (writer) and this reader requires the SAME
# SID, sanitised identically, in both hook invocations. The SID comes from the
# hook's STDIN .session_id (a stable per-session id the harness injects into
# every hook payload) — NOT from the CLAUDE_SESSION_ID env, which is NOT set in
# this harness's hook env. The old env-based derivation fell back to `local-$$`,
# the hook subprocess PID, which differs on every invocation, so the writer's
# marker (local-<PID_A>) never matched the reader's lookup (local-<PID_B>) and
# the gate over-blocked every command after a real /intake. All three hooks now
# call the shared resolve_session_id helper (_lib/session-id.sh): stdin
# .session_id, then env, then local-$$. The per-session intake marker
# ($HARNESS_DATA/intake-markers/$SID.marker) is the SOLE "intake ran this
# session" satisfier; it is written by intake-fingerprint-audit.sh on every
# /intake and cleared per session by session-start-bootstrap.sh, so it is
# inherently session-scoped. AC-13 guards the round-trip via the real stdin
# .session_id channel (no env crutch).
#
# WHY NO GLOBAL ACTIVE-PIPELINE SATISFIER (removed — see AC-12): an earlier
# revision opened the gate whenever _psp_find_active_pipelines reported ANY
# pipeline-state file with `verdict: in_progress` anywhere under
# $HARNESS_DATA/pipeline-state. That predicate is GLOBAL and UNSCOPED — real
# pipeline.md frontmatter carries no session id (task_id / phase / verdict /
# timestamp / branch only, verified against live state), so a SINGLE orphaned
# in_progress pipeline left behind by a dead session disabled the gate for
# EVERY subsequent session, permanently. On a box with many stale
# pipeline-state dirs the false-allow condition is effectively always present,
# making the gate dead-on-arrival. A resumed pipeline arms the marker
# explicitly (skills/pipeline-resume Step 0 touches it) instead of relying on
# the global scan, so dropping this satisfier does not block a legitimate
# resume.
#
# FAILURE MODE = OVER-BLOCK (recoverable), NOT UNDER-BLOCK: if the stdin
# .session_id is ever absent across the writer and reader hook events, both
# sides fall back to local-$$ (distinct PIDs), the marker is not found after a
# real /intake and the gate over-blocks. That is the SAFE direction — a blocked
# work command is recoverable via the CLAUDE_INTAKE_BACKSTOP=off escape or by
# re-running /intake, whereas an under-block (the old global-pipeline bug)
# silently lets ungated work through.

_IBS_HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=/dev/null
source "$_IBS_HOOK_DIR/_lib/harness-paths.sh"
# shellcheck source=/dev/null
source "$_IBS_HOOK_DIR/_lib/session-id.sh"
# shellcheck source=/dev/null
source "$_IBS_HOOK_DIR/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:${TOOL_NAME:-Bash}"
trap 'log_hook_event $?' EXIT

set -uo pipefail

# shellcheck source=/dev/null
source "$_IBS_HOOK_DIR/hook-profile.sh" && check_hook_profile "standard" || exit 0

# ----- SHARED short-circuits (steps 1-4, all fail-open) ---------------------

# Step 2: per-session escape hatch.
[[ "${CLAUDE_INTAKE_BACKSTOP:-}" == "off" ]] && exit 0

INPUT=$(cat)
TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)

# Step 3a: caller is a subagent (harness injects subagent_type for every
# subagent tool call; empty = the orchestrator's own call). Subagents are
# trusted to do work inside their worktrees.
CALLER_SUBAGENT=$(printf '%s' "$INPUT" | jq -r '.subagent_type // empty' 2>/dev/null)
[[ -n "$CALLER_SUBAGENT" ]] && exit 0

# Step 3b: CWD/worktree fallback (orchestrator-discipline.sh:62-71 shape).
_ibs_caller_in_worktree() {
    local toplevel
    [[ -n "${CLAUDE_WORKTREE_PATH:-}" && "$CLAUDE_WORKTREE_PATH" == *"/.claude/worktrees/agent-"* ]] && return 0
    toplevel=$(git rev-parse --show-toplevel 2>/dev/null)
    [[ "$toplevel" == *"/.claude/worktrees/agent-"* ]] || [[ "$PWD" == *"/.claude/worktrees/agent-"* ]]
}
_ibs_caller_in_worktree && exit 0

# Step 4: intake marker present. SID derives from stdin .session_id via the
# shared resolve_session_id helper — IDENTICAL to the writer
# (intake-fingerprint-audit.sh) and the clearer (session-start-bootstrap.sh), so
# the marker the writer dropped this session is the marker this reader looks up.
SID=$(resolve_session_id "$INPUT")
[[ -f "$HARNESS_DATA/intake-markers/$SID.marker" ]] && exit 0

# NOTE: there is deliberately NO global active-pipeline satisfier here. See the
# "WHY NO GLOBAL ACTIVE-PIPELINE SATISFIER" block in the header — an unscoped
# in_progress-pipeline scan let one orphaned state file disable the gate for
# every session. The session-scoped marker above is the only "intake ran"
# signal; pipeline-resume arms it explicitly (skills/pipeline-resume Step 0).

# ----- Block message (shared) -----------------------------------------------
_ibs_block() {
    cat >&2 <<'EOF'
BLOCKED: This looks like work but /intake hasn't run this session. Invoke /harness:intake to classify and route (or /harness:pipeline-resume to continue an interrupted pipeline), or set CLAUDE_INTAKE_BACKSTOP=off for this session if you're certain.
EOF
    exit 2
}

# =====================================================================
# Agent branch — FAIL-CLOSED allow-list.
# =====================================================================
if [[ "$TOOL_NAME" == "Agent" ]]; then
    # The SPAWN TARGET lives at .tool_input.subagent_type (distinct from the
    # CALLER's .subagent_type used in step 3). Confirmed against
    # pre-agent-allowlist.sh:36.
    TARGET=$(printf '%s' "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)
    # Strip an optional `harness:` prefix for matching.
    TARGET_BARE="${TARGET#harness:}"
    # Allow: empty/non-specialized target, or architect (plan phase precedes intake-routing).
    [[ -z "$TARGET_BARE" || "$TARGET_BARE" == "architect" ]] && exit 0
    case "$TARGET_BARE" in
        software-engineer|frontend-engineer|qa-engineer|database-engineer|infrastructure-engineer|\
        code-reviewer|security-engineer|product-reviewer|patch-critic)
            _ibs_block
            ;;
        *)
            # Unknown / non-specialized target — fail open.
            exit 0
            ;;
    esac
fi

# =====================================================================
# Bash branch — FAIL-OPEN block-list (W1-W8).
# =====================================================================
[[ "$TOOL_NAME" != "Bash" ]] && exit 0

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
[[ -z "$COMMAND" ]] && exit 0

# State-dir allowance: redirects / fs verbs targeting these roots are
# coordination/state writes, not "work". A path token is state-safe if it sits
# under /tmp, $HARNESS_DATA, or one of the named state subdirs.
_ibs_path_is_state() {
    local p="$1"
    [[ "$p" == /tmp/* || "$p" == /tmp ]] && return 0
    [[ -n "${HARNESS_DATA:-}" && "$p" == "$HARNESS_DATA"* ]] && return 0
    [[ "$p" =~ (^|/)(pipeline-state|metrics|learning)(/|$) ]] && return 0
    [[ "$p" =~ (^|/)\.claude(/|$) ]] && return 0
    return 1
}

# W1 — package install.
_ibs_w1_pkg_install() {
    [[ "$1" =~ (npm|yarn|pnpm)[[:space:]]+(add|install|i)([[:space:]]|$) ]] && return 0
    [[ "$1" =~ pip[0-9]?[[:space:]]+install([[:space:]]|$) ]] && return 0
    [[ "$1" =~ bundle[[:space:]]+(install|add)([[:space:]]|$) ]] && return 0
    [[ "$1" =~ gem[[:space:]]+install([[:space:]]|$) ]] && return 0
    [[ "$1" =~ cargo[[:space:]]+add([[:space:]]|$) ]] && return 0
    [[ "$1" =~ go[[:space:]]+get([[:space:]]|$) ]] && return 0
    [[ "$1" =~ (apt-get|apt)[[:space:]]+install([[:space:]]|$) ]] && return 0
    [[ "$1" =~ brew[[:space:]]+install([[:space:]]|$) ]] && return 0
    return 1
}

# W2 — test runner on source. Read-only flags exempt the command.
_ibs_w2_test_runner() {
    [[ "$1" =~ (--collect-only|--co|--dry-run|--list-tests) ]] && return 1
    [[ "$1" =~ (^|[[:space:]])pytest([[:space:]]|$) ]] && return 0
    [[ "$1" =~ npm[[:space:]]+test([[:space:]]|$) ]] && return 0
    [[ "$1" =~ (^|[[:space:]])(jest|rspec)([[:space:]]|$) ]] && return 0
    [[ "$1" =~ go[[:space:]]+test([[:space:]]|$) ]] && return 0
    [[ "$1" =~ cargo[[:space:]]+test([[:space:]]|$) ]] && return 0
    [[ "$1" =~ (^|[[:space:]])bats[[:space:]] ]] && return 0
    [[ "$1" =~ rails[[:space:]]+test([[:space:]]|$) ]] && return 0
    return 1
}

# W3 — build.
_ibs_w3_build() {
    [[ "$1" =~ npm[[:space:]]+run[[:space:]]+build([[:space:]]|$) ]] && return 0
    [[ "$1" =~ (^|[[:space:]])make([[:space:]]|$) && ! "$1" =~ (-n|--dry-run|--just-print) ]] && return 0
    [[ "$1" =~ cargo[[:space:]]+build([[:space:]]|$) ]] && return 0
    [[ "$1" =~ go[[:space:]]+build([[:space:]]|$) ]] && return 0
    [[ "$1" =~ (^|[[:space:]])tsc([[:space:]]|$) ]] && return 0
    [[ "$1" =~ (^|[[:space:]])webpack([[:space:]]|$) ]] && return 0
    [[ "$1" =~ vite[[:space:]]+build([[:space:]]|$) ]] && return 0
    [[ "$1" =~ assets:precompile ]] && return 0
    return 1
}

# W4 — deploy. Read-only counterparts (kubectl get / terraform plan / docker ps) exempt.
_ibs_w4_deploy() {
    [[ "$1" =~ kubectl[[:space:]]+(get|describe|logs|config) ]] && return 1
    [[ "$1" =~ terraform[[:space:]]+(plan|show|validate|fmt|output) ]] && return 1
    [[ "$1" =~ docker[[:space:]]+(ps|images|logs|inspect) ]] && return 1
    [[ "$1" =~ (^|[[:space:]])deploy([[:space:]]|$) ]] && return 0
    [[ "$1" =~ gh[[:space:]]+release[[:space:]]+create ]] && return 0
    [[ "$1" =~ (^|[[:space:]])heroku([[:space:]]|$) ]] && return 0
    [[ "$1" =~ fly[[:space:]]+deploy ]] && return 0
    [[ "$1" =~ kubectl[[:space:]]+apply ]] && return 0
    [[ "$1" =~ terraform[[:space:]]+apply ]] && return 0
    [[ "$1" =~ docker[[:space:]]+push ]] && return 0
    return 1
}

# W5 — in-place file mutation outside state dirs.
_ibs_w5_inplace() {
    [[ "$1" =~ sed[[:space:]]+(-i|--in-place) ]] && return 0
    [[ "$1" =~ (^|[[:space:]])truncate([[:space:]]|$) ]] && return 0
    [[ "$1" =~ dd[[:space:]].*of= ]] && return 0
    # tee (non -a/--append) to a non-state path.
    if [[ "$1" =~ (^|[[:space:]])tee([[:space:]]|$) && ! "$1" =~ tee[[:space:]]+(-a|--append) ]]; then
        local tgt="${1##*tee }"; tgt="${tgt%% *}"
        _ibs_path_is_state "$tgt" || return 0
    fi
    # `>`/`>>` redirect to a path outside the state-dir set.
    if [[ "$1" =~ \>\>?[[:space:]]*([^[:space:]]+) ]]; then
        local rt="${BASH_REMATCH[1]}"
        _ibs_path_is_state "$rt" || return 0
    fi
    return 1
}

# W6 — fs mutation verbs whose target is outside state dirs.
_ibs_w6_fs_mutation() {
    [[ "$1" =~ (^|[[:space:]])(mkdir|mv|cp|rm|touch|rmdir|ln)([[:space:]]|$) ]] || return 1
    # Inspect every non-flag token; block if ANY token is a non-state path-like
    # argument (contains a slash or looks like a filename). Fail-open: a command
    # whose only path tokens are state-safe is allowed.
    local tok
    for tok in $1; do
        case "$tok" in
            mkdir|mv|cp|rm|touch|rmdir|ln|-*|sudo) continue ;;
        esac
        # Treat tokens with a slash, or a plain filename, as path targets.
        if [[ "$tok" == */* || "$tok" =~ \. ]]; then
            _ibs_path_is_state "$tok" || return 0
        fi
    done
    return 1
}

# W7 — git history/index mutation. Read-only git verbs exempt.
_ibs_w7_git_mutation() {
    [[ "$1" =~ git[[:space:]]+(status|log|diff|show|rev-parse|branch[[:space:]]+--list|remote|config[[:space:]]+--get) ]] && return 1
    [[ "$1" =~ gh[[:space:]]+pr[[:space:]]+(view|list|checks|diff|status) ]] && return 1
    [[ "$1" =~ git[[:space:]]+(commit|add|merge|rebase|reset|cherry-pick|push)([[:space:]]|$) ]] && return 0
    [[ "$1" =~ git[[:space:]]+(checkout|switch)[[:space:]]+(-b|-B|-c|-C|[A-Za-z]) ]] && return 0
    [[ "$1" =~ gh[[:space:]]+pr[[:space:]]+(create|merge) ]] && return 0
    return 1
}

# W8 — migration / destructive DB (governance-capture.sh:65-72 shapes).
_ibs_w8_migration() {
    [[ "$1" =~ db:migrate ]] && return 0
    [[ "$1" =~ alembic[[:space:]]+upgrade ]] && return 0
    [[ "$1" =~ flyway[[:space:]]+migrate ]] && return 0
    [[ "$1" =~ DROP[[:space:]]+(TABLE|DATABASE) ]] && return 0
    return 1
}

_ibs_is_work() {
    _ibs_w1_pkg_install "$1" && return 0
    _ibs_w2_test_runner "$1" && return 0
    _ibs_w3_build "$1" && return 0
    _ibs_w4_deploy "$1" && return 0
    _ibs_w5_inplace "$1" && return 0
    _ibs_w6_fs_mutation "$1" && return 0
    _ibs_w7_git_mutation "$1" && return 0
    _ibs_w8_migration "$1" && return 0
    return 1
}

_ibs_is_work "$COMMAND" || exit 0

_ibs_block
