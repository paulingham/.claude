#!/usr/bin/env bats
# Approval token gate docs — Wave 4-N
# Regression tests verifying SKILL.md and protocols/pipeline-protocol.md
# document the approval-token gate. These complement test_approval_token_gate.bats
# (which covers the shell/lib code) by guarding the documentation surface.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  PRODUCT_ACCEPTANCE="$REPO_ROOT/skills/product-acceptance/SKILL.md"
  PR_CREATION="$REPO_ROOT/skills/pr-creation/SKILL.md"
  PIPELINE_PROTOCOL="$REPO_ROOT/protocols/pipeline-protocol.md"
}

# --- product-acceptance/SKILL.md: Step 4 (Write Approval Token) ---

@test "product-acceptance: file exists" {
  [ -f "$PRODUCT_ACCEPTANCE" ]
}

@test "product-acceptance: contains '### 4. Write Approval Token (MANDATORY)' heading" {
  grep -qF "### 4. Write Approval Token (MANDATORY)" "$PRODUCT_ACCEPTANCE"
}

@test "product-acceptance: references write-approval-token.sh wrapper" {
  grep -qF "hooks/_lib/write-approval-token.sh" "$PRODUCT_ACCEPTANCE"
}

@test "product-acceptance: documents --task-id and --verdict flags" {
  grep -qF -- "--task-id" "$PRODUCT_ACCEPTANCE"
  grep -qF -- "--verdict" "$PRODUCT_ACCEPTANCE"
}

@test "product-acceptance: lists all three verdicts" {
  grep -qF "APPROVED" "$PRODUCT_ACCEPTANCE"
  grep -qF "APPROVED_WITH_CONDITIONS" "$PRODUCT_ACCEPTANCE"
  grep -qF "REJECTED" "$PRODUCT_ACCEPTANCE"
}

@test "product-acceptance: documents Reflect step 6d cleanup" {
  grep -qF "Reflect step 6d" "$PRODUCT_ACCEPTANCE"
}

@test "product-acceptance: Step 3 cross-references Step 4" {
  grep -qF "proceed to Step 4" "$PRODUCT_ACCEPTANCE"
}

# --- pr-creation/SKILL.md: Step 0 (Approval Token Gate) ---

@test "pr-creation: file exists" {
  [ -f "$PR_CREATION" ]
}

@test "pr-creation: contains 'Step 0 — Approval Token Gate (HARD GATE)' heading" {
  grep -qF "Step 0 — Approval Token Gate (HARD GATE)" "$PR_CREATION"
}

@test "pr-creation: Step 0 appears before Worktree Precondition" {
  step0_line=$(grep -n "Step 0 — Approval Token Gate" "$PR_CREATION" | head -1 | cut -d: -f1)
  worktree_line=$(grep -n "Worktree Precondition (HARD GATE)" "$PR_CREATION" | head -1 | cut -d: -f1)
  [ -n "$step0_line" ]
  [ -n "$worktree_line" ]
  [ "$step0_line" -lt "$worktree_line" ]
}

@test "pr-creation: references approval-token.sh library" {
  grep -qF "hooks/_lib/approval-token.sh" "$PR_CREATION"
}

@test "pr-creation: references check-approval-token.sh" {
  grep -qF "check-approval-token.sh" "$PR_CREATION"
}

@test "pr-creation: documents PR_BLOCKED on missing/REJECTED token" {
  grep -qF "PR_BLOCKED" "$PR_CREATION"
}

@test "pr-creation: documents manual PR path when no active pipeline" {
  grep -qF "manual PR path" "$PR_CREATION"
}

@test "pr-creation: cross-references auto-pr.sh advisory read" {
  grep -qF "auto-pr.sh" "$PR_CREATION"
}

@test "pr-creation: Prerequisite section mentions approval token" {
  # Look for the approval token entry in the Prerequisite section (case-insensitive grep
  # for "approval token written" phrase indicating the prerequisite was added).
  grep -qiF "Approval token written" "$PR_CREATION"
}

# --- protocols/pipeline-protocol.md: three additions ---

@test "pipeline-protocol: file exists" {
  [ -f "$PIPELINE_PROTOCOL" ]
}

@test "pipeline-protocol: Ship row references approval.token requirement" {
  grep -qF "{task-id}-approval.token" "$PIPELINE_PROTOCOL"
}

@test "pipeline-protocol: Ship row mentions APPROVED or APPROVED_WITH_CONDITIONS verdicts" {
  grep -qF "APPROVED_WITH_CONDITIONS" "$PIPELINE_PROTOCOL"
}

@test "pipeline-protocol: Ship row references Step 0 gate location" {
  grep -qF "Step 0" "$PIPELINE_PROTOCOL"
}

@test "pipeline-protocol: Orchestrator Responsibilities mentions approval.token cleanup" {
  # Single bullet that references the token AND Reflect step 6d cleanup
  grep -qE "approval\.token.*Reflect step 6d|Reflect step 6d.*approval\.token" "$PIPELINE_PROTOCOL"
}

@test "pipeline-protocol: documents stale token risk" {
  grep -qF "Stale APPROVED tokens" "$PIPELINE_PROTOCOL"
}

@test "pipeline-protocol: contains 'gh pr create Bypass' residual-risk note" {
  grep -qF "gh pr create" "$PIPELINE_PROTOCOL"
  grep -qiF "bypass" "$PIPELINE_PROTOCOL"
}

@test "pipeline-protocol: residual-risk note references future pr-approval-guard.sh hook" {
  grep -qF "pr-approval-guard.sh" "$PIPELINE_PROTOCOL"
}
