---
name: "project-setup"
description: "Scaffold a project-level .claude/CLAUDE.md by detecting tech stack, commands, architecture, and conventions. Use when starting work in a repo that lacks a project CLAUDE.md."
context: fork
agent: infrastructure-engineer
---

# Project Setup

## What This Skill Does

Scaffolds a project-level `.claude/CLAUDE.md` by analyzing the codebase.

## Process

### 1. Detect Tech Stack

Scan for:
- `Gemfile` → Ruby/Rails
- `package.json` → Node.js/React
- `pyproject.toml` / `requirements.txt` → Python
- `go.mod` → Go
- `Cargo.toml` → Rust

### 2. Identify Commands

Find test, build, lint, and dev server commands from:
- `Makefile`, `package.json` scripts, `Procfile`, `docker-compose.yml`
- CI config files (`.github/workflows/`, `.circleci/`)

### 2b. Dev Server Configuration (MANDATORY for frontend projects)

If the project has frontend code (package.json with react/vue/svelte/next/vite/astro deps):

Detect and document:
- **Dev command**: from package.json scripts (`dev`, `start`, `serve`)
- **Dev port**: Vite=5173, Next.js=3000, CRA=3000, Astro=4321, custom from config files
- **Build command**: from package.json scripts (`build`)
- **Health check URL**: `http://localhost:{port}`

Add to the generated CLAUDE.md:
```markdown
## Dev Server
- Command: {detected command}
- Port: {detected port}
- Health check: http://localhost:{port}
- Build command: {detected build command}
```

This contract is read by `/design-qc` during the pipeline. If these fields are missing, Design QC will fail loudly.

If frontend deps are found but no dev/build scripts exist in package.json → add a warning:
```markdown
## Dev Server
WARNING: Frontend dependencies detected but no dev/build scripts found in package.json.
Add `dev` and `build` scripts to enable visual QA via /design-qc.
```

### 3. Map Architecture

- Directory structure and key modules
- Entry points and routing
- Database and ORM patterns
- External service integrations

### 3b. Classify Service Architecture

Determine the project's role in a larger architecture. Check signals in
order — the first match wins. The modular-monolith row is checked FIRST
because it is the default project shape; only fall through to the
multi-service signals if a modules directory is not present.

| Signal | Classification |
|--------|---------------|
| Single codebase with modules under `src/modules/`, `app/modules/`, `internal/modules/`, or `{package}/modules/` | **Modular Monolith** |
| No references to other services, self-contained, no modules directory | **Standalone App** |
| `docker-compose.yml` references other service containers | **Service in Multi-Service** |
| Published as npm/gem/pip package, consumed by others | **Shared Library** |
| Gateway/proxy config (Kong, Traefik, nginx config) | **API Gateway** |
| BFF naming, channel-specific routes | **Backend for Frontend** |
| Alexa skill.json, Google actions.yaml, Twilio config | **Voice Skill** |
| MQTT, device shadow, firmware files | **IoT/Device Service** |

For **Modular Monolith**, detect and document:
- The modules directory location (one of the four canonical paths above)
- The list of declared modules (each immediate subdirectory of the
  modules directory, excluding dotfiles and `README.md`)
- The fact that the project is a single deploy unit — no upstream or
  downstream services by definition

Generate the `## Service Context` section with these exact values:
```markdown
## Service Context
- **Role**: modular-monolith
- **Upstream**: none
- **Downstream**: none
- **Modules**: [comma-separated list of detected module directory names,
  or "none declared yet" if the modules directory exists but is empty]
- **Modules directory**: [detected path, e.g. `src/modules/`]
```

For **Service in Multi-Service**, detect and document:
- Upstream dependencies (services this one calls)
- Downstream dependents (services that call this one)
- Shared contracts (OpenAPI specs, Protobuf files, event schemas)
- Deployment dependencies (which services must be healthy first)

Add a `## Service Context` section to the generated CLAUDE.md:
```markdown
## Service Context
- **Role**: [standalone | service | shared-library | gateway | bff | voice-skill | iot-service]
- **Upstream**: [services this depends on, or "none"]
- **Downstream**: [services that depend on this, or "none"]
- **Contracts**: [paths to OpenAPI/Protobuf/event schema files, or "none"]
- **Deploy Dependencies**: [services that must be healthy before deploying, or "none"]
- **Channel**: [web | mobile | voice | device | all, if applicable]
```

### 3c. Frontend Design System Check

If the project has a frontend (React, Next.js, Vue, or similar detected in Step 1):

1. Check for an existing design system:
   - `tailwind.config.*` with theme.extend.colors → tokens exist
   - `styles/tokens.css` or CSS custom properties (--color-*, --spacing-*) → tokens exist
   - `components/ui/` directory with primitives → component library exists

2. If NO design system detected: invoke `/design-system-init` to generate tokens, Tailwind config, primitive components, and dark mode before any frontend build work begins.

3. If a partial system exists (e.g., Tailwind but no tokens): `/design-system-init` will enhance rather than replace.

This is automatic — the user does not need to invoke `/design-system-init` manually.

### 3d. Post-Greenfield Mode

If this skill is invoked after `/greenfield-scaffold` (detect by checking for `pipeline-state/{task-id}/tech-stack.md` and `pipeline-state/{task-id}/product-brief.md`):

1. **Read the greenfield artifacts** instead of scanning from scratch:
   - Product brief → use for CLAUDE.md project description
   - Tech stack ADR → use for tech stack section (no need to detect)
   - UI architecture → use for Architecture section (routes, components)
   - Design brief → use for Conventions section (design tokens, font pairing)

2. **Document what was created** in the generated CLAUDE.md:
   - List all DevX tooling installed (ESLint config, Prettier, Husky)
   - List the design system primitives available in `components/ui/`
   - List the MSW mock handlers available for development
   - Document the seed data script location and usage

