---
task_id: s9-residual
phase: test
verdict: COVERED
timestamp: 2026-04-20T22:45:00Z
reviewer: qa-engineer
branch: fix/s9-residual-bootstrap-and-settings
---

## QA Test Strategy — S9 residual (bootstrap docs + settings.json hygiene)

### Summary

All 9 acceptance criteria across slices 1 and 2 are mapped to concrete evidence
(a passing test, an operational verification, or a grep-based doc invariant).
The new regression test `BootstrapSuiteLeavesSettingsByteIdentical` is
demonstrably falsifiable — the build report captures the exact leaked byte
payload observed in RED before `patch.dict` wraps were applied, proving the
guard asserts real behavior rather than a tautology. Fresh verification
(pytest full suite, targeted tests, module-resolution smoke checks) all green.
No gaps. Single informational note on M1 follow-up (out of scope per plan).

### Verdict: COVERED

### AC Coverage Matrix

#### Slice 1 — Bootstrap docs fix

| AC | Evidence Type | Location / Command | Fresh Status |
|----|---------------|--------------------|--------------|
| 1. `cd ~/.claude && PYTHONPATH=skills python3 -m embedder._lib.bootstrap` resolves | Operational | Re-ran: `exit=0`, no ModuleNotFoundError | PASS |
| 2. `cd /tmp && PYTHONPATH=$HOME/.claude/skills python3 -m embedder._lib.bootstrap` resolves | Operational (cwd-independent) | Re-ran: `exit=0` | PASS |
| 3. Every `python3 -m embedder` in `skills/` + `session-memory/` is prefixed | Grep invariant | 8 occurrences: 3 in `embedder/SKILL.md`, 2 in `embedder/download-model.sh`, 2 in `project-setup/SKILL.md` (absolute), 1 in `session-memory/.../notes.md`. Zero unprefixed. Relative/absolute split correct. | PASS |
| 4. `tests/test_project_setup_embedder_step.py` passes | Automated test | `test_project_setup_embedder_step.py` — 4 tests, all PASSED (re-run now) | PASS |

#### Slice 2 — settings.json hygiene + regression test

| AC | Evidence Type | Location / Command | Fresh Status |
|----|---------------|--------------------|--------------|
| 5. `RunDownloadsModelWhenMissing` passes under new `patch.dict` wrap | Automated test | `tests/test_bootstrap.py::RunDownloadsModelWhenMissing::test_invokes_download_script_with_noninteractive_env` (line 141, re-ran: PASSED) | PASS |
| 5. `RunWarnsWhenDownloadFails` passes under new `patch.dict` wrap | Automated test | `tests/test_bootstrap.py::RunWarnsWhenDownloadFails::test_download_script_nonzero_returns_partial` (line 168, re-ran: PASSED) | PASS |
| 6. New test `BootstrapSuiteLeavesSettingsByteIdentical` passes | Automated test | `tests/test_bootstrap_settings_disk_invariant.py::BootstrapSuiteLeavesSettingsByteIdentical::test_subprocess_unittest_preserves_both_settings_files` (re-ran: PASSED) | PASS |
| 7. Running `tests.test_bootstrap` via subprocess with tempfile settings leaves tempfile AND real settings bytes unchanged | Automated test (same as AC6 — dual-snapshot design covers both assertions) | `test_bootstrap_settings_disk_invariant.py:47-49` (tempfile assertion + real-file assertion) | PASS |
| 8. `~/.claude/settings.json` scrubbed of `/tmp/exists` (verified clean — no-op scrub) | Grep invariant | `grep -nE 'ORT_DYLIB\|BGE_MODEL\|CLAUDE_SETTINGS\|/tmp/exists' settings.json` returns ONLY legitimate `ORT_DYLIB_PATH=/opt/homebrew/lib/libonnxruntime.dylib`. Zero `/tmp/exists` matches. | PASS |
| 9. Full suite passes (≥420 target) | Automated test | `PYTHONPATH=skills python3 -m pytest tests/` — **409 passed, 11 skipped, 0 failed** | PASS (intent) — see note |

