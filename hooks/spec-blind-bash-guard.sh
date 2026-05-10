#!/usr/bin/env bash
# spec-blind-bash-guard PreToolUse hook (Bash).
#
# Closes the Bash bypass surface for the spec-blind-validator. Without this
# guard, `cat src/x.ts` (or `node -e 'require("./src/x")'`) would let the
# validator read implementation source even with the read-guard active.
#
# When subagent_type == spec-blind-validator:
#   1. Reuses find_blocking_clause from hooks/_lib/no-shell-read-helpers.sh
#      to detect cat/head/tail/sed/awk targeting paths inside the repo —
#      the existing per-clause parser returns the offending command word.
#   2. Adds spec-blind-specific shape detection: node -e, python -c,
#      ruby -e, perl -e, xxd, hexdump, grep -r <src>, find <src>.
#   3. Allows ONLY commands matching the 7-runner allowlist at
#      hooks/_lib/spec-blind-test-runners.txt.
#
# For every other subagent, fast-exits 0. The fast-exit branch (grep -F over
# raw stdin BEFORE jq) preserves the AC17 budget for the no-op path even
# though Bash itself is the highest-volume PreToolUse matcher.
#
# IF SPEC-BLIND BASH IS LEAKING: check .subagent_type top-level JSON field.
# IF BASH GUARD IS OVER-BLOCKING legitimate test runs: check the runner ladder
# at hooks/_lib/spec-blind-test-runners.txt — if your test command isn't there,
# add it (V1 ships exactly 7 entries).
#
# enforces: rules/_detail/pipeline-protocol.md (Final Gate § In-Cycle Fix Rule)
# protects: spec-blind-validate

set -uo pipefail

INPUT=$(cat)
if ! printf '%s' "$INPUT" | grep -F -q "spec-blind-validator"; then
  exit 0
fi

# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Bash"
trap 'log_hook_event $?' EXIT

TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')
SUBAGENT_TYPE=$(printf '%s' "$INPUT" | jq -r '.subagent_type // empty')
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
SESSION_RAW=$(printf '%s' "$INPUT" | jq -r '.session_id // empty')
SESSION=$(printf '%s' "$SESSION_RAW" | tr -dc 'A-Za-z0-9_-' | head -c 64)
[[ -z "$SESSION" ]] && SESSION="unknown"

[[ "$SUBAGENT_TYPE" != "spec-blind-validator" ]] && exit 0
[[ "$TOOL_NAME" != "Bash" ]] && exit 0
[[ -z "$COMMAND" ]] && exit 0

# ---- Allowlist check ---------------------------------------------------------
# If the command matches one of the 7 enumerated test runners exactly, allow.
RUNNER_FILE="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/spec-blind-test-runners.txt"
ALLOWED=0
if [[ -f "$RUNNER_FILE" ]]; then
  while IFS= read -r pat; do
    case "$pat" in ''|'#'*) continue ;; esac
    if [[ "$COMMAND" =~ $pat ]]; then
      ALLOWED=1
      break
    fi
  done < "$RUNNER_FILE"
fi

if [[ "$ALLOWED" -eq 1 ]]; then
  exit 0
fi

# ---- Content-leak detection --------------------------------------------------
# Reuse the existing per-clause parser from no-shell-read for cat|head|tail
# targeting in-repo paths. find_blocking_clause returns the offending command
# word (e.g. "cat") on hit, empty otherwise.
REPO_ROOT=$(git -C "$(pwd)" rev-parse --show-toplevel 2>/dev/null || echo "$(pwd)")

OFFENDER=""
# shellcheck source=/dev/null
if [[ -f "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/no-shell-read-helpers.sh" ]]; then
  source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/no-shell-read-helpers.sh"
  OFFENDER=$(find_blocking_clause "$COMMAND" "$REPO_ROOT" 2>/dev/null || true)
fi

# Spec-blind-specific shapes the standard helper does not cover.
# Each pattern is an ERE matched against the full command string.
SPEC_BLIND_LEAK_PATTERNS=(
  'sed[[:space:]]+-n'
  'sed[[:space:]]+[^|]*[[:space:]]+[^[:space:]/]*src/'
  'awk[[:space:]]+[^|]*[[:space:]]+[^[:space:]/]*src/'
  'node[[:space:]]+-e'
  'python[[:space:]]+-c'
  'python3[[:space:]]+-c'
  'ruby[[:space:]]+-e'
  'perl[[:space:]]+-e'
  'xxd([[:space:]]|$)'
  'hexdump([[:space:]]|$)'
  'grep[[:space:]]+-r[[:space:]]'
  'find[[:space:]]+[^[:space:]]*src/'
  'find[[:space:]]+[^[:space:]]*lib/'
  'find[[:space:]]+[^[:space:]]*app/'
)

if [[ -z "$OFFENDER" ]]; then
  for pat in "${SPEC_BLIND_LEAK_PATTERNS[@]}"; do
    if [[ "$COMMAND" =~ $pat ]]; then
      OFFENDER="${BASH_REMATCH[0]%% *}"
      break
    fi
  done
fi

# Either the command matched no allowlist entry AND triggered a leak shape,
# OR it matched no allowlist entry at all. Both are blocked.
LOG_DIR="${HOME:-/tmp}/.claude/metrics/$SESSION"
mkdir -p "$LOG_DIR" 2>/dev/null || exit 2
LOG_FILE="$LOG_DIR/spec-blind-violations.jsonl"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
[[ -z "$OFFENDER" ]] && OFFENDER="non-allowlisted-command"

jq -nc \
  --arg ts "$TS" \
  --arg subagent "spec-blind-validator" \
  --arg tool "Bash" \
  --arg cmd "$COMMAND" \
  --arg offender "$OFFENDER" \
  --arg session "$SESSION" \
  --arg guard "bash-guard" \
  '{ts:$ts, record_type:"spec_blind_blocked", subagent_type:$subagent, tool:$tool, attempted_command:$cmd, offender:$offender, session_id:$session, guard:$guard, action:"blocked"}' \
  >> "$LOG_FILE" 2>/dev/null

echo "BLOCKED: spec-blind-validator may not run '$OFFENDER' (full command: $COMMAND). Allowed runners: npm test, pnpm test, yarn test, bundle exec rspec, pytest, cargo test, go test." >&2
exit 2
