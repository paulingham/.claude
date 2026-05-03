---
paths:
  - "maestro/**"
  - "**/*.tsx"
  - "**/app/**"
---

# E2E Protocol

Defines when Maestro E2E tests are required, which flows to run, prerequisites, and pass/fail criteria.

## Trigger Matrix

Changed files are checked against this matrix to determine if E2E flows are required.

### E2E Required (YES)

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

### E2E Not Required (NO)

- CSS injection files that are purely cosmetic (`css-typography-tables.ts`, `css-cookie-banner.ts`, `css-navigation-hide.ts`) -- unless they modify layout or element visibility
- Visual-only components (e.g., `LoadingOverlay.tsx`, `BiometricOverlay.tsx`) -- unless they gate user access
- Test files (`__tests__/**`)
- Maestro flow files (`maestro/**`)
- Documentation and config (`.md`, `package.json` version bumps)

## Flow-to-File Mapping

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

## Prerequisites

All must be met before E2E execution:

1. **Maestro CLI**: `maestro` command available on PATH
2. **Booted simulator**: iOS Simulator or Android Emulator running
3. **Dev build**: Expo development build installed on the simulator (not Expo Go)
4. **Test credentials**: Environment variables set:
   - `MAESTRO_ADVISER_USERNAME` -- adviser test account
   - `MAESTRO_ADVISER_PASSWORD` -- adviser test account password
   - `MAESTRO_CLIENT_USERNAME` -- client test account
   - `MAESTRO_CLIENT_PASSWORD` -- client test account password

If any prerequisite is not met, E2E status is SKIP (not FAIL).

## Execution

### Full Suite
```bash
maestro test maestro/
```

### Targeted Flows
```bash
maestro test maestro/app-launch.yaml
maestro test maestro/adviser-login-flow.yaml
```

### With Environment Variables
```bash
MAESTRO_ADVISER_USERNAME=user MAESTRO_ADVISER_PASSWORD=pass maestro test maestro/
```

## Pass/Fail Criteria

| Exit Code | Status | Meaning |
|-----------|--------|---------|
| 0 | PASS | All executed flows passed |
| Non-0 | FAIL | One or more flows failed |
| N/A | SKIP | Prerequisites not met -- not a hard blocker |

## Retry Policy

- One retry per flow on failure
- If a flow fails twice, it is a genuine failure (not flakiness)
- Record both attempts in the verification report

## Verdict Integration

E2E results feed into the `/verify` skill (Tier 4):

| E2E Status | Verify Verdict |
|------------|---------------|
| PASS | VERIFIED (standard) |
| FAIL | UNVERIFIED |
| SKIP | VERIFIED_WITH_SKIP -- product-reviewer must acknowledge |
| N/A | VERIFIED (no trigger files changed) |

## Web Trigger Matrix

Parallel to the mobile Maestro matrix above. Web (browser-rendered) projects must
exercise a real environment when any of the categories below are touched. "Real
environment" means a deployed preview URL or an ephemeral `docker-compose` stack
spun up for the test run — NOT JSDOM, NOT a unit-test mock. Driver: Playwright
or Cypress.

### Web E2E Required (YES)

| Category | Trigger |
|----------|---------|
| Route changes | New/renamed/removed route, route-level redirect, route auth guard change |
| Auth/Session | Login/logout flow, session cookie shape, JWT issuance, RBAC guard, OAuth callback |
| Migrations (FK / NOT NULL) | Any schema migration adding, removing, or modifying a foreign key OR a `NOT NULL` column. SQL-only migrations count |
| Env var addition | New required env var consumed at runtime (front-end build constants OR back-end config). Optional env vars with safe defaults are exempt |
| Public API contract | Endpoint added/removed, request or response shape change, status code change, public webhook payload change |

### Web E2E Not Required (NO)

- Pure styling tweaks (CSS/Tailwind) that do not change layout/visibility
- Internal helper refactors with no public API surface change
- Test-only files (`*.test.*`, `__tests__/`)
- Documentation, READMEs, comments
- Optional env vars with safe defaults (already covered by unit tests)

### Real-Environment Stack Requirements

At least ONE of the following must be wired up before the suite can satisfy the
"real environment" requirement:

| Stack | Use when |
|-------|----------|
| Deployed preview URL (Vercel/Netlify/Render PR preview) | The repo has CI-provisioned preview deploys for every PR |
| `docker-compose up -d` ephemeral stack | The repo ships a `docker-compose.e2e.yml` (or equivalent) that boots app + DB + dependencies |
| Cloud ephemeral env (Fly Machines, Heroku Review App, Railway env) | The repo provisions PR-scoped ephemeral envs |

If NONE of these is available, web E2E status is `SKIP` (parallel to mobile's
"prerequisites not met" rule). Skip is NOT a hard blocker but the
product-reviewer must acknowledge it in `/product-acceptance`.

### Driver Selection

| Driver | When |
|--------|------|
| Playwright | Default. Cross-browser, fast, CI-friendly. |
| Cypress | When the project already has a Cypress harness — do not introduce a second driver. |

Targeted runs are an optimization. Full suite (`playwright test` /
`cypress run`) is the default for changes spanning ≥2 trigger categories.

## Incident Context

This protocol exists because unit tests passed while the app was broken in production. A login domain was not whitelisted in `constants.ts`, and no E2E flow caught it because Maestro was not integrated into the pipeline. Unit tests mocked the URL classification layer, so the bug was invisible to the test suite.

The web matrix was added in Wave 2 (Apr 27 2026 cohort) to close the same hole
on browser projects: a route or migration change shipping with green unit tests
but no real-environment exercise is the same failure mode in a different shell.
