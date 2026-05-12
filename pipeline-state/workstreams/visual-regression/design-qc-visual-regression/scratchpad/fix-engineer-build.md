---
category: decision
---

**Stryker decision: Option B (committed manual runner under `tests/mutation/`).**

Reasoning: the harness has no top-level `package.json` (verified by
`ls package.json` returning ENOENT at the worktree root and the
`.gitignore` shape that tracks everything explicitly under `!tests/**` etc.
without any node_modules / npm-package surface). Installing Stryker would
force a top-level package.json, a node_modules/ commitment, and ~80 MB of
JS mutation-tester scaffolding into a tree designed as bash + Python + plain
JS. `skills/verify/SKILL.md` § Manual fallback explicitly allows a sed-based
runner provided it is reproducible.

The runner was MOVED from `.claude-scratch-tools/` (which is gitignored per
`.gitignore` line 84) to `tests/mutation/` (tracked under `!tests/**`).
The previous location made the kill rate non-reproducible for downstream
reviewers — they could not re-run the same mutation set against the same
source. The new location is committed to the tree and re-runnable
verbatim.

The `.claude-scratch-tools/` path remains gitignored harness-wide;
slice-b / slice-c authors should publish reproducible mutation runners
under `tests/mutation/<module>_runner.sh` if they want their kill rate
verified independently. The scratchpad pattern from
software-engineer-build.md still holds for ephemeral tools that genuinely
do not need to ship.

---
category: decision
---

**M8 finding: existing analysis is CORRECT. Test docstring was wrong.**

The round-1 code-reviewer flagged a contradiction between build-mutation.md
(M8 = survived, equivalent) and the `partial-alpha pixels correctly` test
docstring (claiming to discriminate M8). I empirically re-ran the
contradiction:

1. Applied the M8 sed `255 + → 255 -` to `hooks/_lib/visual_diff.js`.
2. Ran `node --test tests/test_visual_diff.js`.
3. Result: ALL 21 JS tests pass, including `partial-alpha pixels correctly`.

Per-pair empirical check:
- opaque-black vs half-transp-black, 4×4, threshold 0.02:
  Correct ratio: 1.0  |  M8 mutant ratio: 1.0

Both formulas push the YIQ distance above the 3521 threshold for this
input. The test's `> 0.5` assertion is satisfied by both. M8 IS effectively
equivalent under the integer pixel input space the test suite exercises.

The fix was therefore to update the test docstring (and point to the
build-mutation.md M8 rationale) rather than reclassify M8. The
build-mutation.md analysis is unchanged; an addendum section documents the
re-verification.

---
category: fragility
---

**Heavy Tier 2 install cost (~200 MB Playwright browser engines).**

The new `tests/integration/test_design_qc_visual_regression_e2e.py`
installs `@playwright/test` + chromium engine the first time it runs in a
fresh environment. Cold-cache cost: ~30-60s for npm install +
~30-60s for `playwright install chromium`. Warm cache: ~5-10s total.

For CI environments where this is too expensive, the test honours
`CLAUDE_SKIP_HEAVY_INTEGRATION=1` and skips cleanly via setUpClass. It
also skips if `node` or `npm` is not on `PATH` (mirrors the
`tests/test_visual_diff.py::_which_node` pattern at lines 262-277).

Slice-b/c reviewers running this test for the first time should expect
the install delay; subsequent runs will be fast because npm and
Playwright cache globally.

---
category: warning
---

**Fixture is NOT a real Next.js runtime — it ships the Next.js
file-shape (app/page.tsx, app/layout.tsx, next.config.js) and a static
`server.js` that serves equivalent HTML.**

Rationale: bootstrapping `next dev` would require a multi-minute first
build, a real TypeScript compile, and React reconciliation — none of
which the test contract requires (the test asserts on artifact paths,
not framework behaviour). The README at
`tests/fixtures/visual-regression-next/README.md` documents this
explicitly.

If a future slice needs to exercise actual Next.js build pipeline
behaviour (e.g. AC-level test of the SSR rendering path), the fixture
will need to be upgraded to a real `next dev` server. Today's contract
(plan § 6 row Tier 2 slice-a) does not require this.

---
category: pattern
---

**Reproducible mutation runner template** for future slice-b / slice-c
mutation gates: copy `tests/mutation/visual_diff_mutation_runner.sh` and
adjust:

1. `TARGET` and `TEST_FILE` paths.
2. The `_apply_<ID>` perl functions (one per mutant).
3. The `MUTANTS=(...)` registry and `EQUIVALENT_MUTANTS=(...)` set.

The runner enforces:
- Sha-sum check before/after each `_apply_<ID>` — refuses to count a
  no-op apply as a kill.
- Documented equivalents excluded from the unexpected-survivor gate.
- Separate raw vs effective kill rates, both reported.
- Trap-based restore of the target file on any exit.

Apply-failure detection is the most important guard — a sed/perl
expression that silently matches nothing would otherwise be counted as
"killed" (test still passes because source is unchanged).
