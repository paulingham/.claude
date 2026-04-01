---
name: "web-frontend-patterns"
description: "Use when user wants to Web frontend reference: React/Next.js patterns, component architecture, state management, accessibility (WCAG 2.1 AA), performance optimization, testing. Equivalent to react-native-patterns for web."
argument-hint: "Framework context (e.g., 'Next.js App Router', 'Vite + React', 'Remix')"
---

# Web Frontend Patterns

## What This Skill Does

Provides comprehensive patterns and conventions for web frontend development. Covers React and Next.js patterns, component architecture, state management, accessibility, performance, caching, and testing. This is the web equivalent of the `react-native-patterns` skill.

## When to Invoke

- Building or scaffolding a web frontend
- Adding new pages or features to a React/Next.js app
- Implementing state management, data fetching, or caching
- Reviewing frontend code for accessibility or performance
- Setting up frontend testing strategy

## Framework Detection

| Signal | Framework | Router |
|--------|-----------|--------|
| `next.config.*` + `app/` directory | Next.js (App Router) | File-based (app/) |
| `next.config.*` + `pages/` directory | Next.js (Pages Router) | File-based (pages/) |
| `remix.config.*` | Remix | File-based (routes/) |
| `vite.config.*` + `react` | Vite + React | react-router / TanStack Router |
| `gatsby-config.*` | Gatsby | File-based |
| Plain `react` + `react-dom` | Create React App / custom | react-router |

## Component Architecture

### Component Types

| Type | Purpose | State | Data Fetching | Example |
|------|---------|-------|--------------|---------|
| **Page** | Route entry point | Minimal (route params) | Yes (server or client) | `app/users/page.tsx` |
| **Layout** | Shared UI wrapper | Navigation state | Auth check | `app/layout.tsx` |
| **Feature** | Business logic container | Yes (domain state) | Yes (via hooks) | `UserProfile` |
| **UI** | Reusable presentation | Props only | No | `Button`, `Card`, `Modal` |
| **Form** | User input handling | Form state (react-hook-form) | On submit | `LoginForm` |

### File Organization
```
src/
  app/                    # Next.js App Router pages
    layout.tsx
    page.tsx
    users/
      page.tsx
      [id]/page.tsx
  components/
    ui/                   # Design system primitives
      button.tsx
      input.tsx
      modal.tsx
    features/             # Business feature components
      auth/
        login-form.tsx
        signup-form.tsx
      users/
        user-profile.tsx
        user-list.tsx
  lib/                    # Business logic (no React imports)
    services/             # API clients, service objects
    hooks/                # Custom React hooks
    utils/                # Pure utility functions
    types/                # TypeScript type definitions
  styles/                 # Global styles, theme
```

### Component Rules
- **50-line limit** applies to components (enforced by `code-shape-check.sh`)
- Extract custom hooks for any logic beyond simple state
- UI components are pure functions of props — no side effects, no data fetching
- Feature components compose UI components and connect to data via hooks
- Co-locate tests: `user-profile.tsx` → `user-profile.test.tsx`

### Composition Patterns

Read `~/.claude/knowledge/composition-patterns.md` for the full reference.

