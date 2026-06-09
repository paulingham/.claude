#!/usr/bin/env bats
# Black-box behavioural tests for the Ship-phase hook-pytest gate.
#
# Gate under test (black-box, invoked as external process only):
#   skills/pr-creation/lib/check-hook-pytest-gate.sh
#
# Public contract under test (from intake/plan — NOT from source):
#
#   CONTRACT-1  When branch diff (vs main) includes a non-blank body change to
#               hooks/*.sh, the gate MUST run targeted pytest. If pytest fails,
#               gate EXITS 2 (PR_BLOCKED). If pytest passes, gate EXITS 0.
#
#   CONTRACT-2  When branch diff includes a non-blank body change to
#               hooks/_lib/*.sh, same behaviour as CONTRACT-1 (fires + pytest).
#
#   CONTRACT-3  When branch diff touches NO hooks/*.sh or hooks/_lib/*.sh body
#               (only docs/config/non-hook code), gate MUST EXIT 0 and MUST NOT
#               run pytest at all.
#
#   CONTRACT-4  A change to a hooks/tests/*.sh file ALONE does NOT fire the gate
#               (EXIT 0, no pytest).
#
#   CONTRACT-5  Only blank-line changes to a hook file (no non-blank diff) MUST
#               NOT fire the gate (EXIT 0, no pytest).
#
#   CONTRACT-6  CLAUDE_DISABLE_HOOK_PYTEST_GATE=1 bypasses the gate (EXIT 0)
#               even when a hook body has changed and pytest would fail.
#
#   CONTRACT-7  Only the exact value "1" triggers the bypass. Other values
#               ("true", "yes", "0", "false") do NOT bypass the gate.
#
#   CONTRACT-8  Hook body change with passing pytest -> gate EXITS 0.
#
# Strategy: construct hermetic fixture git repos + worktrees in mktemp dirs.
# Invoke the gate script as a plain external bash process (black-box).
# Assert on exit code and presence/absence of pytest sentinel file only.
# Do NOT source implementation. Do NOT import from src/.
#
# bash-3.2 clean (macOS default shell).

WORKTREE_PATH="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
GATE_SCRIPT="$WORKTREE_PATH/skills/pr-creation/lib/check-hook-pytest-gate.sh"

# ---------------------------------------------------------------------------
# Shared helpers (black-box only — no sourcing of implementation)
# ---------------------------------------------------------------------------

# Create a minimal git repo with an empty commit on "main".
_bb_make_repo() {
  local dir="$1"
  mkdir -p "$dir"
  git -C "$dir" init -q -b main
  git -C "$dir" config user.email "spec-blind@test"
  git -C "$dir" config user.name "spec-blind"
  git -C "$dir" commit -q --allow-empty -m "root: init main"
}

# Add a git worktree branching off the given repo.
_bb_make_worktree() {
  local repo="$1" wt="$2" branch="$3"
  git -C "$repo" worktree add -q -b "$branch" "$wt"
}

# Commit a file with the given content into a repo/worktree directory.
_bb_commit() {
  local dir="$1" relpath="$2" content="$3" msg="$4"
  mkdir -p "$(dirname "$dir/$relpath")"
  printf '%s' "$content" > "$dir/$relpath"
  git -C "$dir" add "$relpath"
  git -C "$dir" commit -q -m "$msg"
}