**Note on AC9**: Plan's `≥420 passed` estimate was off vs. the actual project
baseline of 408 tests. Actual post-build count is 409 (baseline 408 + 1 new
regression). The meaningful intent — "baseline + 1 new regression test, zero
failures, zero regressions" — is fully satisfied. Build report 2 explicitly
flagged this numeric mismatch; it is a plan-estimate drift, not a coverage gap.

### Falsifiability Audit (AC6/AC7 — the new regression test)

The QA-specific concern for this pipeline is whether the new guard actually
validates what it claims. Five checks:

1. **Well-named?** YES. `BootstrapSuiteLeavesSettingsByteIdentical::
   test_subprocess_unittest_preserves_both_settings_files` reads as the
   invariant it asserts. Failure mode is obvious from the name.
2. **Observed RED?** YES. Build-slice-2 report captures the exact RED output:
   `AssertionError: b'{\n  "env": {\n    "ORT_DYLIB_PATH": "/tmp/exists"\n  }\n}'
   != b'{"env": {}}'`. That is the precise leaked payload — the test saw the
   real leak, not a synthetic failure. No test-weakening.
3. **Exercises the right boundary?** YES. The subprocess runs `-m unittest
   tests.test_bootstrap` (all 14 bootstrap tests) with
   `CLAUDE_SETTINGS_PATH` pointed at a tempfile. Any bootstrap test that
   writes without honoring the override trips the tempfile assertion;
   defence-in-depth real-file assertion catches writes that also bypass the
   override. Subprocess isolation avoids meta-runner recursion.
4. **PYTHONPATH dual-root correctness?** YES. Child env sets
   `PYTHONPATH=f"{REPO_ROOT}:{REPO_ROOT}/skills"` — `REPO_ROOT` so child can
   import `tests.test_bootstrap`, `REPO_ROOT/skills` so child can import
   `embedder.*`. CR-2 round-2 concern fully addressed.
5. **Timeout + check=True?** YES. `subprocess.run(..., check=True, timeout=60)`
   with `except subprocess.TimeoutExpired → self.fail()` converts hang into
   a diagnostic test failure rather than a cascaded exception.
   `check=True` ensures a non-zero exit from the child is treated as a
   regression (silent degradation prevented).

**Verdict on regression test**: falsifiable, well-scoped, captures the
specific leak class. Meets QA standards.

### Coverage Assessment

**Behavior under test (Slice 2)**: test hygiene — `bootstrap_settings.apply()`
MUST NOT write to real `~/.claude/settings.json` when invoked under pytest.

**Coverage tiers**:
- **Direct unit fix**: two tests (`RunDownloadsModelWhenMissing`,
  `RunWarnsWhenDownloadFails`) redirected via `patch.dict` → writes land in
  tempfile, not real disk.
- **Regression guard**: subprocess-isolated dual-snapshot → catches any
  bootstrap-module test that leaks in the future.
- **Scrub**: post-fix grep confirms no residual pollution.

**Gap analysis**: The regression guard is scoped to `tests.test_bootstrap`
per plan R-Option B. A new test file outside that module that leaks would
NOT be caught by this guard. Plan documents this consciously; scope
discipline over breadth. Acceptable per the pipeline's "fix the known leak;
don't build general-purpose infrastructure until a third leak appears"
decision rule.

**Shape verification**: `tests/test_bootstrap_settings_disk_invariant.py`
is 49 lines (within 50-line limit). Helper functions (`_child_env`,
`_run_bootstrap_suite`, `_make_tempfile_settings`) keep method bodies
short. Main test method delegates to `_exercise` — single responsibility
preserved.

### Edge Cases — Covered

- **Tempfile settings pre-write** (`{"env": {}}`): baseline bytes captured
  before subprocess — asserts byte-for-byte invariance, not just "unchanged
  key presence."