**Critical rules:**
- **Max 3 boolean props** per component. If you need a 4th → compound component pattern
- **No `show*/hide*` props** → use compound children (Card.Header renders or doesn't)
- **Named variants over boolean combinations** → use CVA explicit variants
- **Compound components** for anything with 3+ visual sections (Card.Header, Card.Body, Card.Footer)
- **Provider pattern** only for infrequently-changing values (theme, locale, auth)
- **Slot pattern** for flexible layout insertion points

## React Patterns

### Server Components (Next.js App Router)
```
Default: Server Component (no "use client" directive)
Use server components for: static content, data fetching, SEO-critical pages
Switch to client component when: interactivity, browser APIs, hooks (useState, useEffect)
```

**Rule**: Start with server components. Add `"use client"` only when you need interactivity. Push client boundaries as low as possible in the component tree.

### Custom Hooks
```
- One hook per concern (useFetchUser, useFormValidation, useDebounce)
- Hooks return { data, error, isLoading } (TanStack Query pattern)
- Never put business logic in components — extract to hooks or lib/services/
- Test hooks with @testing-library/react renderHook
```

### Error Boundaries
```
- Wrap feature sections, not individual components
- Provide meaningful fallback UI (not just "Something went wrong")
- Log errors to monitoring (Sentry) from the boundary
- Use Next.js error.tsx convention in App Router
```

## State Management

### Decision Tree
```
Is the state from the server?
  → YES: TanStack Query (React Query) — cache, refetch, optimistic updates
  → NO: Is it shared across many components?
    → YES: Zustand (simple global store) or Context (small/infrequent updates)
    → NO: useState / useReducer (local component state)
```

### TanStack Query (Server State)
```typescript
// Queries: GET operations with caching
const { data, isLoading, error } = useQuery({
  queryKey: ['users', userId],
  queryFn: () => api.getUser(userId),
  staleTime: 5 * 60 * 1000,     // Cache for 5 minutes
  gcTime: 30 * 60 * 1000,       // Keep in memory 30 minutes
});

// Mutations: POST/PATCH/DELETE with optimistic updates
const mutation = useMutation({
  mutationFn: api.updateUser,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
});
```

### Zustand (Client State)
```typescript
// Simple, minimal global state — no boilerplate
const useAuthStore = create<AuthState>((set) => ({
  user: null,
  login: (user) => set({ user }),
  logout: () => set({ user: null }),
}));
```

### State Anti-Patterns
- **Prefer** Zustand over Redux for new projects unless the project already uses Redux or has complex requirements that benefit from Redux Toolkit's middleware
- **Do NOT** cache server data in client state (use TanStack Query)
- **Do NOT** prop-drill more than 2 levels (extract to hook or context)
- **Do NOT** use Context for frequently updating state (triggers full subtree re-render)

## Caching Patterns

### HTTP Caching
```
Static assets:     Cache-Control: public, max-age=31536000, immutable
API responses:     Cache-Control: private, max-age=0, must-revalidate
                   ETag: "abc123" (conditional requests)
HTML pages:        Cache-Control: no-cache (always revalidate, serve stale while revalidating)
```

### Next.js Caching
```
// Static generation (build time) — fastest
export const revalidate = 3600; // ISR: regenerate every hour

// Dynamic rendering (request time)
export const dynamic = 'force-dynamic';

// Route segment config
export const fetchCache = 'default-cache';
```

### Application-Level Caching
```
Redis for:
  - Session data
  - Rate limiting counters
  - Expensive query results (cache-aside pattern)
  - Real-time leaderboards / counters

Pattern: Cache-Aside
  1. Check cache
  2. If miss: query database, store in cache with TTL
  3. If hit: return cached value
  4. On write: invalidate cache key
```

### CDN Configuration
```
- Static assets (JS, CSS, images): CDN with immutable caching (hash in filename)
- API responses: Do NOT cache through CDN unless specifically designed for it
- HTML: CDN with short TTL (60s) or stale-while-revalidate
```

## Security

### Auth Token Storage
- Store session tokens in `httpOnly`, `Secure`, `SameSite=Strict` cookies only
- **Never** store tokens in `localStorage` or `sessionStorage` (vulnerable to XSS theft)
- Client-side auth state (user object, roles) is derived from the session, not the raw token
- Use the backend's session cookie — the frontend never sees or handles the JWT directly

### XSS Prevention
- React escapes JSX by default — this is your primary defense. Do not bypass it.
- **Never** use `dangerouslySetInnerHTML` — if unavoidable, sanitize with `DOMPurify` first
- Never render user-controlled content in `<script>`, `<style>`, or `href="javascript:..."` attributes
- Validate all user-provided URLs before rendering as `href` or `src` (allow only `https://`)

### Content Security Policy (CSP)
- Configure CSP via Next.js middleware or `<meta>` tag
- Minimum policy: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:;`
- Use nonces for inline scripts when required (`next/headers` API in App Router)
- Never use `'unsafe-eval'` in production

### CSRF Protection
- Use `SameSite=Strict` cookies (prevents CSRF by default in modern browsers)
- For APIs using cookie auth: require a CSRF token on state-changing requests
- For APIs using Bearer tokens: CSRF is not applicable (tokens are not sent automatically)

## Accessibility (WCAG 2.1 AA)

### Mandatory Checks (every component)
```
- Semantic HTML: Use <button>, <nav>, <main>, <article>, not div-soup
- Keyboard navigation: All interactive elements focusable and operable
- ARIA labels: Icons, images, and non-text content have aria-label or alt text
- Color contrast: 4.5:1 for normal text, 3:1 for large text
- Focus indicators: Visible focus ring on all interactive elements
- Form labels: Every input has a visible <label> with htmlFor
- Error messages: Associated with inputs via aria-describedby
- Skip navigation: "Skip to main content" link at top of page
```

### Testing Accessibility
```
- Automated: axe-core via @axe-core/react or jest-axe
- Manual: Keyboard-only navigation test per page
- Screen reader: Test with VoiceOver (macOS) or NVDA (Windows)
- Lighthouse: Accessibility score >90
```

### Common Anti-Patterns
- `div` with `onClick` instead of `<button>` (not keyboard accessible)
- `placeholder` as label (disappears on input, fails contrast)
- Color-only state indication (red for error without icon or text)
- `outline: none` without replacement focus indicator
- Modal without focus trap (tab escapes the modal)
- Dynamic content without `aria-live` announcement

## Performance

Read `~/.claude/knowledge/performance-design-patterns.md` for the full 57-rule deep reference.

### Core Web Vitals Targets
```
LCP (Largest Contentful Paint):  < 2.5s
INP (Interaction to Next Paint): < 200ms
CLS (Cumulative Layout Shift):   < 0.1
```

### CRITICAL Priority (fix these first)

**Request Waterfalls** — the #1 performance killer:
```
"Too many developers jump to useMemo when the real bottleneck is waterfalls."
Sequential fetches (A→B→C = 600ms) should be parallel (Promise.all = 200ms).
Detection: useEffect that fetches data depending on another useEffect's result.
Fix: Promise.all, useSuspenseQueries, route-level loaders, prefetch on hover.
```

**Bundle Size** — barrel file anti-pattern:
```
BAD:  import { Button } from '@/components'  // pulls EVERYTHING
GOOD: import { Button } from '@/components/ui/button'  // just the button
```

### Optimization Techniques

| Technique | When | How |
|-----------|------|-----|
| Code splitting | Always | Dynamic `import()`, Next.js `dynamic()` |
| Image optimization | Images >50KB | Next.js `<Image>`, `srcset`, AVIF > WebP > PNG |
| Font optimization | Custom fonts | `next/font`, `font-display: swap`, subset latin only |
| Bundle analysis | Before release | `@next/bundle-analyzer`, `source-map-explorer` |
| Lazy loading | Below-fold content | `loading="lazy"`, Intersection Observer |
| Memoization | Expensive renders | `React.memo`, `useMemo`, `useCallback` (**only when measured**) |
| Virtualization | Lists >100 items | `@tanstack/react-virtual` (preferred over react-window) |
| Prefetching | Predictable navigation | `<Link prefetch>`, `router.prefetch()` |
| Container queries | Component responsiveness | `@container` instead of JS-based resize logic |
| Content-visibility | Long pages | `content-visibility: auto` for below-fold sections |

### Performance Anti-Patterns
- **Do NOT** `useMemo`/`useCallback` everything (premature optimization — profile first)
- **Do NOT** import entire icon/component libraries (tree-shake or cherry-pick)
- **Do NOT** render large lists without virtualization
- **Do NOT** load all data on page mount (paginate, lazy-load)
- **Do NOT** block render with synchronous data fetching (use Suspense)
- **Do NOT** use barrel files that re-export everything (kills tree-shaking)
- **Do NOT** use dynamic class names with Tailwind (`bg-${color}-500` — not purgeable)

## Next-Generation Interaction Patterns

Read `~/.claude/knowledge/next-gen-interaction-patterns.md` for the full reference.

### Key Patterns for Web Frontend

**Multimodal Input**: Support touch + voice + keyboard simultaneously. Persistent voice input button in search/input areas. All three converge at the same action dispatcher.

**Social-Feed Vertical Scroll**: Content-first cards with `scroll-snap-type: y mandatory`. Swipe-to-action with horizontal gesture detection. Pull-to-refresh with spring animation. Infinite scroll with intelligent preloading.

**Bottom Sheet Navigation (Mobile)**: Replace top dropdowns and modals with bottom sheets. Thumb-zone optimized (primary actions in bottom 40% of screen). Drag handle for sheet resize (peek → half → full).

**Streaming AI Content**: Typewriter effect with SSE/WebSocket streaming. ARIA `live="polite"` on response containers. Content container height transitions (smooth expand). Skeleton → shimmer → real content crossfade.

**Gesture-Driven Interactions**: Swipe-to-dismiss, pull-to-refresh, drag-to-reorder. Always provide non-gesture alternative (button, ⋯ menu) for accessibility. Use velocity threshold for gesture detection (not just distance).

**Adaptive Layouts**: Container queries over viewport breakpoints where possible. Fluid values with `clamp()` for continuous adaptation. Context-aware restructuring (time-of-day, device orientation).

## Testing

### Test Strategy
```
Unit tests:        Pure functions, hooks, utilities (Jest + React Testing Library)
Component tests:   Render + interact + assert (React Testing Library)
Integration tests: Page-level flows with mocked API (MSW)
E2E tests:         Critical user journeys (Playwright or Cypress)
Visual regression: Screenshot comparison (Chromatic or Percy)
```

### React Testing Library Principles
```
- Query by role, label, or text — NOT by test ID or class name
- Test behavior, not implementation
- Simulate user interactions (click, type, select), not state changes
- Assert on visible output, not internal component state
- getByRole('button', { name: 'Submit' }) over getByTestId('submit-btn')
```

### Mock Service Worker (MSW)
```
- Mock API responses at the network level, not the module level
- Define handlers once, reuse across tests
- Override per-test for error scenarios
- MSW works with both Jest and Playwright
```

### What to Test
```
- User interactions (click, form submit, navigation)
- Conditional rendering (loading, error, empty states)
- Accessibility (jest-axe assertions on every component)
- Edge cases (long text, empty data, network errors)
```

### What NOT to Test
```
- Implementation details (state values, hook internals)
- Third-party library behavior (TanStack Query caching logic)
- CSS styling (use visual regression tools instead)
- Static content without logic
```

## Phase Output

```
Verdict: PATTERNS_APPLIED (informational — no pipeline gate)
Next: Continue with /build-implementation using these patterns
Artifacts: [component architecture, state management setup, accessibility audit, performance baseline]
```
$ARGUMENTS
