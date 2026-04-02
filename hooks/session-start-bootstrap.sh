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

echo ""
echo "IRON LAWS:"
echo "- NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST"
echo "- NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE"
echo "- THE ORCHESTRATOR NEVER WRITES SOURCE CODE"
echo "- NO PHASE SKIPPED. NO GATE BYPASSED. NO SKILL OMITTED."
