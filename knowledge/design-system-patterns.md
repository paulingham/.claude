# Design System Patterns

## Design Token Architecture

### Token Layers
```
Primitive tokens (raw values):
  --color-blue-500: hsl(220, 90%, 56%)
  --font-size-16: 1rem
  --spacing-4: 1rem
  --radius-8: 0.5rem

Semantic tokens (purpose-mapped):
  --color-primary: var(--color-blue-500)
  --color-destructive: var(--color-red-500)
  --color-muted: var(--color-gray-400)
  --text-body: var(--font-size-16)
  --space-element: var(--spacing-4)

Component tokens (scoped):
  --button-bg: var(--color-primary)
  --button-radius: var(--radius-8)
  --card-padding: var(--space-element)
```

**Rule:** Components reference semantic tokens, never primitives. Theme changes swap semantic → primitive mappings. Components never change.

### Tailwind Integration
```typescript
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
        destructive: { DEFAULT: 'hsl(var(--destructive))', foreground: 'hsl(var(--destructive-foreground))' },
        muted: { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },
        accent: { DEFAULT: 'hsl(var(--accent))', foreground: 'hsl(var(--accent-foreground))' },
        card: { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },
        border: 'hsl(var(--border))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
      },
    },
  },
};
```

## Typography Scale

### Major Third (1.25 ratio) — recommended for most apps
```css
--text-xs:   clamp(0.64rem, 0.58rem + 0.29vw, 0.80rem);
--text-sm:   clamp(0.80rem, 0.73rem + 0.36vw, 1.00rem);
--text-base: clamp(1.00rem, 0.91rem + 0.45vw, 1.25rem);
--text-lg:   clamp(1.25rem, 1.14rem + 0.57vw, 1.56rem);
--text-xl:   clamp(1.56rem, 1.42rem + 0.71vw, 1.95rem);
--text-2xl:  clamp(1.95rem, 1.78rem + 0.89vw, 2.44rem);
--text-3xl:  clamp(2.44rem, 2.22rem + 1.11vw, 3.05rem);
```

### Line Height
```
Headings:   1.1 (tight)
Body text:  1.5 (comfortable)
Long-form:  1.7 (relaxed)
UI labels:  1.3 (compact)
```

### Font Pairing Strategy
```
Display + Body pairing:
  - Display: distinctive, personality-driven (headings only)
  - Body: highly legible, neutral (everything else)

Examples:
  - Instrument Serif + Inter (elegant + clean)
  - Space Grotesk + DM Sans (modern + friendly)
  - Fraunces + Source Sans 3 (editorial + readable)

Max 2-3 font families. Load via next/font for zero layout shift.
```

### Letter Spacing
```
Large text (>24px):  -0.02em (tighten — large text has natural spacing)
Body text:           0 (default)
Small text (<14px):  +0.01em (loosen — small text needs air)
All-caps labels:     +0.05em to +0.1em (tracking for readability)
```

## Spacing System

### Base Unit: 4px (0.25rem)
```
Scale (Tailwind classes → values):
  0.5  →  2px   (hairline gaps, icon-to-text)
  1    →  4px   (tight component internals)
  1.5  →  6px   (compact padding)
  2    →  8px   (standard component padding)
  3    →  12px  (related element spacing)
  4    →  16px  (section content padding)
  6    →  24px  (between form fields)
  8    →  32px  (between sections)
  12   →  48px  (major section dividers)
  16   →  64px  (page section spacing)
  24   →  96px  (hero spacing)
```

### When to Use Each Size
```
2-4px:   Icon-to-label gap, checkbox-to-text, tight button groups
8px:     Padding inside small components (badges, chips)
12px:    Padding inside medium components (inputs, buttons)
16px:    Card padding, list item padding
24px:    Between form fields, between list items
32px:    Between sections within a card, sidebar item groups
48-64px: Between page sections
96px+:   Hero/marketing spacing
```

### Optical Alignment
```
Mathematical alignment is not always visually correct.
- Text next to icons: align by optical center, not bounding box
- First/last items in a list: may need reduced margin (padding handles edge)
- Rounded buttons: increase horizontal padding ~20% (curves eat visual space)
```

## Color System

