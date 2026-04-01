---
name: "greenfield-scaffold"
description: "Full greenfield project bootstrap: product discovery, tech stack decision, UI architecture, framework init, DevX setup, design system, infrastructure, and seed data. Use when building a new project from scratch with no existing code."
argument-hint: "Product description (e.g., 'project management app for remote teams')"
---

# Greenfield Scaffold

## What This Skill Does

Bootstraps a complete project from an empty directory. Orchestrates multiple agents and existing skills to produce a real, running project ready for the normal pipeline.

After this skill completes: the dev server runs, tests pass, linting works, the design system is initialized, infrastructure is configured, and placeholder pages show real-looking content. The normal pipeline (`/epic-breakdown` → `/pipeline` per story) takes over.

## When to Invoke

- User says "Build me X" and the directory is empty
- No `package.json`, `Gemfile`, `go.mod`, or equivalent exists
- Classified as **Greenfield** by `/intake`
- Auto-detected by `/pipeline` Step 2b (empty directory check)

## Process

### Step 1: Product Discovery (Interactive)

The orchestrator asks the user directly (not via agent):

```
Product Discovery:
1. What is the product? (one sentence)
2. Who is the target user? (persona: developers, consumers, executives, etc.)
3. What are the 3-5 core features (MVP scope)?
4. Any constraints? (platform, technology preferences, existing brand, timeline)
5. What does success look like? (key metric or outcome)
```

If the user's original request already includes this detail, extract directly — don't re-ask.

Persist to `pipeline-state/{task-id}-product-brief.md`:
```markdown
---
task_id: {task-id}
phase: greenfield
step: product-discovery
timestamp: {ISO 8601}
---

## Product Brief: {product name}

### Product
{one sentence description}

### Target User
{persona description}

### Core Features (MVP)
1. {feature}
2. {feature}
3. {feature}

### Constraints
{platform, tech preferences, brand, timeline}

### Success Metric
{key metric or outcome}
```

### Step 2: Tech Stack Decision (Architect)

Spawn the architect agent (subagent, read-only):

```
Agent({
  subagent_type: "architect",
  prompt: "Read ~/.claude/knowledge/tech-stack-decision-matrix.md.
    Based on this product brief, recommend a tech stack.
    Product: {product brief from Step 1}

    Produce:
    1. Recommended stack (frontend, backend, database, ORM, auth, hosting, testing)
    2. The EXACT bootstrap command from the decision matrix
    3. ## Alternatives Considered (minimum 2 alternatives with rejection rationale)
    4. Any constraint-driven overrides from the Constraint Modifiers table

    Output as a structured ADR in markdown."
})
```

Persist to `pipeline-state/{task-id}-tech-stack.md`.

**Present to user for approval** (same pattern as pipeline plan validation interactive mode). If the user specifies a different stack, the architect adapts.

### Step 3: UI Architecture (Architect — frontend projects only)

If the recommended stack includes a frontend framework:

Spawn the architect agent (subagent, read-only):

```
Agent({
  subagent_type: "architect",
  prompt: "Read ~/.claude/knowledge/ui-pattern-library.md and
    ~/.claude/knowledge/ux-heuristics.md.
    Based on this product brief and tech stack, produce a UI architecture.
    Product: {product brief}
    Stack: {tech stack ADR}

    Produce:
    1. Screen inventory (every page/screen with screen type from ui-pattern-library)
    2. Navigation structure (routes, nav pattern: sidebar/bottom tabs/breadcrumbs)
    3. User flows (top 3-5 journeys as step sequences)
    4. Component hierarchy (page → feature → UI component mapping)
    5. Empty/loading/error state identification per screen

    This is NOT code. It is an information architecture document."
})
```

Persist to `pipeline-state/{task-id}-ui-architecture.md`.

### Step 4: Framework Bootstrap (Infrastructure Engineer)

Spawn infrastructure-engineer (subagent, worktree):

```
Agent({
  subagent_type: "infrastructure-engineer",
  isolation: "worktree",
  mode: "bypassPermissions",
  prompt: "Bootstrap a new project.

    Pre-flight: verify the runtime exists:
    - Node.js: node --version (require 18+)
    - Ruby: ruby --version
    - Python: python3 --version
    - Go: go version
    If missing, report the error clearly — do not proceed.

    Run the EXACT bootstrap command:
    {bootstrap command from tech stack ADR}

    After bootstrap:
    1. Verify the project builds: {build command}
    2. Verify the dev server starts: {dev command}
    3. Commit: 'chore: bootstrap {framework} project'

    Do NOT install additional dependencies beyond the bootstrap.
    Do NOT configure DevX tooling — that is Step 5."
})
```

After merge: `package.json` (or equivalent) exists on disk. All detection logic now works.

### Step 5: DevX Setup (Infrastructure Engineer)

Spawn infrastructure-engineer (subagent, worktree):

```
Agent({
  subagent_type: "infrastructure-engineer",
  isolation: "worktree",
  mode: "bypassPermissions",
  prompt: "Read ~/.claude/knowledge/devx-patterns.md.
    Set up developer experience tooling for a {framework} project.

    Install and configure:
    1. ESLint (flat config, ESLint 9+) with: @typescript-eslint, react-hooks,
       jsx-a11y, import ordering
    2. Prettier (.prettierrc + .prettierignore)
    3. TypeScript strict mode (verify tsconfig has strict: true,
       noUncheckedIndexedAccess: true)
    4. Testing infrastructure: Vitest (or Jest if Vitest unsupported),
       @testing-library/react, @testing-library/user-event,
       @testing-library/jest-dom, jest-axe, MSW
    5. Git hooks: Husky + lint-staged + commitlint
    6. .editorconfig
    7. VS Code workspace settings (.vscode/settings.json + extensions.json)
    8. Standard package.json scripts (dev, build, test, lint, typecheck, format)
    9. Worktree exclusion in test runner config

    Verify after setup:
    - npm run lint → exits clean
    - npm run typecheck → exits clean
    - npm test → runs (may have 0 tests, that's OK)
    - npm run format:check → exits clean

    Commit: 'chore: configure developer experience tooling'"
})
```

