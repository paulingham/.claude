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

### E2E Not Required (NO)

- CSS injection files (`css-base-layout.ts`, `css-containers.ts`, `css-forms-buttons.ts`, `css-typography-tables.ts`, `css-cookie-banner.ts`, `css-assembly.ts`, `css-injection.ts`) -- unless they modify viewport or session behavior
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

## Incident Context

This protocol exists because unit tests passed while the app was broken in production. A login domain was not whitelisted in `constants.ts`, and no E2E flow caught it because Maestro was not integrated into the pipeline. Unit tests mocked the URL classification layer, so the bug was invisible to the test suite.
