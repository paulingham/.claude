---
name: "accessibility-check"
description: "Run axe-core against changed routes and gate on WCAG 2.1 AA violations; invoked by the pipeline after frontend Build and by design-qc in-process during Final Gate."
verdict: "A11Y_CHECK_PASSED / A11Y_CHECK_FAILED / A11Y_CHECK_SKIPPED"
phase: "utility"
dispatch: "subagent"
context: fork
agent: qa-engineer
---

# Accessibility Check

## What This Skill Does

Scans changed frontend routes with axe-core against WCAG 2.1 A/AA rules. Gates the pipeline on any gating violation (wcag2a, wcag2aa, wcag21a, wcag21aa tagged). Reports per-route results so engineers can pinpoint which route introduced the violation.

## Entry Conditions

Invoked in two modes:

1. **Pipeline standalone** — at Final Gate, after frontend Build, when changed files include `.tsx`, `.jsx`, `.vue`, `.svelte`, or CSS files. Parallel with `/harness:design-qc`.
2. **design-qc in-process** — called from `skills/design-qc/SKILL.md` Step 6.26 while the design-qc dev server is already running.

## Procedure

### Step 1: Detect Changed Routes

#### 1a. Run the diff
```bash
git diff --name-only origin/main...HEAD
```

#### 1b. Cross-reference with file-based router page directory

Supported router layouts:

- **Next.js**: `app/` or `pages/` — derive URL path from file path
  - `app/dashboard/page.tsx` → `/dashboard`
  - `pages/dashboard.tsx` → `/dashboard`
- **Remix / Astro**: `src/pages/` — derive URL path from file path
- **Vue Router**: read the router config file for defined routes

#### 1c. Always append `/` unconditionally

Root is always included regardless of what the diff shows.

#### 1d. Deduplicate

If the resulting set is `{'/'}` (zero non-root routes detected from the diff), that is valid — scan `/` only. Never produce a zero-length URL list.

#### 1e. Pass all collected URLs to axe_runner.js

```bash
node hooks/_lib/axe_runner.js --url / --url /dashboard [--url ...]
```

Repeated `--url` flags, one per route.

### Step 2: Invocation Modes

#### Pipeline Standalone (via Dev Server Contract)

The pipeline orchestrator starts the dev server per the project `## Dev Server` contract before invoking this skill. If the `## Dev Server` contract is absent from the project CLAUDE.md:

- emit `A11Y_CHECK_SKIPPED` with `skip_reason: no-dev-server-contract`
- write a scratchpad warning (see Failure Modes below)
- pipeline continues

After route detection (Step 1), invoke:

```bash
node hooks/_lib/axe_runner.js --url <url1> [--url <url2>...]
```

Parse the exit code and stdout JSON (output is stdout-only).

#### design-qc In-Process

When called from design-qc Step 6.26, the dev server is already running. design-qc passes the `axeRunFn` callable (bound to the Playwright page). Call `run_main(argv, { axeRunFn })` directly from Node.js rather than spawning a child process.

### Step 3: Interpret Results

The stdout JSON shape:

```json
{
  "verdict": "A11Y_CHECK_PASSED | A11Y_CHECK_FAILED | A11Y_CHECK_SKIPPED",
  "gating_violations": [
    {
      "id": "color-contrast",
      "help": "Elements must have sufficient color contrast",
      "nodes": [{ "target": ".btn", "html": "<button>" }],
      "route_url": "/dashboard"
    }
  ],
  "incomplete": [],
  "routes": [
    {
      "url": "/",
      "verdict": "A11Y_CHECK_PASSED",
      "gating_violations": [],
      "incomplete": []
    }
  ],
  "skip_reason": "env-hatch | no-dev-server-contract | browser-launch-failed"
}
```

Exit code mapping:

- `0` → `A11Y_CHECK_PASSED`
- `1` → `A11Y_CHECK_FAILED`
- `2` → `A11Y_CHECK_SKIPPED`

### Step 4: Emit Verdict

- `A11Y_CHECK_PASSED` — all routes clean; pipeline continues
- `A11Y_CHECK_FAILED` — halt; list gating violations with `{id, help, nodes}` actionability
- `A11Y_CHECK_SKIPPED` — infrastructure unavailable; pipeline continues; emit scratchpad warning

### Verdict Semantics

| Verdict | Polarity | Meaning |
|---------|----------|---------|
| `A11Y_CHECK_PASSED` | success | All scanned routes have zero WCAG 2.1 A/AA gating violations |
| `A11Y_CHECK_FAILED` | failure | One or more routes have gating violations; lists each with `id`, `help`, `nodes`, `route_url` |
| `A11Y_CHECK_SKIPPED` | info | Infrastructure unavailable (no dev server, browser launch failure, or env hatch); reason ∈ {`no-dev-server-contract`, `browser-launch-failed`, `env-hatch`} |

**GATING_TAGS**: `['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']`. A violation is gating iff its `tags` array intersects GATING_TAGS. `best-practice`, `experimental`, `cat.*` tags are never gating.

**axe `incomplete` results**: reported in the `incomplete[]` array; they never gate. They are advisory — engineers should review them but they do not block the pipeline.

**Multi-route aggregation rule**: every scanned route must be clean for `A11Y_CHECK_PASSED`. One route with gating violations → `A11Y_CHECK_FAILED`; per-route result blocks are present in `routes[]` for all scanned URLs.

### Failure Modes

| Failure | Condition | Outcome |
|---------|-----------|---------|
| No dev server contract | `## Dev Server` absent from project CLAUDE.md | `A11Y_CHECK_SKIPPED` with `skip_reason: no-dev-server-contract`; scratchpad warning with token `axe-scan-failed` |
| Browser launch failed | `axeRunFn` throws | `A11Y_CHECK_SKIPPED` with `skip_reason: browser-launch-failed`; scratchpad warning with token `axe-scan-failed` |
| Env hatch | `CLAUDE_A11Y=0` set | `A11Y_CHECK_SKIPPED` with `skip_reason: env-hatch`; no scratchpad warning |
| WCAG violations found | gating violations > 0 | `A11Y_CHECK_FAILED`; list violations with actionability fields |

Scratchpad warning format for skip conditions (except env-hatch):

```yaml
---
category: warning
---

axe-scan-failed: <skip_reason>. Route(s) not scanned: <urls>.
```

### CLI Standalone Mode — Dependency Resolution

When `axe_runner.js` is invoked directly (`node hooks/_lib/axe_runner.js --url ...`), it resolves `playwright-core` and `axe-core` in this order:

1. `<process.cwd()>/node_modules/` — the consumer project's installed packages.
2. `tests/fixtures/accessibility-check/.deps/node_modules/` — the fixture dependency cache (populated by the fixture integration test).

If neither location provides both `playwright`/`playwright-core` and `axe-core`, the runner emits `A11Y_CHECK_SKIPPED` with `skip_reason: browser-launch-failed` and exits `2`. This is the legitimate env-unavailability path, not a hard failure.

The resolver is DI-testable: `_resolve_cli_deps(candidates, requireFn, readFileFn)` accepts injectable require and readFile functions.

### Environment Escape Hatch

`CLAUDE_A11Y=0` — skip all axe scanning; emit `A11Y_CHECK_SKIPPED` with `skip_reason: env-hatch`. Use when the Playwright environment is unavailable and the operator accepts the skip.

## Phase Output

```
Verdict: A11Y_CHECK_PASSED / A11Y_CHECK_FAILED / A11Y_CHECK_SKIPPED
Routes scanned: [list]
Gating violations: [list with id, help, route_url, nodes]
Incomplete (advisory): [count]
```
