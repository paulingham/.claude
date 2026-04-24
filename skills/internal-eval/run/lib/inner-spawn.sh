#!/usr/bin/env bash
# Inner-pipeline spawn helpers. Splits the "live" path (no isolation) from the
# pinned path (shadow HOME + symlinked .claude → resolved harness worktree)
# so runner.sh stays within the 50-line shell-shape budget.
# Contract: skills/internal-eval/run/ISOLATION.md.

# _run_inner <run_dir> <inner> <sha>
# Dispatches to live or pinned variant based on resolved sha.
_run_inner() {
  [ "$3" = "live" ] && { _invoke_stub "$1" "$2"; return; }
  _invoke_stub_pinned "$1" "$2" "$3"
}

# _invoke_stub_pinned <run_dir> <inner> <sha>
# Resolves harness worktree, mounts it under a shadow HOME, exports the
# isolation env contract, then runs the stub in a subshell so HOME is local.
_invoke_stub_pinned() {
  local run_dir="$1" inner="$2" sha="$3" shadow root
  shadow="$(shadow_home_path "$run_dir" "$CASE_ID")"
  root="$(resolve_harness_root "$sha" "$run_dir/harness-wt")" || return 2
  ( mount_harness_root "$shadow" "$root" && export_isolation_env "$RUN_ID" "$CASE_ID" "$shadow" && _invoke_stub "$run_dir" "$inner" )
}
