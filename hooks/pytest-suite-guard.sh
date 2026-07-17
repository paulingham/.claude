#!/usr/bin/env bash
# pytest-suite-guard — PreToolUse Bash hook.
# Blocks two command shapes that have twice hung/corrupted the pipeline during
# verification:
#   RULE 1: unbounded whole-suite pytest (no file scope, no -k/-m/--timeout/--co).
#   RULE 2: a worktree-reverting git op (git stash push, or `git checkout <ref> --`
#           pathspec revert) paired with a pytest run in the same command string.
# Fails OPEN (exit 0) on empty/garbage/parse-error and on any non-Bash tool call.
#
# enforces: protocols/atdd-procedure.md:verification
# protects: build-verification, test-execution
# self-test: skip
#
# bash-3.2 clean; no `set -e` (we return/exit explicitly so a parse miss never
# aborts mid-evaluation).
set -uo pipefail

# --- read + parse (mirror quality-gate.sh:20-23) ----------------------------
INPUT=$(cat)
[ -z "$INPUT" ] && exit 0
TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Bash-tool gate + fail-open on no command (covers garbage/parse-error: jq
# emits empty, so we exit 0).
[ "$TOOL_NAME" != "Bash" ] && exit 0
[ -z "$COMMAND" ] && exit 0

# --- detectors --------------------------------------------------------------

# A pytest INVOCATION — pytest occupying command position, not merely
# appearing as text (a grep pattern, a quoted/printed string, a comment).
# Command position = leading token of the whole command, or the leading
# token immediately after a clause separator (&&, ||, ;, |) or a command
# substitution opener ($(). Splits on those separators first (each becomes
# its own candidate clause), then anchors the match to the START of each
# candidate — so `grep -E "pytest-suite-guard"` or `print("about pytest")`
# no longer match: in both, pytest is preceded by a quote/word inside an
# argument, not at clause-start.
_psg_has_pytest() {
  local cmd clause
  cmd=$(printf '%s' "$1" | sed -E 's/(&&|\|\||[;|]|\$\()/\n/g')
  while IFS= read -r clause; do
    clause=$(printf '%s' "$clause" | sed -E 's/^[[:space:]]*\(?[[:space:]]*//')
    printf '%s' "$clause" | grep -Eq '^(python[0-9.]*[[:space:]]+-m[[:space:]]+)?pytest($|[^[:alnum:]_])' && return 0
  done <<< "$cmd"
  return 1
}

# A specific test-file path arg: `tests/....py`, `*_test.py`, or `test_*.py`.
_psg_has_scope_file() {
  printf '%s' "$1" | grep -Eq '(^|[[:space:]])[^[:space:]]*(tests/[^[:space:]]*\.py|[^/[:space:]]*_test\.py|test_[^/[:space:]]*\.py)'
}

# Any non-file scoping/opt-out flag that bounds or sidesteps a full run.
# Strip the `python -m pytest` module selector first so its `-m` is not read as
# a pytest marker flag.
_psg_has_scope_flag() {
  local cmd
  cmd=$(printf '%s' "$1" | sed -E 's/python[0-9.]*[[:space:]]+-m[[:space:]]+pytest/pytest/g')
  printf '%s' "$cmd" | grep -Eq '(^|[[:space:]])(-k|-m|--timeout|--co|--collect-only|--help|-h)([[:space:]=]|$)'
}

# Worktree-reverting git op: `git stash` push form, or `git checkout <ref> -- `
# pathspec revert. `git stash list/show/pop/apply/drop` are NOT push.
_psg_has_revert_op() {
  local cmd="$1"
  # `git checkout ... -- ` pathspec form (reverts tracked files to a ref).
  printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+checkout[[:space:]].*[[:space:]]--[[:space:]]' && return 0
  # `git stash` push form: bare `git stash`, `git stash push`, `git stash save`,
  # `git stash -...`. Excludes the read/restore subcommands.
  printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+stash([[:space:]]+(push|save|-)|[[:space:]]*($|[&;|]))'
}

# --- RULE 2: revert op paired with pytest (check first; more specific) -------
if _psg_has_pytest "$COMMAND" && _psg_has_revert_op "$COMMAND"; then
  {
    printf 'BLOCKED: do not compute baselines by reverting the worktree mid-pipeline.\n'
    printf 'The command pairs a worktree-reverting git op (git stash push, or a\n'
    printf 'git checkout <ref> -- pathspec revert) with a pytest run — this\n'
    printf 'corrupted a worktree this session.\n'
    printf 'To check whether a failure is pre-existing: run the named failing test(s) against the\n'
    printf 'base commit in a SEPARATE checkout, or reference the catalogued baseline\n'
    printf '(memory: pr-gate-120-red-baseline).\n'
  } >&2
  exit 2
fi

# --- RULE 1: unbounded whole-suite pytest -----------------------------------
if _psg_has_pytest "$COMMAND" \
   && ! _psg_has_scope_file "$COMMAND" \
   && ! _psg_has_scope_flag "$COMMAND"; then
  {
    printf 'BLOCKED: unbounded whole-suite pytest run.\n'
    printf 'The full suite is ~2640 tests — slow and nondeterministic, and has hung verification twice.\n'
    printf 'Scope to the changed files and add a timeout, e.g.:\n'
    printf '  pytest tests/test_foo.py tests/test_bar.py -q --timeout=60\n'
    printf 'Or, if you genuinely need a bounded full run, use -k / -m / --timeout / --co.\n'
  } >&2
  exit 2
fi

exit 0
