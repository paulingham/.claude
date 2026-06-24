#!/usr/bin/env bats
# Wire-in tests: AC12 (gate invoked before deploy in pipeline/SKILL.md) and
# AC15 (CLAUDE_CI_GREEN_GATE=off documented in reversibility escape surface).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export REPO_ROOT
  SKILL_MD="$REPO_ROOT/skills/pipeline/SKILL.md"
  AGENT_PROTOCOL="$REPO_ROOT/protocols/agent-protocol.md"
  export SKILL_MD AGENT_PROTOCOL
}

# ─── AC12: Gate invoked before deploy in pipeline/SKILL.md ───────────────────

@test "AC12_pipeline_step5_invokes_gate_before_deploy: check-ci-green-gate.sh before auto-invoke in Step 5" {
  # check-ci-green-gate.sh must appear in pipeline/SKILL.md
  grep -q "check-ci-green-gate.sh" "$SKILL_MD"

  # Step 5 begins at the '### Step 5: Deploy' header
  step5_start=$(grep -n "### Step 5: Deploy" "$SKILL_MD" | head -1 | cut -d: -f1)
  [ -n "$step5_start" ]

  # Gate must appear in Step 5 (after the Step 5 header)
  gate_pos=$(awk -v start="$step5_start" 'NR > start && /check-ci-green-gate\.sh/ {print NR; exit}' "$SKILL_MD")
  [ -n "$gate_pos" ]

  # The auto-invoke line ("automatically invoke /harness:deploy") must appear after gate
  deploy_pos=$(awk -v start="$step5_start" 'NR > start && /automatically invoke.*\/harness:deploy/ {print NR; exit}' "$SKILL_MD")
  [ -n "$deploy_pos" ]

  # Gate line number must be less than the auto-invoke line number
  [ "$gate_pos" -lt "$deploy_pos" ]
}

@test "AC12_gate_exit2_causes_CI_RED_not_deploy: Step 5 text describes CI_RED halt on exit 2" {
  # The SKILL.md must describe what happens on gate exit 2 (CI_RED + halt)
  grep -q "CI_RED" "$SKILL_MD"
}

# ─── AC15: Reversibility escape documented ────────────────────────────────────

@test "AC15_reversibility_escape_documented: CLAUDE_CI_GREEN_GATE in agent-protocol.md escape table" {
  grep -q "CLAUDE_CI_GREEN_GATE" "$AGENT_PROTOCOL"
}
