# Security Baseline

## Input & Data
- Parameterized queries only — no SQL interpolation
- Input validation on all external boundaries
- Content-Type validation on file uploads

## Secrets & Access
- No secrets in code, commits, or logs
- RBAC deny-by-default at controller/resolver level
- HTTPS everywhere, secure cookie flags (HttpOnly, Secure, SameSite)

## Dependencies
- Audit dependencies before shipping (`bundle audit`, `npm audit`, `pip-audit`)
- Lock files committed, no outdated packages with known CVEs

## Environment Segregation
- Local/staging/production environments fully isolated
- Environment-specific secrets never shared across boundaries
- CI/CD pipelines verify no prod credentials in test
