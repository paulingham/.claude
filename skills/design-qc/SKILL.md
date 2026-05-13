---
name: "design-qc"
description: "Use when user wants to Visual QA with full DevOps lifecycle enforcement. Installs deps, builds, starts dev server, captures screenshots at desktop and mobile viewports, stops server. Mandatory for all frontend changes. Fails loudly at every step."
context: fork
agent: qa-engineer
---

# Design QC

## What This Skill Does

Proves frontend code renders correctly by running the full DevOps lifecycle: install dependencies, build the project, start the dev server, capture screenshots, and stop the server. This is not optional — if frontend files changed, visual proof is required.

**Principle:** If the pipeline produces frontend code, the pipeline MUST prove it renders correctly. Not "tests pass" — visually verified against a running application.

## When to Invoke

- MANDATORY when changed files include `.tsx`, `.jsx`, `.vue`, `.svelte`, `.html`, or CSS files
- Invoked by the pipeline as part of the Final Gate (parallel with verify + qa + accept)
- If this skill returns `CAPTURE_FAILED`, the pipeline BLOCKS

## Process

### Step 1: Read Project Contract

Read the project's `.claude/CLAUDE.md` and extract the Dev Server section:

```
## Dev Server
- Command: {dev command}
- Port: {port number}
- Health check: {health check URL}
- Build command: {build command}
```

**If these fields are missing** → verdict `CAPTURE_FAILED`:
```
CAPTURE_FAILED: Project CLAUDE.md missing '## Dev Server' section.
Required fields: Command, Port, Health check, Build command.
Run /project-setup to detect and add dev server configuration.
```

Do NOT probe random ports or guess commands. The contract is the source of truth.

### Step 2: Install Dependencies

```bash
npm install  # or yarn/pnpm per project convention
```

If the project does not have `playwright` in devDependencies (Playwright is now the
canonical browser driver — AC2 port from Puppeteer):
```bash
npm install --save-dev @playwright/test
```

**If install fails** → verdict `CAPTURE_FAILED` with the npm error output.

### Step 3: Build

```bash
{build command from CLAUDE.md}  # e.g., npm run build
```

The build MUST succeed. This catches:
- TypeScript compilation errors that `tsc --noEmit` misses (bundler-specific issues)
- Missing imports that tests mock away
- Asset pipeline failures

**If build fails** → verdict `CAPTURE_FAILED` with build error output.

### Step 4: Start Dev Server

```bash
{dev command from CLAUDE.md} &  # e.g., npm run dev &
DEV_PID=$!
```

Poll health check URL every 2 seconds, max 60 seconds:
```bash
for i in $(seq 1 30); do
    if curl -s -o /dev/null -w "%{http_code}" "{health check URL}" | grep -q "200"; then
        echo "Server ready on port {port}"
        break
    fi
    sleep 2
done
```

**If server doesn't start within 60s** → `kill $DEV_PID`, verdict `CAPTURE_FAILED` with "Dev server failed to start. Check {dev command} and port {port}."

### Step 5: Detect Routes

For file-based routing frameworks:
- **Next.js**: Scan `app/` or `pages/` directory for page files
- **Vite/React Router**: Read router config, extract route paths
- **Expo Router**: Scan `app/` directory
- **Astro**: Scan `src/pages/` directory
- **Vue Router**: Read router config

Cross-reference with `git diff --name-only` to limit to routes affected by the current change. Always include the root route `/`.

### Step 5.5: Capture Baseline (Visual Regression Producer — AC1)

Before capturing screenshots on the current branch, capture **baselines** from the
project's `main` HEAD so pixel-diff in Step 6 has something to compare against.

The helper `hooks/_lib/baseline_capture.sh` performs:

1. `git -C "$REPO_ROOT" worktree add --detach "$BASELINE_WT" main` (Iron Law 4 —
   never bare `git checkout`).
2. Run the project's build command inside the baseline worktree.
3. Capture screenshots through the same Playwright pump as Step 6, routed to
   `pipeline-state/{task-id}/visual-baselines/{slug}-{viewport}.png`.
4. Tear down the baseline worktree (`git worktree remove --force`).

**Failure-mode-1 (baseline build fails on main HEAD)**: ALL routes are treated as
auto-bless (new-route path); scratchpad warning `category: warning` with literal
token `baseline-build-failed` is appended to
`pipeline-state/{task-id}/scratchpad/design-qc-build.md`; index.json
`visual_regression.captured` is set to `false`. design-qc still emits
`SCREENSHOTS_CAPTURED` — capture failure does NOT change the design-qc verdict.

