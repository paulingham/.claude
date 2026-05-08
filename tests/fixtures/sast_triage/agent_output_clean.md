# Security Assessment: Sample Feature

## Risk Level: HIGH

## Findings

- **rules.py.security.sql-injection** `src/queries.py:42` — agent_verdict: confirmed
  - Severity: HIGH
  - Remediation: parameterize the query.
- **rules.py.security.weak-hash** `src/auth.py:88` — agent_verdict: downgraded
  - Original SAST severity: HIGH; downgraded to LOW.
  - Rationale: hash usage is for cache-key only, not authentication.

## Dependency Audit
No new dependencies.

## Secrets Scan
No leaked secrets.