3. **Add a `## Greenfield Bootstrap` section**:
   ```markdown
   ## Greenfield Bootstrap
   This project was bootstrapped via `/greenfield-scaffold` on {date}.
   - Framework: {from tech stack ADR}
   - Design system: {from design brief — font pairing, palette}
   - Seed data: {location of seed script and MSW handlers}
   - All DevX tooling pre-configured (ESLint, Prettier, TypeScript strict, Vitest, Husky)
   ```

This mode produces a richer CLAUDE.md than standard detection because it has access to the reasoning behind every choice (the ADRs), not just the detected result.

### 4. Generate CLAUDE.md and AGENTS.md

Generate both files at the project root.

**AGENTS.md** is a cross-tool convention read by OpenHands, Codex, and other AI coding tools. It provides a minimal agent roster and pipeline overview so any tool can orient itself to this project's conventions.

AGENTS.md template:
```markdown
# Agent Roster — [Project Name]

This file follows the cross-tool AGENTS.md convention (readable by OpenHands, Codex, Claude Code, etc.).

## Agent Roles

| Agent | Purpose | Model |
|-------|---------|-------|
| architect | System design, API contracts, ADRs | opus |
| software-engineer | Backend implementation, TDD, services | opus |
| frontend-engineer | UI, accessibility (WCAG 2.1 AA), React | opus |
| database-engineer | Schema, migrations, query optimisation | sonnet |
| infrastructure-engineer | Docker, CI/CD, IaC | opus |
| code-reviewer | SOLID/DRY/design audit (read-only) | opus |
| security-engineer | OWASP Top 10 audit (read-only) | sonnet |
| qa-engineer | Test strategy, integration/E2E tests | sonnet |
| product-reviewer | AC validation, business value (read-only) | sonnet |

## Pipeline Phases

Build → Review → Verify → Test → Accept → Ship

See `.claude/CLAUDE.md` for full orchestration protocol.

## Tech Stack

[Detected from codebase — fill in]

## Key Commands

- **Test**: [detected]
- **Lint**: [detected]
- **Dev**: [detected]
```

### 5. Jira Automation Setup

If `~/.claude/automation/daemon.sh` exists (automation system is installed):

1. Create `.claude/automation.env` with project-specific defaults:
   ```bash
   # Jira automation config for [Project Name]
   # These override ~/.claude/automation/default.env
   JIRA_PROJECT_KEY=
   JIRA_AC_CUSTOM_FIELD=
   BUDGET_CAP=10.00
   POOL_SIZE=3
   ```

2. Add `.tickets/` to `.gitignore` (the worktree pool directory)

3. Report to user: "Automation env created at .claude/automation.env -- set JIRA_PROJECT_KEY to enable."

### 6. Generate CLAUDE.md

```markdown
# [Project Name]

## Commands
- **Test**: [detected test command]
- **Lint**: [detected lint command]
- **Dev server**: [detected dev command]
- **Build**: [detected build command]

## Architecture
[Brief description of directory structure and patterns]

## Key Files
- [entry point] — [description]
- [config file] — [description]
- [main module] — [description]

## Conventions
- [Language-specific conventions detected]
- [Framework patterns in use]

## Module Boundaries
[Include this section ONLY when Step 3b classified the project as
 **Modular Monolith**. Omit for other roles.]

This project is a modular monolith. Module boundaries are governed by
`~/.claude/rules/_detail/module-boundaries-protocol.md` — read that file before
creating a new module, adding a cross-module call, or proposing a
service split.

Currently declared modules (detected from `[modules directory path]`):
- [module-name-1] — [one-line purpose if inferable from README, else "no description"]
- [module-name-2] — [...]
- [...]

Splitting a module into a separate service requires a named forcing
function (FF1–FF5) from the rules file. "We might want to split this
later" is not a forcing function.

## Gotchas
- [Any unusual patterns or configurations found]
```

### 6b. Embedder bootstrap (macOS)

After generating CLAUDE.md, bootstrap the semantic-rerank embedder so it
works out of the box on a fresh macOS clone. This step is optional-but-
automatic and platform-gated.

Run:

```bash
PYTHONPATH=$HOME/.claude/skills python3 -m embedder._lib.bootstrap
```

Expected behaviour:
- **macOS + healthy system** (doctor verdict OK): no-op, returns 0
- **macOS + missing ORT dylib**: `brew install onnxruntime`
- **macOS + missing BGE model**: invokes `skills/embedder/download-model.sh`
  with `NONINTERACTIVE=1`
- **macOS + settings.json missing `ORT_DYLIB_PATH`**: patches the file
  atomically (existing values preserved byte-for-byte)
- **Linux/Windows**: skipped, logs `embedder bootstrap skipped (non-macOS)`

Failure semantics: bootstrap **never blocks** `/project-setup`. Every
failure path (brew absent, download failure, settings write error)
logs a WARN line and continues. A partial bootstrap leaves capture
path unaffected — recall degrades to BM25-only, which is the
existing graceful-fallback behaviour.

Report the stdout line to the user so they have visible signal if any
step was skipped. After bootstrap, the user can verify with:

```bash
PYTHONPATH=$HOME/.claude/skills python3 -m embedder cli doctor
```

## Output

- Creates `.claude/CLAUDE.md` at project root
- Creates `AGENTS.md` at project root (cross-tool convention)
- Reports what was detected and any gaps to fill manually

## Phase Output

```
Verdict: PROJECT_SETUP_COMPLETE (informational — no gate)
Next: Read generated CLAUDE.md, confirm no conflicts with global rules, then proceed to Plan phase
Artifacts: [.claude/CLAUDE.md, detection report]
```
