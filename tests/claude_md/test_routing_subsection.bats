#!/usr/bin/env bats
# Slice A — AC2
# Asserts CLAUDE.md (a) has a new `### Work-Class Routing (T0-T6)` subsection
# between `### How the System Works` and `### Delivery Pipeline`, (b) the
# `/intake` row in protocols/skill-directory.md was rewritten verbatim with the
# fingerprint phrasing, and (c) the `/plan-self-validation` row's Verdict cell
# in protocols/skill-directory.md includes `ROUTING_UPSHIFTED`.
#
# Skill Directory rebase note: PR #127 moved the Skill Directory table OUT of
# CLAUDE.md into protocols/skill-directory.md. CLAUDE.md retains only a pointer.
# Assertions (b) and (c) target the new location.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  CLAUDE_MD="$REPO_ROOT/CLAUDE.md"
  SKILL_DIR="$REPO_ROOT/protocols/skill-directory.md"
  TARGET="$CLAUDE_MD"
}

@test "CLAUDE.md exists" {
  [ -f "$TARGET" ]
}

@test "protocols/skill-directory.md exists" {
  [ -f "$SKILL_DIR" ]
}

@test "Work-Class Routing (T0-T6) subsection exists" {
  grep -qE '^### Work-Class Routing \(T0-T6\)$' "$TARGET"
}

@test "Routing subsection is positioned AFTER How the System Works" {
  local routing_line how_line
  routing_line=$(grep -nE '^### Work-Class Routing \(T0-T6\)$' "$TARGET" | head -1 | cut -d: -f1)
  how_line=$(grep -nE '^### How the System Works$' "$TARGET" | head -1 | cut -d: -f1)
  [ -n "$routing_line" ]
  [ -n "$how_line" ]
  [ "$routing_line" -gt "$how_line" ]
}

@test "Routing subsection is positioned BEFORE Delivery Pipeline" {
  local routing_line deliv_line
  routing_line=$(grep -nE '^### Work-Class Routing \(T0-T6\)$' "$TARGET" | head -1 | cut -d: -f1)
  deliv_line=$(grep -nE '^### Delivery Pipeline$' "$TARGET" | head -1 | cut -d: -f1)
  [ -n "$routing_line" ]
  [ -n "$deliv_line" ]
  [ "$routing_line" -lt "$deliv_line" ]
}

@test "Routing subsection contains an 8-row tier table" {
  local count
  count=$(awk '/^### Work-Class Routing \(T0-T6\)$/,/^### Delivery Pipeline$/' "$TARGET" \
    | grep -cE '^\|[[:space:]]*\*\*(T[0-6]|T3H)\*\*')
  [ "$count" -eq 8 ]
}

@test "/intake row has pinned fingerprint phrasing (protocols/skill-directory.md)" {
  grep -qF '**Entry point** — first skill for any user request; emits Step 1.5 fingerprint (tier T0..T6) alongside criticality/budget' "$SKILL_DIR"
}

@test "/plan-self-validation row mentions re-fingerprint (protocols/skill-directory.md)" {
  grep -E '^\| \`/plan-self-validation\`' "$SKILL_DIR" | grep -qF 're-fingerprint'
}

@test "/plan-self-validation row Verdict cell contains ROUTING_UPSHIFTED (protocols/skill-directory.md)" {
  grep -E '^\| \`/plan-self-validation\`' "$SKILL_DIR" | grep -qF 'ROUTING_UPSHIFTED'
}
