# Next-Generation Interaction Patterns

Interfaces must be designed for how users interact with TikTok, Instagram, voice assistants, and AI-native apps today — not how they used desktop software in 2020.

## Multimodal Input Orchestration

Interfaces support touch + voice + gesture simultaneously without mode switching.

### Architecture
```
Input Layer:
  Touch → gesture recognizer → action dispatcher
  Voice → speech-to-text → intent parser → action dispatcher
  Keyboard → shortcut manager → action dispatcher
  
  All three converge at the same action dispatcher.
  The UI doesn't care HOW the action was triggered — it responds the same way.
```

### Implementation Patterns
```
Persistent mic button:
  - Visible in the input area (not buried in settings)
  - Waveform animation while listening
  - Live transcription appears in text field as user speaks
  - Clear "listening" state with obvious exit (tap to stop)

Voice + text hybrid:
  - User starts typing, switches to voice mid-sentence → seamless
  - Voice fills the same input field text appears in
  - User can edit voice-transcribed text with keyboard

Gesture shortcuts:
  - Swipe down from top: search/command palette
  - Long press: context menu (replaces right-click on mobile)
  - Pinch: zoom in data visualizations
  - Two-finger swipe: navigate between views
```

### Accessibility for Multimodal
```
Every voice action has a touch equivalent.
Every gesture action has a button equivalent.
Every visual state has an ARIA announcement.
No modality is required — all are optional enhancements.
```

## Social-Media-Influenced UI

Users trained by TikTok, Instagram, and Twitter expect these patterns:

### Vertical Scroll Feed
```
Content-first: each card fills or nearly fills the viewport
Infinite scroll with intelligent preloading (next 3-5 items)
Pull-to-refresh (mobile): spring animation, haptic feedback
Scroll snap: content cards snap to viewport edges
  scroll-snap-type: y mandatory;
  scroll-snap-align: start;
```

### Swipe-to-Action
```
Horizontal swipe reveals action tray:
  Left swipe:  destructive actions (delete, archive)
  Right swipe: positive actions (save, favorite, share)

Implementation:
  - Gesture detection with velocity threshold (not just distance)
  - Rubber-band effect at limits (spring physics)
  - Haptic feedback at action threshold
  - Undo toast after destructive action (3-5 second window)
  - Non-swipe alternative always available (⋯ menu)
```

### Bottom Sheet Navigation
```
RULE: On mobile, bottom sheets replace top dropdowns, modals, and menus.

Why: Thumb zone. The bottom 40% of the screen is the comfort zone.
Top nav bars force users to reach to the top — hostile to one-handed use.

Pattern:
  - Bottom tab bar for primary navigation (4-5 items max)
  - Bottom sheet for secondary actions (slides up from bottom)
  - Drag handle for sheet resize (peek → half → full)
  - Background dims but remains visible and tappable (to dismiss)
```

### Story-Style Content
```
Ephemeral / sequential content (tap to advance):
  - Full-screen, one item at a time
  - Progress bar segments at top
  - Tap left/right to navigate
  - Swipe to skip to next story
  - Auto-advance timer (5-15 seconds, with pause on hold)
Use: Onboarding, tutorials, product highlights, notifications digest
```

### Reaction/Engagement Patterns
```
Quick reactions: emoji row, single tap (not a separate screen)
Share as first-class action (not buried in ⋯ menu)
Save/bookmark: visible, one-tap, with visual confirmation
Social proof: "12 people saved this" (when appropriate)
```

## Voice-First Patterns

Voice as a primary input path, not a novelty feature.

### Voice Input UI
```
Persistent mic button:
  Resting state: subtle mic icon in input area
  Listening state: pulsing ring, waveform visualization
  Processing state: typing indicator dots
  Result state: transcribed text in input field, editable

  ARIA: role="button" aria-label="Voice input"
  State announcements: "Listening", "Processing", "Text entered"
```

