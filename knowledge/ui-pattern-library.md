# UI Pattern Library

## Screen Type Patterns

### Dashboard
```
Anatomy:
  ┌─────────────────────────────────────────┐
  │  Filter Bar  │  Date Range  │  Refresh  │
  ├─────────┬─────────┬─────────┬───────────┤
  │  KPI 1  │  KPI 2  │  KPI 3  │  KPI 4   │
  ├─────────────────────┬───────────────────┤
  │                     │                   │
  │   Primary Chart     │  Supporting       │
  │   (2/3 width)       │  Chart (1/3)      │
  │                     │                   │
  ├─────────────────────┴───────────────────┤
  │  Data Table (recent activity)           │
  └─────────────────────────────────────────┘

KPI cards: value + label + delta (↑12% vs last period) + sparkline
Primary chart: largest, most important metric (line or area)
Supporting: secondary metric or breakdown (donut, bar)
Color coding: consistent across all charts on the page
```

### Data Table
```
Anatomy:
  ┌──────────────────────────────────────────┐
  │  Search  │  Filter  │  Bulk Actions  │+  │
  ├──────────────────────────────────────────┤
  │  □ │ Name ▲ │ Status │ Date │ Actions   │
  │  □ │ Item 1 │ Active │ Mar  │ ⋯         │
  │  □ │ Item 2 │ Draft  │ Feb  │ ⋯         │
  │  ■ │ Item 3 │ Active │ Jan  │ ⋯         │
  ├──────────────────────────────────────────┤
  │  Showing 1-10 of 48  │  ← 1 2 3 ... →  │
  └──────────────────────────────────────────┘

Features:
  - Sortable columns (click header, toggle asc/desc)
  - Filterable (dropdown or chip filters above table)
  - Searchable (debounced, 300ms delay)
  - Selectable rows (checkbox column, bulk action bar appears)
  - Row actions (⋯ menu: edit, duplicate, delete)
  - Expandable rows (click to show detail panel)
  - Pagination (prefer numbered pages for data tables, infinite scroll for feeds)

Responsive (mobile):
  - Show only priority columns (name + status)
  - Switch to card view below 768px
  - Swipe for row actions on mobile

Loading: skeleton rows (3-5 rows matching column layout)
Empty: illustration + "No [items] found" + primary CTA
```

### Form
```
Anatomy:
  ┌──────────────────────────────┐
  │  Form Title                  │
  │  Subtitle / description      │
  │                              │
  │  Label                       │
  │  ┌────────────────────────┐  │
  │  │ Input                  │  │
  │  └────────────────────────┘  │
  │  Helper text                 │
  │                              │
  │  Label                       │
  │  ┌────────────────────────┐  │
  │  │ Input     ⚠ Error msg  │  │
  │  └────────────────────────┘  │
  │                              │
  │  ┌──────┐  ┌──────────────┐  │
  │  │Cancel│  │ Save Changes │  │
  │  └──────┘  └──────────────┘  │
  └──────────────────────────────┘

Rules:
  - Single column (never multi-column for form fields — kills scan path)
  - Labels above inputs (not beside — better mobile, better scan)
  - Validation on blur (not on every keystroke)
  - Error messages below the field, not in a banner
  - Required indicator: asterisk on label (not "optional" on everything)
  - Submit button: right-aligned, primary style, specific verb ("Save Changes")
  - Cancel: text button or outline, left of submit
  - Destructive action: red button, require confirmation dialog

Multi-step wizard:
  - Step indicator at top (step 1 of 3)
  - "Back" + "Next" buttons
  - Persist progress (don't lose data on back/forward)
  - Review step before final submit
```

### Settings / Preferences
```
Anatomy:
  ┌───────────┬──────────────────────────────┐
  │  Sidebar  │  Section Title                │
  │           │  Description                  │
  │  Profile  │  ┌────────────────────────┐   │
  │  Account  │  │ Setting with toggle    │   │
  │  Team     │  │ Setting with input     │   │
  │  Billing  │  └────────────────────────┘   │
  │  Notifs   │                               │
  │           │  ── Danger Zone ────────────  │
  │           │  Delete Account  [Delete]      │
  └───────────┴──────────────────────────────┘

Rules:
  - Group related settings in cards
  - Toggle switches for boolean settings (not checkboxes)
  - Auto-save toggles (no save button needed for toggles)
  - Save button for text inputs (appears on change, sticky bottom)
  - Danger zone: visually distinct (red border), at bottom, confirmation required
  - Mobile: sidebar becomes top tabs or accordion
```

