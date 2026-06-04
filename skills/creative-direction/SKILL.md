---
name: "creative-direction"
description: "Pre-build design thinking phase that produces a distinctive design brief. Takes brand context, outputs font pairing, color palette, layout philosophy, interaction paradigm, and visual personality. Run before design-system-init to prevent generic Inter+blue defaults."
context: fork
agent: frontend-engineer
argument-hint: "Brand context: product name, target audience, personality keywords, competitor URLs, or inspiration references"
---

# Creative Direction

## What This Skill Does

Produces a distinctive design brief that drives all downstream visual decisions. This is the creative thinking phase — it runs BEFORE `/harness:design-system-init` and BEFORE `/harness:build-implementation` for frontend features.

**Why this exists**: Without creative direction, Claude defaults to Inter + blue + 8px radius + centered hero + 3-column card grid. This is "distributive convergence" — reproducing the statistical center of design decisions. This skill breaks that pattern by forcing intentional, distinctive choices.

## When to Invoke

- Automatically by pipeline Step 2b when frontend files are detected and no design brief exists
- Manually when starting a new project or establishing brand identity
- When redesigning an existing product's visual identity

## Prerequisites

- Read `~/.claude/knowledge/creative-direction-database.md` for curated alternatives
- Read `~/.claude/knowledge/design-system-patterns.md` for token architecture
- Read `~/.claude/knowledge/next-gen-interaction-patterns.md` for interaction paradigm options

## Process

### Step 1: Gather Context

From the skill argument or project context, extract:
```
Product type:     [SaaS, consumer app, dashboard, marketing site, etc.]
Target audience:  [developers, executives, consumers, healthcare workers, etc.]
Personality:      [3-5 adjectives — e.g., "bold, technical, trustworthy"]
Competitors:      [optional — what to differentiate from]
Constraints:      [existing brand guidelines, required colors, platform restrictions]
```

If no argument provided, infer from:
1. The project's `CLAUDE.md` (product description, tech stack)
2. Existing UI code (if any — detect current patterns)
3. The feature being built (from pipeline state)

### Greenfield Interview Mode

If ALL of these are true: (a) no project CLAUDE.md exists, (b) no existing UI code exists, (c) no pipeline state design brief exists — this is a greenfield project.

1. **Product brief**: Check `$state_dir/{task-id}/product-brief.md` (from `/harness:greenfield-scaffold` Step 1). If found, extract product type, target audience, and personality clues.

2. **Competitive differentiation**: From the product brief's product type, identify 2-3 visual patterns common in that space. The design brief should DIFFERENTIATE from these, not reproduce them.

3. **Audience-driven personality mapping**:
   - Developers → technical, precise, dark-mode-first
   - Executives → authoritative, clean, data-dense
   - Consumers → warm, approachable, playful
   - Healthcare workers → trustworthy, calm, accessible
   - Creative professionals → bold, expressive, editorial

4. **UI Architecture alignment**: Check `$state_dir/{task-id}/ui-architecture.md`. If found, use the screen inventory to influence layout archetype:
   - Dashboard-heavy → Dashboard density or Asymmetric bento grid
   - Content-heavy → Magazine editorial or Generous white space
   - List/table-heavy → Dashboard density
   - Social/feed → Vertical feed or Card mosaic

If no greenfield artifacts exist either (creative-direction invoked standalone on a blank project), ask 3 targeted questions:
- "What is the product?" → product type
- "Who uses it?" → audience → personality
- "Name 2-3 apps whose visual style you admire" → competitive context

### Step 2: Anti-Convergence Gate

**MANDATORY before any selection.** Read the Banned Defaults section in `creative-direction-database.md`. For every choice you're about to make, check:

```
- [ ] Font is NOT Inter, Roboto, Open Sans, Arial, Helvetica, Lato, or Montserrat
- [ ] Primary color is NOT default blue (hsl 210-230 range)
- [ ] Layout is NOT centered-hero-gradient + 3-column-card-grid
- [ ] Border radius is NOT 8px on everything
- [ ] Navigation is NOT desktop-style top nav bar on mobile
```

If ANY choice matches a banned default, select an alternative from the database. The only exception is if the brand brief explicitly requires a banned choice (e.g., "our brand color is blue").

### Step 3: Font Selection

Reference `creative-direction-database.md` → Font Pairing Library.

1. Match the product personality to an archetype (editorial, technical, warm, bold, elegant, playful)
2. Select a display + body pairing from that archetype
3. Verify the pairing on Google Fonts (free, available everywhere)
4. Document the rationale: why this pairing matches the personality

```
Output:
  Display font: [name] ([weight])
  Body font:    [name] ([weight])
  Archetype:    [category]
  Rationale:    [why this pairing]
```

### Step 4: Color Selection

Reference `creative-direction-database.md` → Color Palette Archetypes.

