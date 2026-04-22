---
category: discovery
---

Hooks that source helper libraries must use `$(dirname "${BASH_SOURCE[0]}")/_lib/…` NOT `$HOME/.claude/hooks/_lib/…`. The former is worktree/checkout-location agnostic; the latter fails whenever the hook is invoked from a worktree or agent branch whose files have not yet been merged to the canonical `~/.claude`. `hooks/tests/test-hooks.sh` runs hooks against the worktree's `$HOOKS_DIR`, not against the canonical `~/.claude` — this exposed the bug quickly.

---
category: pattern
---

`_md5_hash` primitive + `_project_hash --fallback VALUE` wrapper is the right split: the primitive preserves the existing `pipe | _md5_hash` semantics at all 6 call sites, while the wrapper absorbs the 3 distinct fallback semantics (literal "local", literal "", basename expression). Arg form (`_md5_hash "abc"`) was rejected in the plan for good reason — command-substitution inside the arg swallows upstream `git` failure and breaks `set -e`.

---
category: fragility
---

`_project_hash` must distinguish three failure modes of its upstream pipe:
1. `git remote get-url origin` exits non-zero (no remote / outside repo)
2. `git remote get-url origin` exits 0 with empty stdout (very rare but possible)
3. `_md5_hash` exits non-zero (neither md5sum nor openssl on PATH)

Naive `git ... | _md5_hash` would hand the empty-input canonical digest `d41d8cd98f00b204e9800998ecf8427e` to the caller for case 1, silently wrong. The fix: explicitly check `git` exit code via `url=$(...) || fallback` AND check `-z "$url"` before piping.

---
category: decision
---

AC1.2 (Ubuntu 24.04 parity) is proved via a dual-backend test that runs both `md5sum` and `openssl dgst -md5` locally and asserts identical canonical digests for `abc` and empty input. Docker was not available on the build host; live Ubuntu verification must happen in CI when a Linux runner executes the same bats spec. Both backends are spec-compliant MD5 implementations — if they agree on `abc` and the empty input, they agree on all inputs.

---
category: warning
---

Byte-for-byte parity with the pre-migration `git remote get-url origin | openssl md5 -r` pipeline was at risk. The old pipeline preserved git's trailing newline. The new `_project_hash` captures git output into `$(...)` (which strips trailing newline) then re-emits via `printf`. Without explicit handling, digests would diverge, orphaning every existing `session-memory/{old-hash}/` and `learning/{old-hash}/` directory.

Fix: `_project_hash` uses `printf '%s\n' "$url"` (with newline) before piping to `_md5_hash`. This re-adds the trailing newline that `$(...)` stripped, restoring byte-for-byte parity. Verified via `tests/shell/project-hash.bats::AC1.5f` which creates a throwaway git repo, computes the digest both ways, and asserts equality. Reviewers: DO NOT remove the `\n` from that printf.

This is a genuinely subtle invariant — the primitive `_md5_hash` takes stdin as-is (AC1.1 requires no newline for `abc`), so the newline MUST be added by `_project_hash`, not by `_md5_hash`. The asymmetry is correct: `_md5_hash` is a pure MD5 primitive; `_project_hash` preserves legacy call-site behavior.
