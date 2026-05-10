#!/usr/bin/env bash
# spec-blind-bash-guard PreToolUse hook (Bash).
#
# Closes the Bash bypass surface for the spec-blind-validator. Without this
# guard, `cat src/x.ts` or `node -e 'require("./src/x")'` would leak source
# even with the read-guard active. When subagent_type == spec-blind-validator:
#   1. 7-runner allowlist at hooks/_lib/spec-blind-test-runners.txt. Each
#      pattern's argument suffix excludes shell metachars (& | ; < > $ ` \
#      ( ) cntrl) so chains like `npm test && cat src/x` are rejected
#      (SEC-CRIT-1).
#   2. Otherwise apply leak shapes (cat/head/tail on src|lib|app, sed/awk
#      on src, node -e, python -c, ruby -e, perl -e, xxd, hexdump, grep -r
#      <src>, find <src|lib|app>) via textual prefix matching — does NOT
#      depend on git-rev-parse(pwd) (CR-MED-3).
#   3. Deny-by-default: anything else blocked as `non-allowlisted-command`.
# For every other subagent, fast-exits 0 (grep -F over raw stdin BEFORE jq)
# preserving the AC17 budget for the no-op path.
#
# IF LEAKING: check .subagent_type JSON field OR CLAUDE_SUBAGENT_TYPE env
# (SEC-MED-2 fallback). IF OVER-BLOCKING legitimate test runs: check
# hooks/_lib/spec-blind-test-runners.txt — V1 ships exactly 7 entries.
#
# enforces: rules/_detail/pipeline-protocol.md (Final Gate § In-Cycle Fix Rule)
# protects: spec-blind-validate

set -uo pipefail

INPUT=$(cat)
if ! printf '%s' "$INPUT" | grep -F -q "spec-blind-validator" \
   && [[ "${CLAUDE_SUBAGENT_TYPE:-}" != "spec-blind-validator" ]]; then
  exit 0
fi

# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Bash"
trap 'log_hook_event $?' EXIT

# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/spec-blind-guard-common.sh"
_spec_blind_parse_input

[[ "$SUBAGENT_TYPE" != "spec-blind-validator" ]] && exit 0
[[ "$TOOL_NAME" != "Bash" ]] && exit 0
[[ -z "$COMMAND" ]] && exit 0

# ---- Allowlist check ---------------------------------------------------------
# If the command matches one of the 7 enumerated test runners exactly, allow.
# The patterns reject shell-metachar suffixes (SEC-CRIT-1) so chain bypasses
# fall through to the leak-pattern list below.
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
# Spec-blind-specific shapes — textual prefix matching on `src/`, `lib/`,
# `app/` substrings. CR-MED-3: previously this fell through to
# find_blocking_clause, which resolves relative paths via $(pwd) and
# silently no-oped when pwd was outside the repo (e.g. in bats tests).
# Replacing the call with explicit ERE patterns over the raw command string
# eliminates the env-fragility — the spec-blind threat model is "leak source
# from tree-shaped path tokens", which is detectable from the command text
# alone without needing pwd-resolved repo-root knowledge.
SPEC_BLIND_LEAK_PATTERNS=(
  'cat([[:space:]]+[^[:space:]]+)*[[:space:]]+(/?)((/[^[:space:]]+/)?(src|lib|app)/)'
  'head([[:space:]]+[^[:space:]]+)*[[:space:]]+(/?)((/[^[:space:]]+/)?(src|lib|app)/)'
  'tail([[:space:]]+[^[:space:]]+)*[[:space:]]+(/?)((/[^[:space:]]+/)?(src|lib|app)/)'
  'sed[[:space:]]+-n'
  'sed[[:space:]]+[^|]*(src|lib|app)/'
  'awk[[:space:]]+[^|]*(src|lib|app)/'
  'node[[:space:]]+-e'
  'python3?[[:space:]]+-c'
  'ruby[[:space:]]+-e'
  'perl[[:space:]]+-e'
  'xxd([[:space:]]|$)'
  'hexdump([[:space:]]|$)'
  'grep[[:space:]]+(-[a-zA-Z]*r[a-zA-Z]*[[:space:]]|.*[[:space:]]-r[[:space:]])'
  'find[[:space:]]+[^|]*(src|lib|app)/'
)

OFFENDER=""
for pat in "${SPEC_BLIND_LEAK_PATTERNS[@]}"; do
  if [[ "$COMMAND" =~ $pat ]]; then
    # Extract leading verb word for the offender field.
    OFFENDER="${COMMAND%% *}"
    break
  fi
done

# Either the command matched no allowlist entry AND triggered a leak shape,
# OR it matched no allowlist entry at all. Both are blocked.
[[ -z "$OFFENDER" ]] && OFFENDER="non-allowlisted-command"

_spec_blind_log_violation "bash-guard" "Bash" "$COMMAND" "$OFFENDER"

# Stderr message redacts the command body so secrets in the blocked command
# do not leak to the log streams (SEC-MED-1).
REDACTED_CMD="$(_spec_blind_redact "$COMMAND")"
echo "BLOCKED: spec-blind-validator may not run '$OFFENDER' (full command: $REDACTED_CMD). Allowed runners: npm test, pnpm test, yarn test, bundle exec rspec, pytest, cargo test, go test." >&2
exit 2