**AC6 — new-route auto-bless**: if a route is present on the current branch but
absent on main HEAD (e.g. a newly-added page), the helper captures the current
branch screenshot AS its own baseline and appends a scratchpad warning
`category: warning` with the literal token `auto-blessed-baseline` naming the
route. This is the documented onboarding semantic for new pages.

**AC8 / failure-mode-8 (worktree collision)**: the baseline worktree path is
suffixed with a process-id + timestamp to avoid colliding with concurrent
pipelines. The teardown runs even if the build fails.

### Step 6: Capture Screenshots (Playwright — AC2)

For each detected route, capture at two viewports:

| Viewport | Width | Height | Name |
|----------|-------|--------|------|
| Desktop | 1440 | 900 | `{route}-desktop-{section}.jpg` |
| Mobile | 375 | 812 | `{route}-mobile-{section}.jpg` |

Capture method:
1. Navigate to route URL (`http://localhost:{port}{route}`)
2. Wait for network idle (no pending requests for 500ms)
3. Scroll through page, capture viewport-height JPEG sections
4. JPEG quality: 80 (~2500 tokens per screenshot)
5. Max 8 sections per page
6. Save to `.claude/screenshots/`

Use Playwright via `@playwright/test`:

```javascript
// Playwright Test config — explicitly override the default snapshot directory
// `__screenshots__/` to `.claude/screenshots/` so the existing consumer-project
// path contract is preserved across the Puppeteer→Playwright port (SE-5 /
// failure-mode-9).
const testConfig = {
  snapshotDir: '.claude/screenshots',
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.02,  // AC7 default; per-route override via project CLAUDE.md
    },
  },
};

// Per-route capture + pixel-diff (AC2):
const { chromium } = require('@playwright/test');
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width, height } });
const page = await context.newPage();
await page.goto(url, { waitUntil: 'networkidle' });

// Pixel-diff against the baseline captured in Step 5.5. Snapshots are written
// to `.claude/screenshots/{slug}-{viewport}.png` (NOT Playwright's default
// `__screenshots__/` — config override above).
const result = await expect(page).toHaveScreenshot(
  `${slug}-${viewport}.png`,
  { maxDiffPixelRatio: routeThreshold },
);

await context.close();
await browser.close();
```

The measured `pixel_diff_ratio` for each route is computed via
`hooks/_lib/visual_diff.js` (typed signature
`computePixelDiffRatio(baseline: Buffer, current: Buffer, threshold: number,
dimensions): number`) and written into the index.json `visual_regression` block
described below.

**Per-route threshold (AC7)**: the per-route threshold is consulted FIRST (from
the project CLAUDE.md `## Visual Regression` `per_route` map), with the
`default_max_diff_pixel_ratio` (default `0.02`) as fallback. Per-route override
of `0.05` with a measured diff of `0.04` does NOT trip the global 0.02
threshold.

**Failure-mode-2 (Playwright returns null diff — internal error)**: the per-route
call is wrapped in try/except; on null result the route's `pixel_diff_ratio` is
set to `1.0` (worst-case sentinel) and a scratchpad `category: fragility` entry
is appended with literal token `playwright-null-diff-{route}`. The pipeline
continues with remaining routes — capture failure on one route does not abort
the whole run.

**Failure-mode-9 (snapshot output dir mismatch)**: Playwright's default snapshot
output is `__screenshots__/`, which would break consumer-project tests that
assert against the existing `.claude/screenshots/` contract. The
`testConfig.snapshotDir = '.claude/screenshots'` override is load-bearing — if
removed, consumer projects will see "snapshot not found at __screenshots__/..."
errors. Sanity-check via Tier 2 integration test.

### Step 6.25: A11y Tree Capture (Dual-Output)

After Step 6 screenshots, while the dev server is still running and Playwright is still in-process, capture an accessibility-tree snapshot per (route, viewport). The output is owned by `patch-critic` (machine-checkable rubric § 5). Product-reviewer continues to consume only the screenshots — see `agents/product-reviewer.md`.

**Index file** (canonical artifact for downstream consumers):
- Path: `pipeline-state/{task-id}/design-qc/index.json`
- Schema: `schema_version: 2` (bumped 1 → 2 in this pipeline to add the
  `visual_regression` block; one-shot bump, no DUAL_PATH soak — index.json is
  pipeline-scoped state deleted at Reflect step 6d).
- Top-level shape: `{schema_version: 2, task_id, captured_at, build_status,
  server_started, routes: [...], a11y_global: {...}, visual_regression: {...}}`
- Per-route entry: `{route, screenshots: [...], a11y: {captured, capture_path?,
  reason?, snapshots: [{viewport, path}]}, visual_regression: {pixel_diff_ratio,
  baseline_path, current_path}}`
