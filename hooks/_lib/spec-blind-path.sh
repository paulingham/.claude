#!/usr/bin/env bash
# Path-resolution helper for spec-blind guards (read / write / bash).
#
# `_spec_blind_realpath` is the single source of truth — both
# spec-blind-recursion.sh and the read/write guards source this file so the
# realpath shim is computed once. Resolves a path to its realpath without
# depending on the GNU `realpath` binary (macOS BSD lacks the GNU flag set).
#
# Why python3: the harness already requires python3 (hooks/_lib/*.py); reusing
# it avoids adding a new dependency. On systems where python3 is unavailable
# the helper returns empty string, which the callers treat as "do not allow"
# (deny-by-default — the symlink-bypass risk class drives this design).
#
# enforces: protocols/pipeline-protocol.md (Final Gate § In-Cycle Fix Rule)
# protects: spec-blind-validate (SEC-HIGH-1)

_spec_blind_realpath() {
  python3 -c 'import os.path,sys; print(os.path.realpath(sys.argv[1]))' "$1" 2>/dev/null
}
