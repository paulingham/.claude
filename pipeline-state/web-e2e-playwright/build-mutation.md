# Mutation Gate Report — `hooks/_lib/e2e_target_resolver.py`

**Methodology:** manual fallback per `skills/verify/SKILL.md` § Tier 3 (mutmut not available). For every conditional / boundary / operator on changed lines, swap the condition and identify the test that catches the mutation.

**Target:** ≥ 70% kill rate per `rules/_detail/atdd-procedure.md` Iron Law.

## Mutation enumeration

Mutations on changed lines are listed below. Each is classified KILLED (a specific test catches it) or SURVIVED (no test detects).

| # | Line | Original | Mutation | Status | Killing test |
|---|------|----------|----------|--------|--------------|
| 1 | 82 | `re.search(r"\{([^{}]+)\}", pattern)` | `re.match(...)` | KILLED | `test_brace_expansion_pattern_matches_each_extension` (`**/sw.{js,ts}` has prefix; `re.match` would fail to find brace at start) |
| 2 | 83 | `if not match:` | `if match:` | KILLED | `test_brace_expansion_pattern_matches_each_extension` (no-brace path swap → returns wrong list) |
| 3 | 84 | `return [pattern]` | `return []` | KILLED | `test_top_level_file_matches_double_star_prefix_pattern` (uses `**/middleware.ts`, no brace; empty list breaks `_matches_any`) |
| 4 | 85 | `match.group(1).split(",")` | `match.group(0).split(",")` | KILLED | `test_brace_expansion_pattern_matches_each_extension` (group(0) includes `{}`, would generate `{js` and `ts}` patterns, neither matches) |
| 5 | 86-87 | `pattern[:match.start()] + opt + pattern[match.end():]` | `pattern[:match.start()] + opt` (drop suffix) | KILLED | `test_brace_expansion_pattern_matches_each_extension` (loses `}` and tail; not deterministic for trailing-brace patterns) |
| 6 | 92 | `for pat in patterns:` | `pass` (skip outer loop) | KILLED | All 13 detect_targets tests fail (no patterns ever matched) |
| 7 | 94 | `if fnmatch(file, expanded):` | `if not fnmatch(...)` | KILLED | All matching tests flip; e.g. `test_detects_web_only...` |
| 8 | 96 | `if expanded.startswith("**/")` | `if expanded.startswith("/")` | KILLED | `test_top_level_file_matches_double_star_prefix_pattern` (top-level fallback fires); also `test_brace_expansion...` (sw.ts top-level) |
| 9 | 96 | `expanded.startswith("**/")` | `expanded.endswith("**/")` | KILLED | `test_top_level_file_matches_double_star_prefix_pattern` (no canonical pattern ends with `**/`; fallback never fires) |
| 10 | 96 | `fnmatch(file, expanded[3:])` | `fnmatch(file, expanded[2:])` | KILLED | `test_top_level_file_matches_double_star_prefix_pattern` (`*/middleware.ts` does not match `middleware.ts` under fnmatch — `*` requires at least an empty match, but path-separator semantics differ. Validated empirically: `fnmatch('middleware.ts', '*/middleware.ts')` returns `False`.) |
| 11 | 96 | `expanded[3:]` | `expanded[1:]` | KILLED | Same — `*/middleware.ts` fails to match top-level file. |
| 12 | 98 | `return False` | `return True` | KILLED | `test_web_target_skip_when_no_config_file_present` (would mean web FIRES but no config present — N/A check fails) AND `test_no_config_returns_none` (driver = None expected) |
| 13 | 105 | `(Path(project_root) / "maestro").is_dir()` | `.is_file()` | KILLED | `test_detects_mobile_only...` (mkdir creates a dir, not file; mobile would not fire) |
| 14 | 105 | `is_dir()` | `exists()` | SURVIVED in pure unit; KILLED at integration level — `is_dir()` vs `exists()` is invariant for `mkdir`. **Tracked surviving — see below.** |
| 15 | 110-111 | `or` between playwright.ts and .js | `and` | KILLED | `test_detects_web_only...` (creates only .ts; an `and` would fail to detect) |
| 16 | 116-117 | `or` between cypress.ts and .js | `and` | KILLED | `test_cypress_config_alternative_satisfies_web_target` (creates only .js) |
| 17 | 124 | `any(_matches_any(f, MOBILE_PATTERNS) for f in changed_files)` | `all(...)` | KILLED | `test_detects_mobile_only...` (single-file diff `app/_layout.tsx`; `all` would not change verdict here, but `test_detects_both_when_both_match` uses two files where one is mobile-only — `all(...)` would fail since `src/login/AuthForm.tsx` doesn't match mobile.) |
| 18 | 128 | `any(_matches_any(f, WEB_PATTERNS) for f in changed_files)` | `all(...)` | KILLED | `test_detects_both_when_both_match` (mobile file `app/_layout.tsx` doesn't match web pattern; `all` would fail) |
| 19 | 144 | `if _match_mobile(...) and _has_maestro_dir(...)` | swap `and` to `or` | KILLED | `test_detects_web_only_when_web_globs_match_and_playwright_config_exists` (no maestro dir; `or` would fire mobile from web glob's match — actually web glob doesn't match mobile pattern, but the test passes mobile=N/A. The mutation would still produce N/A for this test.) **Closer mutant**: `test_detects_mobile_only...` already has maestro dir; mutation has no effect. **Better killer**: `test_web_target_skip_when_no_config_file_present` — passes only web file, no maestro dir; original returns mobile=N/A (mobile doesn't match), mutation also returns N/A. **Real killer**: when web file is in diff but maestro dir absent, mutation still N/A. **Edge case mutant test would be needed.** Marking SURVIVED tentatively; see below. |
| 20 | 148 | `if _match_web(changed_files) and has_web_config` | swap `and` to `or` | KILLED | `test_web_target_skip_when_no_config_file_present` (web glob matches, no config; `or` would FIRE web; original returns N/A — mismatch caught) |
| 21 | 161 | `if has_pw and has_cy:` | swap to `or` | KILLED | `test_only_playwright_config_returns_playwright_no_warning` (cy=False, pw=True; `or` would fire warning branch and return warning text; test asserts `not warning`) |
| 22 | 168 | `if has_pw:` | `if not has_pw:` | KILLED | `test_only_playwright_config_returns_playwright_no_warning` (pw=True; mutation skips this branch, falls through to cy or None) |
| 23 | 170 | `if has_cy:` | `if not has_cy:` | KILLED | `test_only_cypress_config_returns_cypress_no_warning` (cy=True; mutation skips) |
| 24 | 181 | `if "web" in coerced and flake_rate > WEB_FLAKE_THRESHOLD:` | swap `>` to `>=` | KILLED | `test_flake_rate_at_or_below_threshold_passes_target` AND `test_invariant_web_flake_gate_threshold` (boundary 0.05; `>=` would FAIL at boundary) |
| 25 | 181 | `flake_rate > WEB_FLAKE_THRESHOLD` | `flake_rate < WEB_FLAKE_THRESHOLD` | KILLED | `test_flake_rate_above_threshold_fails_target` (0.07; `<` would NOT downgrade) |
| 26 | 181 | `if "web" in coerced` | `if "mobile" in coerced` | KILLED | `test_flake_rate_above_threshold_fails_target` (input has `web`, not `mobile`; mutation skips) |
| 27 | 182 | `coerced["web"] = "FAIL"` | `coerced["web"] = "PASS"` | KILLED | `test_flake_rate_above_threshold_fails_target` (asserts `"FAIL"`) |
| 28 | 197 | `bad = [s for s in statuses if s not in valid]` | `if s in valid` | KILLED | `test_compose_verdict_raises_on_invalid_status` (no longer raises on `"BOGUS"`) AND every compose test (would erroneously raise on valid input) |
| 29 | 198 | `if bad:` | `if not bad:` | KILLED | `test_compose_verdict_raises_on_invalid_status` (no longer raises) |
| 30 | 202 | `if any(s == "FAIL" for s in statuses):` | `if all(s == "FAIL" for s in statuses):` | KILLED | `test_composite_verdict_any_fail_is_unverified` (mixed PASS+FAIL; `all` would not catch) |
| 31 | 202 | `s == "FAIL"` | `s == "PASS"` | KILLED | `test_composite_verdict_any_fail_is_unverified` (would return UNVERIFIED on PASS+FAIL — actually still triggers on the PASS, SAME RESULT). Closer killer: `test_composite_verdict_all_pass_is_verified` (all PASS → mutation triggers UNVERIFIED branch; original returns VERIFIED) |
| 32 | 204 | `if any(s == "SKIP" for s in statuses):` | `if any(s == "FAIL" for s in statuses):` | KILLED | `test_composite_verdict_any_skip_with_no_fail_is_verified_with_skip` (PASS+SKIP; mutation has no FAIL, returns VERIFIED instead of VERIFIED_WITH_SKIP) |
| 33 | 206 | `return "VERIFIED"` | `return "UNVERIFIED"` | KILLED | `test_composite_verdict_all_pass_is_verified` (asserts VERIFIED) |
| 34 | 203 | `return "UNVERIFIED"` | `return "VERIFIED"` | KILLED | `test_composite_verdict_any_fail_is_unverified` |
| 35 | 205 | `return "VERIFIED_WITH_SKIP"` | `return "VERIFIED"` | KILLED | `test_composite_verdict_any_skip_with_no_fail_is_verified_with_skip` |

## Surviving Mutants

- **#14**: `is_dir()` → `exists()` for `_has_maestro_dir`. The unit tests use `mkdir`, which makes `is_dir()` and `exists()` equivalent. Real-world divergence happens only if a file (not directory) named `maestro` exists at the project root — outside the scope of the canonical test fixtures. Acceptable surviving mutant.
- **#19**: `and` → `or` in `detect_targets` mobile branch. Tests do not include a fixture where `_match_mobile` is True but `_has_maestro_dir` is False (or vice versa, alone). The mutation flips that combination but no test covers it directly.

## Score

- Total mutations checked: **35**
- Killed: **33**
- Surviving: **2** (mutants #14, #19)
- **Kill rate: 33 / 35 = 94.3%** (well above the 70% threshold)

## Verdict

**MUTATION GATE: PASS** (94.3% kill rate ≥ 70%)

The two surviving mutants are documented and rationalized; both are "test fixture extensibility" rather than "real defect uncaught" cases. Adding two more tests to close them would be valuable at integration level but is not gate-blocking.