- Per-snapshot file: `pipeline-state/{task-id}/design-qc/a11y/{route-slug}-{viewport}.json` with `schema_version: 1` and a normalised tree shape

**Visual regression block** (NEW in schema_version 2):

```json
{
  "visual_regression": {
    "captured": true,
    "baselines_dir": "pipeline-state/{task-id}/visual-baselines",
    "default_max_diff_pixel_ratio": 0.02
  },
  "routes": [
    {
      "route": "/dashboard",
      "visual_regression": {
        "pixel_diff_ratio": 0.0123,
        "baseline_path": "pipeline-state/{task-id}/visual-baselines/dashboard-desktop.png",
        "current_path": ".claude/screenshots/dashboard-desktop.png"
      }
    }
  ]
}
```

Per-route `pixel_diff_ratio` is a float in `[0.0, 1.0]` (`0.0` = identical,
`1.0` = maximally different). When Playwright internal error produces a null
result, `pixel_diff_ratio` is set to `1.0` (worst-case sentinel — see
failure-mode-2 / `playwright-null-diff-{route}` scratchpad token).

**Capture strategy** (probe → fallback):

```
Probe Playwright MCP (one inert call, 2s timeout):
  ok        -> use MCP for the rest of this design-qc run; capture_path = "mcp"
  error     -> fall back to library API (page.accessibility.snapshot())
  timeout   -> fall back to library API
For each captured (route, viewport):
  Normalise the result via hooks/_lib/a11y_normalize.js
  Write to pipeline-state/{task-id}/design-qc/a11y/{slug}-{viewport}.json
```

**Failure handling:**

| Condition | a11y_global | Per-route entry | Scratchpad warning |
|-----------|-------------|------------------|--------------------|
| MCP probe + library both fail | `{captured: false, reason: "mcp-unavailable", capture_path: null}` | `snapshots: []` | Yes — category `warning`, body contains literal token `mcp-unavailable` |
| Per-route capture errored (other routes ok) | `{captured: true, capture_path: ...}` | `{captured: false, reason: "capture-error", error_snippet: <first 200 chars>}` | No — partial-capture is normal |
| Project CLAUDE.md `## Dev Server` declares `target: native` | `{captured: false, reason: "non-web-target", capture_path: null}` | omitted | No |

**Dependency-injected probe** (`hooks/_lib/a11y_probe.js`):
- `probe_mcp_availability(invoker, timeout_ms = 2000)` accepts an injected callable. Production binds `invoker` to the active MCP client's send method; tests substitute success/timeout/error stubs. No real MCP needed for unit tests.

**Adapter byte-equivalence**:
- `normalize_mcp_yaml(yamlStr, viewport, route, captured_at)` and `normalize_library_json(node, viewport, route, captured_at)` produce byte-equal JSON (sorted keys, identical null-fields) for the same DOM. This is a contract test (AC15) — adapter drift fails CI.

**SKIP warning (when capture unavailable)** — written to `pipeline-state/{task-id}/scratchpad/design-qc-build.md`:

```
---
category: warning
---

A11y capture unavailable: mcp-unavailable.
```

**Iron law for this step**: capture failure does NOT change the design-qc verdict. SCREENSHOTS_CAPTURED still emits. The verdict surface for design-qc is unchanged from Slice 1; capture state is communicated via the index file alone.

### Step 6.5: Automated Design Evaluation

While the browser is still open, evaluate each captured page programmatically:

**1. Contrast Check**
```javascript
// Extract all text elements and their computed background colors
const elements = await page.$$eval('*', els => els.map(el => {
  const style = getComputedStyle(el);
  return { text: el.textContent?.trim(), color: style.color, bg: style.backgroundColor, fontSize: parseFloat(style.fontSize) };
}).filter(e => e.text));
// Calculate WCAG contrast ratio: (L1 + 0.05) / (L2 + 0.05)
// Flag any text below 4.5:1 (normal) or 3:1 (large text >= 18px)
```

**2. Typography Hierarchy**
- Extract all `font-size` values on the page
- Verify they match the type scale from `tokens.css` (within ±2px tolerance)
- Check heading hierarchy: h1 > h2 > h3, no skips
- Flag any font-size not in the design token scale

**3. Spacing Rhythm**
- Sample `margin` and `padding` values from major layout elements
- Check against 4px base grid (values should be multiples of 4)
- Flag off-grid spacing values

**4. Token Coverage**
- Extract computed colors from all elements
- Check against defined CSS custom properties in the document
- Flag any color that doesn't match a token value (hardcoded hex/rgb)
- Output: token coverage percentage

