#!/usr/bin/env bash
# Path-resolution helper for vlm-critic-read-guard.
#
# `_vlm_critic_realpath` is the realpath shim used by the read-guard to
# resolve symlink targets BEFORE allowlist matching (SEC-HIGH-1). Resolves
# without depending on the GNU `realpath` binary (macOS BSD lacks the GNU
# flag set).
#
# Why python3: the harness already requires python3 (hooks/_lib/*.py); reusing
# it avoids adding a new dependency. On systems where python3 is unavailable
# the helper returns empty string, which the caller treats as "do not allow"
# (deny-by-default — the symlink-bypass risk class drives this design).
#
# This is a parallel clone of `hooks/_lib/spec-blind-path.sh`. Consolidation
# deferred to the post-2026-06-09 follow-up pipeline (see
# `pipeline-state/vlm-spec-blind-common-extract-soak-end/pipeline.md`).
#
# enforces: protocols/pipeline-protocol.md (Final Gate § In-Cycle Fix Rule)
# protects: vlm-critic (SEC-HIGH-1)

_vlm_critic_realpath() {
  python3 -c 'import os.path,sys; print(os.path.realpath(sys.argv[1]))' "$1" 2>/dev/null
}
