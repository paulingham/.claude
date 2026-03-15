---
name: "Accessibility First"
description: "WCAG 2.1 AA enforcement: semantic HTML, ARIA, keyboard navigation, contrast, focus management. Use for all frontend and mobile development."
---

# Accessibility First

## What This Skill Does

Enforces WCAG 2.1 AA compliance as a first-class requirement, not an afterthought.

## Semantic HTML

- Use correct elements: `<button>` for actions, `<a>` for navigation, `<input>` for data
- Structure with landmarks: `<nav>`, `<main>`, `<aside>`, `<footer>`, `<header>`
- Heading hierarchy: one `<h1>` per page, sequential levels (no skipping h2 to h4)
- Lists for groups: `<ul>`/`<ol>` for navigation menus and item collections
- `<table>` with `<thead>`, `<th scope>` for tabular data only

## ARIA Patterns

- ARIA is a last resort — prefer native HTML semantics
- Live regions for dynamic content: `aria-live="polite"` for updates, `"assertive"` for errors
- Expanded/collapsed: `aria-expanded` on toggle triggers
- Dialogs: `role="dialog"`, `aria-modal="true"`, `aria-labelledby`
- Tabs: `role="tablist"`, `role="tab"`, `role="tabpanel"`, `aria-selected`

## Keyboard Navigation

- All interactive elements focusable and operable via keyboard
- Visible focus indicators (min 2px outline, 3:1 contrast against adjacent)
- Logical tab order matching visual layout
- Skip-to-content link as first focusable element
- Escape key closes overlays, returns focus to trigger
- Arrow keys for widget navigation (tabs, menus, listboxes)

## Color and Contrast

- Text: 4.5:1 contrast ratio minimum (3:1 for large text 18px+/14px bold+)
- UI components: 3:1 contrast against adjacent colors
- Never convey information by color alone — use icons, text, or patterns
- Test with color blindness simulators (protanopia, deuteranopia, tritanopia)

## Focus Management

- Move focus to new content on route changes (heading or main content)
- Return focus to trigger when closing modals/dialogs
- Trap focus within modal dialogs
- Announce loading states with `aria-busy` and live regions
- Skip repetitive navigation with skip links

## Forms

- Every input has a visible `<label>` (not just placeholder)
- Error messages linked with `aria-describedby`
- Required fields marked with `aria-required="true"` and visible indicator
- Group related fields with `<fieldset>` and `<legend>`
- Autocomplete attributes for common fields (`name`, `email`, `tel`)

## Testing

- **Static analysis**: eslint-plugin-jsx-a11y (catches 30% of issues)
- **Component tests**: jest-axe assertions in every component test
- **Integration**: @axe-core/react for runtime violation detection
- **Manual**: Keyboard-only navigation, screen reader testing (VoiceOver, NVDA)
- **Automated**: Lighthouse accessibility audit in CI (score >= 90)