- **Real-file absent** (`if real_before is not None:`): guard skips the
  real-file assertion when `~/.claude/settings.json` doesn't exist —
  prevents spurious failures on fresh CI environments.
- **Subprocess timeout** (60s, diagnostic `self.fail()` branch): prevents
  hang propagation.
- **Non-zero child exit** (`check=True`): surfaces as regression, not
  silent success.

### Edge Cases — NOT Covered (with justification)

- **Leak from a test file other than `tests.test_bootstrap`**: out of scope
  per plan; no known leak site exists today. If a third leaking test
  appears, plan's "Watch" clause promotes to class-level helper.
- **Leak from outside the pytest harness** (e.g., developer running
  `python -c "from embedder._lib import bootstrap; bootstrap.run()"`): not
  a test-hygiene concern; that is production usage and `settings.json`
  mutation is the documented behavior.

### Integration Tests Written
None. All ACs are covered by existing or newly-added tests from the build
phase. QA phase is read-only analysis here.

### E2E Flows (Jest / Maestro)
N/A — this pipeline modifies Python test hygiene and Markdown documentation.
No mobile surface, no UI, no user journey triggers. E2E trigger matrix
(`rules/e2e-protocol.md`) does not apply.

### Test Quality Observations

- **No coverage padding**: every assertion checks observable bytes on disk
  or a test exit code — no `typeof X === 'function'` type assertions, no
  implementation-detail probing.
- **Error path covered**: `try/except subprocess.TimeoutExpired` + `check=True`
  together handle hang and non-zero exit. Missing: explicit assertion that a
  non-zero child exit fails with a diagnostic message (relies on pytest's
  default `CalledProcessError` traceback). Minor — pytest output is adequate
  diagnostic.
- **TDD trail audit**: build report 2 captures RED output verbatim with the
  exact `/tmp/exists` leak payload. This is the single strongest piece of
  evidence that the test is genuinely observing the leak vector.

### Informational — M1 Follow-Up (Out of Scope)

