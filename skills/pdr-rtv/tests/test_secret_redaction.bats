#!/usr/bin/env bats
# Security-review F4 — `distill_rollout` redacts secret-shaped substrings
# from the engineer-authored `[SUMMARY]…[/SUMMARY]` block before writing
# `summary.md`. Patterns covered:
#   - AWS access keys: AKIA[0-9A-Z]{16}
#   - GitHub tokens:   gh[pousr]_[A-Za-z0-9]{36,}
#   - High-entropy:    [A-Za-z0-9+/=]{40,}
#   - .env-style:      ^[A-Z_]+=<value-len-20+>
#
# Each match is replaced with `[REDACTED:<pattern-class>]` and a forensic
# JSONL record is appended to metrics/{session}/pdr-secret-redactions.jsonl.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  DISTILL_PATH="$REPO_ROOT/skills/pdr-rtv/lib/distill.sh"
  TMPROOT="$(mktemp -d)"
  WORKTREE="$TMPROOT/worktree"
  STATE_ROOT="$TMPROOT/state"
  TASK_ID="redact-test-task"
  SLUG="cand-redact"
  mkdir -p "$WORKTREE" "$STATE_ROOT"

  # Forensic JSONL goes to a session-isolated metrics dir.
  export CLAUDE_SESSION_ID="redact-test-$$"
  METRICS_DIR="$HOME/.claude/metrics/$CLAUDE_SESSION_ID"
  mkdir -p "$METRICS_DIR"
}

teardown() {
  rm -rf "$TMPROOT"
  rm -rf "$HOME/.claude/metrics/$CLAUDE_SESSION_ID" 2>/dev/null || true
  unset CLAUDE_SESSION_ID
}

_run_distill_with_summary() {
  local body="$1"
  cat > "$WORKTREE/COMMIT_MSG" <<EOF
[SUMMARY]
HYPOTHESES: $body
PROGRESS: pushed core path
FAILURES: edge case remained
[/SUMMARY]

Rollout summary commit.
EOF
  # AC1 — distill_rollout requires a commit at HEAD (writes meta file
  # with sha + diff_stat). Initialise the worktree as a git repo with
  # one commit so secret-redaction behaviour can still be exercised.
  if [ ! -d "$WORKTREE/.git" ]; then
    ( cd "$WORKTREE" \
        && git init -q \
        && git config user.email t@t.t \
        && git config user.name "t" \
        && git add COMMIT_MSG \
        && git commit -q -m "fixture commit for secret redaction tests" )
  fi
  # shellcheck source=/dev/null
  source "$DISTILL_PATH"
  distill_rollout "$WORKTREE" "$STATE_ROOT" "$TASK_ID" "$SLUG"
  cat "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$SLUG/summary.md"
}

@test "F4: redacts AWS access key" {
  out="$(_run_distill_with_summary "tried AKIAABCDEFGHIJKLMNOP as test creds")"
  [[ "$out" != *"AKIAABCDEFGHIJKLMNOP"* ]]
  [[ "$out" == *"[REDACTED:aws-key]"* ]]
}

@test "F4: redacts GitHub token (gh* family)" {
  out="$(_run_distill_with_summary "leaked token ghp_abcdefghijklmnopqrstuvwxyz0123456789AB still present")"
  [[ "$out" != *"ghp_abcdefghijklmnopqrstuvwxyz0123456789AB"* ]]
  [[ "$out" == *"[REDACTED:github-token]"* ]]
}

@test "F4: redacts high-entropy base64-shaped string" {
  out="$(_run_distill_with_summary "found AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHHIIIIJJJJ in env")"
  [[ "$out" != *"AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHHIIIIJJJJ"* ]]
  [[ "$out" == *"[REDACTED:high-entropy]"* ]]
}

@test "F4: redacts env-style assignment" {
  out="$(_run_distill_with_summary "DATABASE_URL=postgresql://user:secretpassword@host/db")"
  # The env-style line should be redacted.
  [[ "$out" != *"DATABASE_URL=postgresql://user:secretpassword@host/db"* ]]
  [[ "$out" == *"[REDACTED:env-style]"* ]]
}

@test "F4: leaves clean text untouched" {
  out="$(_run_distill_with_summary "tried strategy A then B; landed core path")"
  [[ "$out" == *"tried strategy A then B"* ]]
  [[ "$out" != *"[REDACTED"* ]]
}

@test "F4: emits forensic JSONL record on redaction" {
  _run_distill_with_summary "leak AKIAABCDEFGHIJKLMNOP here" >/dev/null
  JSONL="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/pdr-secret-redactions.jsonl"
  [ -f "$JSONL" ]
  grep -q '"source": "pdr-secret-redacted"' "$JSONL"
  grep -q '"pattern_class": "aws-key"' "$JSONL"
  grep -q "\"task_id\": \"$TASK_ID\"" "$JSONL"
}

@test "F4: no JSONL emission when no secrets present" {
  _run_distill_with_summary "tried strategy A then B; landed core path" >/dev/null
  JSONL="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/pdr-secret-redactions.jsonl"
  # File may not exist, OR exists empty.
  if [ -f "$JSONL" ]; then
    line_count="$(wc -l <"$JSONL" | tr -d ' ')"
    [ "$line_count" -eq 0 ]
  fi
}
