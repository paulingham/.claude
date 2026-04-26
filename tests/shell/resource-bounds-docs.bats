#!/usr/bin/env bats
# Slice 4 — docs + orchestrator template propagation.
# T4.1-T4.7 covering AC4.1-AC4.9.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "T4.1 rules/parallel-dispatch-protocol.md has ## Resource Bounds H2" {
  grep -q '^## Resource Bounds' "$REPO_ROOT/rules/parallel-dispatch-protocol.md"
}

@test "T4.2 rules/agent-protocol.md has ## Resource Bounds H2" {
  grep -q '^## Resource Bounds' "$REPO_ROOT/rules/agent-protocol.md"
}

@test "T4.3 orchestrator/agent-orchestration.md mentions CLAUDE_SUBAGENT_DEPTH" {
  grep -q 'CLAUDE_SUBAGENT_DEPTH' "$REPO_ROOT/orchestrator/agent-orchestration.md"
}

@test "T4.4 orchestrator/parallel-dispatch-details.md mentions CLAUDE_SUBAGENT_DEPTH" {
  grep -q 'CLAUDE_SUBAGENT_DEPTH' "$REPO_ROOT/orchestrator/parallel-dispatch-details.md"
}

@test "T4.5 README.md has Resource Bounds entry under hooks/architecture overview" {
  # The entry must be in the Mechanical Enforcement (Hooks) section, not in
  # user-visible product features (per AC4.7 reframed).
  awk '/^## Mechanical Enforcement \(Hooks\)/,/^## Omnichannel Support/' \
    "$REPO_ROOT/README.md" | grep -q 'Resource Bounds'
}

@test "T4.6 Wave-1 hot files: rules/*.md show ZERO deletions vs main" {
  cd "$REPO_ROOT"
  local del_count
  del_count=$(git diff main..HEAD --numstat -- 'rules/*.md' 2>/dev/null \
    | awk '{ sum += $2 } END { print sum+0 }')
  [ "$del_count" = "0" ]
}

@test "T4.7 example body assignment present in BOTH orchestrator docs" {
  # AC4.4a / AC4.5a — literal CLAUDE_SUBAGENT_DEPTH= assignment (trailing =
  # is load-bearing — proves an assignment line exists, not just a bare token).
  grep -q 'CLAUDE_SUBAGENT_DEPTH=' "$REPO_ROOT/orchestrator/agent-orchestration.md"
  grep -q 'CLAUDE_SUBAGENT_DEPTH=' "$REPO_ROOT/orchestrator/parallel-dispatch-details.md"
}

@test "T4.8 Teammate Prompt Template includes Subagent depth context line" {
  # AC4.6 (revised) — both the documented context line AND the surrounding
  # prose noting the spawn-shell env var.
  grep -q 'Subagent depth: {N}' "$REPO_ROOT/rules/parallel-dispatch-protocol.md"
  grep -q 'CLAUDE_SUBAGENT_DEPTH' "$REPO_ROOT/rules/parallel-dispatch-protocol.md"
}
