#!/usr/bin/env bats
# AC4 + AC4-bis — `orchestrator/parallel-dispatch-details.md § PDR-RTV`
# step 4 documents the orchestrator-side live-picker exports
# (`CLAUDE_PDR_RTV_LIVE_PICKER=1` and `PDR_RTV_VERDICT_DIR`), the per-match
# `tee` of Agent stdout, and renames the diff-stat heuristic from "primary
# verdict source" to "documented tie-breaker per agents/patch-critic.md
# § Tournament Mode". Step 6 documents the operator-facing forensics
# sentence about tournament-time `meta-missing` indicating filesystem race
# or post-distill corruption (since distill fails-loud at the upstream
# producer).

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  DISPATCH_DOC="$REPO_ROOT/orchestrator/parallel-dispatch-details.md"
}

# Helper: extract `### PDR-RTV...` section bounded by the next `### ` heading.
# The PDR-RTV section is a fenced region; we collect every line from the
# section's opening `### PDR-RTV` heading up to (but excluding) the next
# `### ` heading.
_pdr_section() {
  awk '
    /^### PDR-RTV Build Team Dispatch/ {
      in_section = 1
      print
      next
    }
    in_section && /^### / { exit }
    in_section { print }
  ' "$DISPATCH_DOC"
}

@test "AC4: parallel-dispatch-details.md PDR-RTV step 4 documents live-picker exports and verdict-dir tee" {
  [ -f "$DISPATCH_DOC" ]

  # bats 1.13 does not abort on `[[ ]]` returning 1; force failure with `|| false`.
  section="$(_pdr_section)"
  # Literal env-var export documented (operator copy-pastes this).
  [[ "$section" == *"export CLAUDE_PDR_RTV_LIVE_PICKER=1"* ]] || false
  # Verdict-dir env var named.
  [[ "$section" == *"PDR_RTV_VERDICT_DIR"* ]] || false
  # Per-match tee of Agent stdout documented.
  [[ "$section" == *"tee"* ]] || false
  # Diff-stat is renamed to "documented tie-breaker".
  [[ "$section" == *"documented tie-breaker"* ]] || false
}

@test "AC4-bis: parallel-dispatch-details.md PDR-RTV step 6 documents meta-missing operator forensics sentence" {
  [ -f "$DISPATCH_DOC" ]
  section="$(_pdr_section)"

  # The literal forensic sentence per AC4-bis (M2).
  [[ "$section" == *"Tournament-time \`meta-missing\` indicates filesystem race or post-distill corruption"* ]] || false
}
