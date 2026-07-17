#!/usr/bin/env bats
# Structural contract for skills/pair/SKILL.md — the Pair-gear entry point
# (Phase A). Pair mode's speed comes from skipping worktree/PR/multi-gate
# ceremony, NEVER from letting the orchestrator itself write code. These
# tests pin the safety invariant text and the skill's frontmatter shape so
# a future edit cannot silently drop the write-boundary statement.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SKILL_FILE="$REPO_ROOT/skills/pair/SKILL.md"
}

@test "PAIR1.1 skills/pair/SKILL.md exists" {
  [ -f "$SKILL_FILE" ]
}

@test "PAIR1.2 frontmatter name is 'pair'" {
  run bash -c "sed -n '2,20p' '$SKILL_FILE' | grep -E '^name:'"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qE '^name:[[:space:]]*"?pair"?[[:space:]]*$'
}

@test "PAIR1.3 frontmatter declares dispatch: subagent (single worker, no team ceremony)" {
  run bash -c "sed -n '2,20p' '$SKILL_FILE' | grep -E '^dispatch:'"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q 'subagent'
}

@test "PAIR1.4 frontmatter declares a phase" {
  run bash -c "sed -n '2,20p' '$SKILL_FILE' | grep -E '^phase:'"
  [ "$status" -eq 0 ]
}

@test "PAIR1.5 states the orchestrator-never-writes safety invariant explicitly" {
  run grep -qi 'orchestrator never writes code' "$SKILL_FILE"
  [ "$status" -eq 0 ]
}

@test "PAIR1.6 states that even in Pair mode a spawned engineer worker does the Edit/Write" {
  run grep -qi 'spawned' "$SKILL_FILE"
  [ "$status" -eq 0 ]
  run grep -qiE 'worker|engineer' "$SKILL_FILE"
  [ "$status" -eq 0 ]
}

@test "PAIR1.7 explicitly states no worktree-branch ceremony, no PR, no multi-gate" {
  run grep -qi 'no PR' "$SKILL_FILE"
  [ "$status" -eq 0 ]
}

@test "PAIR1.8 skill file stays short (anti-thesis of the 24KB intake skill) — under 4000 bytes" {
  size=$(wc -c < "$SKILL_FILE" | tr -d ' ')
  [ "$size" -lt 4000 ]
}

@test "PAIR1.9 does not introduce a bare backtick /pair invocation ref (namespacing convention)" {
  run grep -cE '`/pair`' "$SKILL_FILE"
  [ "$status" -ne 0 ] || [ "$output" -eq 0 ]
}
