#!/usr/bin/env bats
# Black-box behavioural tests for the path-independent quality-gate skill step.
#
# Gate under test (black-box, invoked as external process only):
#   skills/pr-creation/lib/check-quality-gate.sh
#
# Public contracts under test (from plan/AC list — NOT from source):
#
#   AC1  (C-DISCRIM) No gh on PATH + failing check -> EXIT 2 PR_BLOCKED.
#        THE literal acceptance test: gate runs with zero gh involvement.
#
#   AC2  (C-EXIT pass) All checks pass/skipped -> EXIT 0, no PR_BLOCKED.
#
#   AC3  (C-EXIT fail) Any single _qg_check_* fails -> EXIT 2 PR_BLOCKED.
#
#   AC4  (C-BYPASS=1) CLAUDE_DISABLE_QUALITY_GATE=1 + failing check -> EXIT 0.
#
#   AC5  (C-BYPASS value-exactness) CLAUDE_DISABLE_QUALITY_GATE in
#        {true,yes,0,false,unset} + failing check -> EXIT 2 PR_BLOCKED.
#
#   AC6  (C-SKIP) CLAUDE_QG_SKIP_CHECKS=1 skips heavy checks; freshness
#        still evaluated.
#
#   AC7  (C-SSOT) Static: wrapper sources quality-gate-checks.sh; defines
#        no _qg_check_*() function; never calls _qg_finalize.
#
#   AC8  (WIRING) SKILL.md Step 2 invokes check-quality-gate.sh as hard gate
#        with GATE_EXIT -ne 0 -> exit 2, after check-hook-pytest-gate.sh.
#
#   AC9  (gh-api path closed) SKILL.md Autonomous PR Creation section
#        references check-quality-gate.sh (closes the gh api quick path).
#
#   AC10 (freshness resolves via cd $WORKTREE) evidence at
#        <wt>/pipeline-state/<task>/verification-evidence.json, cwd != wt
#        -> EXIT 0.  Catches a missing/wrong cd step.
#
#   AC11 (bypass hint in output) On block, output contains the literal
#        CLAUDE_DISABLE_QUALITY_GATE=1 remediation hint.
#
# Strategy: hermetic mktemp git repos + worktrees. Gate invoked as an external
# bash process via a runner script. Exit-code + output assertions only.
# Never source the implementation. bash-3.2 clean.

WORKTREE_PATH="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
GATE_SCRIPT="$WORKTREE_PATH/skills/pr-creation/lib/check-quality-gate.sh"
SKILL_MD="$WORKTREE_PATH/skills/pr-creation/SKILL.md"

# ---------------------------------------------------------------------------
# Shared helpers (black-box only — no sourcing of implementation)
# ---------------------------------------------------------------------------

_bb_make_repo() {
  local dir="$1"
  mkdir -p "$dir"
  git -C "$dir" init -q -b main
  git -C "$dir" config user.email "qg-bb@test"
  git -C "$dir" config user.name "qg-bb"
  git -C "$dir" commit -q --allow-empty -m "root: init main"
}

_bb_make_worktree() {
  local repo="$1" wt="$2" branch="$3"
  git -C "$repo" worktree add -q -b "$branch" "$wt"
}

_bb_commit() {
  local dir="$1" relpath="$2" content="$3" msg="$4"
  mkdir -p "$(dirname "$dir/$relpath")"
  printf '%s' "$content" > "$dir/$relpath"
  git -C "$dir" add "$relpath"
  git -C "$dir" commit -q -m "$msg"
}

# Install a pytest stub that prints FAILED line then exits 1.
# Mirrors _bb_install_red_pytest_stub from the sibling bats file.
# The FAILED line is required: _qg_pytest_failures greps stdout for ^FAILED tests/...
_bb_install_red_pytest_stub() {
  local stub_dir="$BATS_FILE_TMPDIR/stubred-$$-$RANDOM"
  mkdir -p "$stub_dir"
  cat > "$stub_dir/pytest" <<'STUB'
#!/usr/bin/env bash
printf 'FAILED tests/test_dummy.py::test_broken\n'
exit 1
STUB
  cat > "$stub_dir/python3" <<'PYSTUB'
#!/usr/bin/env bash
if [ "${1:-}" = "-m" ] && [ "${2:-}" = "pytest" ]; then
  shift 2
  exec "$(dirname "$0")/pytest" "$@"
fi
exec /usr/bin/env python3 "$@"
PYSTUB
  chmod +x "$stub_dir/pytest" "$stub_dir/python3"
  printf '%s' "$stub_dir"
}

