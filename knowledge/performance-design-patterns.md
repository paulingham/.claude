# Performance Design Patterns

## Priority: CRITICAL (fix these first)

### Request Waterfalls

The #1 performance killer. Most developers reach for `useMemo` when the real bottleneck is sequential network requests.

```
WATERFALL (bad):
  Component mounts → fetch user (200ms)
    → fetch user's projects (200ms)
      → fetch project stats (200ms)
  Total: 600ms sequential

PARALLEL (good):
  Component mounts → Promise.all([
    fetch user,        (200ms)
    fetch projects,    (200ms) ← runs simultaneously
    fetch stats        (200ms)
  ])
  Total: 200ms parallel
```

**Detection**: Any `useEffect` that fetches data depending on another `useEffect`'s result.

**Fixes**:
```
1. Parallel data loading: Promise.all, useSuspenseQueries
2. Route-level preloading: loader functions (Next.js, Remix, TanStack Router)
3. Prefetch on hover: router.prefetch(), queryClient.prefetchQuery()
4. Streaming: React Suspense boundaries with server-side streaming
5. Stale-while-revalidate: show cached data instantly, refresh in background
```

**Next.js specifics**:
```
- Parallel routes: fetch multiple data sources simultaneously
- Streaming with Suspense: show UI progressively as data arrives
- generateStaticParams: pre-render known pages at build time
- Route segments: each segment fetches independently
```

### Bundle Size

```
RULE: If a page imports a module, the user downloads it. Period.

Top offenders:
  moment.js (300KB) → date-fns (tree-shakeable, import only what you use)
  lodash (70KB)     → lodash-es (tree-shakeable) or native methods
  Chart.js (200KB)  → Recharts or lightweight-charts (tree-shakeable)
  Material UI full  → import { Button } from '@mui/material/Button' (not '@mui/material')
```

**Barrel File Anti-Pattern**:
```tsx
// BAD: barrel re-exports defeat tree-shaking
// components/index.ts
export { Button } from './button';
export { Input } from './input';
export { DataGrid } from './data-grid'; // 150KB — pulled in even if unused

// GOOD: direct imports
import { Button } from '@/components/ui/button';
```

**Dynamic Imports**:
```tsx
// Heavy components loaded only when needed
const DataGrid = dynamic(() => import('./data-grid'), {
  loading: () => <TableSkeleton />,
  ssr: false, // if not needed server-side
});

// Route-level code splitting (automatic in Next.js App Router)
// Each page.tsx is a separate chunk
```

**Analysis tools**:
```
@next/bundle-analyzer — visual bundle inspection
source-map-explorer — dependency size mapping
Import Cost (VS Code extension) — inline size display
```

### Layout Thrashing

```
THRASHING: DOM reads interleaved with DOM writes force reflows.

BAD:
  elements.forEach(el => {
    const height = el.offsetHeight;  // FORCED REFLOW (read)
    el.style.height = height + 10;   // write
  });

GOOD:
  // Batch reads, then batch writes
  const heights = elements.map(el => el.offsetHeight); // all reads
  elements.forEach((el, i) => {
    el.style.height = heights[i] + 10; // all writes
  });

CSS CONTAINMENT:
  .isolated-section { contain: layout paint; }
  // Browser skips this section when reflowing other parts

WILL-CHANGE (last resort):
  .animating { will-change: transform, opacity; }
  // Promotes to GPU layer — use sparingly, remove after animation
```

## Priority: HIGH

### Re-render Optimization

**When React.memo HELPS** (all must be true):
- Component renders frequently (parent re-renders often)
- Component is expensive (deep tree, complex calculations)
- Props are referentially stable (primitives, or memoized objects)

**When React.memo DOESN'T HELP**:
- Component is cheap to render (few elements, no calculation)
- Parent rarely re-renders
- Props change on every render (new objects/arrays created inline)

```tsx
// ONLY memoize after measuring with React DevTools Profiler
const ExpensiveChart = memo(function ExpensiveChart({ data }: Props) {
  // 50+ SVG elements, complex layout calculation
  return <svg>...</svg>;
});

// DON'T memoize
// function SimpleLabel({ text }: { text: string }) {
//   return <span>{text}</span>; // trivial render, memo overhead > render cost
// }
```

**useMemo/useCallback rules**:
```
1. Never use prophylactically ("just in case")
2. Use when: value is expensive to compute AND used in dependency array
3. Use when: reference stability matters (memo'd child prop, effect dependency)
4. Profile first: React DevTools → Profiler → "Why did this render?"
```

### Image Performance

