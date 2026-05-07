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

- MANDATORY when changed files include `.tsx`, `.jsx`, `.vue`, `.svelte`, or CSS files
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

If the project does not have `puppeteer` or `playwright` in devDependencies:
```bash
npm install --save-dev puppeteer
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

### Step 6: Capture Screenshots

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

Use Puppeteer:
```javascript
const browser = await puppeteer.launch({ headless: true });
const page = await browser.newPage();
await page.setViewport({ width, height });
await page.goto(url, { waitUntil: 'networkidle0' });
await page.screenshot({ path, type: 'jpeg', quality: 80, fullPage: true });
await browser.close();
```

**If capture fails** (browser crash, navigation error) → log the failing route but continue with remaining routes. Report partial results.

### Step 6.25: A11y Tree Capture (Dual-Output)

After Step 6 screenshots, while the dev server is still running and Playwright is still in-process, capture an accessibility-tree snapshot per (route, viewport). The output is owned by `patch-critic` (machine-checkable rubric § 5). Product-reviewer continues to consume only the screenshots — see `agents/product-reviewer.md`.

**Index file** (canonical artifact for downstream consumers):
- Path: `pipeline-state/{task-id}/design-qc/index.json`
- Schema: `{schema_version: 1, task_id, captured_at, build_status, server_started, routes: [...], a11y_global: {...}}`
- Per-route entry: `{route, screenshots: [...], a11y: {captured, capture_path?, reason?, snapshots: [{viewport, path}]}}`
- Per-snapshot file: `pipeline-state/{task-id}/design-qc/a11y/{route-slug}-{viewport}.json` with `schema_version: 1` and a normalised tree shape

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
