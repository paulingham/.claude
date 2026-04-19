---
task_id: claude-mem-s6
phase: fix
verdict: FIX_COMPLETE
timestamp: 2026-04-19T00:00:00Z
base_branch: feat/s6/build
fix_branch: feat/s6/fix-security
base_sha: c6f4a57
---

## Summary
Addressed S6 security review blocking findings H1 (file-matcher glob semantics) and M1 (UnicodeDecodeError crash) with TDD red-green-refactor cycles. L1 (unrelated settings.json) verified as a reviewer false positive — no revert needed. All 275 tests green (269 baseline + 6 new regression tests).

## Commits
| SHA | Message |
|-----|---------|
| 29eaf29 | fix(s6): allowlist file-matcher handles /-containing globs (H1) |
| ed050cb | fix(s6): allowlist loader catches UnicodeDecodeError (M1) |

## Test Results
- Before: 269 tests, OK (skipped=1)
- After: 275 tests, OK (skipped=1)
- New regression tests: 6 (5 for H1, 1 for M1)

## Finding Status

### H1 (HIGH) — FIXED
**File:** `skills/capture/_lib/allowlist_matcher.py`
**Root cause:** `_file_matches` three-way evaluator (basename fnmatch + full-path fnmatch + endswith("/"+glob)) silently failed for globs containing both `/` and `*`. Path `/Users/x/.ssh/id_rsa` did not match glob `.ssh/*` under any branch — SSH private keys captured `is_private=0` and indexed.
**Fix:** New `_glob_hits` helper branches on `/` presence: slash-containing globs match via `fnmatch(path, glob)` OR `fnmatch(path, "*/" + glob)`. Basename-only globs keep prior semantics.
**Tests (5):**
- `.ssh/*` vs `/Users/someone/.ssh/id_rsa` → True
- `.ssh/*` vs `/home/bar/.ssh/config` → True
- `.aws/sso/cache/*.json` vs `/Users/x/.aws/sso/cache/abc123.json` → True
- `secrets/*.pem` vs `/repo/secrets/key.pem` → True
- `.ssh/*` vs `/tmp/notssh/file` → False (negative)
**Shape:** file 35 lines; functions: is_private=3, _file_matches=4, _glob_hits=3, _content_matches=3, _haystack=1.

### M1 (MEDIUM) — FIXED
**File:** `skills/capture/_lib/allowlist_loader.py`
**Root cause:** `_safe_parse` caught only `(json.JSONDecodeError, OSError)`. `UnicodeDecodeError` (ValueError subclass) from `Path.read_text()` on non-UTF8 files escaped, crashing the capture hook subprocess and dropping the observation silently — violated AC7 fail-safe posture.
**Fix:** Broaden except to `Exception`. The empty-allowlist fallback + stderr warning is the correct posture on ANY parse failure.
**Tests (1):** Binary/invalid-utf8 user file returns empty allowlist + logs warning, no exception escapes.
**Shape:** file 40 lines; _safe_parse=4 body lines.

### L1 (LOW) — NO ACTION (false positive)
**Investigation:** `git log main..HEAD -- settings.json` returned empty — no S6 commit touched settings.json. `main..HEAD` diff showed settings.json differences because `main` had advanced (commit b7ae469 "path-scoped allows under ~/.claude") while S6 branched off an earlier main. Not S6 scope creep. No revert commit created.

## Shape Self-Check
```
  35 skills/capture/_lib/allowlist_matcher.py
  40 skills/capture/_lib/allowlist_loader.py
```
Both files ≤50 lines. All modified function bodies ≤5 lines, CC ≤5, nesting ≤2.

## Branching
- Branched from: `feat/s6/build` @ c6f4a57
- Fix branch: `feat/s6/fix-security` (2 commits ahead of build)
- Orchestrator to merge `feat/s6/fix-security` → `feat/s6/build` after security re-review.

## Next Phase Input
- Re-dispatch security-engineer on the cumulative diff (feat/s6/build..feat/s6/fix-security).
- Re-review should focus on: (a) new `_glob_hits` semantics are correct for default-shipped patterns, (b) broadened `except Exception` does not mask operational errors (it is bounded to a fail-safe return + stderr log), (c) L1 false-positive classification.
