---
name: "React Native Patterns"
description: "Expo Router v4 patterns, NativeWind, Gluestack UI v3, TanStack Query + Zustand, platform handling, Maestro E2E. Use for all React Native/Expo development."
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

## Maestro E2E Testing

- YAML-based test flows in `e2e/` directory
- Test critical user journeys: onboarding, auth, core features
- Platform-specific assertions with `platform: ios` / `platform: android`
- Screenshot testing for visual regression
- Run in CI with `maestro test`