Code-reviewer raised M1: `embedder cli doctor` and `embedder backfill`
documented in `skills/embedder/SKILL.md` + `download-model.sh` still fail
with `No module named embedder.__main__` post-fix because the package has
no `__main__.py` dispatcher. Slice-1 AC ("module `embedder._lib.bootstrap`
resolves") is satisfied — `bootstrap` is reachable as
`embedder._lib.bootstrap`. The `embedder cli doctor` / `embedder backfill`
forms require a separate fix (`__main__.py` dispatcher or doc retarget to
`embedder._lib.cli` / `embedder._lib.backfill`).

**This is NOT a coverage gap for this pipeline.** Slice-1 AC scope was
explicitly "module resolves." Flagging here only as an informational
handoff: the follow-up ticket should be opened before docs ship widely,
since `download-model.sh:57,59` are user-facing post-download output.

### Risk Assessment (Uncovered Paths)

| Risk | Severity | Mitigation |
|------|----------|------------|
| Future bootstrap test leaks without `patch.dict` wrap | LOW | Subprocess regression guard catches it |
| Leaking test added to a new file outside `tests/test_bootstrap.py` | LOW | Plan's "Watch → promote to class-level helper at third leak" covers promotion trigger |
| `embedder cli doctor` / `embedder backfill` invoked by user → `No module named embedder.__main__` (M1) | MEDIUM | Out of scope; must file follow-up ticket |
| `/project-setup` run from non-default project root → absolute `$HOME/.claude/skills` still resolves | LOW | Verified with `cd /tmp && PYTHONPATH=$HOME/.claude/skills python3 -m embedder._lib.bootstrap` → exit 0 |

### Next Phase Input

All ACs covered, no gaps. Advance to **Accept** phase (product-acceptance).
M1 follow-up is a separate ticket, not a gate on this pipeline.

---

## Round 2 (Slice 3) — M1 dispatcher

**Scope**: `skills/embedder/__main__.py` dispatcher (commit `a75f22a`, merged `5265d40`).

### AC Coverage Matrix

| AC | Evidence | Location | Status |
|----|----------|----------|--------|
| AC3.1 `cli doctor` does NOT raise `No module named embedder.__main__` | `test_cli_doctor_does_not_raise_module_not_found` asserts `_DISPATCHER_MISS` absent from combined stdout+stderr | `tests/test_embedder_cli_dispatcher.py:36-39` | COVERED |
| AC3.2 `backfill --help` does NOT raise `No module named embedder.__main__` | `test_backfill_help_does_not_raise_module_not_found` asserts `_DISPATCHER_MISS` absent | `tests/test_embedder_cli_dispatcher.py:43-46` | COVERED |
| AC3.3 Explicit module path (`python3 -m embedder._lib.bootstrap`) still resolves | Operational: re-ran `PYTHONPATH=.:skills python3 -m embedder._lib.bootstrap` post-merge → exit 0. Indirect: Slice 1 tests `test_bootstrap_integration.py` and siblings invoke bootstrap via explicit module paths on every suite run — they remain green (422 passed) | Operational + transitive | COVERED (indirect) |
| AC3.4 Shape limits | `__main__.py` = 19 lines (limit 50). `main()` body = 3 lines (limit 5). Verified via AST inspection. | `skills/embedder/__main__.py` | COVERED |
| AC3.5 No regression on Slices 1+2 | Full suite `python3 -m unittest discover -s tests`: 422 tests, 11 skipped, 0 failed, 3.866s. `test_bootstrap_settings_disk_invariant.py` (settings.json regression guard) still green. | full suite | COVERED |

### Verification Evidence (FRESH)

```
$ python3 -m unittest tests.test_embedder_cli_dispatcher -v
test_backfill_help_does_not_raise_module_not_found ... ok
test_cli_doctor_does_not_raise_module_not_found ... ok
Ran 2 tests in 0.089s — OK

$ python3 -m unittest discover -s tests
Ran 422 tests in 3.866s — OK (skipped=11)

$ wc -l skills/embedder/__main__.py tests/test_embedder_cli_dispatcher.py
      19 skills/embedder/__main__.py
      50 tests/test_embedder_cli_dispatcher.py

$ PYTHONPATH=.:skills python3 -m embedder._lib.bootstrap; echo $?
0
```

### Gap Analysis

- **Minor gap (non-blocking)**: AC3.3 has no dedicated automated regression test asserting explicit module paths still resolve after the dispatcher was added. Transitively covered by the existing Slice 1 bootstrap integration tests (which invoke `embedder._lib.bootstrap` directly and remain green). A dedicated one-line subprocess assertion would tighten the contract but is not required to gate this pipeline — the recurring suite already fails fast if the dispatcher ever intercepts explicit paths.
- **Test shape**: `test_embedder_cli_dispatcher.py` at 50 lines is exactly at the QA-relaxation ceiling (100) with room; no extraction needed.
- **Assertion quality**: Tests assert observable behavior (subprocess stdout/stderr content), not implementation details. No callability/typeof padding. Both tests would fail if the dispatcher regressed.

### Follow-Up (OUT OF SCOPE for Slice 3)

The build scratchpad (`software-engineer-build-slice3.md`, fragility note) flags a pre-existing bug in `skills/embedder/_lib/doctor.py`: unqualified `from _lib import embed_banner` causes `ModuleNotFoundError: No module named '_lib'` when `doctor` is invoked downstream of the dispatcher. This is **not a Slice 3 regression** — the dispatcher contract (AC3.1) only requires that `embedder.__main__` resolves, which it does. The downstream doctor failure pre-existed the dispatcher addition.

**Recommendation**: File a separate ticket to fix `_lib/doctor.py` import style (`from embedder._lib import embed_banner`). Not a gate on this pipeline.

### Risk Assessment (Uncovered Paths — Slice 3)

| Risk | Severity | Mitigation |
|------|----------|------------|
| Future dispatcher change intercepts explicit module paths | LOW | Slice 1 bootstrap integration tests fail fast; consider adding a direct subprocess assertion in a future hardening pass |
| Unknown subcommand falls through to `cli.main` (per dispatcher code) | LOW | Intentional fallback behavior matches existing `python3 -m embedder` invocation semantics; no AC requires stricter handling |
| Downstream `_lib/doctor.py` bug masks real doctor failures | MEDIUM | Out of scope — filed as follow-up |

### Verdict: COVERED

Slice 3 acceptance criteria are verified by 2 new tests + operational evidence + transitive coverage via the full suite. Shape limits honored. No regression on Slices 1+2. One minor parallel-AC gap flagged (AC3.3 dedicated regression test) as non-blocking improvement for a future hardening pass. Pre-existing `_lib/doctor.py` import bug called out as a separate follow-up, not a Slice 3 gate.

Advance to **Accept** phase.

---

## Round 3 (Slice 4) — M2 doctor `_lib` import fix

**Scope**: `skills/embedder/_lib/doctor.py` sys.path-prepend + `from _lib import embed_banner` (commit `99e4698`, merged `4540595`).

### AC Coverage Matrix

| AC | Evidence | Location | Status |
|----|----------|----------|--------|
| AC4.1 `PYTHONPATH=skills python3 -m embedder cli doctor` runs without `ModuleNotFoundError: No module named '_lib'` | `DoctorImportsLibAsQualified::test_cli_doctor_does_not_raise_lib_not_found` asserts `_LIB_MISS` absent from combined stdout+stderr; operational re-run emits full 6-field doctor report + `verdict: OK` | `tests/test_embedder_cli_dispatcher.py:50-54` + operational | COVERED |

### Fresh Verification Evidence

```
$ cd ~/.claude && PYTHONPATH=skills python3 -m embedder cli doctor; echo exit:$?
ORT_DYLIB_PATH: /opt/homebrew/lib/libonnxruntime.dylib
BGE_MODEL_PATH: <unset>
last_error: ...
last_success_at: 2026-04-20T21:18:04.357284+00:00
unembedded_count: 0
embed: on
verdict: OK
exit:0

$ cd /tmp && PYTHONPATH=$HOME/.claude/skills python3 -m embedder cli doctor; echo exit:$?
(same 6-field report + verdict: OK)
exit:0

$ cd ~/.claude && PYTHONPATH=skills python3 -m embedder backfill --help; echo exit:$?
usage: python3.14 -m embedder [-h] --db DB
exit:0

$ PYTHONPATH=skills python3 -m unittest tests.test_embedder_cli_dispatcher -v
test_backfill_help_does_not_raise_module_not_found ... ok
test_cli_doctor_does_not_raise_module_not_found ... ok
test_cli_doctor_does_not_raise_lib_not_found ... ok
Ran 3 tests in 0.327s — OK

$ PYTHONPATH=skills python3 -m unittest discover -s tests
Ran 423 tests in 4.044s — OK (skipped=11)

$ wc -l skills/embedder/_lib/doctor.py tests/test_embedder_cli_dispatcher.py
      48 skills/embedder/_lib/doctor.py
      58 tests/test_embedder_cli_dispatcher.py
```

Baseline was 422 after Slice 3; Slice 4 adds 1 new regression test → 423. Zero failures, zero regressions.

### Falsifiability Audit (AC4.1 regression test)

1. **Well-named?** YES. `DoctorImportsLibAsQualified::test_cli_doctor_does_not_raise_lib_not_found` describes the invariant exactly. The class name also encodes the design intent (doctor must resolve `_lib` even across the hyphenated skill boundary).
2. **Observed RED?** YES (transitively). Pre-fix, running the same `[sys.executable, "-m", "embedder", "cli", "doctor"]` with `PYTHONPATH={REPO_ROOT}:{REPO_ROOT}/skills` surfaced `ModuleNotFoundError: No module named '_lib'` — that was the exact symptom documented in the Slice-3 scratchpad and the commit message for `99e4698`. The assertion `assertNotIn("No module named '_lib'", combined)` trips on that payload.
3. **Exercises the right boundary?** YES. The subprocess is a true separate Python process with only `PYTHONPATH={REPO_ROOT}:{REPO_ROOT}/skills` on sys.path — mirroring the documented invocation environment. In-process tests cannot catch this because the test harness has already prepended `skills/reindex-memory/` to sys.path, masking the bug. Subprocess isolation is essential.
4. **Shares harness with Slice 3?** YES (intentional). Reuses `_run`, `_env`, `_KWARGS`, `REPO_ROOT`. No duplication. New constant `_LIB_MISS` is local to this concern. Third test class keeps single-responsibility — each class asserts one distinct failure mode (dispatcher miss, dispatcher routing backfill, doctor's `_lib` import).
5. **check=True + timeout?** The Slice-4 test does NOT set `check=True` (intentional — `cli doctor` returns non-zero verdicts on degraded systems, which is normal doctor behavior, not a test failure). It still uses `timeout=30` via `_KWARGS` → timeout surfaces as `AssertionError` via the harness's `except subprocess.TimeoutExpired`. Correct choice — doctor's job is to report degraded state without raising.

**Verdict on regression test**: falsifiable, well-scoped, captures the exact import-failure class. Meets QA standards.

### Gap Analysis

**Requested checks**:

1. **Does the test cover AC4.1?** YES. Direct subprocess assertion against `_LIB_MISS` + operational re-run shows full doctor output.
2. **What about `cli doctor` from cwd other than `~/.claude`?** COVERED operationally. Re-ran `cd /tmp && PYTHONPATH=$HOME/.claude/skills python3 -m embedder cli doctor` → exit 0, full 6-field report. The sys.path prepend in `doctor.py:13-16` uses `Path(__file__).resolve().parents[3] / "skills" / "reindex-memory"` — cwd-independent by construction. The test itself uses `cwd=str(REPO_ROOT)` but the fix's correctness is cwd-invariant (no `Path.cwd()` reads in the resolution logic). **Minor gap (non-blocking)**: no dedicated automated regression test for alternate-cwd invocation; transitively covered by the resolution design using `__file__`.
3. **Does `backfill` also depend on the `_lib` import chain?** NO. `skills/embedder/backfill.py:13` uses `from embedder._lib import backfill_batch` — fully qualified, no `_lib` bare import. Backfill does not reach into `reindex-memory/_lib/`. Fresh verification: `backfill --help` exit 0.
4. **Grep for other `from _lib import X` in `skills/embedder/`**: only `doctor.py:17` (the fixed occurrence). Elsewhere in the repo: `recall/_lib/api_args.py:9` (self-protected via its own sys.path prepend at lines 5-9 — the precedent Slice 4 mirrors), and every `reindex-memory/_lib/*.py` match (self-resolving because `_lib` is beside them in that skill's own `_lib/` directory). **No other embedder-side occurrence; Slice 4 closed the only hole.**

### Coverage Assessment

**Behavior under test**: `python3 -m embedder cli doctor` must resolve `embed_banner` when only `skills/` is on `PYTHONPATH` (the documented user-facing invocation environment post-Slice-3).

**Coverage tiers**:
- **Unit boundary**: subprocess regression test (`DoctorImportsLibAsQualified`) — falsifiable, cwd-controlled, PYTHONPATH-controlled.
- **Integration**: doctor's sys.path prepend is exercised by the test's full stdout/stderr capture — if the prepend were removed, the assertion would trip on `_LIB_MISS`.
- **Operational**: three fresh smoke re-runs (repo-root cwd, `/tmp` cwd, backfill --help) all green.
- **Full suite**: 423 tests, 11 skipped, 0 failed.

**Shape verification**:
- `skills/embedder/_lib/doctor.py` = 48 lines (within 50-line limit; +10 from baseline for the sys.path guard + comment explaining the hyphenated-skill idiom).
- `tests/test_embedder_cli_dispatcher.py` = 58 lines (well under QA-relaxation 100-line ceiling).
- `_render()` remains 5 lines; `_value()` is 3 lines — no shape regressions from the change.

### Edge Cases — Covered

- **Hyphenated skill boundary**: fix exists precisely to cross this boundary (`reindex-memory` cannot be imported as a package); sys.path prepend at module load is the repo idiom.
- **Idempotent sys.path insert**: `if _REINDEX not in sys.path:` prevents duplicate entries on repeat imports.
- **Combined stdout+stderr assertion**: `_LIB_MISS` would appear on stderr (as Python's default traceback channel); the test reads both streams.
- **Alternate cwd**: `Path(__file__).resolve().parents[3]` makes resolution cwd-independent; operationally verified from `/tmp`.

### Edge Cases — NOT Covered (with justification)

- **Dedicated alternate-cwd automated regression test**: no. Transitively covered by the `__file__`-rooted resolution design; operationally verified. Adding a second subprocess test that only changes `cwd` would be coverage theatre unless paired with a design change that introduces cwd-sensitivity.
- **`reindex-memory` directory renamed or removed**: out of scope. If `skills/reindex-memory/` disappears, `doctor.py`'s sys.path prepend becomes a silent no-op and the `from _lib import embed_banner` raises — but that is a cross-skill contract change orthogonal to this slice. No AC requires guarding it here.
- **Running from a Python where `sys.path` is pre-mutated** (e.g., a wrapper that already inserted `skills/reindex-memory/`): the `if _REINDEX not in sys.path:` guard is idempotent; benign.

### Integration Tests Written
None. The regression test was added in the build phase (`99e4698`). QA Round 3 is read-only analysis + fresh verification.

### E2E Flows (Jest / Maestro)
N/A — Python CLI tooling. No mobile surface. E2E trigger matrix does not apply.

### Test Quality Observations

- **No padding**: assertion checks observable subprocess output, not import-table state or callability.
- **Harness reuse**: Slice 4 extends Slice 3's `_run`/`_env`/`_KWARGS` — DRY, single test file houses three related regression guards against `python3 -m embedder` module-load failures.
- **Error path implicit**: `_LIB_MISS` is an error-path signature; the test's absence assertion IS the error-path coverage. A passing doctor that prints `ModuleNotFoundError: No module named '_lib'` nowhere proves the fix resolves cleanly.
- **Pattern reusability**: the scratchpad note (subprocess + PYTHONPATH + `assertNotIn("No module named 'X'", ...)`) is now applied three times in one file. Clean regression-guard template for future module-resolution fixes.

### Risk Assessment (Uncovered Paths — Slice 4)

| Risk | Severity | Mitigation |
|------|----------|------------|
| `reindex-memory` renamed without updating doctor's sys.path prepend | LOW | Full test suite exercises `doctor.report()` indirectly via doctor-related tests; grep for `reindex-memory` would surface all dependents at rename time |
| New `from _lib import X` added elsewhere in `skills/embedder/` without the sys.path prepend | LOW | Grep invariant currently clean; easy to re-run. No dedicated automated guard, but the recurring full-suite + subprocess smoke would surface a regression |
| `doctor.py` line count drift above 50 as more fields are added | LOW | Currently 48/50; next addition will trigger refactor |
| `sys.path` contamination in the parent process due to module load order | LOW | The prepend is guarded by `if _REINDEX not in sys.path:`; idempotent |

### Verdict: COVERED

AC4.1 is verified by a dedicated subprocess regression test + two operational smoke checks (repo-root cwd, `/tmp` cwd) + `backfill --help` confirmation + full-suite green (423 passed, 11 skipped, 0 failed — baseline 422 + 1 new test). Grep confirmed `doctor.py:17` was the only offender in `skills/embedder/`. Shape limits honored. No regression on Slices 1-3. Minor non-blocking observation: no dedicated alternate-cwd automated test (transitively covered by the `__file__`-rooted resolution design).

Advance to **Accept** phase.