# Install a pytest stub that records $PWD to PYTEST_SENTINEL and exits with
# PYTEST_STUB_RC (default 0). The stub dir is prepended to PATH.
# Returns the stub dir path in stdout.
_bb_install_pytest_stub() {
  local stub_dir="$BATS_FILE_TMPDIR/stubbin-$$-$RANDOM"
  mkdir -p "$stub_dir"
  cat > "$stub_dir/pytest" <<'STUB'
#!/usr/bin/env bash
sentinel="${PYTEST_SENTINEL:-/dev/null}"
printf 'PWD=%s\nARGV=%s\n' "$PWD" "$*" >> "$sentinel"
exit "${PYTEST_STUB_RC:-0}"
STUB
  # Also handle python3 -m pytest
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

# Install a pytest stub that always returns RED (rc=1).
_bb_install_red_pytest_stub() {
  local stub_dir="$BATS_FILE_TMPDIR/stubred-$$-$RANDOM"
  mkdir -p "$stub_dir"
  cat > "$stub_dir/pytest" <<'STUB'
#!/usr/bin/env bash
sentinel="${PYTEST_SENTINEL:-/dev/null}"
printf 'PWD=%s\nARGV=%s\n' "$PWD" "$*" >> "$sentinel"
printf 'FAILED tests/test_something.py::test_broken\n'
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

# Run the gate script as a black-box external process.
# Sets WORKTREE env var and cwd to the given worktree path.
# PATH is prepended with stub_dir.
# Captures combined stdout+stderr.
# Writes a runner script to a tmp file to avoid PATH expansion pitfalls
# with multiline bash -c strings in bats.
_bb_run_gate() {
  local wt="$1" stub_dir="$2"
  local runner="$BATS_FILE_TMPDIR/run-gate-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export PATH="${stub_dir}:${PATH}"
export PYTEST_SENTINEL="${PYTEST_SENTINEL}"
export PYTEST_STUB_RC="${PYTEST_STUB_RC:-0}"
cd "${wt}"
WORKTREE="${wt}" bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1
}

# ---------------------------------------------------------------------------
# setup / teardown
# ---------------------------------------------------------------------------

setup() {
  BATS_FILE_TMPDIR="$(mktemp -d -t bbgate.XXXXXX)"
  export PYTEST_SENTINEL="$BATS_FILE_TMPDIR/pytest-sentinel.txt"
  export PYTEST_STUB_RC="0"
  rm -f "$PYTEST_SENTINEL"
}

teardown() {
  rm -rf "$BATS_FILE_TMPDIR"
}

# ---------------------------------------------------------------------------
# CONTRACT-1: hooks/*.sh non-blank body change fires pytest; EXIT 2 on red
# ---------------------------------------------------------------------------

@test "CONTRACT-1a: hooks/*.sh body change with RED pytest -> EXIT 2 with PR_BLOCKED" {
  # Arrange: a feature branch that adds a non-blank hooks/*.sh file.
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/hook-change"

  _bb_commit "$wt" "hooks/my-hook.sh" \
    '#!/usr/bin/env bash
echo "body line"
' \
    "add hooks/my-hook.sh with body"

  # Add a test file so subset resolver has something to find.
  _bb_commit "$wt" "tests/test_my_hook_invariants.py" \
    "# invariants for my-hook\nimport hooks  # noqa\n" \
    "add invariants test"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  # Act: invoke gate as external process.
  _bb_run_gate "$wt" "$stub_dir"

  # Assert: gate must EXIT 2 and print PR_BLOCKED.
  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]

  # Assert: pytest WAS invoked (sentinel written).
  [ -f "$PYTEST_SENTINEL" ]
}

@test "CONTRACT-1b: hooks/*.sh body change with GREEN pytest -> EXIT 0" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/hook-green"

  _bb_commit "$wt" "hooks/passing-hook.sh" \
    '#!/usr/bin/env bash
echo "body"
' \
    "add passing hook"

  _bb_commit "$wt" "tests/test_passing_hook_invariants.py" \
    "# invariants\nimport hooks  # noqa\n" \
    "add invariants test"

  local stub_dir
  stub_dir="$(_bb_install_pytest_stub)"  # exits 0 (green)

  _bb_run_gate "$wt" "$stub_dir"

  # Assert: gate exits 0 (green pytest = no block).
  [ "$status" -eq 0 ]

  # pytest WAS invoked.
  [ -f "$PYTEST_SENTINEL" ]
}

# ---------------------------------------------------------------------------
# CONTRACT-2: hooks/_lib/*.sh non-blank body change also fires the gate
# ---------------------------------------------------------------------------

@test "CONTRACT-2a: hooks/_lib/*.sh body change with RED pytest -> EXIT 2 with PR_BLOCKED" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/lib-change"

  _bb_commit "$wt" "hooks/_lib/helper.sh" \
    '#!/usr/bin/env bash
helper_fn() { echo "lib body"; }
' \
    "add _lib helper with body"

  _bb_commit "$wt" "tests/test_helper_invariants.py" \
    "# invariants\nimport hooks  # noqa\n" \
    "add invariants test"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  _bb_run_gate "$wt" "$stub_dir"

  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
  [ -f "$PYTEST_SENTINEL" ]
}

@test "CONTRACT-2b: hooks/_lib/*.sh body change with GREEN pytest -> EXIT 0" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/lib-green"

  _bb_commit "$wt" "hooks/_lib/helper.sh" \
    '#!/usr/bin/env bash
helper_fn() { echo "lib body"; }
' \
    "add _lib helper with body"

  _bb_commit "$wt" "tests/test_helper_invariants.py" \
    "# invariants\nimport hooks  # noqa\n" \
    "add invariants test"

  local stub_dir
  stub_dir="$(_bb_install_pytest_stub)"  # green

  _bb_run_gate "$wt" "$stub_dir"

  [ "$status" -eq 0 ]
  [ -f "$PYTEST_SENTINEL" ]
}