### Step 6: Creative Direction + Design System

Invoke existing skills in sequence:

1. `/creative-direction` with the product brief as argument
   - Reads product brief and UI architecture from pipeline-state/
   - Produces design brief

2. `/design-system-init`
   - Reads design brief
   - Produces tokens, Tailwind config extensions, primitive components

### Step 7: Infrastructure Scaffold

Invoke `/infra-scaffold` (existing skill):
- Produces Dockerfile, docker-compose, CI/CD pipeline, health endpoints, .env.example
- Puppeteer/Playwright for visual testing

### Step 8: Seed Data + Placeholder UI

Spawn two agents in parallel (both with worktree):

**Software Engineer** — seed data and mock API:
```
Agent({
  subagent_type: "software-engineer",
  isolation: "worktree",
  mode: "bypassPermissions",
  prompt: "Create seed data and mock API handlers for development.
    Product: {product brief}
    Screens: {screen inventory from UI architecture}

    Create:
    1. MSW handlers (src/mocks/handlers.ts) for every API endpoint
       the screens need. Use realistic data (install @faker-js/faker).
    2. Factory functions (src/test/factories/) for generating test data
       per entity type.
    3. MSW browser setup (src/mocks/browser.ts) for development mode.
    4. Seed script or fixture file if the project uses a database.

    Every screen in the screen inventory must have mock data that
    makes the dev server show real-looking content.

    Follow TDD protocol. Commit: 'feat: add seed data and MSW mock handlers'"
})
```

**Frontend Engineer** — placeholder pages:
```
Agent({
  subagent_type: "frontend-engineer",
  isolation: "worktree",
  mode: "bypassPermissions",
  prompt: "Create placeholder pages for the application.
    UI Architecture: {from pipeline-state/{task-id}-ui-architecture.md}
    Design Brief: {from pipeline-state/{task-id}-design-brief.md}
    Design system primitives are in components/ui/.

    For each screen in the screen inventory:
    1. Create the route/page file
    2. Use the correct screen type layout (from ui-pattern-library.md)
    3. Wire up to MSW mock handlers (import from src/mocks/browser.ts)
    4. Show skeleton loading states, then rendered data
    5. Show proper empty states (illustration placeholder + headline + CTA)
    6. Use design system primitives (Button, Card, Input, etc.)
    7. Include proper navigation between screens

    The goal: npm run dev shows a real-looking (if shallow) application
    that demonstrates the layout, navigation, and data patterns.

    Follow TDD protocol. Commit: 'feat: add placeholder pages with mock data'"
})
```

### Step 9: Project Documentation

Invoke `/project-setup` (existing skill):
- Detects and documents everything that was just created
- Produces `.claude/CLAUDE.md` and `AGENTS.md`
- Enhanced post-greenfield mode reads the ADRs and product brief for richer documentation

### Step 10: State Tracking

Update `pipeline-state/{task-id}-greenfield.md`:
```markdown
---
task_id: {task-id}
phase: greenfield
verdict: GREENFIELD_SCAFFOLD_COMPLETE
timestamp: {ISO 8601}
---

## Greenfield Bootstrap Complete

### Steps Completed
1. Product Discovery: ✓ (product-brief.md)
2. Tech Stack Decision: ✓ (tech-stack.md)
3. UI Architecture: ✓ (ui-architecture.md)
4. Framework Bootstrap: ✓ ({framework})
5. DevX Setup: ✓ (ESLint, Prettier, TypeScript, Vitest, Husky)
6. Design System: ✓ (creative-direction + design-system-init)
7. Infrastructure: ✓ (Dockerfile, CI/CD, health endpoints)
8. Seed Data: ✓ (MSW handlers, factories, placeholder pages)
9. Documentation: ✓ (CLAUDE.md, AGENTS.md)

### Project State
- Dev server: {command} on port {port}
- Tests: {count} tests passing
- Lint: clean
- TypeCheck: clean
- Design system: {font pairing}, {palette}
- Pages: {count} placeholder pages

### Next Steps
→ /epic-breakdown to decompose product into implementable stories
→ /pipeline per story using the normal delivery pipeline
```

## Error Recovery

| Step | Failure | Recovery |
|------|---------|---------|
| 4. Bootstrap | Runtime not found | Report: "Install Node.js 18+ / Ruby / Python" |
| 4. Bootstrap | Command fails | Try alternative from tech-stack ADR |
| 5. DevX | Package install fails | Retry with --legacy-peer-deps, then escalate |
| 6. Design | Creative direction blind | Fall back to product-type personality mapping |
| 8. Seed data | MSW handler errors | Simplify: static JSON responses instead of faker |

## Phase Output

```
Verdict: GREENFIELD_SCAFFOLD_COMPLETE
Next: /epic-breakdown → /pipeline per story
Artifacts: [product-brief.md, tech-stack.md, ui-architecture.md, design-brief.md,
            project files, CLAUDE.md, AGENTS.md]
```
$ARGUMENTS
