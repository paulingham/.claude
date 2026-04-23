#!/usr/bin/env bats
# L1: README has a dedicated Linux / Claude Code Cloud subsection under
# Getting Started pointing operators at scripts/install-tools.sh and the
# CLAUDE_REQUIRE_DIPPY opt-in. Guards against the README drifting back to
# brew-only onboarding.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  README="$REPO_ROOT/README.md"
}

@test "L1.1 README has a Linux / Claude Code Cloud subsection" {
  run grep -cE '^### Linux / Claude Code Cloud$' "$README"
  [ "$status" -eq 0 ]
  [ "$output" = "1" ]
}

@test "L1.2 subsection references scripts/install-tools.sh" {
  section="$(awk '/^### Linux \/ Claude Code Cloud$/{f=1;next} f && /^(## |### )/{f=0} f' "$README")"
  echo "$section" | grep -q 'scripts/install-tools.sh'
}

@test "L1.3 subsection mentions CLAUDE_REQUIRE_DIPPY opt-in" {
  section="$(awk '/^### Linux \/ Claude Code Cloud$/{f=1;next} f && /^(## |### )/{f=0} f' "$README")"
  echo "$section" | grep -q 'CLAUDE_REQUIRE_DIPPY'
}

@test "L1.4 subsection sits under Getting Started (not orphaned)" {
  # Every ### Linux / Claude Code Cloud occurrence must be preceded by
  # a ## Getting Started heading somewhere above it in the file.
  gs_line="$(grep -nE '^## Getting Started' "$README" | head -1 | cut -d: -f1)"
  lc_line="$(grep -nE '^### Linux / Claude Code Cloud$' "$README" | head -1 | cut -d: -f1)"
  [ -n "$gs_line" ]
  [ -n "$lc_line" ]
  [ "$lc_line" -gt "$gs_line" ]
}