### Conversation Threading
```
Context persistence across voice turns:
  User: "Show me last week's reports"
  [system shows reports]
  User: "Compare that to this week"  // "that" refers to previous context
  
Implementation: maintain conversation context stack
  - Last 3-5 turns in memory
  - Pronouns resolved against context
  - "Go back" / "Undo" always works
```

### Voice Command Discovery
```
"What can I say?" — accessible from any screen
Contextual voice hints: show available commands relevant to current view
Progressive disclosure: basic commands always, advanced commands on request
Never require voice — always provide touch/keyboard alternative
```

## Ambient AI Integration

AI as an invisible background layer, not a chat widget bolted on.

### Auto-Adaptation
```
Interface restructures based on:
  - Usage patterns: frequently used features move up, rarely used fade
  - Time of day: dark mode auto-switch, different content priority
  - Task context: relevant tools surface when editing, hide when browsing
  - Error patterns: if user keeps correcting a field, offer assistance

MUST include:
  "Personalized for you" label (transparency)
  "Reset to default" option (user agency)
  Settings to disable adaptation (control)
```

### Smart Defaults
```
Auto-fill based on intent prediction:
  - Date fields default to contextual date (not just "today")
  - Address fields pre-fill from previous entries
  - Form fields suggest based on similar past submissions
  - Search suggests based on current page context

Implementation:
  - Suggestion appears as ghost text (lighter opacity)
  - Tab to accept, keep typing to override
  - Never auto-submit — user confirms every action
```

### Contextual Suggestions
```
Surfaced at point-of-need, not in a sidebar:
  - After creating 3 items: "Tip: you can bulk-import from CSV"
  - After viewing a chart: "Want to set an alert for this metric?"
  - After an error: "This usually means X. Try Y."

Implementation:
  - Inline card below the relevant element (not a modal)
  - Dismissable with "Don't show again" option
  - Maximum 1 suggestion visible at a time
  - Never interrupt active user input
```

## Conversational UI Patterns

### Chat-as-Navigation
```
Command palette / chat input replaces traditional menus for power users:
  Cmd+K → type natural language → system interprets + acts
  
Examples:
  "create new project" → opens project creation
  "show sales from last quarter" → navigates to report
  "invite maria@example.com" → opens invite flow pre-filled

Implementation:
  - Fuzzy matching on commands and content
  - Recent commands for quick re-execution
  - Typeahead suggestions as user types
  - Keyboard navigation through results
```

### Streaming AI Content
```
Typewriter effect (perceived wait drops 55-70%):
  - Tokens appear as generated, not after full completion
  - Subtle cursor animation (2px bar, 500ms blink)
  - Content container smoothly expands (height transition)
  - User can scroll while content still generating

Implementation:
  - Server-Sent Events (SSE) or WebSocket for streaming
  - ARIA live region on response container: aria-live="polite"
  - role="status" on loading indicator
  - Focus management: direct keyboard users to completed response

Skeleton during AI inference:
  - 3-5 decreasing-width lines mimicking natural text
  - Shimmer animation (gradient sweep)
  - Replace with real content via crossfade (not hard swap)
```

### Confidence Indicators
```
Visual signals for AI certainty:
  High (>90%):    Green border/badge, no qualifier
  Medium (60-90%): Amber border, "Likely: ..." prefix
  Low (<60%):     Gray border, "Uncertain: ..." prefix, source citations

Implementation:
  - Percentage badge: small pill next to AI response
  - Source citations: collapsible list of references
  - "How was this generated?" expandable explainer
  - Never present uncertain output as definitive
```

## Gesture-Driven Navigation

### Dissolving Chrome
```
Navigation disappears when not needed:
  - Toolbar fades after 3 seconds of no interaction
  - Reappears on: scroll up, tap near edge, gesture
  - Floating action button remains (primary action always accessible)
  
  CSS: transition: opacity 0.3s ease, transform 0.3s ease;
  Hidden state: opacity: 0; transform: translateY(-100%); pointer-events: none;
```

