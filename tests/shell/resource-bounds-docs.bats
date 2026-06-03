#!/usr/bin/env bats
# Slice 4 — docs + orchestrator template propagation.
# T4.1-T4.7 covering AC4.1-AC4.9.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "T4.1 protocols/parallel-dispatch-protocol.md has ## Resource Bounds H2" {
  grep -q '^## Resource Bounds' "$REPO_ROOT/protocols/parallel-dispatch-protocol.md"
}

@test "T4.2 protocols/agent-protocol.md has ## Resource Bounds H2" {
  grep -q '^## Resource Bounds' "$REPO_ROOT/protocols/agent-protocol.md"
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

# T4.6 retired (per-task-subdirs refactor, 2026-05).
# The original invariant — "rules/*.md show ZERO deletions vs main" — was a
# wave1-B-specific guard while resource-bounds-protocol prose was being
# additively layered into protocols/agent-protocol.md and
# protocols/parallel-dispatch-protocol.md. The wave1-B work has long since
# merged. The per-task-subdirs refactor intentionally rewrites
# pipeline-state path formats (e.g., `{task-id}-scratchpad/` →
# `{task-id}/scratchpad/`) across protocols/*.md, which is a legitimate
# refactor, not a regression of the wave1-B additivity contract. Keeping
# this assertion in place would block all future protocols/*.md evolution.
#
# Replacement coverage: T4.1-T4.5, T4.7, T4.8 still pin the documented
# anchors that wave1-B introduced (## Resource Bounds H2,
# CLAUDE_SUBAGENT_DEPTH mention/assignment, Subagent depth context line).
# Anchor-based assertions are how we should have scoped this from the
# start.

@test "T4.7 example body assignment present in BOTH orchestrator docs" {
  # AC4.4a / AC4.5a — literal CLAUDE_SUBAGENT_DEPTH= assignment (trailing =
  # is load-bearing — proves an assignment line exists, not just a bare token).
  grep -q 'CLAUDE_SUBAGENT_DEPTH=' "$REPO_ROOT/orchestrator/agent-orchestration.md"
  grep -q 'CLAUDE_SUBAGENT_DEPTH=' "$REPO_ROOT/orchestrator/parallel-dispatch-details.md"
}

@test "T4.8 Teammate Prompt Template includes Subagent depth context line" {
  # AC4.6 (revised) — both the documented context line AND the surrounding
  # prose noting the spawn-shell env var.
  grep -q 'Subagent depth: {N}' "$REPO_ROOT/protocols/parallel-dispatch-protocol.md"
  grep -q 'CLAUDE_SUBAGENT_DEPTH' "$REPO_ROOT/protocols/parallel-dispatch-protocol.md"
}
