---
paths:
  - "maestro/**"
  - "**/*.tsx"
  - "**/app/**"
  # Web target globs (R5: union into frontmatter alongside mobile)
  - "**/*Auth*.{tsx,ts,jsx,js}"
  - "**/login/**"
  - "**/logout/**"
  - "**/session/**"
  - "**/middleware.{ts,js}"
  - "**/_redirects"
  - "**/next.config.{js,ts,mjs}"
  - "**/router/**"
  - "**/*Form*.{tsx,ts,jsx,js}"
  - "**/forms/**"
  - "**/actions/**"
  - "**/api/**/*.{ts,js}"
  - "**/checkout/**"
  - "**/payment*/**"
  - "**/billing/**"
  - "**/stripe/**"
  - "**/*Checkout*.{tsx,ts}"
  - "**/*Iframe*.{tsx,ts}"
  - "**/embed*/**"
  - "**/widgets/**"
  - "**/sw.{js,ts}"
  - "**/service-worker.{js,ts}"
  - "**/workbox*.{js,ts}"
---

# E2E Protocol

Defines when E2E tests are required, which flows to run, prerequisites, and pass/fail criteria. Multi-target: mobile (Maestro) and web (Playwright / Cypress) are siblings under `## Targets`. Both share the per-target verdict enum {PASS, FAIL, SKIP, N/A}; composition into VERIFIED / VERIFIED_WITH_SKIP / UNVERIFIED is documented under `## Shared Verdict Semantics`.

## Targets

### Mobile (Maestro)

#### Trigger Matrix

Changed files are checked against this matrix to determine if mobile E2E flows are required.

##### E2E Required (YES)

| Category | Files |
|----------|-------|
| URL/Navigation | `url-classification.ts`, `url-parse-helpers.ts`, `navigation-helpers.ts`, `useNavigationHandler.ts`, `navigationCallbacks.ts` |
| Auth/Session | `session-store.ts`, `session-message-handler.ts`, `useWebViewAuth.ts`, `useWebViewMessages.ts` |
| Biometric | `useBiometricGating.ts`, `useBiometricState.ts`, `biometric-auth.ts` |
| WebView Core | `WebViewContainer.tsx`, `WebViewScreen.tsx`, `_layout.tsx`, `index.tsx` |
| Network | `NetworkBanner.tsx`, `useNetworkStatus.ts` |
| Downloads/Cookies | `file-download.ts`, `cookie-manager.ts` |
| Injection (behavioral) | `viewport-meta.ts`, `session-check.ts` |
| Constants (domain) | `constants.ts` (only when `WEBVIEW_ORIGIN_WHITELIST` or domain URLs change) |
| CSS Injection (layout) | `css-forms-buttons.ts`, `css-containers.ts`, `css-base-layout.ts`, `css-media-elements.ts`, `css-document-viewer.ts`, `css-assembly.ts` |

##### E2E Not Required (NO)

- CSS injection files that are purely cosmetic (`css-typography-tables.ts`, `css-cookie-banner.ts`, `css-navigation-hide.ts`) -- unless they modify layout or element visibility
- Visual-only components (e.g., `LoadingOverlay.tsx`, `BiometricOverlay.tsx`) -- unless they gate user access
- Test files (`__tests__/**`)
- Maestro flow files (`maestro/**`)
- Documentation and config (`.md`, `package.json` version bumps)

#### Flow-to-File Mapping

Which Maestro flows to run based on which files changed.

| Maestro Flow | Trigger Files |
|-------------|---------------|
| `app-launch.yaml` | Always (smoke test for every E2E run) |
| `adviser-login-flow.yaml` | URL/Navigation files, Auth/Session files, WebView Core files, Constants (domain), Injection (behavioral) |
| `client-login-flow.yaml` | URL/Navigation files, Auth/Session files, WebView Core files, Constants (domain), Injection (behavioral) |
| `offline-banner.yaml` | `NetworkBanner.tsx`, `useNetworkStatus.ts` |
| `documents-page.yaml` | CSS Injection (layout) files, WebView Core files |
| `document-viewer.yaml` | CSS Injection (layout) files, Downloads/Cookies files |

When in doubt, run the full suite (`maestro test maestro/`). Targeted runs are an optimization, not a requirement.

#### Prerequisites

All must be met before mobile E2E execution:

1. **Maestro CLI**: `maestro` command available on PATH
2. **Booted simulator**: iOS Simulator or Android Emulator running
3. **Dev build**: Expo development build installed on the simulator (not Expo Go)
4. **Test credentials**: Environment variables set:
   - `MAESTRO_ADVISER_USERNAME` -- adviser test account
   - `MAESTRO_ADVISER_PASSWORD` -- adviser test account password
   - `MAESTRO_CLIENT_USERNAME` -- client test account
   - `MAESTRO_CLIENT_PASSWORD` -- client test account password

