# Security Assessment: Sample Feature

## Risk Level: LOW

## Findings

- **rules.py.security.sql-injection** `src/queries.py:42` — agent_verdict: confirmed
  - Severity: HIGH

## Dismissed

- **rules.py.security.weak-hash** `src/auth.py:88` — this rule was dismissed.

## Not Applicable

- ~~**rules.py.security.lfi** `src/files.py:11`~~ — wrapped in strikethrough.

## Dependency Audit
No new dependencies.