### HSL-Based Palette Generation
```
From a brand hue (e.g., blue = 220°):

Primary scale (10 shades):
  50:  hsl(220, 90%, 97%)   — barely tinted background
  100: hsl(220, 85%, 93%)   — subtle hover
  200: hsl(220, 80%, 85%)   — border, divider
  300: hsl(220, 75%, 72%)   — muted text on dark bg
  400: hsl(220, 70%, 60%)   — secondary text
  500: hsl(220, 65%, 50%)   — primary brand color
  600: hsl(220, 70%, 42%)   — hover on primary
  700: hsl(220, 75%, 35%)   — active on primary
  800: hsl(220, 80%, 25%)   — dark text
  900: hsl(220, 85%, 15%)   — near-black
  950: hsl(220, 90%, 8%)    — darkest

Derive secondary/accent:
  Complementary: hue + 180° (high contrast, vibrant)
  Analogous: hue ± 30° (harmonious, subtle)
  Triadic: hue + 120°, hue + 240° (balanced, diverse)
```

### Semantic Color Mapping
```
--color-primary:     brand blue (actions, links, focus)
--color-secondary:   muted purple (secondary actions)
--color-accent:      vibrant teal (highlights, badges)
--color-destructive: red (delete, error, danger)
--color-success:     green (confirmation, valid)
--color-warning:     amber (caution, attention)
--color-muted:       gray (disabled, placeholder, secondary text)
```

### WCAG Contrast at Token Level
```
Enforce at definition time, not component time:
  --foreground on --background: must meet 4.5:1 (AA normal text)
  --primary-foreground on --primary: must meet 4.5:1
  --muted-foreground on --background: must meet 4.5:1

Test every semantic pair. If contrast fails, adjust the shade — do not ship.
```

## Dark Mode

```
Dark mode is NOT inverted light mode. It is a separate token layer.

Key differences:
  Background:  dark gray (not pure black — hsl(220, 15%, 10%))
  Surfaces:    slightly lighter gray (elevation via lightness, not shadow)
  Shadows:     minimal or none (dark backgrounds don't show shadows well)
  Text:        off-white (not pure white — reduces eye strain)
  Colors:      desaturated compared to light mode (bright colors vibrate on dark bg)
  Borders:     lighter, more visible (compensate for low-contrast surfaces)

Implementation:
  Use CSS custom properties in :root and .dark (or [data-theme="dark"]):
  :root { --background: 0 0% 100%; --foreground: 220 15% 10%; }
  .dark { --background: 220 15% 10%; --foreground: 0 0% 93%; }

  Tailwind: dark: prefix classes with class-based dark mode strategy
  Persistence: localStorage + system preference detection
```

## Border Radius Scale
```
--radius-none: 0
--radius-sm:   0.25rem  (4px — subtle rounding)
--radius-md:   0.5rem   (8px — standard components)
--radius-lg:   0.75rem  (12px — cards, dialogs)
--radius-xl:   1rem     (16px — prominent elements)
--radius-2xl:  1.5rem   (24px — hero cards)
--radius-full: 9999px   (pills, avatars)

Nested radius rule:
  inner radius = outer radius - gap between elements
  Card (radius-lg 12px) with 8px padding → inner content radius = 4px (radius-sm)
```

## Shadow / Elevation System
```
Level 0: no shadow (flat, default)
Level 1: 0 1px 2px hsl(var(--shadow) / 0.05)           — subtle lift (cards)
Level 2: 0 2px 4px hsl(var(--shadow) / 0.08)            — hover state
Level 3: 0 4px 8px hsl(var(--shadow) / 0.10)            — dropdown, popover
Level 4: 0 8px 16px hsl(var(--shadow) / 0.12)           — modal, dialog
Level 5: 0 16px 32px hsl(var(--shadow) / 0.15)          — toast, notification

Shadow color: derived from palette (not black). Use foreground hue at low opacity.
Dark mode: reduce or remove shadows. Use border or surface tint for elevation instead.
```

## Component Generation with CVA

```typescript
// class-variance-authority for type-safe variant components
import { cva, type VariantProps } from 'class-variance-authority';

const button = cva(
  'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        outline: 'border border-input bg-background hover:bg-accent hover:text-accent-foreground',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
      },
      size: {
        sm: 'h-8 px-3 text-xs',
        md: 'h-10 px-4',
        lg: 'h-12 px-6 text-base',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: { variant: 'default', size: 'md' },
  }
);
```

## Brand Brief Interpretation

```
Given a brand brief or inspiration, extract:

1. Dominant hue → primary color, generate full scale
2. Energy level → spacing density (spacious = luxury, compact = productivity)
3. Personality → border radius (sharp = professional, rounded = friendly, pill = playful)
4. Voice → font pairing (serif = editorial, geometric sans = modern, rounded sans = approachable)
5. Contrast preference → shadow depth (flat = minimal, elevated = material)

No brief provided? Default to:
  - Primary: blue (trustworthy, universally safe)
  - Spacing: comfortable (16px base padding)
  - Radius: md (8px — friendly but professional)
  - Font: Inter (neutral, legible, free)
  - Shadows: Level 1-2 (subtle depth)
```
