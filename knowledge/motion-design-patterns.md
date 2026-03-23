# Motion Design Patterns

## Motion Principles

Animation communicates. It does not decorate.

### Three Valid Purposes
```
1. ORIENT:   Help user understand spatial relationships
             Page transitions, navigation, element repositioning

2. CAUSE:    Show cause and effect
             Button press → card appears, swipe → item dismissed

3. ATTENTION: Draw focus to something important
              Notification badge, validation error, new item in list

If an animation serves NONE of these → remove it.
```

## Duration Scale

```
Micro-interactions:     100-200ms   (button press, toggle, checkbox)
Emphasis transitions:   200-400ms   (card expand, accordion, tooltip)
Complex choreography:   400-700ms   (page transition, modal enter, list reorder)
Maximum:                700ms       (anything longer feels sluggish)

Rule: exit animations are faster than enter animations
  Enter: 250ms (user needs to see where it came from)
  Exit:  150ms (user already knows where it went)
```

## Easing

### Spring Physics (Preferred)

```typescript
// Framer Motion spring presets
const snappy   = { type: "spring", stiffness: 500, damping: 30 };   // UI controls
const smooth   = { type: "spring", stiffness: 300, damping: 30 };   // Standard
const bouncy   = { type: "spring", stiffness: 200, damping: 15 };   // Playful
const gentle   = { type: "spring", stiffness: 120, damping: 20 };   // Large elements
```

### CSS Easing (When Springs Are Not Available)
```css
/* Standard (most animations) */
transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);

/* Decelerate (enter animations — element arrives) */
transition-timing-function: cubic-bezier(0, 0, 0.2, 1);

/* Accelerate (exit animations — element leaves) */
transition-timing-function: cubic-bezier(0.4, 0, 1, 1);

/* NEVER use 'linear' for UI motion — feels robotic */
```

## Framer Motion Patterns

### Layout Animations
```tsx
// Automatic animation when layout changes
<motion.div layout>
  {isExpanded && <motion.p layout>Expanded content</motion.p>}
</motion.div>
```

### Shared Layout Animations
```tsx
// Card → detail page transition (shared element)
<motion.div layoutId={`card-${id}`}>
  <h2>{title}</h2>
</motion.div>
// Same layoutId on the detail page → smooth morph transition
```

### Enter/Exit Animations
```tsx
<AnimatePresence mode="wait">
  {isVisible && (
    <motion.div
      key="modal"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.2 }}
    >
      {children}
    </motion.div>
  )}
</AnimatePresence>
```

### Staggered Lists
```tsx
const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.05 }  // 50ms between items
  }
};
const item = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0 }
};

<motion.ul variants={container} initial="hidden" animate="show">
  {items.map(i => <motion.li key={i.id} variants={item}>{i.name}</motion.li>)}
</motion.ul>
```

### Gesture Animations
```tsx
<motion.div
  whileHover={{ scale: 1.02 }}     // Subtle lift on hover
  whileTap={{ scale: 0.98 }}       // Press-down on click
  transition={snappy}
>
  <Card />
</motion.div>
```

## Skeleton Loading

```
Match the actual content layout:
  ┌──────────────────────────────┐
  │  ████████████  ██████        │  ← Title + badge
  │  ██████████████████████████  │  ← Description line 1
  │  ██████████████████          │  ← Description line 2
  │                              │
  │  ████  ████████  ████████    │  ← Metadata
  └──────────────────────────────┘

Rules:
  - Show within 200ms if data not ready
  - Pulse animation (subtle opacity oscillation, not shimmer)
  - Match exact dimensions of real content (prevents layout shift)
  - Transition: fade from skeleton to content (not instant swap)
  - 3-5 skeleton items for lists (not 20)
```

### Implementation
```tsx
function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn("animate-pulse rounded-md bg-muted", className)} />
  );
}

// Usage:
<Skeleton className="h-6 w-48" />     // Title
<Skeleton className="h-4 w-full" />    // Body line
<Skeleton className="h-4 w-3/4" />     // Shorter body line
<Skeleton className="h-10 w-10 rounded-full" /> // Avatar
```

## Page Transitions

```
Lateral navigation (tabs, siblings):
  → Slide left/right in direction of tab

Hierarchical navigation (drill-down):
  → Forward: slide left + fade in
  → Back: slide right + fade in

Modal/dialog:
  → Enter: fade + scale from 0.95 to 1.0
  → Exit: fade + scale from 1.0 to 0.95

Bottom sheet (mobile):
  → Enter: slide up from bottom
  → Exit: slide down, or swipe to dismiss

Shared element (card → detail):
  → Morph: card grows to fill the page (layoutId)
```

## Gesture Interactions (Mobile)

```
Swipe to dismiss:   horizontal swipe removes item (with undo toast)
Pull to refresh:    overscroll triggers refresh (with bounce)
Long press:         context menu (with haptic feedback if available)
Pinch to zoom:      images, maps (with min/max bounds)

Spring-back physics:
  - Gesture starts: element follows finger
  - Released before threshold: springs back to original position
  - Released after threshold: completes the action (dismiss/delete)
  - Velocity matters: fast flick completes even if distance is short
```

## Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

```
Reduced motion means INSTANT, not SLOW:
  - Opacity: 0 → 1 instantly (no fade)
  - Position: final position instantly (no slide)
  - Scale: final size instantly (no zoom)
  - Provide equivalent information without motion
  - Progress bar instead of animated loader
  - Static icon instead of spinning icon
```

## Anti-Patterns

```
- Animation for its own sake (bouncing logo, decorative parallax)
- Duration > 700ms (feels sluggish, blocks interaction)
- Linear easing (robotic, unnatural)
- Animating on page load (user didn't trigger it, feels slow)
- Different animation for same action in different places (inconsistent)
- Blocking interaction during animation (user can't click while animating)
- No reduced motion support (accessibility violation)
```
