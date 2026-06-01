---
name: "design-system-init"
description: "Use when user wants to Generate design tokens, primitive components, and dark mode for a project. Creates Tailwind config extensions, CSS custom properties, and cva-based component primitives."
context: fork
agent: frontend-engineer
argument-hint: "Optional: brand brief or inspiration (colors, personality, font preferences)"
---

# Design System Init

## What This Skill Does

Generates a complete design system foundation for a project: design tokens (colors, typography, spacing, radius, shadows), CSS custom properties, Tailwind config extensions, primitive UI components (Button, Input, Badge, Avatar, Card), and dark mode support. Produces production-ready files, not stubs.

## When to Invoke

- Project setup (no design system exists)
- Before any frontend build work in a new project
- When refactoring from ad-hoc styles to a systematic approach

## Prerequisites

- Tailwind CSS configured in the project
- Read `~/.claude/knowledge/design-system-patterns.md` for the full token architecture
- Read `~/.claude/knowledge/creative-direction-database.md` for curated font/palette alternatives

## Process

### Step 1: Assess Current State

```
Check for existing design system:
- tailwind.config.ts → theme.extend section
- CSS custom properties (--color-*, --spacing-*)
- Component library (components/ui/ directory)
- Design token files (tokens.css, variables.css)

If exists: enhance and systematize (don't replace)
If absent: generate from scratch
```

### Step 2: Gather Brand Inputs

**Priority order for design inputs** (first match wins):

1. **Design brief exists**: Check `pipeline-state/{task-id}/design-brief.md` (output from `/harness:creative-direction`). If found, extract: font pairing, palette HSL values, layout archetype, interaction paradigm. This is the primary source — skip to Step 3.

2. **User provides a brand brief**: Extract dominant hue → primary color scale, energy level → spacing density, personality → border radius style, voice → font pairing.

3. **No brief provided**: Reference `~/.claude/knowledge/creative-direction-database.md` and select curated alternatives. **Do NOT default to Inter + blue.** Instead:
   - Select a font pairing from the database matching the product type
   - Select a palette from the industry/mood archetypes
   - Select a layout archetype that fits the project

4. **Last resort** (database unavailable): Use sensible but non-generic defaults:
```
Primary:  teal (hsl 175° — modern trust, NOT default blue)
Spacing:  comfortable (16px base)
Radius:   lg (12px — approachable, not the generic 8px)
Font:     Outfit + Plus Jakarta Sans (warm modern, NOT Inter)
Shadows:  subtle (level 1-2)
```

### Step 2.5: Anti-Convergence Validation

After selecting fonts and colors (from any source), verify against banned defaults:
```
- [ ] Font is NOT Inter, Roboto, Open Sans, Arial, Helvetica, Lato, or Montserrat
- [ ] Primary is NOT hsl 210-230 (default blue range)
- [ ] Radius is NOT 8px on every element (vary by component importance)
```
If any check fails AND no explicit brand requirement mandates it: pick an alternative from `creative-direction-database.md`.

### Step 3: Generate Design Tokens

**Create `styles/tokens.css`:**
```css
:root {
  /* Color primitives (generated from brand hue) */
  --primary: [H] [S]% [L]%;
  --primary-foreground: 0 0% 100%;
  /* ... full scale: secondary, accent, destructive, muted, background, foreground */

  /* Typography */
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-display: '[Display Font]', serif;

  /* Spacing (base 4px) */
  --space-1: 0.25rem;
  /* ... full scale */

  /* Radius */
  --radius-sm: 0.25rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;

  /* Shadows */
  --shadow: 220 15% 15%;
}

.dark {
  --background: 220 15% 10%;
  --foreground: 0 0% 93%;
  /* ... dark mode overrides */
}
```

**Extend `tailwind.config.ts`** with semantic color mappings, radius scale, and font families (per design-system-patterns.md).

### Step 4: Generate Primitive Components

Using `cva` (class-variance-authority) for type-safe variants:

**Generate these primitives in `components/ui/`:**

| Component | Variants | File |
|-----------|----------|------|
| Button | default, destructive, outline, ghost, link × sm, md, lg, icon | button.tsx |
| Input | default, error × sm, md, lg | input.tsx |
| Badge | default, secondary, destructive, outline | badge.tsx |
| Avatar | sm, md, lg, xl | avatar.tsx |
| Card | default (with CardHeader, CardContent, CardFooter) | card.tsx |
| Skeleton | (animated placeholder) | skeleton.tsx |

Each component:
- Uses design tokens exclusively (no hardcoded values)
- Has a `className` prop for composition (via `cn()` utility)
- Follows the 50-line file limit
- Is accessible (proper ARIA, keyboard support, focus management)
- Supports dark mode via token layer

### Step 5: Generate Utility Function

```typescript
// lib/utils.ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

### Step 6: Generate Dark Mode Toggle

```typescript
// Hook for dark mode with persistence
function useTheme() {
  // Detect system preference
  // Persist user choice in localStorage
  // Apply .dark class to html element
  // Return { theme, setTheme, toggleTheme }
}
```

### Step 7: Verify

```
- [ ] All tokens defined in tokens.css
- [ ] Tailwind config references tokens correctly
- [ ] Each primitive component renders in both light and dark mode
- [ ] No hardcoded colors, spacing, or typography in components
- [ ] All components pass jest-axe accessibility checks
- [ ] Components compose correctly (Button inside Card, Input in Form)
```

## Phase Output

```
Verdict: DESIGN_SYSTEM_READY
Next: Use primitives in /harness:build-implementation. Extend with compound components as needed.
Artifacts: [tokens.css, tailwind.config.ts extensions, components/ui/ primitives, dark mode hook]
Tokens: [primary hue, font pairing, spacing density, radius style]
```
$ARGUMENTS