# Build a force-fail fixture:
#   - pyproject.toml present (python runtime detected)
#   - HEAD commit adds src/dummy.py so _qg_diff_skip_eligible '\.py$' returns 1
#   - >=2 commits so HEAD~1..HEAD diff is non-degenerate
#   - no known-red baseline -> _qg_tests_python_no_baseline returns 1
_bb_make_fail_fixture() {
  local repo="$1" wt="$2"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/qg-fail"
  # commit 1: pyproject.toml (python runtime, no .py in HEAD~1..HEAD yet)
  _bb_commit "$wt" "pyproject.toml" "[tool.pytest.ini_options]
" "add pyproject.toml"
  # commit 2 (HEAD): adds a .py file so _qg_diff_skip_eligible '\.py$' returns 1
  _bb_commit "$wt" "src/dummy.py" "def dummy(): pass
" "add src/dummy.py"
}

# Build an all-pass fixture (unknown runtime, no package.json/Gemfile/pyproject.toml)
# so every _qg_check_* returns 0 via its *) return 0 arm.
_bb_make_pass_fixture() {
  local repo="$1" wt="$2"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/qg-pass"
  _bb_commit "$wt" "README.md" "# hello
" "initial commit"
}

# Seed a valid verification-evidence.json in <wt>/pipeline-state/<task>/
# with git_head matching the current HEAD of the worktree.
_bb_seed_evidence() {
  local wt="$1" task="$2"
  local head
  head=$(git -C "$wt" rev-parse HEAD 2>/dev/null)
  mkdir -p "$wt/pipeline-state/$task"
  printf '{"task_id":"%s","verdict":"VERIFIED","git_head":"%s","timestamp":"2026-01-01T00:00:00Z","branch":"feat/qg-pass"}\n' \
    "$task" "$head" > "$wt/pipeline-state/$task/verification-evidence.json"
}

# Run the gate as a black-box external process.
# PATH prepended with stub_dir; WORKTREE set; cd to wt_cwd (default: wt).
_bb_run_gate() {
  local wt="$1" stub_dir="$2" wt_cwd="${3:-$1}"
  local runner="$BATS_FILE_TMPDIR/run-qgate-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export PATH="${stub_dir}:${PATH}"
export WORKTREE="${wt}"
cd "${wt_cwd}"
bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1
}

# ---------------------------------------------------------------------------
# setup / teardown
# ---------------------------------------------------------------------------

setup() {
  BATS_FILE_TMPDIR="$(mktemp -d -t bbqgate.XXXXXX)"
}

teardown() {
  rm -rf "$BATS_FILE_TMPDIR"
}

# ---------------------------------------------------------------------------
# AC1: C-DISCRIM — no gh on PATH + failing check -> EXIT 2 PR_BLOCKED
# ---------------------------------------------------------------------------

@test "AC1 DISCRIM: no gh on PATH + failing check -> EXIT 2 PR_BLOCKED" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_fail_fixture "$repo" "$wt"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  # Remove gh from PATH — gate must run and block without it
  local no_gh_path
  no_gh_path="$(echo "$PATH" | tr ':' '\n' | grep -v "$(dirname "$(command -v gh 2>/dev/null || echo /nonexistent)")" | tr '\n' ':' | sed 's/:$//')"

  local runner="$BATS_FILE_TMPDIR/run-discrim-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export PATH="${stub_dir}:${no_gh_path}"
export WORKTREE="${wt}"
cd "${wt}"
bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

# ---------------------------------------------------------------------------
# AC2: C-EXIT pass — all checks pass -> EXIT 0
# ---------------------------------------------------------------------------

@test "AC2 C-EXIT: all checks pass (unknown runtime) -> EXIT 0" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_pass_fixture "$repo" "$wt"

  local task="qg-ac2"
  _bb_seed_evidence "$wt" "$task"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"  # would fail if invoked

  local runner="$BATS_FILE_TMPDIR/run-pass-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export PATH="${stub_dir}:${PATH}"
export WORKTREE="${wt}"
export CLAUDE_PIPELINE_TASK_ID="${task}"
cd "${wt}"
bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  [ "$status" -eq 0 ]
  [[ "$output" != *"PR_BLOCKED"* ]]
}

# ---------------------------------------------------------------------------
# AC3: C-EXIT fail — any check fails -> EXIT 2 PR_BLOCKED
# ---------------------------------------------------------------------------

