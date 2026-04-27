---
name: "health-scan"
description: "Use when user wants to Scan a codebase for security vulnerabilities, dependency freshness, test coverage gaps, tech debt signals, and dead code. Produces a ranked health report. Optionally auto-creates Jira tickets for critical findings."
argument-hint: "Optional: 'security-only', 'deps-only', 'full' (default: full)"
---

# Codebase Health Scanner

## What This Skill Does

Proactively scans a codebase for issues the team hasn't asked about yet. Produces a ranked health report that identifies security vulnerabilities, stale dependencies, test coverage gaps, tech debt, and dead code. Can auto-create Jira tickets for critical findings.

This is the proactive value generation layer — the system identifies work rather than waiting to be told.

## When to Invoke

- **On schedule**: via `/schedule` (e.g., weekly) for continuous hygiene
- **On demand**: when the user asks about codebase health
- **After major features**: as part of post-delivery housekeeping
- **At project onboarding**: to understand a new codebase's health

## Process

### 1. Detect Project Stack

Read the project's `.claude/CLAUDE.md` for stack info. Determine which scanners apply:

| Stack | Security | Deps | Coverage | Shape |
|-------|----------|------|----------|-------|
| Node/TS | `npm audit` | `npm outdated` | jest --coverage | eslint, tsc |
| Ruby | `bundle audit` | `bundle outdated` | simplecov | rubocop |
| Python | `pip-audit` | `pip list --outdated` | coverage.py | ruff, mypy |
| Go | `govulncheck` | `go list -m -u all` | go test -cover | golangci-lint |

### 2. Security Scan

```bash
# Node
npm audit --json 2>/dev/null

# Ruby  
bundle audit check --format json 2>/dev/null

# Python
pip-audit --format json 2>/dev/null
```

Classify findings: CRITICAL (known exploit), HIGH (CVE with no exploit), MEDIUM (indirect dep), LOW (dev-only dep).

### 3. Dependency Freshness

Check for outdated dependencies. Flag:
- **Major version behind**: MEDIUM (potential breaking changes, likely missing security fixes)
- **2+ major versions behind**: HIGH (significantly out of date)
- **Known EOL/deprecated**: HIGH (no future patches)

### 4. Test Coverage Gaps

Run coverage analysis and identify:
- **Files with zero coverage**: HIGH (untested code)
- **Files below project threshold**: MEDIUM (insufficient coverage)
- **New files without corresponding test files**: MEDIUM (test file missing)

### 5. Tech Debt Signals

Search for indicators:
```bash
# TODO/FIXME/HACK comments with age (from git blame)
grep -rn "TODO\|FIXME\|HACK" --include="*.{ts,tsx,js,jsx,rb,py,go}" .

# Files exceeding shape limits
# (use code-shape-check logic: >50 lines per file, >8 lines per function)

# High cyclomatic complexity functions
# (use cc-check logic)
```

### 6. Dead Code Detection

- Exported functions/classes with zero internal references
- Unused dependencies in package.json/Gemfile/requirements.txt
- Unreachable routes or unused API endpoints

### 7. Produce Report

Write to `pipeline-state/health-report-{date}.md`:

```markdown
---
project: {name}
scanned: {ISO 8601}
findings: {total count}
critical: {count}
high: {count}
medium: {count}
---

## Health Score: {A/B/C/D/F}

Scoring: A = 0 critical/high, B = 0 critical + <3 high, C = 0 critical + 3+ high, D = any critical, F = 5+ critical

## Critical Findings
1. [Security] CVE-2024-XXXX in {package} — remote code execution
2. [Coverage] {file} has zero test coverage and handles user input

## High Findings
...

## Medium Findings
...

## Recommendations
1. {Highest-impact fix with estimated effort}
2. {Second-highest}
3. {Third}
```

### 8. Auto-Create Tickets (Optional)

If Jira automation is configured (`~/.claude/automation/config.sh` exists and `JIRA_BASE_URL` is set):
- Create tickets for CRITICAL findings automatically
- Create tickets for HIGH findings if `HEALTH_SCAN_AUTO_TICKET=true`
- Each ticket references the health report and includes fix guidance

## Phase Output

```
Verdict: HEALTHY / NEEDS_ATTENTION / CRITICAL_ISSUES
Score: {A/B/C/D/F}
Findings: {critical}/{high}/{medium} (critical/high/medium)
Report: pipeline-state/health-report-{date}.md
Tickets created: {N} (if Jira configured)
```
$ARGUMENTS
