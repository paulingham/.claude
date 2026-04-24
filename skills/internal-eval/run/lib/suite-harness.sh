#!/usr/bin/env bash
# Shared harness-ref worktree — created ONCE at suite start and reused across
# all cases. Delegates to Story 6's resolve_harness_root (idempotent by design:
# if worktree path already exists it is returned as-is).

# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/harness-ref.sh"

# setup_shared_harness <sha> <wt-path>  -- empty sha returns $HOME (live).
setup_shared_harness() {
  resolve_harness_root "$1" "$2"
}
