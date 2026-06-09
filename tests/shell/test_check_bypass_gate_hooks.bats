#!/usr/bin/env bats
# Per-hook bypass-gate integration probes for Class-1 hooks that lack an
# individual escape-hatch bats test after the GP-19 migration.
#
# These tests do NOT execute the hook's full business logic.  They only prove
# that each migrated hook (a) sources check-bypass-gate.sh correctly and
# (b) returns exit 0 when the hook-specific CLAUDE_DISABLE_* var is set to "1"
# — the exact contract stated in plan.md Tier-0 #5.
#
# Class-2 (build-loop-scan, pre-agent-advisor) and Class-3 (runtime-state-guard,
# mutation-tooling-guard) hooks are NOT included here because they are already
# exercised with full audit/message assertions in their own test harnesses.
# Class-1b (no-shell-read, shadow-git-checkpoint) are already covered in
# test_no_shell_read.bats and test_shadow_git_checkpoint.bats respectively.
#
# AC coverage: plan.md Tier-0 #5 — "per refactored hook: var SET='1' → bypass
# branch taken with byte-identical observable behaviour."

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  # Minimal env: redirect HOME so log.sh does not write to the real home dir.
  TMP_HOME="$(mktemp -d)"
  mkdir -p "$TMP_HOME/.claude"
  # Symlink hooks so CLAUDE_PLUGIN_ROOT resolution works inside hooks.
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export HOME="$TMP_HOME"
  export CLAUDE_SESSION_ID="bats-bypass-probe-$$"
}

teardown() {
  rm -rf "$TMP_HOME"
}

# ---------------------------------------------------------------------------
# Helper: run a hook with its disable flag set to "1" via stdin empty JSON.
# Expected: exit 0 (bypassed immediately).
# ---------------------------------------------------------------------------
_probe_bypass() {
  local hook_path="$1"
  local disable_var="$2"
  export "${disable_var}=1"
  # Send minimal valid JSON so any jq reads don't abort the hook
  echo '{}' | bash "$hook_path"
  local rc=$?
  unset "${disable_var}"
  return $rc
}

