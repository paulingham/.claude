---
name: "security-review"
description: "Use when user wants to Review phase skill: spawn security-engineer agent for OWASP Top 10 audit, dependency scanning, secrets detection, and auth/authz review. Runs in parallel with code-review."
context: fork
agent: security-engineer
---

# Security Review

## Advisor Mode (Sonnet executor + Opus advisor)

**Pairing**: security-engineer ships with `executor: claude-sonnet-4-6` and `advisor: claude-opus-4-7` in its frontmatter. Sonnet drives the OWASP/secrets sweep, Opus is consulted for threat-model and severity-classification calls.

**Status**: This is the **intended default** — currently advisory because the Agent input schema does not yet expose `advisor`. Will become the enforced default the moment the schema lands. Until then, the `pre-agent-advisor.sh` PreToolUse hook logs the would-be pairing to `metrics/{session}/advisor-dispatch.jsonl` for observability; no spawn is blocked, no model is downgraded.

**Fallback semantics** (all log-only today, all enforced later):
- Frontmatter pairing present + `ANTHROPIC_API_KEY` set + `CLAUDE_REVIEW_ADVISOR_DISABLED` unset → executor=sonnet, advisor=opus (`source: frontmatter-pairing`)
- `CLAUDE_REVIEW_ADVISOR_DISABLED=1` → executor/advisor both null, `source: env-disabled` (operator override; pure `model:` opus solo)
- `ANTHROPIC_API_KEY` missing → executor/advisor both null, `source: no-api-key`
- Frontmatter omits executor/advisor (non-reviewer agents) → `source: no-pairing-frontmatter`

**Cost** (PROVISIONAL pending advisor-baseline):
- Naive Opus-solo cost vs. Sonnet+Opus-advisor pairing: roughly ~40% cheaper per review (PROVISIONAL — see `eval/baselines/{latest}-advisor-baseline.md`).
- Quality-equivalence claim (≥95% verdict-agreement on the regression suite) is also PROVISIONAL until advisor-baseline runs.

## What This Skill Does

Automates the Review phase security audit. Spawns a read-only security-engineer agent to assess security posture.

## Current Context
- Branch: !`git branch --show-current`
- Changed files: !`git diff main...HEAD --name-only 2>/dev/null || echo 'N/A'`
- Diff stats: !`git diff main...HEAD --stat 2>/dev/null || echo 'N/A'`

## When to Invoke

- After Build phase completes
- Run IN PARALLEL with `/code-review` — spawn both in a single message
- Both must APPROVE before advancing to Verify phase

## Process

### 1. Spawn Security Engineer

```
// Spawn in same message as code-reviewer for parallel execution
Agent({
  subagent_type: "security-engineer",
  prompt: "Security review of changes on this branch against main. Assess:
    - OWASP Top 10 vulnerabilities (injection, XSS, CSRF, etc.)
    - Authentication and authorization (are auth checks present and correct?)
    - Input validation at system boundaries
    - Secrets in code or commits (API keys, tokens, passwords)
    - Dependency vulnerabilities (run npm audit / bundle audit)
    - Secure cookie flags, HTTPS enforcement
    - Content-Type validation on file uploads
    Produce a verdict with severity levels: CRITICAL, HIGH, MEDIUM, LOW.
    APPROVE if no CRITICAL, HIGH, or MEDIUM findings. CHANGES_REQUESTED if any CRITICAL, HIGH, or MEDIUM findings exist. LOW and INFO findings are noted in the review output but do not block."
})
```

No `isolation: "worktree"` — security-engineer is read-only.

### 2. Process Verdict

- **APPROVE** (no CRITICAL/HIGH/MEDIUM): Advance. Record security summary for PR narrative.
- **CHANGES_REQUESTED**: Spawn engineer (with worktree) to fix CRITICAL/HIGH/MEDIUM findings. Then re-run both reviews.

## Security Checklist

- [ ] No SQL/NoSQL injection vectors
- [ ] No XSS vulnerabilities (output encoding, CSP)
- [ ] No hardcoded secrets or credentials
- [ ] Auth checks on all protected routes/endpoints
- [ ] Input validation on external boundaries
- [ ] Dependencies free of known CVEs (`npm audit` / `bundle audit`)
- [ ] Secure cookie flags (HttpOnly, Secure, SameSite)
- [ ] No sensitive data in logs or error messages
- [ ] HTTPS enforced for all external communication
- [ ] File upload validation (type, size, content)

## Supply Chain Security (if Trail of Bits plugins available)

When Trail of Bits security skills are installed (`supply-chain-risk-auditor`, `variant-analysis`, `differential-review`):

- [ ] Run `supply-chain-risk-auditor` on new/updated dependencies (typosquatting, maintainer compromise, post-install scripts)
- [ ] If a vulnerability is found, run `variant-analysis` to find similar patterns across the codebase
- [ ] Use `differential-review` for security-focused diff analysis on high-risk changes

These complement `npm audit`/`bundle audit` by covering supply chain threats that package auditors miss.

## Parallel Execution

This skill belongs to the `review` parallel group. It is dispatched via Parallel Dispatch Protocol (see `rules/_detail/parallel-dispatch-protocol.md`), not via sequential Skill tool invocation. The security-engineer agent reads this file directly and executes it.

When dispatched in parallel:
1. The orchestrator spawns code-reviewer + security-engineer in a single message
2. Each agent reads its own skill file independently
3. The orchestrator collects both verdicts before proceeding

## Prerequisite

- Build phase complete: BUILD_COMPLETE verdict from `/build-implementation`, `/refactor`, or `/bug-fix`
- Must be dispatched IN PARALLEL with `/code-review` via Parallel Dispatch Protocol

## Severity Grading

Every finding MUST be assigned a severity. Use the calibration table below:

| Severity | Definition | Examples | Blocks? |
|----------|-----------|----------|---------|
| CRITICAL | Security vulnerability or data loss risk | SQL injection, exposed secrets, auth bypass | Yes |
| HIGH | Correctness bug or significant design flaw | Missing error handling, broken invariant, SOLID violation | Yes |
| MEDIUM | Code quality issue causing maintenance pain | DRY violation across files, unclear naming, missing edge case test, unnecessary coupling | Yes |
| LOW | Minor improvement or style preference | Variable rename suggestion, comment improvement | No |
| INFO | Observation, context, or positive feedback | "Nice pattern," "FYI this also handles X" | No |

**Verdict rule:** APPROVE if no CRITICAL, HIGH, or MEDIUM findings. CHANGES_REQUESTED if any CRITICAL, HIGH, or MEDIUM findings exist. LOW and INFO are noted but do not block.

**In-cycle enforcement:** CHANGES_REQUESTED findings MUST be fixed in the current pipeline. The orchestrator is not permitted to downgrade findings to follow-up tickets, ship with known-broken security behavior, or ask the user whether to defer. See `rules/_detail/pipeline-protocol.md` § In-Cycle Fix Rule. If a finding is genuinely orthogonal (different attack surface, different module), mark it INFO, not MEDIUM.

## Phase Output

```
Verdict: APPROVE / CHANGES_REQUESTED
Next: If BOTH code-review and security-review APPROVE → /verify
      If CHANGES_REQUESTED → spawn engineer to fix → re-invoke BOTH review skills
Findings: [severity-rated findings: CRITICAL, HIGH, MEDIUM, LOW]
Agent summaries: [security-engineer's 2-3 sentence summary]
```
