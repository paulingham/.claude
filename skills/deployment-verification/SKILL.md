---
disable-model-invocation: true
name: "deployment-verification"
description: "Use when user wants to Post-deploy verification: health checks, smoke tests against live URL, error rate monitoring, automatic rollback trigger. Runs after /harness:deploy."
context: fork
agent: infrastructure-engineer
argument-hint: "Deployed URL and environment (e.g., 'https://staging.app.com staging')"
---

# Deployment Verification

## What This Skill Does

Verifies a deployment is healthy after `/harness:deploy` completes. Hits the live URL, runs smoke tests, monitors error rates, and triggers rollback if verification fails. This is the automated gate between "deployed" and "confirmed working."

## When to Invoke

- Automatically after `/harness:deploy` reports DEPLOYED
- Manually when verifying a deployment in any environment

## Process

### Step 1: Health Check Verification

```bash
# Hit health endpoint, verify 200 OK
curl -sf "${DEPLOY_URL}/health" | jq .

# Hit readiness endpoint, verify all dependencies connected
curl -sf "${DEPLOY_URL}/health/ready" | jq .
```

Retry up to 5 times with 10-second intervals (services may need startup time).

If health check fails after 5 retries: **TRIGGER ROLLBACK** (invoke `/harness:deploy` with rollback flag).

### Step 2: Smoke Tests

Run critical-path requests against the live URL:

```markdown
## Smoke Test Checklist
- [ ] GET /health → 200 OK
- [ ] GET /health/ready → 200 with all checks passing
- [ ] GET /api/v1/[primary-resource] → 200 (list endpoint works)
- [ ] POST /api/v1/auth/login → 200 or 401 (auth endpoint responds)
- [ ] GET /[frontend-route] → 200 (if web frontend deployed)
- [ ] Response times < 1s for all endpoints
```

Adapt endpoints based on the project's API routes (check project CLAUDE.md or OpenAPI spec).

### Step 3: Error Rate Monitoring

```
Monitor for 5 minutes after deployment:
1. Check application logs for new errors (grep for ERROR, FATAL, 5xx)
2. Compare error rate to pre-deploy baseline
3. If error rate > 2x baseline: flag as WARNING
4. If error rate > 5x baseline: TRIGGER ROLLBACK

Tools (check what's available):
- Sentry: check for new error spikes via API
- Application logs: tail and count errors
- Health endpoint: poll every 30 seconds for 5 minutes
```

### Step 4: Database Verification

```
- [ ] Pending migrations: none (all applied)
- [ ] Connection pool healthy (not exhausted)
- [ ] No long-running queries from deployment (check pg_stat_activity or equivalent)
```

### Step 5: Rollback Decision

| Condition | Action |
|-----------|--------|
| All checks pass, no errors | DEPLOYMENT_VERIFIED |
| Health check fails after retries | AUTO_ROLLBACK |
| Error rate > 5x baseline | AUTO_ROLLBACK |
| Smoke tests fail | AUTO_ROLLBACK |
| Minor warnings, endpoints respond | DEPLOYMENT_VERIFIED_WITH_WARNINGS |

On AUTO_ROLLBACK:
1. Execute platform rollback (per `/harness:deploy` Step 5)
2. Verify rollback health check passes
3. Report: what failed, rollback status, recommended investigation

## Phase Output

```
Verdict: DEPLOYMENT_VERIFIED / DEPLOYMENT_VERIFIED_WITH_WARNINGS / AUTO_ROLLBACK
Next: Monitor dashboards / Investigate rollback cause
Artifacts: [health check results, smoke test results, error rate comparison, rollback status]
Environment: [staging/production]
Duration: [time from deploy to verification complete]
```
$ARGUMENTS
