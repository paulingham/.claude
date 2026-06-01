#!/usr/bin/env bash
# Session-start hook: bootstrap skill awareness and iron laws
# Outputs a concise skill directory reminder so the model knows what skills exist
#
# enforces: rules/core.md:Iron Laws
# protects: pipeline, pipeline-resume

# ---------------------------------------------------------------------------
# Background services (silent — output goes to logs, not Claude's context)
# ---------------------------------------------------------------------------

# Auto-start automation supervisor if repos are registered and it's not running
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "SessionStart"
trap 'log_hook_event $?' EXIT

SUPERVISOR="$HOME/.claude/automation/supervisor.sh"
SUPERVISOR_PID="$HOME/.claude/automation/supervisor.pid"
REPOS_CONF="$HOME/.claude/automation/repos.conf"

if [[ -x "$SUPERVISOR" && -f "$REPOS_CONF" ]]; then
    # Check if repos.conf has any non-comment, non-empty lines
    REPO_COUNT=$(grep -cvE '^\s*(#|$)' "$REPOS_CONF" 2>/dev/null || echo "0")
    if [[ "$REPO_COUNT" -gt 0 ]]; then
        # Check if supervisor is already running
        RUNNING=false
        if [[ -f "$SUPERVISOR_PID" ]]; then
            PID=$(cat "$SUPERVISOR_PID" 2>/dev/null)
            if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
                RUNNING=true
            fi
        fi
        if [[ "$RUNNING" == false ]]; then
            # Ensure logs directory exists before starting
            mkdir -p "$HOME/.claude/automation/logs"
            # Start supervisor in background, fully detached
            nohup "$SUPERVISOR" start >> "$HOME/.claude/automation/logs/supervisor.log" 2>&1 &
            disown
        fi
    fi
fi

