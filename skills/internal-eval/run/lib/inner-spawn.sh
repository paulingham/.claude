#!/usr/bin/env bash
# Inner-pipeline spawn helpers. Splits the "live" path (no isolation) from the
# pinned path (shadow HOME + symlinked .claude → resolved harness worktree)
# so runner.sh stays within the 50-line shell-shape budget.
# Contract: skills/internal-eval/run/ISOLATION.md.

# _run_inner <run_dir> <inner> <sha>
# Dispatches to live or pinned variant based on resolved sha. Both variants
# apply the isolation env contract when the real CLI is invoked (stub path
# preserves legacy "no env vars set = unchanged" semantics).
_run_inner() {
  [ "$3" = "live" ] && { _invoke_inner_live "$1" "$2"; return; }
  _invoke_inner_pinned "$1" "$2" "$3"
}

# _invoke_inner_live <run_dir> <inner>
# Live mode (no --harness-ref). Stub path runs unisolated for back-compat;
# real dispatch is isolated via a subshell export of the env contract so the
# inner /pipeline cannot write into the outer harness's state.
_invoke_inner_live() {
  [ -n "${EVAL_INNER_STUB:-}" ] && { _invoke_stub "$1" "$2"; return; }
  ( export_isolation_env "$RUN_ID" "$CASE_ID" "$HOME" && EVAL_INNER_STUB= _invoke_real "$1" "$2" )
}

# _invoke_inner_pinned <run_dir> <inner> <sha>
# Resolves harness worktree, mounts it under a shadow HOME, exports the
# isolation env contract, then dispatches stub (tests) or real CLI.
_invoke_inner_pinned() {
  local run_dir="$1" inner="$2" sha="$3" shadow root
  shadow="$(shadow_home_path "$run_dir" "$CASE_ID")"
  root="$(resolve_harness_root "$sha" "$run_dir/harness-wt")" || return 2
  ( mount_harness_root "$shadow" "$root" && export_isolation_env "$RUN_ID" "$CASE_ID" "$shadow" && _dispatch_inner_cmd "$run_dir" "$inner" )
}

# _dispatch_inner_cmd <run_dir> <inner> — stub when EVAL_INNER_STUB set, else
# real CLI. EVAL_INNER_STUB is cleared before real dispatch so a nested
# inner pipeline cannot accidentally self-stub.
_dispatch_inner_cmd() {
  [ -n "${EVAL_INNER_STUB:-}" ] && { _invoke_stub "$1" "$2"; return; }
  EVAL_INNER_STUB= _invoke_real "$1" "$2"
}