```
Format priority: AVIF > WebP > PNG (photos) / SVG (icons)

Next.js Image:
  <Image src={photo} alt="..." width={800} height={600}
    sizes="(max-width: 768px) 100vw, 50vw"
    placeholder="blur"
    blurDataURL={blurHash}
    loading="lazy"  // default — below fold
    priority        // above fold — preloads
  />

Responsive images (non-Next.js):
  <picture>
    <source srcSet="photo.avif" type="image/avif" />
    <source srcSet="photo.webp" type="image/webp" />
    <img src="photo.jpg" alt="..." loading="lazy"
      srcSet="photo-400.jpg 400w, photo-800.jpg 800w, photo-1200.jpg 1200w"
      sizes="(max-width: 768px) 100vw, 50vw" />
  </picture>
```

### Font Performance

```
next/font (zero CLS):
  import { Outfit, Source_Serif_4 } from 'next/font/google';
  const display = Outfit({ subsets: ['latin'], weight: ['700'], display: 'swap' });
  const body = Source_Serif_4({ subsets: ['latin'], weight: ['400'], display: 'swap' });

Variable fonts (fewer requests):
  // One file instead of 4+ weight files
  const outfit = Outfit({ subsets: ['latin'], variable: '--font-display' });

Subsetting: Only load 'latin' unless i18n required (saves 50-80% of font file)
font-display: swap — text visible immediately with fallback font
Preconnect to Google Fonts: <link rel="preconnect" href="https://fonts.gstatic.com" />
```

## Priority: MEDIUM

### State Management Performance

```
ZUSTAND: Subscribe to slices, not the whole store
  // BAD: re-renders on ANY store change
  const store = useStore();

  // GOOD: re-renders only when 'count' changes
  const count = useStore((state) => state.count);
  const increment = useStore((state) => state.increment);

CONTEXT: Split rarely-changing from frequently-changing
  // BAD: one context for theme + mouse position
  <AppContext value={{ theme, mouseX, mouseY }}>

  // GOOD: separate contexts
  <ThemeContext value={theme}>      // changes rarely
  <PointerContext value={{ x, y }}> // changes on every move

TANSTACK QUERY: Server state is NOT client state
  // DON'T copy server data into Zustand/Redux
  // DO use useQuery — it handles caching, refetching, stale data
```

### Virtualization

```
RULE: Lists with >100 items MUST be virtualized.

@tanstack/react-virtual (recommended — newer, lighter):
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 48,
    overscan: 5,
  });

  // Only renders visible items + overscan buffer
  <div ref={scrollRef} style={{ height: '600px', overflow: 'auto' }}>
    <div style={{ height: virtualizer.getTotalSize() }}>
      {virtualizer.getVirtualItems().map(row => (
        <div key={row.key} style={{ transform: `translateY(${row.start}px)` }}>
          {items[row.index]}
        </div>
      ))}
    </div>
  </div>

For grids: useVirtualizer with both row and column dimensions
For infinite scroll: combine with TanStack Query's useInfiniteQuery
```

### CSS Performance

```
CONTAINER QUERIES over JS-based responsive logic:
  @container (min-width: 400px) { .card { flex-direction: row; } }
  // Component adapts to its container, not the viewport
  // No JS, no resize observers, pure CSS

TAILWIND: Already purges unused classes. But watch for:
  // BAD: dynamic class names (not purgeable)
  className={`bg-${color}-500`}

  // GOOD: complete class names
  className={color === 'blue' ? 'bg-blue-500' : 'bg-red-500'}

CONTENT-VISIBILITY for long pages:
  .below-fold-section {
    content-visibility: auto;
    contain-intrinsic-size: 0 500px; /* estimated height */
  }
  // Browser skips rendering until section is near viewport
```

## Priority: LOW (optimize only when measured)

### Resource Hints
```html
<link rel="preconnect" href="https://api.example.com" />
<link rel="dns-prefetch" href="https://cdn.example.com" />
<link rel="preload" href="/fonts/display.woff2" as="font" crossorigin />
<link rel="prefetch" href="/dashboard" />  <!-- likely next navigation -->
```

### Service Worker Caching
```
Cache-first:    Static assets (JS, CSS, fonts) — immutable, hashed filenames
Network-first:  API responses — fresh data preferred, fallback to cache
Stale-while-revalidate: HTML pages — show cached, refresh in background
```

### HTTP Headers
```
Static assets:     Cache-Control: public, max-age=31536000, immutable
API responses:     Cache-Control: private, no-cache (+ ETag for conditional)
HTML:              Cache-Control: no-cache (always validate, SWR from CDN)
```
