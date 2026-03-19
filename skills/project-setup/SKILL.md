---
name: "Project Setup"
description: "Scaffold a project-level .claude/CLAUDE.md by detecting tech stack, commands, architecture, and conventions. Use when starting work in a repo that lacks a project CLAUDE.md."
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

### 3. Map Architecture

- Directory structure and key modules
- Entry points and routing
- Database and ORM patterns
- External service integrations

### 4. Generate CLAUDE.md

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
- Reports what was detected and any gaps to fill manually

## Phase Output

```
Verdict: PROJECT_SETUP_COMPLETE (informational — no gate)
Next: Read generated CLAUDE.md, confirm no conflicts with global rules, then proceed to Plan phase
Artifacts: [.claude/CLAUDE.md, detection report]
```
