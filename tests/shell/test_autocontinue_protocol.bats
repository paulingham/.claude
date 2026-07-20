#!/usr/bin/env bats
# Doc-structure guards for the Auto-Continue subsection (auto-continue
# bundle, Slice C). This documents an orchestrator-protocol behavior only —
# there is no hook, no watchdog, no poll. These assertions git-grep the
# COMMITTED tree, so this suite must be run AFTER committing the Slice C doc
# edit.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  ORCH="$REPO_ROOT/orchestrator/pipeline-orchestration.md"
}

line_of() {
  git -C "$REPO_ROOT" grep -n -m1 "$2" -- "$1" | head -1 | cut -d: -f2
}

grep_orch() {
  git -C "$REPO_ROOT" grep -q "$1" -- orchestrator/pipeline-orchestration.md
}

@test "AC12 Auto-Continue subsection names the discriminator helper" {
  grep_orch "#### Auto-Continue"
  grep_orch "continuation_decision"
}

@test "AC13 never-poke-WAIT safety clause is present" {
  grep_orch "NEVER poke a WAIT"
  grep_orch "idle mtime is not a stall"
}

@test "AC14 team-only SendMessage vs default re-dispatch distinction is present" {
  grep_orch "RE-DISPATCHES a continuation"
  grep_orch "SendMessage-poke is TEAM-mode only"
}

@test "AC14 breadcrumb names the three checks for a misfiring loop" {
  grep_orch "build_result_reader.py\` status directly"
  grep_orch "git -C \"\$WORKTREE\" log <base>..HEAD"
  grep_orch "ABSOLUTE \`state_dir\` path"
}

# RED-on-reorder/removal canary: the Auto-Continue subsection must remain
# nested under "Detecting Build Completion" (not promoted to a top-level
# section elsewhere), and the WAIT-safety line must survive verbatim. If a
# future edit moves the subsection out from under Detecting Build
# Completion, or drops the never-poke-WAIT line, this test goes RED.
@test "CANARY Auto-Continue sits under Detecting Build Completion and the WAIT-safety line survives" {
  local detect_line auto_continue_line team_state_line
  detect_line=$(line_of "orchestrator/pipeline-orchestration.md" "### Detecting Build Completion")
  auto_continue_line=$(line_of "orchestrator/pipeline-orchestration.md" "#### Auto-Continue")
  team_state_line=$(line_of "orchestrator/pipeline-orchestration.md" "^### Team State")
  [ -n "$detect_line" ]
  [ -n "$auto_continue_line" ]
  [ -n "$team_state_line" ]
  [ "$detect_line" -lt "$auto_continue_line" ]
  [ "$auto_continue_line" -lt "$team_state_line" ]
  grep_orch "NEVER poke a WAIT / unconfirmed-alive agent"
}
