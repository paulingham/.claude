#!/usr/bin/env bats
# Hook-Change Pytest Gate tests — GP-19 closure
#
# Gate: hooks/_lib/hook-pytest-gate.sh (predicate+runner lib)
#       skills/pr-creation/lib/check-hook-pytest-gate.sh (Ship wrapper)
#
# Key design invariants under test:
#   AC1  — fires + runs targeted pytest FROM the worktree (not repo-root)
#   AC2  — blocks (exit 2) when pytest reports a red node
#   AC3  — no-op (exit 0, pytest never invoked) when no hooks/*.sh body changed
#   AC3b — no-op on blank-only hook edit
#   AC4  — hooks/_lib/*.sh body change also fires
#   diff-base — hook change in an EARLIER commit (not HEAD) STILL fires
#             (main...HEAD, not HEAD~1 — the HIGH-1 regression guard)
#   AC5  — Ship-wrapper exits 2 on red, independent of gh command shape
#
# bash-3.2 clean (macOS default); no mapfile/readarray.
# Hermetic: mktemp git repos, PATH-stub for pytest.
# CLAUDE_PLUGIN_ROOT exported in setup.

WORKTREE_PATH="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Create a minimal git repo with an initial commit on "main".
# Usage: _make_repo <dir>
_make_repo() {
  local dir="$1"
  mkdir -p "$dir"
  git -C "$dir" init -q -b main
  git -C "$dir" config user.email "t@t"
  git -C "$dir" config user.name "t"
  git -C "$dir" commit -q --allow-empty -m "init"
}

# Create a git worktree at <wtdir> from <repo>, on branch <branch>.
# Usage: _make_worktree <repo> <wtdir> <branch>
_make_worktree() {
  local repo="$1" wtdir="$2" branch="$3"
  git -C "$repo" worktree add -q -b "$branch" "$wtdir"
}

# Add a file change to the repo (or worktree) and commit it.
# Usage: _commit_file <repodir> <relpath> <content> <message>
_commit_file() {
  local dir="$1" path="$2" content="$3" msg="$4"
  mkdir -p "$(dirname "$dir/$path")"
  printf '%s\n' "$content" > "$dir/$path"
  git -C "$dir" add "$path"
  git -C "$dir" commit -q -m "$msg"
}

# Install a stub pytest on PATH that records $PWD + argv to $PYTEST_SENTINEL,
# then exits with $PYTEST_STUB_RC (default 0).
# Call _install_pytest_stub before the gate under test.
_install_pytest_stub() {
  local stub_dir="$BATS_FILE_TMPDIR/stub-bin"
  mkdir -p "$stub_dir"
  cat > "$stub_dir/pytest" <<'STUB'
#!/usr/bin/env bash
# Stub: record cwd and argv, then exit with configured rc.
sentinel="${PYTEST_SENTINEL:-/dev/null}"
printf 'PWD=%s\nARGV=%s\n' "$PWD" "$*" >> "$sentinel"
exit "${PYTEST_STUB_RC:-0}"
STUB
  # Also stub python3 -m pytest via a python3 wrapper that delegates to pytest
  cat > "$stub_dir/python3" <<'PYSTUB'
#!/usr/bin/env bash
# Stub python3: when called as `python3 -m pytest ...`, delegate to stub pytest.
if [ "${1:-}" = "-m" ] && [ "${2:-}" = "pytest" ]; then
  shift 2
  exec "$(dirname "$0")/pytest" "$@"
fi
exec /usr/bin/env python3 "$@"
PYSTUB
  chmod +x "$stub_dir/pytest" "$stub_dir/python3"
  export PATH="$stub_dir:$PATH"
}

# Source the gate lib from the repo under test (not the local worktree).
# Sets $HPG_LIB to the path.
_source_gate_lib() {
  HPG_LIB="$WORKTREE_PATH/hooks/_lib/hook-pytest-gate.sh"
  # shellcheck source=/dev/null
  source "$HPG_LIB"
}

# ---------------------------------------------------------------------------
# setup / teardown
# ---------------------------------------------------------------------------

setup() {
  BATS_FILE_TMPDIR="$(mktemp -d -t hpg.XXXXXX)"
  export CLAUDE_PLUGIN_ROOT="$WORKTREE_PATH"
  export PYTEST_SENTINEL="$BATS_FILE_TMPDIR/pytest-sentinel.txt"
  export PYTEST_STUB_RC="0"
  # Ensure sentinel is absent at start of each test.
  rm -f "$PYTEST_SENTINEL"
}

teardown() {
  rm -rf "$BATS_FILE_TMPDIR"
}

# ---------------------------------------------------------------------------
# AC1: fires + runs targeted pytest FROM the worktree on a hook-body change
# ---------------------------------------------------------------------------