# ---------------------------------------------------------------------------
# CONTRACT-3: NO hooks body change -> EXIT 0, pytest NOT invoked
# ---------------------------------------------------------------------------

@test "CONTRACT-3a: only docs change -> EXIT 0, pytest never invoked" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/docs-only"

  _bb_commit "$wt" "docs/README.md" "# docs\n" "add docs"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"  # would fail if called

  _bb_run_gate "$wt" "$stub_dir"

  # Gate must exit 0.
  [ "$status" -eq 0 ]
  # Sentinel must NOT exist — pytest was never called.
  [ ! -f "$PYTEST_SENTINEL" ]
}

@test "CONTRACT-3b: only non-hook Python change -> EXIT 0, pytest never invoked" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/python-only"

  _bb_commit "$wt" "skills/some_skill/main.py" \
    "def skill(): pass\n" \
    "add skill python file"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"  # would fail if called

  _bb_run_gate "$wt" "$stub_dir"

  [ "$status" -eq 0 ]
  [ ! -f "$PYTEST_SENTINEL" ]
}

@test "CONTRACT-3c: only config file change -> EXIT 0, pytest never invoked" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/config-only"

  _bb_commit "$wt" "pyproject.toml" "[tool.pytest]\n" "add pyproject config"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"  # would fail if called

  _bb_run_gate "$wt" "$stub_dir"

  [ "$status" -eq 0 ]
  [ ! -f "$PYTEST_SENTINEL" ]
}

# ---------------------------------------------------------------------------
# CONTRACT-4: hooks/tests/*.sh change ALONE does NOT fire the gate
# ---------------------------------------------------------------------------

@test "CONTRACT-4: hooks/tests/*.sh change alone -> EXIT 0, pytest NOT invoked" {
  # This is the spec-blind SWE-Bench-Pro discriminator:
  # An implementation may check 'hooks/*.sh' and accidentally match
  # hooks/tests/*.sh too. The contract explicitly excludes hooks/tests/*.sh.
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/hooks-tests-only"

  # Commit a change to hooks/tests/*.sh (a bats test file under hooks/tests/).
  _bb_commit "$wt" "hooks/tests/test_my_hook.sh" \
    '#!/usr/bin/env bash
# fixture hook-tests file (content irrelevant to the gate)
echo placeholder
' \
    "add hooks/tests bats file"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"  # would fail if called

  _bb_run_gate "$wt" "$stub_dir"

  # Contract: hooks/tests/*.sh alone must NOT fire the gate.
  [ "$status" -eq 0 ]
  [ ! -f "$PYTEST_SENTINEL" ]
}

@test "CONTRACT-4b: hooks/tests/*.sh change alongside hooks/*.sh body change -> fires (hooks/*.sh wins)" {
  # Complementary: when BOTH hooks/tests/ AND hooks/*.sh body are changed,
  # the gate DOES fire (driven by the hooks/*.sh change).
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/both-changes"

  _bb_commit "$wt" "hooks/tests/test_hook.sh" \
    '#!/usr/bin/env bash
# fixture hook-tests file (content irrelevant to the gate)
echo placeholder
' \
    "add hooks/tests bats file"

  _bb_commit "$wt" "hooks/real-hook.sh" \
    '#!/usr/bin/env bash
echo "body line"
' \
    "add hooks body change"

  _bb_commit "$wt" "tests/test_real_hook_invariants.py" \
    "# invariants\nimport hooks  # noqa\n" \
    "add invariants test"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  _bb_run_gate "$wt" "$stub_dir"

  # hooks/*.sh body changed -> gate fires -> red pytest -> EXIT 2.
  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
  [ -f "$PYTEST_SENTINEL" ]
}

# ---------------------------------------------------------------------------
# CONTRACT-5: blank-only hook change -> EXIT 0, no pytest
# ---------------------------------------------------------------------------

@test "CONTRACT-5: blank-only diff to hooks/*.sh -> EXIT 0, pytest NOT invoked" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"

  # Seed main with a hooks/ file.
  _bb_commit "$repo" "hooks/existing.sh" \
    '#!/usr/bin/env bash
echo "existing body"
' \
    "add existing hook on main"

  _bb_make_worktree "$repo" "$wt" "feat/blank-only"

  # Modify the hook file to add only blank lines (no substantive body change).
  printf '#!/usr/bin/env bash\n\n\necho "existing body"\n\n' > "$wt/hooks/existing.sh"
  git -C "$wt" add "hooks/existing.sh"
  git -C "$wt" commit -q -m "blank-only edit to hook"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"  # would fail if called

  _bb_run_gate "$wt" "$stub_dir"

  # Blank-only change must not trigger the gate.
  [ "$status" -eq 0 ]
  [ ! -f "$PYTEST_SENTINEL" ]
}

