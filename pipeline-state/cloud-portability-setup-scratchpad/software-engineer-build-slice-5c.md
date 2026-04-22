---
role: software-engineer
phase: build-slice-5c
task_id: cloud-portability-setup
verdict: BUILD_COMPLETE
timestamp: 2026-04-22
---

## Summary
Delivered `scripts/_lib/state-symlink.sh` (34/40 lines), replaced 5a's stub with real wiring in `scripts/new-session.sh` (46/50 lines), and added `knowledge/session-isolation-patterns.md` (75 lines) plus cross-ref in `rules/agent-protocol.md`. 10 bats tests + 7 Python tests all green. Full harness bats suite: 92 tests, 0 failures.

## Discoveries & Decisions

---
category: fragility
---
`set -e` plus `cond && f` in `main()` — under `set -e`, a function call that is the entire command on a line and returns non-zero kills the script. The 5a stub pattern `[[ "$NO_SHARE" -eq 1 ]] || _apply_state_symlinks ...` was safe because the stub returned 0. Once I replaced it with `_maybe_share_state` that uses `_is_canonical_harness && ...`, a FALSE canonical check returned 1 and killed new-session.sh (AC5c.3 failed). Fix: append `; :` to guarantee 0 exit. Alternative `_is_canonical_harness "$1" || return 0; ...` also works but adds a line.

---
category: decision
---
Chose `ln -sfn` (not `ln -s`) for the whole surface — makes `_apply_state_symlinks` trivially idempotent. Each re-run replaces existing symlinks. This also makes the AC5c.7 mitigation command in the knowledge doc safe to run multiple times.

---
category: discovery
---
The plan's call signature `_apply_state_symlinks "$REPO" "$wt"` (5a stub) suggested the function should take both args, but the harness-detection logic is cleaner if split: `_is_canonical_harness "$REPO"` is the gate, then `_apply_state_symlinks "$wt"` does the linking. Introduced a tiny `_maybe_share_state "$repo" "$wt"` helper in new-session.sh (1-line body) to bridge the two. Net: the `_lib/state-symlink.sh` functions each have a single responsibility.

---
category: pattern
---
Portable `realpath`-with-fallback pattern: `command -v realpath >/dev/null && { realpath "$1"; return; }; (cd "$1" 2>/dev/null && pwd -P) || printf '%s' "$1"`. Works on macOS bash 3.2 (no GNU realpath by default but may have it via homebrew), Linux (GNU realpath), and containers with neither (`pwd -P` alone). Same-truth comparison even when `$HOME` is symlinked (mac /Users -> /private/Users case).

---
category: warning
---
AC5c.8 (memory-follows-user) test relies on inode sharing through symlinks to a real directory. If the harness ever decided to implement this via bind-mount or overlayfs, the test would need redesign — but symlink is the only POSIX-portable approach.

---
category: decision
---
`_SHARED_DIRS` is a space-delimited string (not an array) so the file stays under 40 lines and works in bash 3.2 strict-POSIX paths. `for d in $_SHARED_DIRS` iterates via word-splitting; fine because the values are hand-authored.

## Test Results
- bats (10 new + 82 existing = 92 total): PASS, 0 fail
- Python (7 new state-symlink tests + 4 new-session shim + baseline): PASS
- shellcheck: clean on new-session.sh + all _lib helpers
- bash -n: clean
- shape: state-symlink.sh 34/40; new-session.sh 46/50; knowledge doc 75 lines
- functions: all ≤ 5 lines; CC ≤ 2; nesting ≤ 1

## Next Phase Input
- All 8 ACs (5c.1 through 5c.8) covered by tests.
- Canonical harness detection resolves both sides via `realpath` with `pwd -P` fallback — portable across macOS (symlinked /Users) and Linux (non-symlinked).
- `_maybe_share_state` in new-session.sh is the single call-site replacing 5a's stub; `--no-state-share` still honoured upstream.
- Knowledge doc cross-ref lives in `rules/agent-protocol.md` at the end of "Worktree Lifecycle".
- No changes to scripts/list-sessions.sh or scripts/remove-session.sh (Slice 5b territory, untouched).
