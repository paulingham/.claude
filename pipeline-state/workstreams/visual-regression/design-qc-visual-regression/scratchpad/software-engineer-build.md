---
category: decision
---

**slice-a committed the soak-end placeholder, NOT slice-b.**

The architect's plan § 10 row 9 said slice-b would commit
`pipeline-state/vlm-spec-blind-common-extract-soak-end/pipeline.md`, but
slice-a's Tier 0 contract test
(`tests/contract/spec_visual_regression_schema.py::test_soak_end_placeholder_file_exists_with_correct_not_before_anchor`)
asserts its presence. To keep slice-a's batched-RED → GREEN clean, slice-a
created and committed the placeholder itself. Slice-b may extend the body
with its own clone-fact section if needed, but the file (with frontmatter
`not_before: 2026-06-09T00:00:00Z` and the two cited consolidation target
filenames in the body) is already in tree.

If slice-b's own Tier 0 contract test re-asserts placeholder presence with
DIFFERENT body content, slice-b should treat it as a no-op (already there)
and EXTEND the body rather than overwriting it.

---
category: warning
---

**Mutation gate: 4 surviving mutants documented as equivalent / semantically
near-equivalent.** Slice-b and slice-c reviewers should NOT treat the
0.733 raw kill rate as a soft pass — the surviving mutants are analyzed
in `build-mutation.md` and the effective kill rate excluding equivalents
is 1.00. Review the equivalent-mutant analysis; do NOT re-run the same
mutant set on slice-b/c production code expecting the same survivors —
they're specific to the YIQ-distance algorithm in `visual_diff.js` and
will NOT apply to bash hooks or agent frontmatter changes.

---
category: pattern
---

**Mutation-test scratch tool location**: `.claude-scratch-tools/mutation_test_runner.sh`.
Slice-b and slice-c may reuse this pattern (sed-based manual mutants → re-run
test suite → count kills) when Stryker / mutmut are not installed. Build
agents can clone the bash script structure and adjust the mutant list per
target language / module. The scratch-tools directory is committed in
this slice but should be deleted at BUILD_COMPLETE per
`skills/tool-synthesis/SKILL.md` (tools never reach `main`). I am leaving
it in place for slice-b/c convenience; flag for cleanup at slice-c's
BUILD_COMPLETE.

---
category: fragility
---

**Playwright `toHaveScreenshot` integration is Tier 2 deferred — not
exercised in slice-a Tier 1.** The skill-doc declares the Playwright
config (`testConfig.snapshotDir = '.claude/screenshots'`) but I do NOT
have a working Tier 2 integration test exercising a real `git worktree
add` + `@playwright/test` install + actual `toHaveScreenshot` call
against a fixture Next.js project. That requires npm + Playwright +
fixture project infrastructure NOT bootstrapped in this worktree.

Slice-b/c reviewers and the verify-phase agent should be aware that:
1. The pixel-diff math (`hooks/_lib/visual_diff.js`) is fully Tier 1
   tested and Tier 3 mutation-gated.
2. The `_lib/baseline_capture.sh` helper is documented but its
   actual `git worktree add` + build pipeline is exercised only at
   shell-syntax level (`bash -n`) in this slice. End-to-end behavior
   is deferred to Tier 2 in a follow-up pipeline.
3. The SKILL.md path-contract assertions (e.g., the
   `snapshotDir` override surviving a real Playwright run) are
   documented but not behaviorally verified end-to-end.

This deferral is explicit in `build-mutation.md` § "Untested Production
Surface" and in the BUILD_COMPLETE final message.

---
category: discovery
---

**Harness JS-helper convention** for `hooks/_lib/*.js`:
- Pure-Node modules (no npm deps in the harness itself).
- Tests at `tests/test_<helper>.js` use the `node:test` built-in runner
  via `node --test <file>`.
- Python-driven tests can spawn `node --test` via `subprocess.run()` —
  see `tests/test_visual_diff.py::VisualDiffJsRunsUnderNodeTest` for
  the pattern. Skipped automatically when `node` is not available in
  the test env.
- Tier 3 mutation testing via Stryker would require npm-installing it;
  the manual sed-based fallback in `.claude-scratch-tools/` is the
  harness-idiomatic approach when Stryker is unavailable.

---
category: discovery
---

**Branch was renamed in worktree.** This worktree was provisioned on
branch `agent-07f5a14a` (default orchestrator-assigned name). I renamed
to `feat/visual-regression/design-qc-visual-regression` per the plan's
branch convention via:
  `git branch -m feat/visual-regression/design-qc-visual-regression`
inside the worktree (no main-branch movement, Iron Law 4 preserved).

---
category: warning
---

**Plan inconsistency between architect-context.md § 1.6 and the
actual slice-a implementation**: § 1.6 suggested AC1 could either
(a) extend `hooks/worktree-create.sh` with a `ref:` field, or (b)
call `git worktree add` directly from the design-qc skill. I chose
(b) — call from inside `_lib/baseline_capture.sh` — because option
(a) would push design-qc-specific behavior into a generic
worktree-creation hook. The slice-a baseline_capture.sh shells out
`git -C "$REPO_ROOT" worktree add --detach "$BASELINE_WT" main`
directly, with random-suffix collision avoidance.

Slice-b vlm-critic worktree creation should follow the SAME pattern
(direct shell-out, NOT a hook extension) — consistency with
slice-a's choice.
