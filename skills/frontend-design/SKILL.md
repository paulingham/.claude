---
name: "Frontend Design"
description: "Design-quality frontend principles: typography, color, layout, motion. Produces distinctive UI, not cookie-cutter templates. Use when implementing any user-facing frontend."
---

# Frontend Design

## What This Skill Does

Enforces design-quality standards that produce distinctive, polished interfaces instead of generic SaaS templates.

## Typography

- Choose distinctive typefaces — NOT Inter, Roboto, or system defaults for headings
- Define a type scale using CSS custom properties: `--text-xs` through `--text-6xl`
- Use `clamp()` for fluid responsive sizing
- Maintain consistent line-height ratios: 1.1 for headings, 1.5-1.7 for body
- Limit to 2-3 font families maximum

## Color

- Build a full palette with CSS custom properties: `--color-{name}-{shade}`
- Design for both light and dark modes from the start
- Never use generic purple/blue gradients as hero backgrounds
- Ensure 4.5:1 contrast ratio minimum (WCAG AA)
- Use semantic color tokens: `--color-primary`, `--color-destructive`, `--color-muted`

## Layout

- Generous whitespace — when in doubt, add more space
- Strong visual hierarchy through size, weight, and spacing contrast
- Intentional asymmetry over rigid grids when it serves the content
- Max content width for readability (65-75 characters for prose)
- Use CSS Grid for 2D layouts, Flexbox for 1D alignment

## Motion

- CSS transitions for micro-interactions (hover, focus, state changes)
- Framer Motion for orchestrated animations (page transitions, reveals)
- Staggered animations for lists and grids (`staggerChildren`)
- Spring physics over linear easing (`type: "spring"`)
- Always respect `prefers-reduced-motion: reduce`

## Anti-Patterns

- No generic card grids with identical spacing
- No hero-section-with-gradient-and-centered-text defaults
- No cookie-cutter SaaS landing page patterns
- No decoration-only animations that serve no UX purpose
- No color choices that look "nice" but fail contrast checks