### Micro-Toolbars
```
Appear near selected content:
  - Select text → formatting toolbar appears above selection
  - Select table row → action bar appears inline
  - Hover image → edit/crop/replace overlay appears
  
Position: Calculate based on selection position, keep within viewport
Animation: scale from 0.95 to 1.0, opacity 0 to 1, 150ms
```

### Thumb Zone Design (Mobile)
```
Comfort zone: bottom 40% of screen
  - Primary actions: bottom tab bar or floating action button
  - Secondary actions: bottom sheet (slide up)
  - Tertiary actions: top of screen (acceptable — infrequent)

Avoid: placing frequently-used controls at top of screen on mobile.
Exception: search (muscle memory from platform conventions).
```

## Adaptive / Living Layouts

### Beyond Breakpoints
```
Traditional: layout changes at 768px, 1024px, 1440px (discrete jumps)
Adaptive: layout continuously adjusts using container queries + fluid values

Container queries:
  @container (min-width: 300px) { .card { grid-template-columns: 1fr 1fr; } }
  @container (max-width: 299px) { .card { grid-template-columns: 1fr; } }

Fluid values:
  font-size: clamp(1rem, 0.5rem + 1.5vw, 1.5rem);
  padding: clamp(1rem, 2vw, 3rem);
  gap: clamp(0.5rem, 1vw, 1.5rem);
```

### Context-Aware Restructuring
```
Time-of-day: lighter theme / reduced brightness in evening
Device context: horizontal layout on tablet, vertical on phone
Usage pattern: recently used sections appear first
Network quality: reduce image quality, defer non-essential content on slow connections
```

## Spatial & 3D UI Depth

### Layered Depth (without VR)
```
Subtle 3D creates hierarchy on flat screens:

Background layer:  z-index: 0, muted colors, blur(4px) if content overlaps
Content layer:     z-index: 10, standard colors, shadow-sm
Interactive layer: z-index: 20, elevated, shadow-md, slight scale on hover
Overlay layer:     z-index: 30, modal/sheet, shadow-lg, backdrop dim

Parallax scroll (subtle):
  background: translateY(calc(var(--scroll-y) * 0.3));
  foreground: translateY(calc(var(--scroll-y) * 0.7));
  // Keep parallax ratio under 0.5 — more feels disorienting
```

### Glassmorphism 2.0
```css
/* Dark base with translucent frosted panels */
:root { --bg-base: hsl(230, 20%, 8%); }

.glass-card {
  background: hsl(0 0% 100% / 0.05);
  backdrop-filter: blur(16px) saturate(1.5);
  border: 1px solid hsl(0 0% 100% / 0.08);
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 32px hsl(0 0% 0% / 0.3);
}
/* Use: cards on dark backgrounds, overlays, navigation panels */
/* Requires: backdrop-filter support (98%+ browsers) */
```

## Narrative Interfaces

### Replace Dashboards with Stories
```
Traditional: grid of widgets showing current values (KPI, chart, table)
Narrative: "Here's what changed since you last looked"

Structure:
  1. Headline insight: "Revenue grew 12% this week"
  2. Supporting context: mini chart showing the trend
  3. Anomaly callout: "Unusual spike on Thursday — 3x normal"
  4. Suggested action: "Review Thursday's campaign performance"
  
Implementation:
  - AI generates narrative summary from data
  - User can drill into any insight (progressive disclosure)
  - Time-relative: "since you last viewed" not absolute dates
  - Customizable: user pins what matters, AI prioritizes the rest
```

## Calm Design

### Anxiety-Reducing Principles
```
1. Reduce choice density: max 3 primary actions per viewport
2. Gentle transitions: ease-out curves, 200-400ms duration
3. Progressive disclosure: show essentials, reveal details on demand
4. Predictable behavior: same gesture → same result everywhere
5. Soft color palette: reduced saturation, lower contrast for non-essential elements
6. Breathing room: generous whitespace between interactive elements
7. No urgency theater: no fake countdown timers, no "only 2 left!" manipulation
8. Reversibility: every action can be undone (3-5 second undo window)
```