# Auto-register current repo if it has automation.env and isn't registered yet
if [[ -f ".claude/automation.env" || -f "$(git rev-parse --show-toplevel 2>/dev/null)/.claude/automation.env" ]]; then
    CURRENT_REPO=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
    if [[ -n "$CURRENT_REPO" && -f "$REPOS_CONF" ]]; then
        if ! grep -qxF "$CURRENT_REPO" "$REPOS_CONF" 2>/dev/null; then
            echo "$CURRENT_REPO" >> "$REPOS_CONF"
            # Signal supervisor to re-read if running
            if [[ -f "$SUPERVISOR_PID" ]]; then
                PID=$(cat "$SUPERVISOR_PID" 2>/dev/null)
                [[ -n "$PID" ]] && kill -HUP "$PID" 2>/dev/null || true
            fi
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Skill awareness output (this is what goes into Claude's context)
# ---------------------------------------------------------------------------

echo "SKILL AWARENESS BOOTSTRAP:"
echo "Entry: /intake (classify + route) | /pipeline (drive phases)"
echo "Build: /build-implementation, /refactor, /bug-fix"
echo "Review: /code-review + /security-review (parallel)"
echo "Verify: /verify | Test: /qa-test-strategy | Accept: /product-acceptance"
echo "Ship: /pr-creation | Deploy: /deploy + /deployment-verification"
echo "Scaffold: /api-scaffold, /db-migration, /infra-scaffold, /design-system-init"
echo "Plan: /epic-breakdown, /estimation, /story-writing, /tech-spike"
echo "Debug: /debug (persistent state for complex bugs)"
echo "Utils: /forensics (post-incident investigation) | /workstream (parallel feature isolation)"

# Learning system
# shellcheck source=_lib/project-hash.sh
source "$(dirname "${BASH_SOURCE[0]}")/_lib/project-hash.sh"
LEARNING_DIR="$HARNESS_DATA/learning"
LEARNING_PROJECT_HASH=$(_project_hash --fallback "local")
PROJECT_INSTINCTS_DIR="$LEARNING_DIR/$LEARNING_PROJECT_HASH/instincts"

# Bootstrap per-project instincts dir (idempotent, silent)
mkdir -p "$PROJECT_INSTINCTS_DIR" 2>/dev/null

if [[ -d "$LEARNING_DIR" ]]; then
    # Count instincts: per-project first, falling back to global
    PROJECT_INSTINCT_COUNT=$(find "$PROJECT_INSTINCTS_DIR" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    GLOBAL_INSTINCT_COUNT=$(find "$LEARNING_DIR/instincts" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    INSTINCT_SOURCE_DIR=""
    INSTINCT_COUNT=0
    if [[ "$PROJECT_INSTINCT_COUNT" -gt 0 ]]; then
        INSTINCT_SOURCE_DIR="$PROJECT_INSTINCTS_DIR"
        INSTINCT_COUNT="$PROJECT_INSTINCT_COUNT"
    elif [[ "$GLOBAL_INSTINCT_COUNT" -gt 0 ]]; then
        INSTINCT_SOURCE_DIR="$LEARNING_DIR/instincts"
        INSTINCT_COUNT="$GLOBAL_INSTINCT_COUNT"
    fi
    if [[ -n "$INSTINCT_SOURCE_DIR" ]]; then
        echo ""
        echo "LEARNED PATTERNS ($INSTINCT_COUNT instincts):"
        # Show top 5 by confidence (order as grep returns — sorting left to /learn)
        for f in $(grep -l "confidence:" "$INSTINCT_SOURCE_DIR"/*.md 2>/dev/null | head -5); do
            CONF=$(grep "confidence:" "$f" | head -1 | awk '{print $2}')
            PATTERN=$(grep "^## Pattern" -A1 "$f" | tail -1)
            echo "  [$CONF] $PATTERN"
        done
    fi

    # Nudge /learn when observations have accumulated but no per-project instincts exist
    OBSERVATIONS_FILE="$LEARNING_DIR/$LEARNING_PROJECT_HASH/observations.jsonl"
    if [[ -f "$OBSERVATIONS_FILE" && "$PROJECT_INSTINCT_COUNT" -eq 0 ]]; then
        OBS_COUNT=$(wc -l < "$OBSERVATIONS_FILE" 2>/dev/null | tr -d ' ')
        if [[ "$OBS_COUNT" =~ ^[0-9]+$ && "$OBS_COUNT" -ge 3 ]]; then
            echo ""
            echo "LEARN HINT: $OBS_COUNT observations without instincts — invoke /learn"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Pipeline state detection (output to context — critical for resume)
# ---------------------------------------------------------------------------
# DUAL_PATH: extract task_id from a pipeline file path under either layout.
_ssb_task_id_of() {
    local pf="$1" b; b=$(basename "$pf")
    if [[ "$b" == "pipeline.md" ]]; then
        basename "$(dirname "$pf")"
    else
        echo "$b" | sed 's/-pipeline\.md$//'
    fi
}

PIPELINE_DIR="$HARNESS_DATA/pipeline-state"
if [[ -d "$PIPELINE_DIR" ]]; then
    LEGACY=$(find "$PIPELINE_DIR" -maxdepth 1 -name "*-pipeline.md" 2>/dev/null || true)
    NEW=$(find "$PIPELINE_DIR" -mindepth 2 -maxdepth 2 -name "pipeline.md" 2>/dev/null || true)
    ACTIVE_PIPELINES=$(printf '%s\n%s' "$LEGACY" "$NEW" | grep -v '^$' || true)
    if [[ -n "$ACTIVE_PIPELINES" ]]; then
        echo ""
        echo "ACTIVE PIPELINES (invoke /pipeline-resume):"
        while IFS= read -r pfile; do
            [[ -z "$pfile" ]] && continue
            PNAME=$(_ssb_task_id_of "$pfile")
            CURRENT_PHASE=$(grep -E "in_progress" "$pfile" 2>/dev/null | head -1 | sed 's/^- //' | sed 's/:.*//' | xargs)
            if [[ -n "$CURRENT_PHASE" ]]; then
                echo "  - $PNAME: phase=$CURRENT_PHASE"
            else
                echo "  - $PNAME: (check state file)"
            fi
        done <<< "$ACTIVE_PIPELINES"
    fi

    SHIP_COMPLETE=$(grep -rl "Ship:.*completed\|Ship:.*PR_CREATED" "$PIPELINE_DIR" 2>/dev/null | grep -E '(-pipeline\.md|/pipeline\.md)$' | head -1)
    if [[ -n "$SHIP_COMPLETE" ]]; then
        DEPLOY_PENDING=$(grep -l "Deploy:.*pending" "$SHIP_COMPLETE" 2>/dev/null)
        if [[ -n "$DEPLOY_PENDING" ]]; then
            PNAME=$(_ssb_task_id_of "$SHIP_COMPLETE")
            echo ""
            echo "DEPLOY PENDING: $PNAME (Ship complete, Deploy not started — check if PR merged, then invoke /deploy)"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Session memory (orientation after compaction)
# ---------------------------------------------------------------------------
# shellcheck source=_lib/project-hash.sh
source "$(dirname "${BASH_SOURCE[0]}")/_lib/project-hash.sh"
PROJECT_HASH=$(_project_hash --fallback "local")
SESSION_DIR="$HARNESS_DATA/session-memory/$PROJECT_HASH"
if [[ -d "$SESSION_DIR" ]]; then
    # Any of the 4 injectable sub-files with content (not just header + italic
    # description + blanks) means session memory is live for this project.
    HAS_CONTENT=0
    for SUB in codebase-map build-test patterns fragility; do
        FILE="$SESSION_DIR/$SUB.md"
        [[ -f "$FILE" ]] || continue
        LINES=$(grep -cvE '^\s*(#|_|$)' "$FILE" 2>/dev/null || echo "0")
        [[ "$LINES" -gt 0 ]] && { HAS_CONTENT=1; break; }
    done
    if [[ "$HAS_CONTENT" -eq 1 ]]; then
        echo ""
        echo "SESSION MEMORY: Engineering notes exist for this project at $SESSION_DIR — read on resume or after compaction."
    fi
fi

# ---------------------------------------------------------------------------
# Stale worktree detection
# ---------------------------------------------------------------------------
if git rev-parse --git-dir >/dev/null 2>&1; then
    STALE_WORKTREES=$(git worktree list --porcelain 2>/dev/null | grep "^worktree " | grep -c "\.claude/worktrees/" 2>/dev/null || echo "0")
    if [[ "$STALE_WORKTREES" -gt 0 ]]; then
        echo ""
        echo "STALE WORKTREES: $STALE_WORKTREES orphaned worktree(s) in .claude/worktrees/ — clean up with: git worktree remove .claude/worktrees/<name> --force"
    fi
fi

# ---------------------------------------------------------------------------
# Hook anomaly detection (per-hook latency + failure surface)
# ---------------------------------------------------------------------------
HOOK_SUMMARY="$HOME/.claude/scripts/hook-summary.sh"
HOOK_METRICS_DIR="$HARNESS_DATA/metrics"
if [[ -x "$HOOK_SUMMARY" && -d "$HOOK_METRICS_DIR" ]]; then
    # Run anomaly check silently; only surface if exit_code != 0 (anomaly found).
    # Pass through CLAUDE_HOOK_ANOMALY_THRESHOLD so per-session overrides reach the analyzer.
    HOOK_ANOMALY_OUT=$(CLAUDE_HOOK_ANOMALY_THRESHOLD="${CLAUDE_HOOK_ANOMALY_THRESHOLD:-}" \
        "$HOOK_SUMMARY" --anomaly-check --hours 24 2>/dev/null)
    HOOK_ANOMALY_RC=$?
    if [[ "$HOOK_ANOMALY_RC" != "0" ]]; then
        echo ""
        echo "Hook anomaly detected (last 24h, error-rate threshold ${CLAUDE_HOOK_ANOMALY_THRESHOLD:-0.10}):"
        echo "$HOOK_ANOMALY_OUT" | grep -E "^  " | head -5
        echo "Run: scripts/hook-summary.sh --anomaly-check  for full report"
    fi
fi

echo ""
echo "IRON LAWS:"
echo "- NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST"
echo "- NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE"
echo "- THE ORCHESTRATOR NEVER WRITES SOURCE CODE"
echo "- NO PHASE SKIPPED. NO GATE BYPASSED. NO SKILL OMITTED."

# ---------------------------------------------------------------------------
# Version pin check (Wave 5 / A8.3) — sources _lib/session-start-version-check.sh
# ---------------------------------------------------------------------------
source "$(dirname "${BASH_SOURCE[0]}")/_lib/session-start-version-check.sh" 2>/dev/null
declare -F _ssvc_check_version >/dev/null && _ssvc_check_version
