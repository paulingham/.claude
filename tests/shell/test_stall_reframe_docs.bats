#!/usr/bin/env bats
# Reframe guard for the stall-fix misdiagnosis correction (auto-continue
# bundle). The original #259 docs claimed the build agent's prose report
# "can stall before it is emitted" / the completion "signal is lost" as if
# that were the root cause. It is not: the root cause is an upstream Claude
# Code background-agent loop-scheduling gap (issues #61547/#44783) where the
# agent's loop does not advance to its next inference after a clean
# tool_result until externally poked. The signal is never lost -- the loop
# never reaches the point where it would emit it. These assertions git-grep
# the COMMITTED tree, so this suite must be run AFTER committing the reframe.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

grep_all() {
  git -C "$REPO_ROOT" grep -q "$1" -- "$2"
}

@test "AC1 new causal language present in SKILL.md" {
  grep_all "loop-scheduling" skills/build-implementation/SKILL.md
  grep_all "#61547" skills/build-implementation/SKILL.md
  grep_all "MITIGATION" skills/build-implementation/SKILL.md
}

@test "AC1 new causal language present in orchestrator doc" {
  grep_all "loop-scheduling" orchestrator/pipeline-orchestration.md
  grep_all "#61547" orchestrator/pipeline-orchestration.md
  grep_all "MITIGATION" orchestrator/pipeline-orchestration.md
}

@test "AC2 new causal language present in all 6 write-capable agent defs" {
  for agent_def in agents/software-engineer.md agents/frontend-engineer.md \
    agents/database-engineer.md agents/qa-engineer.md \
    agents/infrastructure-engineer.md agents/fix-engineer.md; do
    grep_all "loop-scheduling" "$agent_def"
    grep_all "#61547" "$agent_def"
    grep_all "MITIGATION" "$agent_def"
  done
}

@test "AC3 new causal language present in build_result_reader.py docstring" {
  grep_all "loop-scheduling" hooks/_lib/build_result_reader.py
  grep_all "#61547" hooks/_lib/build_result_reader.py
  grep_all "MITIGATION" hooks/_lib/build_result_reader.py
}

@test "AC4 old standalone lost-signal misdiagnosis is gone from all 9 locations" {
  ! git -C "$REPO_ROOT" grep -q "prose report can stall before it is emitted" -- \
    skills/build-implementation/SKILL.md \
    orchestrator/pipeline-orchestration.md \
    hooks/_lib/build_result_reader.py \
    agents/software-engineer.md agents/frontend-engineer.md \
    agents/database-engineer.md agents/qa-engineer.md \
    agents/infrastructure-engineer.md agents/fix-engineer.md
}

@test "AC5 SSOT conclusion survives the reframe (file-on-disk-is-source-of-truth)" {
  grep_all "machine-readable source of truth" skills/build-implementation/SKILL.md
  grep_all "Completion Signal (SSOT)" skills/build-implementation/SKILL.md
  grep_all "build_result_reader.py" orchestrator/pipeline-orchestration.md
  grep_all "Read the file FIRST" orchestrator/pipeline-orchestration.md
}