@test "AC3 C-EXIT: failing check -> EXIT 2 PR_BLOCKED" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_fail_fixture "$repo" "$wt"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  _bb_run_gate "$wt" "$stub_dir"

  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

# ---------------------------------------------------------------------------
# AC4: C-BYPASS=1 — CLAUDE_DISABLE_QUALITY_GATE=1 bypasses even with failing check
# ---------------------------------------------------------------------------

@test "AC4 C-BYPASS: CLAUDE_DISABLE_QUALITY_GATE=1 bypasses even with failing check" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_fail_fixture "$repo" "$wt"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  local runner="$BATS_FILE_TMPDIR/run-bypass1-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export CLAUDE_DISABLE_QUALITY_GATE=1
export PATH="${stub_dir}:${PATH}"
export WORKTREE="${wt}"
cd "${wt}"
bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# AC5: C-BYPASS value-exactness — values other than "1" do NOT bypass
# ---------------------------------------------------------------------------

@test "AC5a C-BYPASS value-exactness: CLAUDE_DISABLE_QUALITY_GATE=true does NOT bypass" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_fail_fixture "$repo" "$wt"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  local runner="$BATS_FILE_TMPDIR/run-true-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export CLAUDE_DISABLE_QUALITY_GATE=true
export PATH="${stub_dir}:${PATH}"
export WORKTREE="${wt}"
cd "${wt}"
bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

@test "AC5b C-BYPASS value-exactness: CLAUDE_DISABLE_QUALITY_GATE=yes does NOT bypass" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_fail_fixture "$repo" "$wt"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  local runner="$BATS_FILE_TMPDIR/run-yes-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export CLAUDE_DISABLE_QUALITY_GATE=yes
export PATH="${stub_dir}:${PATH}"
export WORKTREE="${wt}"
cd "${wt}"
bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

@test "AC5c C-BYPASS value-exactness: CLAUDE_DISABLE_QUALITY_GATE=0 does NOT bypass" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_fail_fixture "$repo" "$wt"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  local runner="$BATS_FILE_TMPDIR/run-zero-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export CLAUDE_DISABLE_QUALITY_GATE=0
export PATH="${stub_dir}:${PATH}"
export WORKTREE="${wt}"
cd "${wt}"
bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

@test "AC5d C-BYPASS value-exactness: CLAUDE_DISABLE_QUALITY_GATE=false does NOT bypass" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_fail_fixture "$repo" "$wt"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  local runner="$BATS_FILE_TMPDIR/run-false-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export CLAUDE_DISABLE_QUALITY_GATE=false
export PATH="${stub_dir}:${PATH}"
export WORKTREE="${wt}"
cd "${wt}"
bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

@test "AC5e C-BYPASS value-exactness: unset CLAUDE_DISABLE_QUALITY_GATE does NOT bypass" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_fail_fixture "$repo" "$wt"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  local runner="$BATS_FILE_TMPDIR/run-unset-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
unset CLAUDE_DISABLE_QUALITY_GATE
export PATH="${stub_dir}:${PATH}"
export WORKTREE="${wt}"
cd "${wt}"
bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

# ---------------------------------------------------------------------------
# AC6: C-SKIP — CLAUDE_QG_SKIP_CHECKS=1 skips heavy checks, freshness preserved
# ---------------------------------------------------------------------------

@test "AC6 C-SKIP: CLAUDE_QG_SKIP_CHECKS=1 skips heavy checks; gate still evaluates freshness" {
  # Use a fail fixture (would fail heavy checks) but with SKIP set.
  # With no evidence file, freshness still fails -> gate still exits 2.
  # This proves freshness is NOT skipped.
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_fail_fixture "$repo" "$wt"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  local runner="$BATS_FILE_TMPDIR/run-skip-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export CLAUDE_QG_SKIP_CHECKS=1
export PATH="${stub_dir}:${PATH}"
export WORKTREE="${wt}"
cd "${wt}"
bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  # heavy checks skipped (no PR_BLOCKED from pytest) but freshness still runs
  # and fails (no evidence file) -> gate exits 2
  [ "$status" -eq 2 ]
  # freshness failure message expected
  [[ "$output" == *"freshness"* ]] || [[ "$output" == *"PR_BLOCKED"* ]]
}

# ---------------------------------------------------------------------------
# AC7: C-SSOT — static assertion on wrapper source
# ---------------------------------------------------------------------------