@test "AC1: hook-body change fires gate, pytest runs with worktree as cwd" {
  # Build a fixture repo + worktree where the branch adds a hooks/*.sh body line.
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _make_repo "$repo"
  _make_worktree "$repo" "$wt" "feat/hook-change"

  # Add a hooks/ dir and commit a non-blank body change on the feature branch.
  mkdir -p "$wt/hooks"
  printf '#!/usr/bin/env bash\necho "hello"\n' > "$wt/hooks/my-hook.sh"
  git -C "$wt" add "hooks/my-hook.sh"
  git -C "$wt" commit -q -m "add hook"

  # Also create a tests/ dir with a dummy test file so the subset resolver
  # finds something (avoids the WARN-only empty-subset path).
  mkdir -p "$wt/tests"
  printf '# dummy\n' > "$wt/tests/test_dummy_invariants.py"
  git -C "$wt" add "tests/test_dummy_invariants.py"
  git -C "$wt" commit -q -m "add test"

  _install_pytest_stub

  _source_gate_lib

  # Run the predicate check from the worktree.
  run _hpg_hook_body_changed "$wt"
  [ "$status" -eq 0 ]

  # Run the full gate (predicate + runner).
  # We need a fake subset that includes our dummy file.
  PYTEST_STUB_RC=0 run bash -c "
    source '$HPG_LIB'
    cd '$wt'
    _hpg_run '$wt'
  "
  [ "$status" -eq 0 ]

  # Sentinel must have been written — pytest was invoked.
  [ -f "$PYTEST_SENTINEL" ]

  # The PWD recorded in the sentinel must be the worktree, not repo-root.
  grep -q "PWD=$wt" "$PYTEST_SENTINEL"
}

# ---------------------------------------------------------------------------
# AC2: blocks (exit 2) when pytest reports a red node
# ---------------------------------------------------------------------------

@test "AC2: blocks (exit 2) on red pytest result, prints PR_BLOCKED" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _make_repo "$repo"
  _make_worktree "$repo" "$wt" "feat/hook-change"

  mkdir -p "$wt/hooks" "$wt/tests"
  printf '#!/usr/bin/env bash\necho "hi"\n' > "$wt/hooks/my-hook.sh"
  git -C "$wt" add "hooks/my-hook.sh"
  git -C "$wt" commit -q -m "add hook"
  printf '# dummy\n' > "$wt/tests/test_dummy_invariants.py"
  git -C "$wt" add "tests/test_dummy_invariants.py"
  git -C "$wt" commit -q -m "add test"

  # Stub pytest to return rc=1 (red) and emit a FAILED node.
  local stub_dir="$BATS_FILE_TMPDIR/stub-bin"
  mkdir -p "$stub_dir"
  cat > "$stub_dir/pytest" <<'STUB'
#!/usr/bin/env bash
printf 'PWD=%s\nARGV=%s\n' "$PWD" "$*" >> "${PYTEST_SENTINEL:-/dev/null}"
printf 'FAILED tests/test_something.py::test_invariant_broken\n'
exit 1
STUB
  chmod +x "$stub_dir/pytest"
  export PATH="$stub_dir:$PATH"

  run bash -c "
    source '$WORKTREE_PATH/hooks/_lib/hook-pytest-gate.sh'
    cd '$wt'
    _hpg_run '$wt'
  "
  [ "$status" -ne 0 ]

  # And the wrapper check-hook-pytest-gate.sh should exit 2 with PR_BLOCKED.
  # We need to simulate it being run from the worktree context.
  run bash -c "
    export PYTEST_SENTINEL='$PYTEST_SENTINEL'
    cd '$wt'
    WORKTREE='$wt' bash '$WORKTREE_PATH/skills/pr-creation/lib/check-hook-pytest-gate.sh'
  " 2>&1
  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

# ---------------------------------------------------------------------------
# AC3: no-op when no hooks/*.sh body changed (non-hook files only)
# ---------------------------------------------------------------------------

@test "AC3: no-op (exit 0, pytest never invoked) when diff touches only non-hook files" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _make_repo "$repo"
  _make_worktree "$repo" "$wt" "feat/docs-only"

  # Only commit a .md and .py change (no hooks/).
  mkdir -p "$wt/docs"
  printf '# docs\n' > "$wt/docs/README.md"
  git -C "$wt" add "docs/README.md"
  git -C "$wt" commit -q -m "add docs"

  _install_pytest_stub
  _source_gate_lib

  # Predicate must return 1 (no-op).
  run _hpg_hook_body_changed "$wt"
  [ "$status" -ne 0 ]

  # Sentinel must NOT exist — pytest was not invoked.
  [ ! -f "$PYTEST_SENTINEL" ]
}

