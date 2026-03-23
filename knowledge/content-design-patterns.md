# Content Design Patterns

## Microcopy Principles

```
1. Be specific:    Not "Error" but "Could not save. The title is required."
2. Be constructive: Not "Invalid" but "Must be at least 8 characters."
3. Be brief:       Every word earns its place. "Saved" not "Your changes have been saved successfully."
4. Be human:       Not "Operation completed" but "Done!" or "Project created."
5. Be consistent:  Same action = same language across the entire app.
```

## Error Messages

### Framework: What + Why + What-to-Do
```
What happened:     "Could not save your changes."
Why (if helpful):  "The project name is already taken."
What to do:        "Choose a different name and try again."

Full: "Could not save — the project name is already taken. Choose a different name."
```

### Error Types and Patterns

**Form validation (inline, per field):**
```
Required:     "Project name is required"
Format:       "Enter a valid email address"
Length:        "Must be between 3 and 50 characters"
Unique:       "This email is already registered. [Log in instead?]"
Pattern:      "Use only letters, numbers, and hyphens"
```

**Server errors (toast or banner):**
```
Network:      "Could not connect. Check your internet and try again."
Server:       "Something went wrong on our end. We've been notified."
Timeout:      "This is taking longer than expected. Try again in a moment."
Auth:         "Your session has expired. [Log in again]"
Permission:   "You don't have permission to do that. Contact your admin."
Rate limit:   "Too many requests. Wait a moment and try again."
```

### Error Message Rules
```
- Show next to the affected field (not in a banner for field-level errors)
- Use color + icon + text (never color alone)
- Appear on blur or submit (not on every keystroke)
- Disappear when the error is corrected
- Never show technical details (error codes, stack traces, SQL errors)
- Never blame the user ("You entered an invalid..." → "Enter a valid...")
```

## Empty States

### First-Time Empty (Encouraging)
```
Tone: warm, encouraging, action-oriented

"No projects yet"
→ "Create your first project to get started. Projects help you organize tasks and track progress."
→ [+ Create Project]

Include: illustration (relevant, not generic), headline, brief explanation, primary CTA
```

### No Results (Helpful)
```
Tone: helpful, constructive

"No results for 'xyzzy'"
→ "Try a different search term or [clear filters]."

Include: what they searched for, suggestions for broadening, link to clear filters
Do NOT include: generic illustration, "try again later" (it won't help)
```

### All-Done Empty (Celebratory)
```
Tone: brief, positive

"All caught up!"
→ "No unread notifications."

Include: brief confirmation, no CTA needed (they've completed the work)
Do NOT include: long explanations, suggestions for more work
```

### Error Empty (Empathetic)
```
Tone: empathetic, reassuring

"Could not load your tasks"
→ "Check your connection and try again. If this keeps happening, [contact support]."
→ [Try Again]

Include: what went wrong (vaguely), action to fix, fallback support link
```

## Loading State Copy

```
Fast loads (<2s):     Skeleton screens, no text needed
Medium loads (2-10s): "Loading your dashboard..." (specific, not generic)
Countable progress:   "Processing 3 of 12 files..." (specific count)
Long operations:      "Generating your report. This usually takes about 30 seconds."
Background:           "Importing contacts... We'll notify you when it's done."

NEVER: bare "Loading..." (uninformative)
NEVER: no indication at all (user thinks it's broken)
```

## CTA (Call-to-Action) Patterns

### Button Labels
```
Pattern: Verb + Noun

Good:  "Create Project"    Bad: "Submit"
Good:  "Send Invitation"   Bad: "OK"
Good:  "Export Report"      Bad: "Click Here"
Good:  "Save Changes"      Bad: "Save" (save what?)
Good:  "Delete Project"    Bad: "Delete" (delete what?)
```

### Visual Hierarchy
```
Primary CTA:     Filled button, brand color (one per section)
Secondary CTA:   Outline button or text button
Destructive CTA: Red filled or red outline
Disabled CTA:    Muted, non-interactive, tooltip explains why

Never: two primary buttons competing for attention
Always: primary action is visually dominant
```

### CTA Placement
```
Forms:    Submit right-aligned, cancel left of submit
Modals:   Confirm right, cancel left (follow OS convention)
Cards:    CTA at bottom, full-width or right-aligned
Empty states: CTA centered, prominent
Pricing:  CTA at bottom of each tier column
```

## Confirmation Dialogs

```
Title:       Specific question, not "Are you sure?"
             "Delete this project?" not "Confirm deletion"

Description: Explain the consequence clearly
             "This will permanently delete 'My Project' and all 23 tasks.
              This action cannot be undone."

Buttons:     Specific verbs, not "Yes" / "No"
             "Delete Project" (red) / "Cancel"

Tone:        Calm, factual, not alarming
             State the facts. Let the user decide.
```

### When to Confirm
```
Always confirm:  Destructive actions (delete, remove, revoke)
                 Irreversible actions (send email, publish)
                 Bulk actions (delete 15 items)

Never confirm:   Save, update (provide undo instead)
                 Navigation (back button, close tab)
                 Toggling settings (auto-save with visual feedback)
```

## Onboarding Copy

### Welcome Message
```
"Welcome to [App], [Name]!"
Short, warm, sets expectations.
"Let's get you set up. It takes about 2 minutes."
```

### Checklist Items
```
Action-oriented, specific:
  ✅ Create your account (auto-completed)
  ○  Create your first project
  ○  Invite a team member
  ○  Connect Slack

NOT vague:
  ○  "Get started"
  ○  "Learn more"
  ○  "Explore features"
```

### Contextual Guidance
```
Show guidance when the user encounters a feature for the first time:
  "This is your project dashboard. Pin your most important projects for quick access."

Dismissable, not blocking. Shows once per feature.
Never: front-load all features in a tutorial. Introduce contextually.
```

## Tone Guidelines

```
Voice attributes:
  - Professional but human (not corporate, not casual)
  - Confident, not arrogant ("Here's your report" not "We've prepared your report")
  - Helpful, not patronizing ("Need help?" not "It looks like you're having trouble")
  - Concise, not curt ("Saved" not "Your changes have been saved to the database")

Error states:     Empathetic, not blaming
                  "We could not..." not "You failed to..."

Success states:   Brief, not over-celebratory
                  "Project created" not "🎉 Awesome! You just created a project!"

Empty states:     Encouraging, not depressing
                  "No tasks yet — create one to get started" not "Nothing here"

Destructive:      Calm and factual, not dramatic
                  "This will permanently delete..." not "WARNING: IRREVERSIBLE!"
```

## Formatting

```
Numbers:     Use locale-aware formatting (1,234.56 or 1.234,56)
Dates:       Relative when recent ("3 hours ago"), absolute when old ("Mar 15, 2026")
Currency:    Always include currency symbol, 2 decimal places ($12.00 not $12)
Percentages: 1 decimal place for deltas (+8.3%), 0 for large numbers (85%)
Names:       First name in casual context, full name in formal (invoices, settings)
Lists:       Oxford comma ("tasks, projects, and teams")
```