If any prerequisite is not met, mobile E2E status is SKIP (not FAIL).

#### Execution

##### Full Suite

```bash
maestro test maestro/
```

##### Targeted Flows

```bash
maestro test maestro/app-launch.yaml
maestro test maestro/adviser-login-flow.yaml
```

##### With Environment Variables

```bash
MAESTRO_ADVISER_USERNAME=user MAESTRO_ADVISER_PASSWORD=pass maestro test maestro/
```

#### Pass/Fail Criteria

| Exit Code | Status | Meaning |
|-----------|--------|---------|
| 0 | PASS | All executed flows passed |
| Non-0 | FAIL | One or more flows failed |
| N/A | SKIP | Prerequisites not met -- not a hard blocker |

#### Retry Policy

- One retry per flow on failure
- If a flow fails twice, it is a genuine failure (not flakiness)
- Record both attempts in the verification report

### Web (Playwright / Cypress)

Web (browser-rendered) projects must exercise a real environment when any of the trigger categories below match changed files. "Real environment" means a deployed preview URL or an ephemeral `docker-compose` stack — NOT JSDOM, NOT a unit-test mock.

#### Trigger Matrix (6 canonical categories — schema only)

The schema is **canonical**. Pattern globs are illustrative — adapt per project. Matched against changed files via `hooks/_lib/e2e_target_resolver.py` (which handles `{ext1,ext2}` brace expansion AND top-level files matched against `**/`-prefixed patterns).

| Category | Example pattern globs |
|----------|------------------------|
| `auth-flow` | `**/*Auth*.{tsx,ts,jsx,js}`, `**/login/**`, `**/logout/**`, `**/session/**`, `**/middleware.ts` (auth guards) |
| `routing-redirect` | `**/middleware.ts`, `**/middleware.{js,ts}`, `**/_redirects`, `**/next.config.{js,ts,mjs}`, `**/router/**` |
| `form-submission` | `**/*Form*.{tsx,ts,jsx,js}`, `**/forms/**`, `**/actions/**`, `**/api/**/*.{ts,js}` |
| `payment-checkout` | `**/checkout/**`, `**/payment*/**`, `**/billing/**`, `**/stripe/**`, `**/*Checkout*.{tsx,ts}` |
| `third-party-iframe` | `**/*Iframe*.{tsx,ts}`, `**/embed*/**`, `**/widgets/**` |
| `service-worker` | `**/sw.{js,ts}`, `**/service-worker.{js,ts}`, `**/workbox*.{js,ts}` |

#### Supplementary back-end triggers

The following back-end concerns also force a web E2E run because they cross the front/back boundary in ways unit tests cannot detect. Retained from the pre-restructure web matrix; logically supplementary to the 6 canonical categories above.

| Trigger | Description |
|---------|-------------|
| Migrations (FK / NOT NULL) | Any schema migration adding, removing, or modifying a foreign key OR a `NOT NULL` column. SQL-only migrations count |
| Public API contract | Endpoint added/removed, request or response shape change, status code change, public webhook payload change |

When a back-end target is introduced (deferred, see incident context), these supplementary triggers will migrate under that section.

#### Web E2E Not Required (NO)

- Pure styling tweaks (CSS/Tailwind) that do not change layout/visibility
- Internal helper refactors with no public API surface change
- Test-only files (`*.test.*`, `__tests__/`)
- Documentation, READMEs, comments
- Optional env vars with safe defaults (already covered by unit tests)

#### Real-Environment Stack Requirements

At least ONE of the following must be wired up before the web suite can satisfy the "real environment" requirement:

| Stack | Use when |
|-------|----------|
| Deployed preview URL (Vercel/Netlify/Render PR preview) | The repo has CI-provisioned preview deploys for every PR |
| `docker-compose up -d` ephemeral stack | The repo ships a `docker-compose.e2e.yml` (or equivalent) that boots app + DB + dependencies |
| Cloud ephemeral env (Fly Machines, Heroku Review App, Railway env) | The repo provisions PR-scoped ephemeral envs |

