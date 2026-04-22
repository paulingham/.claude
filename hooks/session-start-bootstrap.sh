#!/bin/bash
# Session-start hook: bootstrap skill awareness and iron laws
# Outputs a concise skill directory reminder so the model knows what skills exist

# ---------------------------------------------------------------------------
# Background services (silent — output goes to logs, not Claude's context)
# ---------------------------------------------------------------------------

# Auto-start automation supervisor if repos are registered and it's not running
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
LEARNING_DIR="$HOME/.claude/learning"
if [[ -d "$LEARNING_DIR" ]]; then
    INSTINCT_COUNT=$(find "$LEARNING_DIR/instincts" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$INSTINCT_COUNT" -gt 0 ]]; then
        echo ""
        echo "LEARNED PATTERNS ($INSTINCT_COUNT instincts):"
        # Show top 5 by confidence
        for f in $(grep -l "confidence:" "$LEARNING_DIR/instincts/"*.md 2>/dev/null | head -5); do
            CONF=$(grep "confidence:" "$f" | head -1 | awk '{print $2}')
            PATTERN=$(grep "^## Pattern" -A1 "$f" | tail -1)
            echo "  [$CONF] $PATTERN"
        done
    fi
fi

# ---------------------------------------------------------------------------
# Pipeline state detection (output to context — critical for resume)
# ---------------------------------------------------------------------------
PIPELINE_DIR="$HOME/.claude/pipeline-state"
if [[ -d "$PIPELINE_DIR" ]]; then
    ACTIVE_PIPELINES=$(find "$PIPELINE_DIR" -maxdepth 1 -name "*-pipeline.md" 2>/dev/null)
    if [[ -n "$ACTIVE_PIPELINES" ]]; then
        echo ""
        echo "ACTIVE PIPELINES (invoke /pipeline-resume):"
        while IFS= read -r pfile; do
            [[ -z "$pfile" ]] && continue
            PNAME=$(basename "$pfile" | sed 's/-pipeline\.md$//')
            # Extract current phase from the file
            CURRENT_PHASE=$(grep -E "in_progress" "$pfile" 2>/dev/null | head -1 | sed 's/^- //' | sed 's/:.*//' | xargs)
            if [[ -n "$CURRENT_PHASE" ]]; then
                echo "  - $PNAME: phase=$CURRENT_PHASE"
            else
                echo "  - $PNAME: (check state file)"
            fi
        done <<< "$ACTIVE_PIPELINES"
    fi

    # Check for merged PRs with pending deploy
    SHIP_COMPLETE=$(grep -rl "Ship:.*completed\|Ship:.*PR_CREATED" "$PIPELINE_DIR"/*-pipeline.md 2>/dev/null | head -1)
    if [[ -n "$SHIP_COMPLETE" ]]; then
        DEPLOY_PENDING=$(grep -l "Deploy:.*pending" "$SHIP_COMPLETE" 2>/dev/null)
        if [[ -n "$DEPLOY_PENDING" ]]; then
            PNAME=$(basename "$SHIP_COMPLETE" | sed 's/-pipeline\.md$//')
            echo ""
            echo "DEPLOY PENDING: $PNAME (Ship complete, Deploy not started — check if PR merged, then invoke /deploy)"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Session memory (orientation after compaction)
# ---------------------------------------------------------------------------
# shellcheck source=_lib/project-hash.sh
source "$HOME/.claude/hooks/_lib/project-hash.sh"
PROJECT_HASH=$(_project_hash --fallback "local")
SESSION_NOTES="$HOME/.claude/session-memory/$PROJECT_HASH/notes.md"
if [[ -f "$SESSION_NOTES" ]]; then
    # Check if notes have actual content (not just template)
    CONTENT_LINES=$(grep -cvE '^\s*(#|_|$)' "$SESSION_NOTES" 2>/dev/null || echo "0")
    if [[ "$CONTENT_LINES" -gt 3 ]]; then
        echo ""
        echo "SESSION MEMORY: Engineering notes exist for this project at $SESSION_NOTES — read on resume or after compaction."
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

echo ""
echo "IRON LAWS:"
echo "- NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST"
echo "- NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE"
echo "- THE ORCHESTRATOR NEVER WRITES SOURCE CODE"
echo "- NO PHASE SKIPPED. NO GATE BYPASSED. NO SKILL OMITTED."