# ---------------------------------------------------------------------------
# AC3b: no-op on blank-only hook edit
# ---------------------------------------------------------------------------

@test "AC3b: no-op (exit 0, pytest never invoked) when hook diff is blank-only" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _make_repo "$repo"

  # Create a hooks/ file on main.
  mkdir -p "$repo/hooks"
  printf '#!/usr/bin/env bash\necho "existing"\n' > "$repo/hooks/my-hook.sh"
  git -C "$repo" add "hooks/my-hook.sh"
  git -C "$repo" commit -q -m "add hook on main"

  _make_worktree "$repo" "$wt" "feat/blank-only"

  # Modify the hook to add only blank lines.
  printf '#!/usr/bin/env bash\n\n\necho "existing"\n\n' > "$wt/hooks/my-hook.sh"
  git -C "$wt" add "hooks/my-hook.sh"
  git -C "$wt" commit -q -m "blank-only hook edit"

  _install_pytest_stub
  _source_gate_lib

  # Predicate must return 1 (no-op) — no non-blank lines added or removed.
  run _hpg_hook_body_changed "$wt"
  [ "$status" -ne 0 ]

  # Sentinel must NOT exist.
  [ ! -f "$PYTEST_SENTINEL" ]
}

# ---------------------------------------------------------------------------
# AC4: hooks/_lib/*.sh body change also fires
# ---------------------------------------------------------------------------

@test "AC4: hooks/_lib/*.sh body change fires the gate" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _make_repo "$repo"
  _make_worktree "$repo" "$wt" "feat/lib-change"

  # Commit a _lib/*.sh body change on the feature branch.
  mkdir -p "$wt/hooks/_lib"
  printf '#!/usr/bin/env bash\necho "lib"\n' > "$wt/hooks/_lib/my-lib.sh"
  git -C "$wt" add "hooks/_lib/my-lib.sh"
  git -C "$wt" commit -q -m "add lib hook"

  _install_pytest_stub
  _source_gate_lib

  # Predicate must fire (return 0).
  run _hpg_hook_body_changed "$wt"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# diff-base: hook change in an EARLIER commit STILL fires (main...HEAD, not HEAD~1)
# This is the HIGH-1 regression guard.
# ---------------------------------------------------------------------------

@test "diff-base: hook change in commit-1 of N still fires when HEAD is a later commit" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _make_repo "$repo"
  _make_worktree "$repo" "$wt" "feat/multi-commit"

  # Commit 1: the hooks/*.sh body change.
  mkdir -p "$wt/hooks"
  printf '#!/usr/bin/env bash\necho "hook body"\n' > "$wt/hooks/my-hook.sh"
  git -C "$wt" add "hooks/my-hook.sh"
  git -C "$wt" commit -q -m "commit-1: add hook"

  # Commit 2: an unrelated test change (HEAD at this commit when gate runs).
  mkdir -p "$wt/tests"
  printf '# test\n' > "$wt/tests/test_something.py"
  git -C "$wt" add "tests/test_something.py"
  git -C "$wt" commit -q -m "commit-2: add test (HEAD)"

  # HEAD is now the test commit; the hook change is in commit-1.
  # With HEAD~1..HEAD the gate would miss it. With main...HEAD it must fire.

  _install_pytest_stub
  _source_gate_lib

  run _hpg_hook_body_changed "$wt"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# AC5: gate is a skill-step lib — wrapper exits 2 on red independent of gh shape
# ---------------------------------------------------------------------------

@test "AC5: check-hook-pytest-gate.sh exits 2 on red, regardless of gh command shape" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _make_repo "$repo"
  _make_worktree "$repo" "$wt" "feat/hook-change"

  mkdir -p "$wt/hooks" "$wt/tests"
  printf '#!/usr/bin/env bash\necho "hook"\n' > "$wt/hooks/hook.sh"
  git -C "$wt" add "hooks/hook.sh"
  git -C "$wt" commit -q -m "add hook"
  printf '# test\n' > "$wt/tests/test_dummy_invariants.py"
  git -C "$wt" add "tests/test_dummy_invariants.py"
  git -C "$wt" commit -q -m "add test"

  # Stub pytest to return red.
  local stub_dir="$BATS_FILE_TMPDIR/stub-ac5"
  mkdir -p "$stub_dir"
  cat > "$stub_dir/pytest" <<'STUB'
#!/usr/bin/env bash
printf 'FAILED tests/test_something.py::test_broken\n'
exit 1
STUB
  chmod +x "$stub_dir/pytest"
  export PATH="$stub_dir:$PATH"

  # Run the wrapper from the worktree — simulating Ship skill invocation.
  run bash -c "
    cd '$wt'
    WORKTREE='$wt' bash '$WORKTREE_PATH/skills/pr-creation/lib/check-hook-pytest-gate.sh'
  " 2>&1
  [ "$status" -eq 2 ]
  [[ "$output" == *"PR_BLOCKED"* ]]
}

