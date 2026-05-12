#!/usr/bin/env bash
# Governance Capture — PreToolUse hook for Bash, Write, Edit
# Detects secrets and policy violations, logs to ~/.claude/metrics/governance.jsonl
# Advisory only (exit 0).
#
# enforces: protocols/reflection-protocol.md:Capture Pipeline Observation
# protects: learn, forensics

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:${TOOL_NAME:-Bash}"
trap 'log_hook_event $?' EXIT

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/loop-guard.sh" && check_loop_guard "governance-capture" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input // empty')

METRICS_DIR="$HOME/.claude/metrics"
mkdir -p "$METRICS_DIR"

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
PROJECT=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")

log_event() {
    local category="$1"
    local detail="$2"
    jq -n \
        --arg ts "$TIMESTAMP" \
        --arg cat "$category" \
        --arg detail "$detail" \
        --arg tool "$TOOL_NAME" \
        --arg project "$PROJECT" \
        '{"timestamp":$ts,"category":$cat,"detail":$detail,"tool":$tool,"project":$project}' \
        >> "$METRICS_DIR/governance.jsonl" 2>/dev/null || true
}

# Combine all available text for scanning
SCAN_TEXT="${COMMAND}${TOOL_INPUT}"

# Secret detection
if echo "$SCAN_TEXT" | grep -qE 'AKIA[0-9A-Z]{16}'; then
    log_event "secret" "AWS access key pattern detected"
fi
if echo "$SCAN_TEXT" | grep -qE 'ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36}'; then
    log_event "secret" "GitHub token pattern detected"
fi
if echo "$SCAN_TEXT" | grep -qE 'eyJ[a-zA-Z0-9_-]{20,}\.eyJ[a-zA-Z0-9_-]{20,}'; then
    log_event "secret" "JWT token pattern detected"
fi
if echo "$SCAN_TEXT" | grep -qiE '-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'; then
    log_event "secret" "Private key header detected"
fi
if echo "$SCAN_TEXT" | grep -qiE '(password|secret|token|api_key)\s*[=:]\s*["\x27][^\s"'\'']{8,}'; then
    log_event "secret" "Generic secret assignment pattern"
fi

# Policy violations (in Bash commands)
if [[ "$TOOL_NAME" == "Bash" ]]; then
    if echo "$COMMAND" | grep -qiE 'DROP\s+(TABLE|DATABASE)'; then
        log_event "policy" "DROP TABLE/DATABASE command"
    fi
    if echo "$COMMAND" | grep -qE 'chmod\s+777'; then
        log_event "policy" "chmod 777 (world-writable)"
    fi
fi

# Sensitive path modifications
if [[ -n "$FILE_PATH" ]]; then
    case "$FILE_PATH" in
        *.env|*.env.*|*/.env) log_event "sensitive_path" "Environment file: $FILE_PATH" ;;
        *credentials*|*secrets*) log_event "sensitive_path" "Credentials file: $FILE_PATH" ;;
        *.pem|*.key|*.p12|*.pfx) log_event "sensitive_path" "Key/cert file: $FILE_PATH" ;;
    esac
fi

exit 0
