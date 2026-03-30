---
name: "Design QC"
description: "Visual QA via screenshots during product acceptance. Auto-detects dev server, captures full-page sectioned screenshots at desktop and mobile viewports, feeds to product-reviewer for visual validation."
context: fork
agent: qa-engineer
---

# Design QC

## What This Skill Does

Captures screenshots of the running application for visual QA during the product acceptance phase. Auto-detects dev servers, captures at desktop and mobile viewports, and provides the screenshots to the product-reviewer for visual validation against acceptance criteria and design system compliance.

## When to Invoke

- During the Final Gate / Accept phase when changed files include frontend code (`.tsx`, `.jsx`, `.vue`, `.svelte`, `.css`)
- Invoked by `/product-acceptance` or by the pipeline orchestrator before/parallel with acceptance
- Requires a running dev server or ability to start one

## Prerequisites

- Puppeteer or Playwright installed (project dependency or global)
- Dev server configuration in project CLAUDE.md Commands section
- Chrome or Chromium available

## Process

### 1. Detect Dev Server

Probe common ports in order:
```bash
for port in 3000 3001 5173 5174 4321 8080 8000 4200; do
    curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port" 2>/dev/null
done
```

If no server running, start from project CLAUDE.md Commands section (e.g., `npm run dev`). Wait for health check to pass (max 30 seconds).

### 2. Detect Routes

For file-based routing frameworks:
- **Next.js**: Scan `app/` or `pages/` directory for page files
- **Expo Router**: Scan `app/` directory
- **Vite/SPA**: Use the root URL `/` and any routes defined in router config
- **Astro**: Scan `src/pages/` directory

Limit to routes affected by the current change (cross-reference with `git diff --name-only`).

### 3. Capture Screenshots

For each detected route, capture at two viewports:
- **Desktop**: 1440x900
- **Mobile**: 375x812

Capture method: full-page sectioned (viewport-height JPEG sections):
- Scroll through page, capture viewport-height sections
- Name: `{route}-{viewport}-{section}.jpg`
- JPEG quality: 80 (balances quality vs token cost, ~2500 tokens per screenshot)
- Max 8 sections per page

### 4. Feed to Product Reviewer

Pass screenshot paths to the product-reviewer during `/product-acceptance`:
```
Screenshots captured for visual review:
- /dashboard (desktop): 3 sections
- /dashboard (mobile): 4 sections
- /settings (desktop): 2 sections
- /settings (mobile): 2 sections

Review for: design system compliance, responsive behavior, visual regressions, empty/error states.
```

### 5. Cleanup

Stop the dev server if we started it. Remove screenshot files after the pipeline completes.

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

## Phase Output

```
Verdict: SCREENSHOTS_CAPTURED / CAPTURE_FAILED / NO_FRONTEND_CHANGES
Next: Feed screenshots to /product-acceptance
Artifacts: [screenshot paths, routes captured, viewports]
```