**5. Visual Weight Balance**
- Check that no single viewport quadrant contains >60% of interactive elements
- Verify primary CTA is the most visually prominent button (largest or highest contrast)
- Check for competing visual weights (multiple equally prominent CTAs)

Output these results as structured data for the report.

### Step 7: Stop Server + Cleanup

```bash
kill $DEV_PID 2>/dev/null
# Also kill any child processes (dev servers often fork)
pkill -P $DEV_PID 2>/dev/null
```

Screenshots persist in `.claude/screenshots/` until the pipeline completes. The orchestrator cleans them up after Ship phase.

### Step 8: Produce Report

```markdown
## Design QC Report

### Build: PASS / FAIL
{build output summary}

### Server: STARTED on port {port} / FAILED
{startup details}

### Screenshots Captured
| Route | Desktop | Mobile | Sections |
|-------|---------|--------|----------|
| / | desktop-1..3.jpg | mobile-1..4.jpg | 3 / 4 |
| /dashboard | desktop-1..2.jpg | mobile-1..3.jpg | 2 / 3 |

### Screenshot Paths
{list of all .jpg files for product-reviewer}

### Design Evaluation
| Check | Score | Details |
|-------|-------|---------|
| Contrast | PASS/WARN/FAIL | N elements checked, M failures |
| Typography | N% | N off-scale sizes found |
| Spacing | N% | N off-grid values found |
| Token Coverage | N% | N hardcoded colors found |
| Visual Balance | PASS/WARN | CTA prominence assessment |

### Actionable Findings
1. {specific element} has contrast ratio {N}:1 (needs 4.5:1). Fix: {suggestion}
2. {element} uses font-size {N}px — nearest token: {token name} ({N}px)

### Verdict: SCREENSHOTS_CAPTURED / CAPTURE_FAILED
Design Evaluation Score: {N}/100
```

## Design System Compliance Checklist (for product-reviewer)

When reviewing screenshots, check:
- [ ] No hardcoded colors (should match design tokens)
- [ ] Spacing follows the scale (4, 8, 16, 24, 32px)
- [ ] Typography uses defined type scale (max 4 sizes)
- [ ] Empty states have illustration + headline + CTA
- [ ] Error messages explain what happened + what to do
- [ ] Loading states use skeleton screens (not spinners for content)
- [ ] Mobile layout is usable (no horizontal scroll, touch targets >= 44px)
- [ ] Animations respect `prefers-reduced-motion`

## Visual Regression (project CLAUDE.md schema — AC7)

Projects MAY declare a `## Visual Regression` section in their `.claude/CLAUDE.md`
to override the default pixel-diff threshold globally or per-route. Schema:

```markdown
## Visual Regression
default_max_diff_pixel_ratio: 0.02
per_route:
  /dashboard: 0.05
  /checkout: 0.01
```

**Field semantics**:
- `default_max_diff_pixel_ratio`: applied to every route that does not appear
  in the `per_route` map. Default value (when the section is absent or the
  field is missing): `0.02`.
- `per_route`: route → threshold map. Consulted FIRST when resolving the
  threshold for a given route — the default is a fallback, not an override.
  Precedence: per-route value (if present) > `default_max_diff_pixel_ratio`
  (always present, defaults to `0.02`).

**Backward compatibility**: projects without a `## Visual Regression` section
get the global default `0.02` for every route. No warning is emitted; absent
section is normal for projects that haven't tuned thresholds yet. Malformed YAML
in the section is treated as failure-mode-6: scratchpad warning with literal
token `claude-md-vr-yaml-error` and fallback to default 0.02 globally.

## Failure Modes

| Step | Failure | Verdict | Message |
|------|---------|---------|---------|
| 1 | Missing CLAUDE.md contract | CAPTURE_FAILED | "Project CLAUDE.md missing Dev Server section" |
| 2 | npm install fails | CAPTURE_FAILED | npm error output |
| 3 | Build fails | CAPTURE_FAILED | Build error output |
| 4 | Server won't start | CAPTURE_FAILED | "Dev server failed to start" |
| 6 | All captures fail | CAPTURE_FAILED | "No screenshots captured" |
| 6 | Some captures fail | SCREENSHOTS_CAPTURED | Partial results + warnings |

Every failure is loud. No silent skips.

## Phase Output

```
Verdict: SCREENSHOTS_CAPTURED / CAPTURE_FAILED
Next: Feed screenshots to /product-acceptance
      If CAPTURE_FAILED → fix build/server issue, re-run
Artifacts: [screenshot paths, routes captured, viewports, build status]
```