# ---------------------------------------------------------------------------
# AC5b: check-hook-pytest-gate.sh exits 0 when no hook changed (no-op path)
# ---------------------------------------------------------------------------

@test "AC5b: check-hook-pytest-gate.sh exits 0 (no-op) when no hooks changed" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _make_repo "$repo"
  _make_worktree "$repo" "$wt" "feat/docs-only"

  # Only a non-hook change.
  mkdir -p "$wt/docs"
  printf '# docs\n' > "$wt/docs/README.md"
  git -C "$wt" add "docs/README.md"
  git -C "$wt" commit -q -m "docs change"

  _install_pytest_stub

  run bash -c "
    cd '$wt'
    WORKTREE='$wt' bash '$WORKTREE_PATH/skills/pr-creation/lib/check-hook-pytest-gate.sh'
  " 2>&1
  [ "$status" -eq 0 ]

  # Sentinel must NOT exist — pytest was not invoked.
  [ ! -f "$PYTEST_SENTINEL" ]
}

# ---------------------------------------------------------------------------
# AC-empty-subset: hook body changed but resolver finds zero matching tests
# Gate must exit 0, emit the WARN on stdout, and never invoke pytest.
# ---------------------------------------------------------------------------

@test "AC-empty-subset: hook changed, empty test subset -> exit 0, WARN surfaced, pytest never ran" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _make_repo "$repo"
  _make_worktree "$repo" "$wt" "feat/hook-change-no-tests"

  # Add a hook body change so the gate fires.
  mkdir -p "$wt/hooks"
  printf '#!/usr/bin/env bash\necho "hook body"\n' > "$wt/hooks/my-hook.sh"
  git -C "$wt" add "hooks/my-hook.sh"
  git -C "$wt" commit -q -m "add hook body"

  # Create a tests/ dir but with NO files matching test_*_invariants.py
  # and NO files containing 'hooks/' — so the resolver returns empty.
  mkdir -p "$wt/tests"
  printf '# unrelated\n' > "$wt/tests/test_unrelated.py"
  git -C "$wt" add "tests/test_unrelated.py"
  git -C "$wt" commit -q -m "add unrelated test (no hooks/ ref)"

  _install_pytest_stub

  # Run the wrapper — must exit 0 and surface the WARN string.
  run bash -c "
    export PYTEST_SENTINEL='$PYTEST_SENTINEL'
    cd '$wt'
    WORKTREE='$wt' bash '$WORKTREE_PATH/skills/pr-creation/lib/check-hook-pytest-gate.sh'
  " 2>&1
  [ "$status" -eq 0 ]
  [[ "$output" == *"HOOK-PYTEST GATE: WARN"* ]]
  [[ "$output" == *"NO targeted tests resolved"* ]]

  # Sentinel must NOT exist — pytest was never invoked.
  [ ! -f "$PYTEST_SENTINEL" ]
}

# ---------------------------------------------------------------------------
# Bypass: CLAUDE_DISABLE_HOOK_PYTEST_GATE=1 skips the gate entirely
# ---------------------------------------------------------------------------

@test "bypass: CLAUDE_DISABLE_HOOK_PYTEST_GATE=1 skips gate (exit 0)" {
  local repo="$BATS_FILE_TMPDIR/repo"
  local wt="$BATS_FILE_TMPDIR/wt"
  _make_repo "$repo"
  _make_worktree "$repo" "$wt" "feat/hook-change"

  mkdir -p "$wt/hooks"
  printf '#!/usr/bin/env bash\necho "hook"\n' > "$wt/hooks/hook.sh"
  git -C "$wt" add "hooks/hook.sh"
  git -C "$wt" commit -q -m "add hook"

  # Stub pytest to always fail — if bypass works, pytest won't be called.
  local stub_dir="$BATS_FILE_TMPDIR/stub-bypass"
  mkdir -p "$stub_dir"
  cat > "$stub_dir/pytest" <<'STUB'
#!/usr/bin/env bash
printf 'FAILED tests/test_something.py::test_broken\n'
exit 1
STUB
  chmod +x "$stub_dir/pytest"
  export PATH="$stub_dir:$PATH"

  run bash -c "
    export CLAUDE_DISABLE_HOOK_PYTEST_GATE=1
    cd '$wt'
    WORKTREE='$wt' bash '$WORKTREE_PATH/skills/pr-creation/lib/check-hook-pytest-gate.sh'
  " 2>&1
  [ "$status" -eq 0 ]
}
