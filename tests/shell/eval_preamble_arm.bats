#!/usr/bin/env bats
# A/B bridge Slice B — --preamble arm-strip tests.
#
# B1  --preamble none strips ladder (no rungs/carve-out sentinel in wt copies)
# B2  --preamble decision-ladder leaves agents byte-unchanged (drift guard)
# B3  strip removes the SKILL.md Decision Ladder note
# B4  invalid --preamble value exits 2
# B5  --preamble none WITHOUT --harness-ref exits 2 at parse time; live ~/.claude untouched
# B6  strip confined: git -C repo-root status --porcelain agents/ is empty after strip
# B7  test_decision_ladder_preamble.py still passes (ladder in real static .md)

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  WORK="$BATS_FILE_TMPDIR/work-$BATS_TEST_NUMBER"

  SUITE_ARGS="$REPO_ROOT/skills/internal-eval/run/lib/suite-args.sh"
  SUITE_PREAMBLE="$REPO_ROOT/skills/internal-eval/run/lib/suite-preamble.sh"

  # Build a minimal fake harness worktree under WORK
  _make_fake_wt() {
    local wt="$1"
    mkdir -p "$wt/agents" "$wt/skills/build-implementation"
    cp "$REPO_ROOT/agents/software-engineer.md" "$wt/agents/software-engineer.md"
    cp "$REPO_ROOT/agents/frontend-engineer.md" "$wt/agents/frontend-engineer.md"
    cp "$REPO_ROOT/skills/build-implementation/SKILL.md" \
       "$wt/skills/build-implementation/SKILL.md"
  }

  mkdir -p "$WORK"
}

# ─── B1: none strips the ladder block ────────────────────────────────────────
@test "B1 preamble none strips Decision Ladder from wt agent copies" {
  local wt="$WORK/wt-b1"
  _make_fake_wt "$wt"

  source "$SUITE_PREAMBLE"
  PREAMBLE="none"
  strip_ladder_from_harness "$wt"

  # Rungs must be gone
  run grep -c "Does this need to exist at all? (YAGNI)" \
      "$wt/agents/software-engineer.md" || true
  [[ "$output" == "0" ]]

  # NEVER simplified away (carve-out sentinel) must be gone
  run grep -c "NEVER simplified away" "$wt/agents/software-engineer.md" || true
  [[ "$output" == "0" ]]

  run grep -c "Does this need to exist at all? (YAGNI)" \
      "$wt/agents/frontend-engineer.md" || true
  [[ "$output" == "0" ]]

  run grep -c "NEVER simplified away" "$wt/agents/frontend-engineer.md" || true
  [[ "$output" == "0" ]]
}

# ─── B2: decision-ladder leaves agents byte-unchanged ─────────────────────────
@test "B2 preamble decision-ladder leaves agent files byte-unchanged" {
  local wt="$WORK/wt-b2"
  _make_fake_wt "$wt"

  local before_se before_fe
  before_se="$(md5 -q "$wt/agents/software-engineer.md" 2>/dev/null || md5sum "$wt/agents/software-engineer.md" | cut -d' ' -f1)"
  before_fe="$(md5 -q "$wt/agents/frontend-engineer.md" 2>/dev/null || md5sum "$wt/agents/frontend-engineer.md" | cut -d' ' -f1)"

  source "$SUITE_PREAMBLE"
  PREAMBLE="decision-ladder"
  strip_ladder_from_harness "$wt"

  local after_se after_fe
  after_se="$(md5 -q "$wt/agents/software-engineer.md" 2>/dev/null || md5sum "$wt/agents/software-engineer.md" | cut -d' ' -f1)"
  after_fe="$(md5 -q "$wt/agents/frontend-engineer.md" 2>/dev/null || md5sum "$wt/agents/frontend-engineer.md" | cut -d' ' -f1)"

  [[ "$before_se" == "$after_se" ]]
  [[ "$before_fe" == "$after_fe" ]]
}

# ─── B3: none strips SKILL.md ladder note ─────────────────────────────────────
@test "B3 preamble none removes Decision Ladder note from SKILL.md copy" {
  local wt="$WORK/wt-b3"
  _make_fake_wt "$wt"

  source "$SUITE_PREAMBLE"
  PREAMBLE="none"
  strip_ladder_from_harness "$wt"

  # The "Decision Ladder (ADVISORY" phrase from build-implementation/SKILL.md must be gone
  run grep -c "Decision Ladder (ADVISORY" \
      "$wt/skills/build-implementation/SKILL.md" || true
  [[ "$output" == "0" ]]
}

# ─── B4: invalid preamble value exits 2 ──────────────────────────────────────
@test "B4 invalid --preamble value exits 2" {
  source "$SUITE_ARGS"
  run parse_suite_args --preamble bogus-value
  [ "$status" -eq 2 ]
}

# ─── B5: none without --harness-ref exits 2 at parse time ────────────────────
@test "B5 preamble none without --harness-ref exits 2 before prologue" {
  source "$SUITE_ARGS"
  run parse_suite_args --run-id myrun --preamble none
  [ "$status" -eq 2 ]
  [[ "$output" =~ "harness-ref" ]] || [[ "$output" =~ "--harness-ref" ]]
}

@test "B5b preamble none without --harness-ref does not touch live HOME/.claude" {
  # Capture state before
  local home_before
  home_before="$(ls -la "$HOME/.claude" 2>/dev/null | md5 -q 2>/dev/null || ls -la "$HOME/.claude" 2>/dev/null | md5sum | cut -d' ' -f1)"

  source "$SUITE_ARGS"
  run parse_suite_args --run-id myrun --preamble none || true

  # State must be unchanged
  local home_after
  home_after="$(ls -la "$HOME/.claude" 2>/dev/null | md5 -q 2>/dev/null || ls -la "$HOME/.claude" 2>/dev/null | md5sum | cut -d' ' -f1)"
  [[ "$home_before" == "$home_after" ]]
}

# ─── B6: strip is confined to wt-path ─────────────────────────────────────────
@test "B6 strip does not modify real agents/ in repo root" {
  local wt="$WORK/wt-b6"
  _make_fake_wt "$wt"

  source "$SUITE_PREAMBLE"
  PREAMBLE="none"
  strip_ladder_from_harness "$wt"

  # git -C repo_root status --porcelain agents/ must be empty
  run git -C "$REPO_ROOT" status --porcelain agents/
  [ "$status" -eq 0 ]
  [[ "$output" == "" ]]
}

# ─── B7: test_decision_ladder_preamble.py still green ─────────────────────────
@test "B7 test_decision_ladder_preamble.py passes (ladder still in static .md)" {
  run python3 -m pytest "$REPO_ROOT/tests/test_decision_ladder_preamble.py" -q \
      --tb=short 2>&1
  [ "$status" -eq 0 ]
}
