# visual-regression-next fixture

Minimal fixture project consumed by
`tests/integration/test_design_qc_visual_regression_e2e.py` (Tier 2
integration test for slice-a-pixel-diff-pump; plan § 6 row Tier 2 slice-a).

## Shape

| File | Role |
|---|---|
| `package.json` | Declares `@playwright/test` devDep; `npm install` + `npx playwright install chromium` set up the runtime. |
| `server.js` | Static HTTP server on `PORT` (default 4321) that serves a deterministic page. Used as the dev-server shim so the integration test does not have to bootstrap a real Next.js build. |
| `app/page.tsx`, `app/layout.tsx`, `next.config.js` | Next.js app-router reference shape — documented for the plan's "fixture Next.js project" wording. Not executed in the integration test runtime (server.js serves the equivalent HTML directly to keep install cost bounded). |
| `playwright-driver.js` | Step 6 Playwright pump shim. Drives `chromium.launch` + `page.screenshot` against the running fixture server at desktop + mobile viewports, writing PNGs under `$PW_OUTPUT_DIR`. |

## How the integration test uses this

1. Copy the fixture into a temp dir.
2. `git init` and commit (so `git worktree add main` works inside the copy).
3. `npm install` + `npx playwright install chromium`.
4. Invoke `bash hooks/_lib/baseline_capture.sh` to exercise the Step 5.5
   worktree-and-build dance.
5. Drive `playwright-driver.js` twice — once for the baseline PNGs (under
   `pipeline-state/test-vr/visual-baselines/`), once for the current PNGs
   (under `.claude/screenshots/`).
6. Run `hooks/_lib/visual_diff.js` against each (baseline, current) pair to
   compute `pixel_diff_ratio`; write `pipeline-state/test-vr/design-qc/index.json`.
7. Assert the four contract artifacts (a-d) per
   `tests/integration/test_design_qc_visual_regression_e2e.py` docstring.

## Skip conditions

The integration test skips when:

- `CLAUDE_SKIP_HEAVY_INTEGRATION=1` is set (CI escape hatch — Playwright pulls
  ~200 MB of browser engines).
- `node` or `npm` is not on `PATH` (mirrors the
  `tests/test_visual_diff.py::_which_node` skip pattern).
- The fixture dir is absent (defensive guard).
