#!/usr/bin/env bash

# Read JSON input
input=$(cat)
cwd=$(echo "$input" | jq -r '.workspace.current_dir')

# Change to the working directory for git commands
cd "$cwd" 2>/dev/null || cd "$HOME"

# Get current directory name (like %c in zsh)
current_dir=$(basename "$(pwd)")

# Check if we're in a git repository and get branch info
git_info=""
if git rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git symbolic-ref --short HEAD 2>/dev/null || git describe --tags --exact-match 2>/dev/null || git rev-parse --short HEAD 2>/dev/null)
    if [ -n "$branch" ]; then
        # Check if repository is dirty
        if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null || [ -n "$(git ls-files --others --exclude-standard 2>/dev/null)" ]; then
            git_info=" git:($branch) ✗"
        else
            git_info=" git:($branch)"
        fi
    fi
fi

# Extract model name (try multiple possible paths defensively)
model=$(echo "$input" | jq -r '.model // empty' 2>/dev/null)
model_info=""
if [ -n "$model" ]; then
    model_info=" \033[35m[$model]\033[0m"
fi

# Extract context window usage percentage (try multiple possible paths defensively)
ctx_pct=$(echo "$input" | jq -r '.context.used_percent // .context_window.used_percent // empty' 2>/dev/null)
ctx_info=""
if [ -n "$ctx_pct" ]; then
    # Round to integer for display
    ctx_int=$(printf "%.0f" "$ctx_pct" 2>/dev/null || echo "0")
    # Color-code: green < 50, yellow 50-80, red > 80
    if [ "$ctx_int" -gt 80 ] 2>/dev/null; then
        ctx_color="\033[1;31m"
    elif [ "$ctx_int" -ge 50 ] 2>/dev/null; then
        ctx_color="\033[1;33m"
    else
        ctx_color="\033[1;32m"
    fi
    ctx_info=" ${ctx_color}ctx:${ctx_int}%\033[0m"

    # Bridge context data for hooks (per-install per-session state, Cloud-safe).
    # PPID-scoped so concurrent Claude sessions sharing $HOME do not collide.
    if [ -n "$ctx_int" ]; then
        # shellcheck source=hooks/_lib/state-dir.sh
        source "${HARNESS_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/state-dir.sh" 2>/dev/null && _ensure_state_dir 2>/dev/null && \
          printf '%s\n' "$ctx_int" | _state_write "ctx-percent-${PPID}" 2>/dev/null
    fi
fi

# Gear segment (Phase A/B three-gear classifier). Additive/no-op when no
# gear-<session_id> marker exists yet — never blocks the rest of the line.
# Keyed by session_id, NOT PPID: gear-select.sh (a UserPromptSubmit hook)
# and this statusline invocation are different subprocesses with different
# PPIDs, so a PPID-keyed read could never see what gear-select wrote (see
# hooks/_lib/gear-gate.sh header for the full rationale). Session id is the
# one value stable across the whole session, carried in this same stdin
# payload as .session_id.
gear_info=""
session_id=$(echo "$input" | jq -r '.session_id // empty' 2>/dev/null)
gear=""
if [ -n "$session_id" ]; then
    gear=$(
      source "${HARNESS_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/state-dir.sh" 2>/dev/null && \
        _state_read "gear-${session_id}" 2>/dev/null
    )
fi
if [ -n "$gear" ]; then
    case "$gear" in
        PAIR) gear_color="\033[36m" ;;
        BUILD) gear_color="\033[33m" ;;
        PIPELINE) gear_color="\033[35m" ;;
        *) gear_color="" ;;
    esac
    if [ -n "$gear_color" ]; then
        gear_info=" ${gear_color}⚙ ${gear}\033[0m"
    fi
fi

# Use printf with %b for segments containing escape codes so ANSI colors render
printf "\033[1;32m➜\033[0m \033[36m%s\033[0m%s%b%b%b" "$current_dir" "$git_info" "$model_info" "$ctx_info" "$gear_info"