1. Select a palette by industry AND mood match
2. If no exact match, use the Palette Generation Formulas to derive from a brand hue
3. Generate the full HSL scale using the formula in `design-system-patterns.md`
4. Verify WCAG contrast for primary-foreground on primary (4.5:1 minimum)

```
Output:
  Primary:    hsl(H, S%, L%) — [usage]
  Secondary:  hsl(H, S%, L%) — [usage]
  Accent:     hsl(H, S%, L%) — [usage]
  Neutral base: hsl(H, S%, L%)
  Palette type: [monochromatic/analogous/split-complementary/triadic]
  Rationale:  [why this palette]
```

### Step 5: Layout Philosophy

Reference `creative-direction-database.md` → Layout Archetypes.

Select the archetype that best serves the product:
- Asymmetric bento grid (dashboards, portfolios)
- Magazine editorial (content-heavy, storytelling)
- Dashboard density (admin, analytics)
- Generous white space (luxury, premium)
- Card mosaic (galleries, discovery)
- Vertical feed (social-influenced content apps)

Document: grid strategy, spacing density, whitespace philosophy.

### Step 6: Visual Texture Selection

Select 0-2 texture patterns from the database:
- Only if they serve the brand personality
- Each must have a specific use case (not "apply everywhere")
- Document when to use and when NOT to use

### Step 7: Interaction Paradigm Assessment

**MANDATORY.** Reference `next-gen-interaction-patterns.md`.

Assess which next-gen interaction patterns apply to this product:

| Pattern | Applies? | Rationale |
|---------|----------|-----------|
| Multimodal input (voice + touch) | Yes/No | [why] |
| Social-feed vertical scroll | Yes/No | [why] |
| Bottom sheet navigation (mobile) | Yes/No | [why] |
| Swipe-to-action gestures | Yes/No | [why] |
| Voice input affordances | Yes/No | [why] |
| Ambient AI integration | Yes/No | [why] |
| Streaming AI content | Yes/No | [why] |
| Gesture-driven navigation | Yes/No | [why] |
| Narrative interfaces | Yes/No | [why] |
| Calm design principles | Yes/No | [why] |

**Future-forward default**: Unless the brief explicitly specifies a conservative approach, at least ONE next-gen pattern must be adopted. The design brief must justify why traditional patterns are chosen over modern alternatives.

### Step 8: Produce Design Brief

Write to `$state_dir/{task-id}/design-brief.md`:

```markdown
---
task_id: {task-id}
phase: creative-direction
verdict: CREATIVE_DIRECTION_COMPLETE
timestamp: {ISO 8601}
---

## Design Brief: {product/feature name}

### Brand Personality
{3-5 adjectives with rationale}

### Typography
- Display: {font name} ({weight}) — {usage}
- Body: {font name} ({weight}) — {usage}
- Archetype: {category}
- Rationale: {why this pairing}

### Color Palette
- Primary: hsl({H}, {S}%, {L}%) — {usage}
- Secondary: hsl({H}, {S}%, {L}%) — {usage}
- Accent: hsl({H}, {S}%, {L}%) — {usage}
- Neutrals: {base hue and range}
- Dark mode: {adjustments — desaturate, darken background}
- Rationale: {why this palette}

### Layout Philosophy
- Archetype: {name}
- Grid: {strategy}
- Density: {spacious/comfortable/compact}
- Signature elements: {distinctive visual features}

### Visual Texture
- {technique}: {when to use} / {when not to use}

### Interaction Paradigm
- Primary paradigm: {e.g., "gesture-rich social feed" or "ambient AI dashboard"}
- Adopted next-gen patterns: {list with brief rationale}
- Traditional patterns justified: {list with why modern alternatives don't fit}

### Anti-Convergence Checklist
- [ ] Fonts are NOT Inter, Roboto, Open Sans, or Arial
- [ ] Primary color is NOT default blue (hsl 210-230)
- [ ] Layout is NOT centered-hero-gradient-card-grid
- [ ] Navigation is NOT desktop top-nav on mobile
- [ ] At least ONE next-gen interaction pattern adopted
```

## If Project Already Has Established Brand

If the project already has a design system with distinctive branding:
1. Read existing tokens (tokens.css, tailwind.config)
2. If the existing system is already distinctive (not default blue/Inter): output `CREATIVE_DIRECTION_SKIPPED` with note that existing brand is used
3. If the existing system is generic: produce a design brief to upgrade it

## Phase Output

```
Verdict: CREATIVE_DIRECTION_COMPLETE / CREATIVE_DIRECTION_SKIPPED
Next: /harness:design-system-init (consumes the design brief) or /harness:build-implementation
Artifacts: [design-brief.md path, font names, palette HSL values, interaction paradigm]
```
$ARGUMENTS
