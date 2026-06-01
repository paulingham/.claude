---
disable-model-invocation: true
name: "deploy"
description: "Use when user wants to Continuous deployment skill: environment-aware deploy with pre-flight checks, staging verification, production rollout, and rollback. Closes the gap between PR merge and production."
context: fork
agent: infrastructure-engineer
argument-hint: "Target environment (staging|production) and optional deployment strategy"
---

# Deploy

## What This Skill Does

Manages the deployment phase after a PR is merged. Detects the deployment platform, runs pre-deploy checks, deploys to the target environment, verifies the deployment, and provides rollback procedures if verification fails.

## When to Invoke

- After `/harness:pr-creation` succeeds and PR is merged
- When deploying a specific branch or tag to staging/production
- When rolling back a failed deployment

## Process

### Step 1: Detect Deployment Platform

Scan the project for deployment configuration:

| File | Platform | Deploy Command |
|------|----------|---------------|
| `fly.toml` | Fly.io | `fly deploy` |
| `Procfile` + `app.json` | Heroku | `git push heroku` / `heroku container:push` |
| `vercel.json` or `next.config.*` | Vercel | `vercel --prod` |
| `Dockerfile` + `docker-compose.yml` | Docker Compose | `docker compose up -d` |
| `.github/workflows/deploy.yml` | GitHub Actions CD | Push triggers workflow |
| `terraform/` or `*.tf` | Terraform + cloud | `terraform apply` |
| `serverless.yml` | Serverless Framework | `serverless deploy` |
| `render.yaml` | Render | Push triggers deploy |
| `railway.json` | Railway | `railway up` |

If no deployment config is found, recommend `/harness:infra-scaffold` first.

### Step 2: Pre-Deploy Checks

All checks must pass before deployment proceeds:

```
1. Tests green:        Run full test suite (project CLAUDE.md Commands section)
2. Migrations pending: Check for unapplied migrations (rails db:migrate:status / prisma migrate status / alembic heads)
3. Env vars set:       Verify required env vars exist in target environment
4. Dependencies:       No known CVEs (npm audit / bundle audit / pip-audit)
5. Build succeeds:     Compile/build step passes (npm run build / bundle exec rake assets:precompile)
6. Branch is clean:    No uncommitted changes, branch is up-to-date with main
7. Security review:    Verify pipeline-state/{task-id}/review.md has security_verdict: APPROVE
```

Output pre-deploy checklist with PASS/FAIL per item. Any FAIL = deployment blocked.

### Step 3: Deploy to Target Environment

#### Staging (default first deploy)
```
1. Deploy to staging environment
2. Wait for health check to pass (GET /health or /api/health — 200 OK)
3. Run smoke tests against staging URL
4. If smoke tests fail: ROLLBACK and report
5. If smoke tests pass: report staging URL and verification results
```

#### Production
```
1. Confirm staging deployment verified (require staging verification artifact)
2. Select deployment strategy based on risk:
   - Rolling update: default for stateless services
   - Blue-green: for zero-downtime with instant rollback
   - Canary: for high-risk changes (route 10% → 50% → 100%)
3. Deploy with selected strategy
4. Monitor health checks for 5 minutes
5. Run smoke tests against production URL
6. If any failure: execute rollback procedure
```

### Step 4: Post-Deploy Verification

Run verification suite against the deployed environment:

```markdown
## Post-Deploy Verification
- [ ] Health endpoint returns 200 OK
- [ ] Key API endpoints respond correctly (smoke test)
- [ ] No new errors in application logs (last 5 minutes)
- [ ] Response times within acceptable range (<500ms p95)
- [ ] Database connections healthy
- [ ] Background job processor running (if applicable)
- [ ] WebSocket/real-time connections functional (if applicable)
```

### Step 5: Rollback Procedure

If post-deploy verification fails:

| Platform | Rollback Command |
|----------|-----------------|
| Fly.io | `fly releases rollback` |
| Heroku | `heroku rollback` |
| Vercel | Vercel dashboard → promote previous deployment |
| Docker Compose | `docker compose down && docker compose pull && docker compose up -d` (use tagged images, not git checkout) |
| Terraform | Revert Terraform code to previous commit, then `terraform plan && terraform apply`. Terraform rollbacks are complex — escalate if uncertain. |
| GitHub Actions | Re-run previous successful workflow |

After rollback:
1. Verify health check passes on rolled-back version
2. Investigate failure cause
3. Create a bug fix story via `/harness:intake`
4. Re-enter pipeline from Build phase

### Step 6: Post-Deploy Verification (Automatic)

After successful deployment, invoke `/harness:deployment-verification` with the deployed URL and environment. This runs health checks, smoke tests, and error rate monitoring for 5 minutes. If verification fails, it triggers automatic rollback.

The deploy phase is only DEPLOYED after `/harness:deployment-verification` returns DEPLOYMENT_VERIFIED.

### Step 7: Migration Pre-Check

Before deploying code with pending database migrations:
1. Verify migrations are backwards-compatible with the currently running code
2. For destructive migrations (column removal, rename): confirm the two-phase deployment is in progress (per `/harness:db-migration` Step 4)
3. Run migrations BEFORE deploying new code (if additive) or AFTER (if removing old columns)
4. Verify migration completed successfully before proceeding with code deployment

## Deployment Strategies Reference

### Rolling Update (default)
- Replace instances one at a time
- Zero-downtime if health checks configured
- Rollback: redeploy previous version
- Use for: most deployments, stateless services

### Blue-Green
- Run two identical environments (blue = current, green = new)
- Switch traffic from blue to green after verification
- Rollback: switch traffic back to blue
- Use for: critical services, database migrations that are backwards-compatible

### Canary
- Route small percentage of traffic to new version
- Monitor error rates and latency
- Gradually increase traffic percentage
- Rollback: route 100% back to stable
- Use for: high-risk changes, new features with uncertain impact

## Phase Output

```
Verdict: DEPLOYED / DEPLOY_FAILED / ROLLED_BACK
Next: Monitor production / Investigate failure / Re-enter pipeline
Artifacts: [deployment URL, health check results, smoke test results, rollback status]
Environment: [staging/production]
Strategy: [rolling/blue-green/canary]
```
$ARGUMENTS