If NONE of these is available AND no driver config is present, the web target status is `N/A` (no driver, no run). If a driver config is present but the stack is unavailable, status is `SKIP` (parallel to mobile's "prerequisites not met"). SKIP is NOT a hard blocker but the product-reviewer must acknowledge it.

#### Driver Selection

| Driver | Selection rule |
|--------|----------------|
| Playwright | Default. Cross-browser, fast, CI-friendly. Selected when `playwright.config.{ts,js}` is present. |
| Cypress | Selected when `cypress.config.{ts,js}` is present AND `playwright.config.{ts,js}` is NOT present. |

> **M4 — Both configs present:** when both `playwright.config.{ts,js}` AND `cypress.config.{ts,js}` are present, the resolver prefers **Playwright** (default) and emits a one-line warning to the verify report: "Both playwright and cypress configs detected; defaulting to playwright. Remove one config to silence this warning." Cypress fires only when the Playwright config is absent.

Targeted runs are an optimization. Full suite (`playwright test` / `cypress run`) is the default for changes spanning ≥2 trigger categories.

#### Prerequisites

All must be met before web E2E execution:

1. **Driver installed**: `npx playwright --version` or `npx cypress --version` resolves
2. **Driver config present**: `playwright.config.{ts,js}` OR `cypress.config.{ts,js}` (see Driver Selection)
3. **Real environment available**: deployed preview URL, docker-compose stack, OR cloud ephemeral env (per Real-Environment Stack Requirements above)
4. **Test credentials**: per-project; document in project CLAUDE.md

If driver config is absent, web E2E status is `N/A`. If driver config is present but other prerequisites fail, status is `SKIP`.

#### Execution

```bash
# Playwright
npx playwright test

# Cypress
npx cypress run
```

#### Flake Handling

> **M5 — Strict gate, no small-suite carve-out:** the flake gate fires at `flake_rate > 0.05` regardless of suite size. A single retry-and-pass in a suite of 19 tests yields `flake_rate ≈ 0.0526`, which exceeds the threshold and downgrades the web target to FAIL → UNVERIFIED. Carve-outs invite borderline rationalisation. The strict `>` is verified by tests `test_invariant_web_flake_gate_threshold` (boundary) and `test_flake_gate_fires_at_small_suite_size_no_carve_out` (small-suite).

Flake-rate semantics: **intra-run** via Playwright's retry counter (Cypress equivalent: `cypress.config retries`). Counted as `retries-that-passed-on-second-attempt / total-tests`. Captured in the verify report as `flake_rate: <decimal>`.

#### Pass/Fail Criteria

| Exit Code | Status | Meaning |
|-----------|--------|---------|
| 0 | PASS | All executed tests passed AND flake_rate ≤ 0.05 |
| 0 with flake_rate > 0.05 | FAIL | Strict flake gate fired; downgraded |
| Non-0 | FAIL | One or more tests failed |
| N/A | SKIP | Prerequisites met but real environment unavailable |
| (no driver config) | N/A | Web target not applicable to this project |

#### Screenshot Evidence Path

Web E2E screenshots-on-assertion land at:

```
pipeline-state/{task_id}/scratchpad/qa-engineer-verify-screenshots/
```

This path is a verbatim invariant (mirrored in `hooks/_lib/e2e_target_resolver.py` as `SCREENSHOT_PATH_TEMPLATE`). Screenshots survive into the PR narrative because the scratchpad subdirectory is preserved through Reflect cleanup until the pipeline state is removed.

## Shared Verdict Semantics

Both targets share the per-target status enum and compose into the same Tier 4 composite verdict.

### Per-target status enum

`{PASS, FAIL, SKIP, N/A}`

- **PASS** — target executed, all tests/flows succeeded
- **FAIL** — target executed, one or more tests/flows failed (or flake gate fired)
- **SKIP** — target applicable but prerequisites unmet (driver installed but no real env, simulator absent, etc.)
- **N/A** — target not applicable (no driver config, or no glob matches)

### Composite verdict (Tier 4)

`compose_verdict(target_results: dict[str, str]) -> str` produces the Tier 4 verdict per the rules below. **Coercion runs FIRST** (`coerce_web_status_for_flake`), then composition.

| Condition | Composite |
|-----------|-----------|
| Any target = FAIL | UNVERIFIED |
| Any target = SKIP and no FAILs | VERIFIED_WITH_SKIP |
| All fired targets = PASS | VERIFIED |
| All N/A | VERIFIED |

This composition is target-agnostic by design — adding a future `backend` target requires no change to `compose_verdict`.

## Incident Context

This protocol exists because unit tests passed while the app was broken in production. A login domain was not whitelisted in `constants.ts`, and no E2E flow caught it because Maestro was not integrated into the pipeline. Unit tests mocked the URL classification layer, so the bug was invisible to the test suite.

The web matrix was added in Wave 2 (Apr 27 2026 cohort) to close the same hole on browser projects: a route or migration change shipping with green unit tests but no real-environment exercise is the same failure mode in a different shell.

The C3 multi-target restructure (May 2026) made the two targets siblings, introduced the 6-category schema, and wired Tier 4 of `/verify` to dispatch per target with a strict flake gate. A future `### Backend (deferred)` migration is anticipated when a third target is needed; the supplementary back-end triggers will move under it then.
