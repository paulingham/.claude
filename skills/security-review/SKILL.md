---
name: "Security Review"
description: "Review phase skill: spawn security-engineer agent for OWASP Top 10 audit, dependency scanning, secrets detection, and auth/authz review. Runs in parallel with code-review."
parallel_group: "review"
---

# Security Review

## What This Skill Does

Automates the Review phase security audit. Spawns a read-only security-engineer agent to assess security posture.

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
    APPROVE if no CRITICAL or HIGH findings. CHANGES_REQUESTED otherwise."
})
```

No `isolation: "worktree"` — security-engineer is read-only.

### 2. Process Verdict

- **APPROVE** (no CRITICAL/HIGH): Advance. Record security summary for PR narrative.
- **CHANGES_REQUESTED**: Spawn engineer (with worktree) to fix CRITICAL/HIGH findings. Then re-run both reviews.

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

## Parallel Execution

This skill belongs to the `review` parallel group. It is dispatched via Parallel Dispatch Protocol (see `rules/parallel-dispatch-protocol.md`), not via sequential Skill tool invocation. The security-engineer agent reads this file directly and executes it.

When dispatched in parallel:
1. The orchestrator spawns code-reviewer + security-engineer in a single message
2. Each agent reads its own skill file independently
3. The orchestrator collects both verdicts before proceeding

## Prerequisite

- Build phase complete: BUILD_COMPLETE verdict from `/build-implementation`, `/refactor`, or `/bug-fix`
- Must be dispatched IN PARALLEL with `/code-review` via Parallel Dispatch Protocol

## Phase Output

```
Verdict: APPROVE / CHANGES_REQUESTED
Next: If BOTH code-review and security-review APPROVE → /verify
      If CHANGES_REQUESTED → spawn engineer to fix → re-invoke BOTH review skills
Findings: [severity-rated findings: CRITICAL, HIGH, MEDIUM, LOW]
Agent summaries: [security-engineer's 2-3 sentence summary]
```