### Onboarding
```
Post-signup checklist pattern:
  ┌──────────────────────────────────────┐
  │  Welcome, [Name]! Let's get started  │
  │                                      │
  │  ✅ Create your account             │
  │  ○  Set up your first project        │
  │  ○  Invite your team                 │
  │  ○  Connect an integration           │
  │                                      │
  │  Progress: 1/4 complete  ████░░░░   │
  └──────────────────────────────────────┘

Rules:
  - 3-5 steps maximum (more = overwhelming)
  - First step auto-completed (creates sense of progress)
  - Dismissable but persistent (sidebar badge: "2 steps remaining")
  - Each step links directly to the relevant feature
  - Celebrate completion (confetti animation, congratulations message)
  - No tooltip tours on first visit (let user explore, then guide contextually)
```

### Empty States
```
Three types, each with different tone:

First-time empty (encouraging):
  ┌──────────────────────────┐
  │      [Illustration]      │
  │                          │
  │  Create your first       │
  │  project to get started  │
  │                          │
  │  [+ New Project]         │
  └──────────────────────────┘

No results (helpful):
  "No results for 'xyz'. Try a broader search or different filters."

All-done empty (celebratory):
  "All caught up! No unread notifications."

NEVER: bare "No data" or an empty white space.
```

### Pricing Page
```
Anatomy:
  ┌──────────────────────────────────────────────┐
  │  Simple, transparent pricing                  │
  │  [Monthly] / [Annual — save 20%]             │
  │                                              │
  │  ┌────────┐  ┌──────────┐  ┌────────────┐   │
  │  │ Free   │  │ Pro ⭐    │  │ Enterprise │   │
  │  │ $0     │  │ $29/mo   │  │ Custom     │   │
  │  │        │  │          │  │            │   │
  │  │ 3 proj │  │ Unlimited│  │ Everything │   │
  │  │ 1 user │  │ 10 users │  │ Unlimited  │   │
  │  │ 1GB    │  │ 50GB     │  │ Custom     │   │
  │  │        │  │          │  │            │   │
  │  │[Start] │  │[Upgrade] │  │[Contact]   │   │
  │  └────────┘  └──────────┘  └────────────┘   │
  │                                              │
  │  Feature comparison table (expandable)        │
  └──────────────────────────────────────────────┘

Rules:
  - Highlight recommended plan (border, badge, slight elevation)
  - Monthly/annual toggle with savings percentage shown
  - 3 tiers maximum visible (more → feature comparison table)
  - CTA verbs: "Start free", "Upgrade", "Contact sales" (not generic "Buy")
  - Enterprise: "Contact sales", not a price
```

### Error Pages
```
404: "This page doesn't exist. It may have been moved or deleted."
     [Go to Dashboard] [Go Back]
     Maintain brand voice. Show navigation. Include search.

500: "Something went wrong on our end. We've been notified."
     [Try Again] [Go to Dashboard]
     No technical details. Reassure the user.

Offline: "You're offline. Check your connection and try again."
         Show cached content where possible.
```

## Responsive Design Patterns

### Mobile-First Breakpoints
```css
/* Mobile first: styles build UP, not strip DOWN */
.container { padding: 1rem; }                    /* Mobile */
@media (min-width: 640px)  { /* sm: tablets */ }
@media (min-width: 768px)  { /* md: landscape tablets */ }
@media (min-width: 1024px) { /* lg: laptops */ }
@media (min-width: 1280px) { /* xl: desktops */ }
@media (min-width: 1536px) { /* 2xl: large screens */ }
```

### Container Queries (Component-Level)
```css
/* Component adapts to its container, not the viewport */
@container (min-width: 400px) {
  .card { flex-direction: row; }
}
@container (max-width: 399px) {
  .card { flex-direction: column; }
}
```

### Responsive Adaptations
| Pattern | Desktop | Mobile |
|---------|---------|--------|
| Navigation | Sidebar | Bottom tab bar |
| Data table | Full columns | Priority columns → card view |
| Dashboard | Grid layout | Stacked cards |
| Forms | Single column (same) | Single column (same) |
| Dialogs | Centered modal | Full-screen sheet |
| Menus | Dropdown | Bottom sheet |
| Search | Inline search bar | Expandable search icon |

### Touch vs Pointer
```css
@media (hover: hover) {
  /* Mouse/trackpad — hover effects OK */
  .button:hover { background: var(--hover); }
}
@media (pointer: coarse) {
  /* Touch — larger targets, no hover dependency */
  .button { min-height: 44px; min-width: 44px; }
}
```

## Dark Mode
```
Implementation checklist:
  - [ ] CSS custom properties for all colors (no hardcoded values)
  - [ ] Dark token layer defined (:root/.dark or media query)
  - [ ] Background: dark gray, not pure black (hsl(220, 15%, 10%))
  - [ ] Text: off-white, not pure white (hsl(0, 0%, 93%))
  - [ ] Shadows: reduced or replaced with borders
  - [ ] Bright colors: desaturated for dark surfaces
  - [ ] Images: consider reducing brightness/contrast
  - [ ] User preference persisted in localStorage
  - [ ] System preference detected via prefers-color-scheme
  - [ ] Toggle accessible in settings/header
```
