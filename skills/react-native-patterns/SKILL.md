---
name: "react-native-patterns"
description: "Use when user wants to Expo Router v4 patterns, NativeWind, Gluestack UI v3, TanStack Query + Zustand, platform handling, Maestro E2E. Use for all React Native/Expo development."
---

# React Native Patterns

## What This Skill Does

Documents and enforces React Native/Expo patterns for mobile development.

## Expo Router v4

- File-based routing in `app/` directory
- Layouts with `_layout.tsx` for shared UI (tab bars, headers)
- Typed routes with `expo-router/typed-routes` for compile-time safety
- Deep linking configured in `app.json` under `expo.scheme`
- Use `<Link>` component for navigation, `router.push()` for imperative
- Route groups with `(group)` folders for organizing without affecting URL

## NativeWind Styling

- Use Tailwind utility classes via `className` prop
- Configure in `tailwind.config.ts` with content paths
- Platform variants: `ios:`, `android:` prefixes
- Dark mode: `dark:` prefix with system preference detection
- Avoid inline `style` prop — use NativeWind utilities or `StyleSheet.create`

## Gluestack UI v3

- Import accessible components: `Button`, `Input`, `Select`, `Modal`, `Toast`
- Customize via NativeWind — Gluestack v3 supports utility-first styling
- Use `FormControl` with `FormControlLabel` and `FormControlError` for forms
- Accessible by default: proper roles, labels, and keyboard support

## State Management

### TanStack Query (Server State -- 80% of state)
- `useQuery` for fetching, `useMutation` for writes
- Stale-while-revalidate with `staleTime` configuration
- Optimistic updates for responsive UI
- Offline persistence with `@tanstack/query-async-storage-persister`
- Prefetch on screen focus with `useFocusEffect`

### Zustand (UI State -- 20% of state)
- Minimal stores for UI-only state (theme, onboarding, filters)
- Persist to AsyncStorage with `zustand/middleware`
- Keep stores flat — avoid nesting
- Use selectors to prevent unnecessary re-renders

## Platform Handling

- `Platform.select({ ios: ..., android: ..., default: ... })` for small differences
- `.ios.tsx` / `.android.tsx` file extensions for large platform divergence
- Safe area handling with `react-native-safe-area-context`
- Haptic feedback on iOS with `expo-haptics`
- Status bar management with `expo-status-bar`

## Performance

- `FlashList` over `FlatList` for large lists
- `React.memo` for expensive pure components
- `useCallback` / `useMemo` for stable references in lists
- Image optimization with `expo-image` (caching, progressive loading)
- Lazy load screens: dynamic imports in route files

## Code Shape (Mandatory)

All React Native code MUST comply with `rules/engineering-protocol.md` (8-line functions, 50-line files, CC <= 5, nesting <= 2, DRY).

### React Native Decomposition Patterns

When a component exceeds limits, decompose using:
- **Custom hooks**: Extract stateful logic (`useQuery`, `useMutation`, effects) into `useXxx` hooks
- **Container/Presenter**: Container fetches data via hooks, presenter receives props and renders
- **Render helpers**: Extract JSX fragments into named functional components in separate files
- **Config objects**: Extract styles, constants, and configuration into dedicated files
- **Compound components**: Split complex components into composable sub-components

Example structure for a screen:
```
screens/Profile/
  index.tsx          # Re-exports ProfileScreen (≤ 10 lines)
  ProfileScreen.tsx  # Container: hooks + layout (≤ 50 lines)
  ProfileHeader.tsx  # Presenter component (≤ 50 lines)
  ProfileStats.tsx   # Presenter component (≤ 50 lines)
  useProfileData.ts  # Custom hook (≤ 50 lines)
  profileConfig.ts   # Constants and config (≤ 50 lines)
```

## Maestro E2E Testing

### Directory Convention

Maestro flow files live in `maestro/` at the project root (not `e2e/`). This keeps them separate from Jest test files in `__tests__/`.

```
maestro/
  app-launch.yaml           # Smoke test: app boots and WebView loads
  adviser-login-flow.yaml   # Adviser SSO login journey
  client-login-flow.yaml    # Client SSO login journey
  offline-banner.yaml       # Offline detection and banner display
```

### Flow YAML Structure

```yaml
appId: com.example.app
name: Feature Area - Action Description
---
# Step 1: Launch and wait for app to be ready
- launchApp
- waitForAnimationToEnd

# Step 2: Interact with the feature
- tapOn:
    id: "element-test-id"
- inputText: "value"

# Step 3: Assert expected state
- assertVisible:
    text: "Expected Text"
- takeScreenshot: "feature-area-final-state"
```

### WebView-Specific Patterns

WebView content is not native -- Maestro interacts with rendered HTML, not React Native components.

**Wait for WebView content to load:**
```yaml
- extendedWaitUntil:
    visible:
      text: "Welcome"
    timeout: 15000
```

**Interact with HTML form elements by ID:**
```yaml
- tapOn:
    id: "username"
- inputText: "test@example.com"
- tapOn:
    id: "password"
- inputText: "secret"
```

**Assert login provider by UI elements (not URLs):**
```yaml
# Correct: assert visible UI text rendered by the auth provider
- assertVisible:
    text: "Sign In"

# Wrong: never assert on internal URLs -- Maestro cannot see WebView navigation
```

### Environment Variables for Credentials

Never hardcode test credentials in flow files. Use Maestro environment variables.

```yaml
- inputText: ${MAESTRO_ADVISER_USERNAME}
- inputText: ${MAESTRO_ADVISER_PASSWORD}
```

Run with:
```bash
MAESTRO_ADVISER_USERNAME=user MAESTRO_ADVISER_PASSWORD=pass maestro test maestro/adviser-login-flow.yaml
```

### Screenshot Capture

Capture screenshots at key states for visual evidence in verification reports.

```yaml
- takeScreenshot: "login-form-loaded"
- takeScreenshot: "dashboard-after-login"
```

Screenshot names should be descriptive: `[feature]-[state].png`.

### Flow Naming Convention

- Pattern: `[feature-area]-[action].yaml`
- Use kebab-case
- Examples: `app-launch.yaml`, `adviser-login-flow.yaml`, `file-download.yaml`

### Anti-Patterns

- **Hardcoded waits**: Use `extendedWaitUntil` or `waitForAnimationToEnd`, never `sleep` with arbitrary durations
- **Fragile selectors**: Prefer `id` attributes over text matching where possible. Text matching breaks on copy changes
- **Assuming auth provider**: Do not assert on Okta-specific implementation details. Assert on visible UI elements that any SSO provider would render
- **Skipping waitForAnimationToEnd**: Always call after `launchApp` and after navigation events. Animations cause flaky assertions
- **Testing visual styling**: Maestro verifies behavior and content, not pixel-perfect styling. Use screenshots for visual regression, not assertions

### Shape Exception

Maestro YAML flow files are exempt from the 50-line file limit and 8-line function limit defined in `rules/engineering-protocol.md`. E2E flows are sequential step lists, not functions, and splitting them across files harms readability.

### E2E Protocol Integration

For trigger criteria, flow-to-file mapping, prerequisites, and pass/fail criteria, see `rules/e2e-protocol.md`. That file is the single source of truth for when E2E tests are required in the pipeline.
