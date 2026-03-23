# UX Heuristics & Evaluation

## Nielsen's 10 Usability Heuristics

### 1. Visibility of System Status
The system should always keep users informed about what is going on.

```
Good: "Saving..." → "Saved ✓" (inline feedback)
Good: Progress bar during file upload (shows percentage)
Good: Loading skeleton matching content layout
Bad:  Spinner with no context ("Loading...")
Bad:  No feedback after clicking submit (did it work?)
Bad:  Background save with no indication
```

### 2. Match Between System and Real World
Use the user's language, not system terminology.

```
Good: "Contacts" (user term) not "Records" (database term)
Good: "3 days ago" not "2026-03-20T00:00:00Z"
Good: Trash can icon for delete
Bad:  "Error 422: Unprocessable Entity"
Bad:  "Null reference in UserRepository"
Bad:  Technical field names in forms ("user_email_address")
```

### 3. User Control and Freedom
Users often make mistakes. Provide undo and easy exit.

```
Good: "Message deleted. [Undo]" (toast with undo action)
Good: Cancel button on every modal/dialog
Good: Back button works predictably
Bad:  "Are you sure?" without explaining consequences
Bad:  No way to undo a bulk action
Bad:  Wizard with no back button
```

### 4. Consistency and Standards
Follow platform conventions. Don't make users guess.

```
Good: Blue underlined text = link (everywhere in the app)
Good: Left sidebar for navigation (standard SaaS pattern)
Good: Red button for destructive, blue for primary
Bad:  Link styles that change between pages
Bad:  Navigation in different positions on different screens
Bad:  Save button on the left on one form, right on another
```

### 5. Error Prevention
Design to prevent errors before they happen.

```
Good: Disable submit button until form is valid
Good: Confirmation dialog for destructive actions ("Delete 5 items?")
Good: Dropdown instead of free text (where options are finite)
Good: Date picker instead of text input for dates
Bad:  Allow typing invalid dates then show error
Bad:  No confirmation before bulk delete
Bad:  Free text field where a select would work
```

### 6. Recognition Over Recall
Make information visible. Don't rely on user memory.

```
Good: Recent items list (don't make them remember the name)
Good: Autocomplete in search (suggest as they type)
Good: Visible labels on form fields (not just placeholder)
Bad:  Placeholder text as the only label (disappears on focus)
Bad:  Keyboard shortcuts with no visible reference
Bad:  "Enter the ID from the previous page" (make them remember)
```

### 7. Flexibility and Efficiency
Accelerators for expert users that don't burden beginners.

```
Good: Keyboard shortcuts for power users (Cmd+K command palette)
Good: Bulk actions for multiple items
Good: Quick filters on data tables
Good: "Jump to..." search across all sections
Bad:  Only one way to accomplish a task (no shortcuts)
Bad:  Forcing wizards on experienced users (no "skip setup")
```

### 8. Aesthetic and Minimalist Design
Every element should serve a purpose. Remove visual noise.

```
Good: White space between sections (breathing room)
Good: Progressive disclosure (advanced options hidden by default)
Good: Single primary CTA per section
Bad:  Every element competing for attention (busy dashboard)
Bad:  Three equally prominent buttons on a card
Bad:  Information density that overwhelms new users
```

### 9. Help Users Recognize, Diagnose, and Recover from Errors
Error messages should be helpful, not technical.

```
Good: "Email is already registered. [Log in instead?]" (what + action)
Good: Inline validation next to the field (not a banner)
Good: "Could not connect to server. Check your internet and try again."
Bad:  "Error 500"
Bad:  "Invalid input" (which input? what's wrong?)
Bad:  Red border with no error message text
```

### 10. Help and Documentation
Provide contextual help, not just a docs link.

```
Good: Tooltip on complex field ("API key is found in Settings > Developer")
Good: "?" icon next to unfamiliar features
Good: Inline guidance on first use ("Click + to add your first task")
Good: Command palette with searchable actions (Cmd+K)
Bad:  "Read the documentation" as the only help
Bad:  Help page with no search
Bad:  Tutorial that can't be replayed
```

## Cognitive Load Reduction

### Chunking
```
Group related fields: personal info, then address, then preferences
Visual dividers between groups (whitespace or subtle lines)
Max 7±2 items in any list, menu, or group before subdividing
```

### Progressive Disclosure
```
Show essentials first. Advanced options behind "Show more" or "Advanced."
Settings: basic on main page, advanced behind expandable sections
Forms: required fields visible, optional behind "Additional details"
```

### Sensible Defaults
```
Pre-fill what you can:
  - Country from browser locale
  - Timezone from browser
  - Date fields default to today
  - New items default to "Draft" status
  - Toggle defaults to the safe/common option
```

### Constraint
```
Disable invalid options rather than showing errors after selection.
If only 3 options exist: show radio buttons, not a dropdown.
If the field must be a date: show a date picker, not a text input.
Prevent the error state rather than recovering from it.
```

## Information Architecture

```
Navigation depth: max 3 clicks to any feature
Breadcrumbs: for any page deeper than 2 levels
Consistent mental model: navigation structure doesn't change by context
Search: available from every page (Cmd+K or persistent search bar)
Primary nav: 5-7 top-level items maximum
Secondary nav: scoped to the current section (sidebar or tabs)
```

## Inclusive Design Beyond WCAG

### Motor Impairment
```
- Touch targets: 44x44px minimum (48x48px preferred)
- No hover-only interactions (every hover action has a click/tap equivalent)
- No time-limited actions (or provide generous extension)
- Drag-and-drop: always provide non-drag alternative (move up/down buttons)
- Focus order: logical, follows visual flow
```

### Cognitive Accessibility
```
- Plain language (Grade 8 reading level for UI text)
- Consistent layout across pages (same navigation, same patterns)
- Predictable behavior (same action → same result everywhere)
- Clear labels (no jargon, no abbreviations)
- Error recovery: clear instructions, not just "invalid"
```

### Low Vision (Beyond Contrast)
```
- Text resizable to 200% without breaking layout
- Zoom-safe: no content clipped at 200% browser zoom
- No information conveyed by color alone (add icons, patterns, labels)
- Focus indicators: visible, high contrast (3:1 minimum)
```

## UX Review Scoring Rubric

Score each applicable heuristic 0-2:
```
0 = Violation (user will struggle)
1 = Partial (functional but not ideal)
2 = Satisfied (follows best practices)

Scoring thresholds:
  16-20: Excellent UX — APPROVED
  14-15: Good UX — APPROVED
  10-13: Acceptable with conditions — APPROVED_WITH_CONDITIONS
  Below 10: Poor UX — REJECTED (specific issues must be addressed)
```
