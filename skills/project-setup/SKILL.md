---
name: "project-setup"
description: "Scaffold a project-level .claude/CLAUDE.md by detecting tech stack, commands, architecture, and conventions. Use when starting work in a repo that lacks a project CLAUDE.md."
context: fork
agent: infrastructure-engineer
model: sonnet
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

Determine the project's role in a larger architecture:

| Signal | Classification |
|--------|---------------|
| No references to other services, self-contained | **Standalone App** |
| `docker-compose.yml` references other service containers | **Service in Multi-Service** |
| Published as npm/gem/pip package, consumed by others | **Shared Library** |
| Gateway/proxy config (Kong, Traefik, nginx config) | **API Gateway** |
| BFF naming, channel-specific routes | **Backend for Frontend** |
| Alexa skill.json, Google actions.yaml, Twilio config | **Voice Skill** |
| MQTT, device shadow, firmware files | **IoT/Device Service** |

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

## Gotchas
- [Any unusual patterns or configurations found]
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