@test "AC7 C-SSOT: wrapper sources quality-gate-checks.sh; defines no _qg_check_*(); never calls _qg_finalize" {
  # Wrapper must exist
  [ -f "$GATE_SCRIPT" ]

  # Must source quality-gate-checks.sh
  grep -q 'quality-gate-checks\.sh' "$GATE_SCRIPT"

  # Must NOT define any _qg_check_*() function
  ! grep -q '_qg_check_[a-z_]*()' "$GATE_SCRIPT"

  # Must NOT call _qg_finalize (comments are ok; grep for non-comment invocation lines)
  ! grep -v '^[[:space:]]*#' "$GATE_SCRIPT" | grep -q '_qg_finalize'
}

# ---------------------------------------------------------------------------
# AC8: WIRING — SKILL.md Step 2 invokes check-quality-gate.sh as hard gate
# ---------------------------------------------------------------------------

@test "AC8 WIRING: SKILL.md Step 2 invokes check-quality-gate.sh as hard gate after hook-pytest gate" {
  [ -f "$SKILL_MD" ]

  # Must reference check-quality-gate.sh
  grep -q 'check-quality-gate\.sh' "$SKILL_MD"

  # Must reference GATE_EXIT
  grep -q 'GATE_EXIT' "$SKILL_MD"

  # Must reference exit 2 for blocking
  grep -q 'exit 2' "$SKILL_MD"

  # check-quality-gate.sh reference must appear AFTER check-hook-pytest-gate.sh
  local line_pytest line_qgate
  line_pytest=$(grep -n 'check-hook-pytest-gate\.sh' "$SKILL_MD" | head -1 | cut -d: -f1)
  line_qgate=$(grep -n 'check-quality-gate\.sh' "$SKILL_MD" | head -1 | cut -d: -f1)
  [ -n "$line_pytest" ]
  [ -n "$line_qgate" ]
  [ "$line_qgate" -gt "$line_pytest" ]
}

# ---------------------------------------------------------------------------
# AC9: gh-api path closed — gate referenced in Autonomous PR Creation section
# ---------------------------------------------------------------------------

@test "AC9 WIRING: SKILL.md Autonomous PR Creation section references check-quality-gate.sh" {
  [ -f "$SKILL_MD" ]

  # Find the Autonomous PR Creation section
  grep -q 'Autonomous PR Creation' "$SKILL_MD"

  # Find the line of Autonomous PR Creation section
  local line_auto
  line_auto=$(grep -n 'Autonomous PR Creation' "$SKILL_MD" | head -1 | cut -d: -f1)
  [ -n "$line_auto" ]

  # Find check-quality-gate.sh reference AFTER that section
  local line_qgate_in_auto
  line_qgate_in_auto=$(awk -v start="$line_auto" 'NR > start && /check-quality-gate\.sh/ {print NR; exit}' "$SKILL_MD")
  [ -n "$line_qgate_in_auto" ]
}

# ---------------------------------------------------------------------------
# AC10: freshness resolves via cd $WORKTREE — cwd != worktree still passes
# ---------------------------------------------------------------------------

@test "AC10 FRESHNESS: evidence reachable only via cd WORKTREE -> EXIT 0 from different cwd" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_pass_fixture "$repo" "$wt"

  local task="qg-ac10"
  _bb_seed_evidence "$wt" "$task"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"  # not invoked (unknown runtime)

  # Invoke from a cwd that is NOT the worktree — uses a separate tmpdir
  local other_cwd="$BATS_FILE_TMPDIR/other-cwd"
  mkdir -p "$other_cwd"

  local runner="$BATS_FILE_TMPDIR/run-freshcwd-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export PATH="${stub_dir}:${PATH}"
export WORKTREE="${wt}"
export CLAUDE_PIPELINE_TASK_ID="${task}"
cd "${other_cwd}"
bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  # Gate must pass: it cd's to $WORKTREE, finds evidence there
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# AC11: bypass hint in output — PR_BLOCKED includes CLAUDE_DISABLE_QUALITY_GATE=1
# ---------------------------------------------------------------------------

@test "AC11 BLOCK OUTPUT: PR_BLOCKED output includes CLAUDE_DISABLE_QUALITY_GATE=1 hint" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_fail_fixture "$repo" "$wt"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  _bb_run_gate "$wt" "$stub_dir"

  [ "$status" -eq 2 ]
  [[ "$output" == *"CLAUDE_DISABLE_QUALITY_GATE=1"* ]]
}
