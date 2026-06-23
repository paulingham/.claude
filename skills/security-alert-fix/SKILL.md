---
name: "security-alert-fix"
description: "Use when the user wants to investigate and fix open GitHub security alerts (CodeQL code-scanning + secret-scanning). Enumerates open alerts via gh api, groups them by rule, drives proper fixes (not suppressions) through the pipeline, and surfaces secret-revocation as a required manual action."
---

# Security Alert Fix

Enumerate and properly fix open GitHub code-scanning and secret-scanning alerts. Fixes address the underlying data-flow or config issue — never CodeQL-ignore comments or `# nosec` suppressions. Secret-scanning alerts additionally require provider-side revocation as a required manual user action.

## When to Use

When the user asks to investigate or fix open security issues or alerts, or after a CodeQL or secret-scanning run surfaces findings. Note: GitHub "security issues" usually means the Security tab (code-scanning / Dependabot / secret-scanning alerts), NOT the Issues tab — check both.

## Steps

1. **Enumerate** — fetch all open alert sources:
   ```bash
   gh api repos/{owner}/{repo}/code-scanning/alerts --paginate \
     --jq '.[] | select(.state=="open") | {number, severity: .rule.security_severity_level, rule: .rule.id, path: .most_recent_instance.location.path, line: .most_recent_instance.location.start_line}'
   gh api repos/{owner}/{repo}/secret-scanning/alerts
   gh api repos/{owner}/{repo}/dependabot/alerts
   gh issue list --label security
   ```
   The Issues tab (`gh issue list --label security`) is a separate source — check it too.

2. **Group by rule** — cluster alerts that share a CodeQL rule id. Examples: all `actions/missing-workflow-permissions` alerts become one least-privilege `permissions:` block per workflow; all `py/clear-text-logging-sensitive-data` alerts become one taint-break at the env/secret read site.

3. **Fix properly** — route each group through the pipeline (Build → review → verify). Common fixes by rule:
   - `actions/missing-workflow-permissions`: add a top-level least-privilege `permissions:` block (`contents: read` for read-only CI).
   - `py/incomplete-url-substring-sanitization`: replace `.startswith(host)` checks with parsed-host comparison (`urlparse(url).hostname == …`, exact match).
   - `py/clear-text-logging-sensitive-data` / `py/clear-text-storage-sensitive-data`: sever the source→sink taint — read sensitive env vars into a local boolean or allowlisted constant before any I/O so the raw value never flows to a sink; never emit raw secret text.

4. **Secrets are different** — a secret-scanning alert (leaked token) requires REVOCATION at the provider (the harness cannot do this). Surface it as a required manual user action with the exact URL (e.g. `huggingface.co/settings/tokens`), remove the secret from HEAD, add a guard preventing re-commit, and only mark the alert resolved after the user confirms revocation. Do NOT rewrite git history unless the user explicitly requests it alongside revocation — it is destructive and pointless without revocation.

5. **Verify** — re-run the test suite for each touched file; confirm behavior is preserved. After merge, the next CodeQL run should auto-close the fixed alerts.

## Output

Per-alert fixes committed through the pipeline, plus a summary listing each alert number, its rule, the fix applied, and any required manual follow-up (secret revocation).

## See Also

- `skills/security-review/SKILL.md` — the broader OWASP/SAST review phase; this skill is alert-driven and narrower.
- `protocols/pipeline-protocol.md` — fixes route through the standard pipeline.