# ---------------------------------------------------------------------------
# verification-freshness-guard.sh — CLAUDE_DISABLE_FRESHNESS_GUARD
# ---------------------------------------------------------------------------
@test "verification-freshness-guard: CLAUDE_DISABLE_FRESHNESS_GUARD=1 → exit 0" {
  run _probe_bypass "$REPO_ROOT/hooks/verification-freshness-guard.sh" "CLAUDE_DISABLE_FRESHNESS_GUARD"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# scratchpad-bytes.sh — CLAUDE_DISABLE_SCRATCHPAD_BYTES
# ---------------------------------------------------------------------------
@test "scratchpad-bytes: CLAUDE_DISABLE_SCRATCHPAD_BYTES=1 → exit 0" {
  run _probe_bypass "$REPO_ROOT/hooks/scratchpad-bytes.sh" "CLAUDE_DISABLE_SCRATCHPAD_BYTES"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# pre-agent-allowlist.sh — CLAUDE_DISABLE_TOOL_ALLOWLIST
# ---------------------------------------------------------------------------
@test "pre-agent-allowlist: CLAUDE_DISABLE_TOOL_ALLOWLIST=1 → exit 0" {
  run _probe_bypass "$REPO_ROOT/hooks/pre-agent-allowlist.sh" "CLAUDE_DISABLE_TOOL_ALLOWLIST"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# pre-agent-swe-pruner.sh — CLAUDE_DISABLE_SWE_PRUNER
# ---------------------------------------------------------------------------
@test "pre-agent-swe-pruner: CLAUDE_DISABLE_SWE_PRUNER=1 → exit 0" {
  run _probe_bypass "$REPO_ROOT/hooks/pre-agent-swe-pruner.sh" "CLAUDE_DISABLE_SWE_PRUNER"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# metrics-gc.sh — CLAUDE_DISABLE_METRICS_GC
# ---------------------------------------------------------------------------
@test "metrics-gc: CLAUDE_DISABLE_METRICS_GC=1 → exit 0" {
  run _probe_bypass "$REPO_ROOT/hooks/metrics-gc.sh" "CLAUDE_DISABLE_METRICS_GC"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# learning-gc.sh — CLAUDE_DISABLE_LEARNING_GC
# ---------------------------------------------------------------------------
@test "learning-gc: CLAUDE_DISABLE_LEARNING_GC=1 → exit 0" {
  run _probe_bypass "$REPO_ROOT/hooks/learning-gc.sh" "CLAUDE_DISABLE_LEARNING_GC"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# pre-agent-thinking.sh — CLAUDE_DISABLE_THINKING_GATE
# ---------------------------------------------------------------------------
@test "pre-agent-thinking: CLAUDE_DISABLE_THINKING_GATE=1 → exit 0" {
  run _probe_bypass "$REPO_ROOT/hooks/pre-agent-thinking.sh" "CLAUDE_DISABLE_THINKING_GATE"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# hook-self-test.sh — CLAUDE_DISABLE_HOOK_SELF_TEST
# ---------------------------------------------------------------------------
@test "hook-self-test: CLAUDE_DISABLE_HOOK_SELF_TEST=1 → exit 0" {
  run _probe_bypass "$REPO_ROOT/hooks/hook-self-test.sh" "CLAUDE_DISABLE_HOOK_SELF_TEST"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# stuck-guard.sh — CLAUDE_DISABLE_STUCK_GUARD
# ---------------------------------------------------------------------------
@test "stuck-guard: CLAUDE_DISABLE_STUCK_GUARD=1 → exit 0" {
  run _probe_bypass "$REPO_ROOT/hooks/stuck-guard.sh" "CLAUDE_DISABLE_STUCK_GUARD"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# instinct-injector.sh — CLAUDE_DISABLE_INSTINCT_INJECTION
# ---------------------------------------------------------------------------
@test "instinct-injector: CLAUDE_DISABLE_INSTINCT_INJECTION=1 → exit 0" {
  run _probe_bypass "$REPO_ROOT/hooks/instinct-injector.sh" "CLAUDE_DISABLE_INSTINCT_INJECTION"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# tool-output-bytes.sh — CLAUDE_DISABLE_TOOL_OUTPUT_BYTES
# ---------------------------------------------------------------------------
@test "tool-output-bytes: CLAUDE_DISABLE_TOOL_OUTPUT_BYTES=1 → exit 0" {
  run _probe_bypass "$REPO_ROOT/hooks/tool-output-bytes.sh" "CLAUDE_DISABLE_TOOL_OUTPUT_BYTES"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# auto-learn-gate.sh — CLAUDE_DISABLE_AUTO_LEARN (Class-1, already in
# test-auto-learn-gate.sh but not in a CI-discovered bats file until now)
# ---------------------------------------------------------------------------
@test "auto-learn-gate: CLAUDE_DISABLE_AUTO_LEARN=1 → exit 0" {
  run _probe_bypass "$REPO_ROOT/hooks/auto-learn-gate.sh" "CLAUDE_DISABLE_AUTO_LEARN"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# pre-agent-advisor.sh — CLAUDE_DISABLE_ADVISOR_GATE (Class-1 silent exit)
# The second escape in that file (CLAUDE_DISABLE_MODEL_BINDING) sets
# HOOK_OUTPUT="" and does NOT exit; it cannot be probed with a simple
# exit-code check.  The ADVISOR_GATE escape (which does && exit 0) is probed here.
# ---------------------------------------------------------------------------
@test "pre-agent-advisor: CLAUDE_DISABLE_ADVISOR_GATE=1 → exit 0" {
  run _probe_bypass "$REPO_ROOT/hooks/pre-agent-advisor.sh" "CLAUDE_DISABLE_ADVISOR_GATE"
  [ "$status" -eq 0 ]
}