# ---------------------------------------------------------------------------
# CONTRACT-6: CLAUDE_DISABLE_HOOK_PYTEST_GATE=1 bypasses gate -> EXIT 0
# ---------------------------------------------------------------------------

@test "CONTRACT-6: CLAUDE_DISABLE_HOOK_PYTEST_GATE=1 bypasses gate even with hook body change and red pytest" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/bypass"

  _bb_commit "$wt" "hooks/hook.sh" \
    '#!/usr/bin/env bash
echo "body"
' \
    "add hook body"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"  # would fail if gate runs pytest

  # Set the bypass env var — write a runner to avoid PATH expansion issues.
  local runner="$BATS_FILE_TMPDIR/run-bypass-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export CLAUDE_DISABLE_HOOK_PYTEST_GATE=1
export PATH="${stub_dir}:${PATH}"
export PYTEST_SENTINEL="${PYTEST_SENTINEL}"
cd "${wt}"
WORKTREE="${wt}" bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  # Must exit 0 despite hook change and red pytest stub.
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# CONTRACT-7: Only exact value "1" bypasses — other values do NOT bypass
# ---------------------------------------------------------------------------

@test "CONTRACT-7a: CLAUDE_DISABLE_HOOK_PYTEST_GATE=true does NOT bypass (fires and blocks)" {
  # This is the key spec-blind discriminator for CONTRACT-7.
  # An implementation that treats any truthy string as bypass would fail here.
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/bypass-true"

  _bb_commit "$wt" "hooks/hook.sh" \
    '#!/usr/bin/env bash
echo "body"
' \
    "add hook body"

  _bb_commit "$wt" "tests/test_hook_invariants.py" \
    "# invariants\nimport hooks  # noqa\n" \
    "add invariants test"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  local runner="$BATS_FILE_TMPDIR/run-true-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export CLAUDE_DISABLE_HOOK_PYTEST_GATE=true
export PATH="${stub_dir}:${PATH}"
export PYTEST_SENTINEL="${PYTEST_SENTINEL}"
cd "${wt}"
WORKTREE="${wt}" bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  # "true" must NOT bypass — gate fires, red pytest -> EXIT 2.
  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

@test "CONTRACT-7b: CLAUDE_DISABLE_HOOK_PYTEST_GATE=yes does NOT bypass" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/bypass-yes"

  _bb_commit "$wt" "hooks/hook.sh" \
    '#!/usr/bin/env bash
echo "body"
' \
    "add hook body"

  _bb_commit "$wt" "tests/test_hook_invariants.py" \
    "# invariants\nimport hooks  # noqa\n" \
    "add invariants"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  local runner="$BATS_FILE_TMPDIR/run-yes-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export CLAUDE_DISABLE_HOOK_PYTEST_GATE=yes
export PATH="${stub_dir}:${PATH}"
export PYTEST_SENTINEL="${PYTEST_SENTINEL}"
cd "${wt}"
WORKTREE="${wt}" bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  # "yes" must NOT bypass.
  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

@test "CONTRACT-7c: CLAUDE_DISABLE_HOOK_PYTEST_GATE=0 does NOT bypass" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/bypass-zero"

  _bb_commit "$wt" "hooks/hook.sh" \
    '#!/usr/bin/env bash
echo "body"
' \
    "add hook body"

  _bb_commit "$wt" "tests/test_hook_invariants.py" \
    "# invariants\nimport hooks  # noqa\n" \
    "add invariants"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  local runner="$BATS_FILE_TMPDIR/run-zero-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export CLAUDE_DISABLE_HOOK_PYTEST_GATE=0
export PATH="${stub_dir}:${PATH}"
export PYTEST_SENTINEL="${PYTEST_SENTINEL}"
cd "${wt}"
WORKTREE="${wt}" bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  # "0" must NOT bypass.
  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

@test "CONTRACT-7d: CLAUDE_DISABLE_HOOK_PYTEST_GATE=false does NOT bypass" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/bypass-false"

  _bb_commit "$wt" "hooks/hook.sh" \
    '#!/usr/bin/env bash
echo "body"
' \
    "add hook body"

  _bb_commit "$wt" "tests/test_hook_invariants.py" \
    "# invariants\nimport hooks  # noqa\n" \
    "add invariants"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  local runner="$BATS_FILE_TMPDIR/run-false-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
export CLAUDE_DISABLE_HOOK_PYTEST_GATE=false
export PATH="${stub_dir}:${PATH}"
export PYTEST_SENTINEL="${PYTEST_SENTINEL}"
cd "${wt}"
WORKTREE="${wt}" bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  # "false" must NOT bypass.
  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

@test "CONTRACT-7e: unset CLAUDE_DISABLE_HOOK_PYTEST_GATE does NOT bypass" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/no-bypass-var"

  _bb_commit "$wt" "hooks/hook.sh" \
    '#!/usr/bin/env bash
echo "body"
' \
    "add hook body"

  _bb_commit "$wt" "tests/test_hook_invariants.py" \
    "# invariants\nimport hooks  # noqa\n" \
    "add invariants"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  local runner="$BATS_FILE_TMPDIR/run-unset-$$.sh"
  cat > "$runner" <<RUNNER
#!/usr/bin/env bash
unset CLAUDE_DISABLE_HOOK_PYTEST_GATE
export PATH="${stub_dir}:${PATH}"
export PYTEST_SENTINEL="${PYTEST_SENTINEL}"
cd "${wt}"
WORKTREE="${wt}" bash "${GATE_SCRIPT}"
RUNNER
  chmod +x "$runner"
  run bash "$runner" 2>&1

  # Unset = no bypass.
  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

# ---------------------------------------------------------------------------
# CONTRACT-8: hook body change across multiple commits still fires
# (gate diffs vs main, not just HEAD~1)
# ---------------------------------------------------------------------------

@test "CONTRACT-8: hook body change in earlier commit (not HEAD) still fires gate" {
  # The gate must diff main...HEAD, not HEAD~1..HEAD.
  # If it only looks at HEAD, it misses hook changes buried in earlier commits.
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/multi-commit"

  # Commit 1 (earlier): the hooks/*.sh body change.
  _bb_commit "$wt" "hooks/hook.sh" \
    '#!/usr/bin/env bash
echo "body"
' \
    "commit-1: hook body change"

  _bb_commit "$wt" "tests/test_hook_invariants.py" \
    "# invariants\nimport hooks  # noqa\n" \
    "commit-1b: add invariants test"

  # Commit 2 (HEAD): an unrelated non-hook change.
  _bb_commit "$wt" "docs/notes.md" "# notes\n" "commit-2: docs (HEAD)"

  # At HEAD, the diff vs main includes hooks/hook.sh from commit-1.
  # A naive HEAD~1..HEAD diff would see only docs/notes.md and miss it.
  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  _bb_run_gate "$wt" "$stub_dir"

  # Gate must fire (hook change is in the full diff vs main) -> EXIT 2.
  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
  [ -f "$PYTEST_SENTINEL" ]
}

# ---------------------------------------------------------------------------
# BOUNDARY: hooks/ subdir that is NOT hooks/tests/ or hooks/_lib/ fires gate
# ---------------------------------------------------------------------------

@test "BOUNDARY: hooks/_lib/ with non-blank content fires gate (not silently skipped)" {
  # Ensure hooks/_lib/ is not confused with hooks/tests/ in any implementation
  # that pattern-matches the exclusion.
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/lib-body"

  _bb_commit "$wt" "hooks/_lib/util.sh" \
    '#!/usr/bin/env bash
util_fn() { echo "util body"; }
' \
    "add _lib util with body"

  _bb_commit "$wt" "tests/test_util_invariants.py" \
    "# invariants\nimport hooks  # noqa\n" \
    "add invariants"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"

  _bb_run_gate "$wt" "$stub_dir"

  # _lib/*.sh fires the gate (red pytest -> EXIT 2).
  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

# ---------------------------------------------------------------------------
# BOUNDARY: hooks/tests/*.sh + non-hook file — still no-op (gate does not fire)
# ---------------------------------------------------------------------------

@test "BOUNDARY: hooks/tests/*.sh plus non-hook file -> EXIT 0, no pytest" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _bb_make_repo "$repo"
  _bb_make_worktree "$repo" "$wt" "feat/tests-plus-docs"

  _bb_commit "$wt" "hooks/tests/test_hook.sh" \
    '#!/usr/bin/env bash
# fixture hook-tests file (content irrelevant to the gate)
echo placeholder
' \
    "add hooks/tests bats file"

  _bb_commit "$wt" "docs/notes.md" "# notes\n" "add docs"

  local stub_dir
  stub_dir="$(_bb_install_red_pytest_stub)"  # would fail if called

  _bb_run_gate "$wt" "$stub_dir"

  # Neither hooks/tests/*.sh nor docs trigger the gate.
  [ "$status" -eq 0 ]
  [ ! -f "$PYTEST_SENTINEL" ]
}
