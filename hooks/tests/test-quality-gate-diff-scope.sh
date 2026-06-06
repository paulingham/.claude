#!/usr/bin/env bash
# Tests for the language-relevance guard on the quality-gate tests check.
#
# Gap fixed: _qg_check_tests_python ran the WHOLE-REPO pytest suite with no
# diff-scoping, so a hook-only PR (only hooks/*.sh changed) was blocked by a
# pre-existing, unrelated pytest baseline. The guard skips the suite ONLY when a
# successfully-computed `git diff HEAD~1 HEAD` contains zero language matches.
#
# Conservative default: an empty-but-successful diff OR an undeterminable diff
# (shallow clone / no HEAD~1) RUNS the suite — never skips.
#
# Run: bash hooks/tests/test-quality-gate-diff-scope.sh
# Exit 0 = all pass; Exit 1 = failures remain.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB="$HOOKS_DIR/_lib/quality-gate-checks.sh"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1"; FAIL=$(( FAIL + 1 )); }

TMPDIR_ROOT=$(mktemp -d)
trap 'rm -rf "$TMPDIR_ROOT"' EXIT

# Fake pytest on PATH: records invocation by touching a sentinel, then exits 0.
FAKE_BIN="$TMPDIR_ROOT/bin"
mkdir -p "$FAKE_BIN"
SENTINEL="$TMPDIR_ROOT/pytest-was-called"
cat > "$FAKE_BIN/pytest" <<EOF
#!/usr/bin/env bash
touch "$SENTINEL"
exit 0
EOF
chmod +x "$FAKE_BIN/pytest"

# Build a throwaway git repo with a controllable HEAD~1 / HEAD diff.
# Modes:
#   sh  -> second commit touches only a .sh file
#   py  -> second commit touches a .py file
#   single -> single commit only (HEAD~1 fails => undeterminable diff)
make_repo() {
  local mode="$1" repo
  repo=$(mktemp -d "$TMPDIR_ROOT/repo.XXXXXX")
  (
    cd "$repo" || exit 1
    git init -q
    git config user.email t@t.t
    git config user.name t
    printf 'echo hi\n' > base.sh
    git add base.sh
    git commit -qm init
    case "$mode" in
      sh) printf 'echo more\n' > extra.sh; git add extra.sh; git commit -qm hook ;;
      py) printf 'print(1)\n' > mod.py; git add mod.py; git commit -qm pychange ;;
      single) : ;;  # leave single-commit so HEAD~1 cannot resolve
    esac
  )
  printf '%s' "$repo"
}

# Run _qg_check_tests_python inside a repo with the fake pytest on PATH.
# Echoes the function's return code; sentinel side-effect is observed by caller.
run_python_check() {
  local repo="$1" rc
  (
    cd "$repo" || exit 99
    PATH="$FAKE_BIN:$PATH"
    # shellcheck disable=SC1090
    source "$LIB"
    _qg_check_tests_python
  ) >/dev/null 2>&1
  rc=$?
  printf '%s' "$rc"
}

echo "=== Quality-Gate Diff-Scope Guard Tests ==="
echo ""

# ── (a) hook-only diff (.sh only) => skip, pytest NOT invoked ─────────────────
echo "-- (a) hook-only (.sh) diff: skip the suite, pytest NOT invoked --"
rm -f "$SENTINEL"
REPO_SH=$(make_repo sh)
RC=$(run_python_check "$REPO_SH")
if [[ "$RC" == "0" ]]; then
  pass "(a1) _qg_check_tests_python returns 0 for a .sh-only diff"
else
  fail "(a1) _qg_check_tests_python returned $RC (expected 0) for a .sh-only diff"
fi
if [[ ! -f "$SENTINEL" ]]; then
  pass "(a2) pytest was NOT invoked for a .sh-only diff"
else
  fail "(a2) pytest WAS invoked for a .sh-only diff (suite not skipped)"
fi
echo ""

# ── (b) diff includes a .py file => suite runs, pytest IS invoked ─────────────
echo "-- (b) diff with a .py file: suite runs, pytest IS invoked --"
rm -f "$SENTINEL"
REPO_PY=$(make_repo py)
RC=$(run_python_check "$REPO_PY")
if [[ -f "$SENTINEL" ]]; then
  pass "(b1) pytest WAS invoked for a .py diff"
else
  fail "(b1) pytest was NOT invoked for a .py diff (suite wrongly skipped)"
fi
if [[ "$RC" == "0" ]]; then
  pass "(b2) _qg_check_tests_python returns 0 when fake pytest passes"
else
  fail "(b2) _qg_check_tests_python returned $RC (expected 0 with passing pytest)"
fi
echo ""

# ── (c) undeterminable diff (single commit) => suite runs (conservative) ──────
echo "-- (c) undeterminable diff (HEAD~1 fails): suite runs, pytest IS invoked --"
rm -f "$SENTINEL"
REPO_ONE=$(make_repo single)
RC=$(run_python_check "$REPO_ONE")
if [[ -f "$SENTINEL" ]]; then
  pass "(c1) pytest WAS invoked when diff is undeterminable (conservative default)"
else
  fail "(c1) pytest was NOT invoked on undeterminable diff (wrongly skipped)"
fi
if [[ "$RC" == "0" ]]; then
  pass "(c2) _qg_check_tests_python returns 0 when fake pytest passes"
else
  fail "(c2) _qg_check_tests_python returned $RC (expected 0 with passing pytest)"
fi
echo ""

# ── Summary ───────────────────────────────────────────────────────────────────
TOTAL=$(( PASS + FAIL ))
echo "=== Results: $PASS/$TOTAL passed ==="
if [[ $FAIL -gt 0 ]]; then
  echo "FAIL: $FAIL test(s) failed"
  exit 1
fi
exit 0
