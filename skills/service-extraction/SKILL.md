---
name: "service-extraction"
description: "Use when user wants to Full autonomous service extraction: analyze monolith boundaries, create new GitHub repo, move code, generate contracts, refactor monolith, wire CI/CD, open PRs in both repos. End-to-end."
context: fork
agent: software-engineer
argument-hint: "What to extract (e.g., 'extract billing module into billing-service')"
---

# Service Extraction

## What This Skill Does

Autonomously extracts a bounded context from a monolith into its own repository. Handles everything: analysis, repo creation, code migration, contract generation, monolith refactoring, CI/CD setup, and PRs in both repos. The human approves the plan — the system executes it.

## When to Invoke

- A module has grown large enough to warrant independent deployment
- Team boundaries require separate repos (different teams, different cadences)
- A component needs independent scaling (e.g., billing, notifications, search)
- Compliance requires data isolation (e.g., PII service, payment processing)

## Prerequisites

- `gh` CLI authenticated (`gh auth status`)
- Git configured with push access to the GitHub org
- Current repo is the monolith being extracted from
- Project CLAUDE.md exists with architecture context

## Process

### Step 0 — Forcing-Function Gate

Before any extraction work, verify at least one FF from `rules/module-boundaries-protocol.md` is named in the task context:

1. Scan the task description for explicit FF phrasing (compliance, scaling, polyglot, blast radius, team ownership, regulatory, HIPAA, PCI, GDPR, data residency).
2. Scan pipeline state (`pipeline-state/{task-id}-intake.md`) for an intake-stamped FF rationale.
3. If neither is present, exit immediately with verdict `WRONG_SKILL: no forcing function detected — use /module-extraction instead`.

### Step 1: Analyze Extraction Boundary

Identify what's being extracted:

```markdown
## Extraction Analysis

### Module to Extract
- Name: [billing, notifications, search, etc.]
- Root directory: [src/billing/, app/services/billing/, etc.]

### Files Belonging to This Module
[List all files — models, services, controllers, tests, migrations]

### Dependencies: Module → Monolith (what the module needs FROM the monolith)
- [User model — needs user_id for ownership]
- [Auth middleware — needs authentication context]
- [Database — currently shares the monolith DB]

### Dependencies: Monolith → Module (what the monolith needs FROM the module)
- [BillingService.charge() — called from OrderController]
- [Subscription.active? — checked in access control]

### Shared Database Tables
- [subscriptions — owned by billing module]
- [invoices — owned by billing module]
- [users — shared, stays in monolith]

### Boundary API (what the contract needs to cover)
- [POST /api/v1/billing/charge — create a charge]
- [GET /api/v1/billing/subscriptions/:user_id — get subscription status]
- [Event: subscription.changed — published when status changes]
```

Present this analysis to the user for approval before proceeding.

### Step 2: Create the New Repository (Manifest-Driven)

Read GitHub config from the project manifest (`~/.claude/manifests/{project-name}.md`). If no manifest exists, auto-create one (see `rules/multi-repo-protocol.md`).

```bash
# Read config from manifest (org, visibility, template, branch_protection)
# Defaults: org from current repo, private, no template, branch protection on

ORG=$(gh repo view --json owner -q '.owner.login')
SERVICE_NAME="[extracted-service-name]"

# Create repo — use template from manifest if configured
gh repo create "${ORG}/${SERVICE_NAME}" \
  --private \
  --description "[Service description]" \
  --clone
# If manifest has template: add --template "${ORG}/${TEMPLATE}"

# Branch protection from manifest config (defaults: required_reviews=1, require_ci=true)
gh api repos/${ORG}/${SERVICE_NAME}/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["test"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1}'

# Create environments from manifest config (defaults: staging + production)
gh api repos/${ORG}/${SERVICE_NAME}/environments/staging --method PUT
gh api repos/${ORG}/${SERVICE_NAME}/environments/production --method PUT

# Update manifest with new repo entry
# → Add to ## Repos table: name, path, role=provider, github, status=active
# → Add to ## Dependencies table if provider/consumer relationships exist
# → Add to ## Deploy Order based on dependency graph
```

After repo creation, run `/project-setup` in the new repo automatically (not a separate command).

### Step 3: Scaffold the New Service

In the cloned new repo, use `/microservices-scaffold` to generate:
- Dockerfile (multi-stage, non-root user, health check)
- docker-compose.yml (with own database + dependencies)
- CI/CD pipeline (GitHub Actions: test, lint, build, deploy)
- Health endpoints (/health, /health/ready, /health/live)
- .env.example with required variables
- .dockerignore
- CLAUDE.md with Service Context section:
  ```markdown
  ## Service Context
  - Role: service
  - Upstream: [monolith services this depends on]
  - Downstream: [monolith — calls this service's API]
  - Contracts: contracts/openapi.yaml, contracts/events.json
  - Deploy Dependencies: [user-service must be healthy]
  ```

### Step 4: Migrate Code to New Service

```bash
# Copy module files to new service repo (preserving structure)
# DO NOT use git filter-branch — clean copy is simpler and safer

# For each file in the extraction boundary:
cp -r src/billing/* ../new-service/src/
cp -r test/billing/* ../new-service/test/

# Adapt imports/requires to new project structure
# Remove monolith-specific dependencies
# Replace direct DB access with own database connection
# Replace shared model references with local models or API calls
```

Restructure to match the new service's architecture:
```
src/
  api/           — HTTP endpoints (from old controllers)
  domain/        — Business logic (from old services/models)
  infrastructure/ — Database, external clients
  events/        — Published and consumed events
contracts/
  openapi.yaml   — API contract for consumers
  events.json    — Event schema for subscribers
```

### Step 5: Generate the Boundary Contract

Create the API contract that replaces direct function calls:

**OpenAPI spec** (`contracts/openapi.yaml`):
```yaml
openapi: 3.0.3
info:
  title: [Service] API
  version: 1.0.0
paths:
  /api/v1/billing/subscriptions/{userId}:
    get:
      summary: Get subscription status
      parameters:
        - name: userId
          in: path
          required: true
          schema: { type: string }
      responses:
        '200':
          description: Subscription details
```

**Event schema** (`contracts/events.json`):
```json
{
  "subscription.changed": {
    "type": "object",
    "properties": {
      "user_id": { "type": "string" },
      "status": { "type": "string", "enum": ["active", "past_due", "canceled"] },
      "plan": { "type": "string" },
      "changed_at": { "type": "string", "format": "date-time" }
    }
  }
}
```

### Step 6: Write Tests for the New Service

Using TDD (per `/build-implementation`):
- Unit tests for migrated business logic
- Integration tests for API endpoints
- Contract tests (verify the OpenAPI spec matches the implementation)
- Event publishing tests (verify events match the schema)

### Step 7: Commit and Push the New Service

```bash
cd ../new-service
git add -A
git commit -m "feat: initial service extraction from monolith

Extracted [module] into independent service.
- API endpoints: [list]
- Events published: [list]
- Database: independent (migrated tables)
- Contract: contracts/openapi.yaml

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"

git push -u origin main
```

### Step 8: Refactor the Monolith

Back in the monolith repo, on a feature branch:

```bash
git checkout -b extract-[service-name]
```

**Replace direct calls with HTTP client calls:**
```typescript
// BEFORE (direct call):
const subscription = await BillingService.getSubscription(userId);

// AFTER (HTTP client to new service):
const subscription = await billingClient.getSubscription(userId);
```

**Create the HTTP client** (with circuit breaker, retry, timeout):
```typescript
class BillingServiceClient {
  constructor(private http: HttpClient, private baseUrl: string) {}

  async getSubscription(userId: string): Promise<Subscription> {
    return this.http.get(`${this.baseUrl}/api/v1/billing/subscriptions/${userId}`);
  }
}
```

**Replace event publishing** (if the module published events inline):
```typescript
// BEFORE: direct event emission
eventBus.emit('subscription.changed', data);

// AFTER: the new service publishes events — monolith subscribes
eventBus.subscribe('subscription.changed', handleSubscriptionChange);
```

**Remove extracted code** from the monolith:
- Delete the module's source files
- Delete the module's tests
- Remove database migrations for extracted tables (or mark as "migrated to [service]")
- Update imports across the monolith
- Remove unused dependencies

**Add the new service as a dependency in docker-compose** (for local dev):
```yaml
services:
  billing-service:
    image: ${ORG}/billing-service:latest
    # Or build from local path during development
    ports: ["3001:3000"]
```

### Step 9: Verify Both Sides

In the new service:
```bash
cd ../new-service
npm test  # All tests pass
```

In the monolith:
```bash
cd ../monolith
npm test  # All tests pass (with new service running or mocked)
```

Run cross-service contract tests:
```bash
# Verify monolith's client expectations match new service's API
npx specmatic test --contract contracts/openapi.yaml --host localhost:3001
```

### Step 10: Open PRs in Both Repos

**New service PR** (if working on a branch):
```bash
cd ../new-service
gh pr create \
  --title "feat: [service-name] — extracted from monolith" \
  --body "$(cat <<'PREOF'
## Summary
- Extracted [module] from [monolith-repo] into independent service
- API contract: contracts/openapi.yaml
- Events: contracts/events.json
- Independent database with migrated schema
- CI/CD pipeline configured
- Health endpoints: /health, /health/ready, /health/live

## Test plan
- [ ] All unit tests pass
- [ ] API contract tests pass
- [ ] Health endpoint responds
- [ ] Docker build succeeds
- [ ] CI pipeline green

🤖 Generated with [Claude Code](https://claude.com/claude-code)
PREOF
)"
```

**Monolith PR:**
```bash
cd ../monolith
gh pr create \
  --title "refactor: extract [module] to [service-name] service" \
  --body "$(cat <<'PREOF'
## Summary
- Replaced direct [module] calls with HTTP client to [service-name]
- Removed extracted source files and tests
- Added [service-name] to docker-compose for local dev
- Contract tests verify client compatibility

## Migration
- [service-name] must be deployed and healthy before merging this PR
- Deploy order: [service-name] first, then this PR

## Test plan
- [ ] All monolith tests pass
- [ ] Contract tests pass against [service-name]
- [ ] No remaining references to extracted module

🤖 Generated with [Claude Code](https://claude.com/claude-code)
PREOF
)"
```

### Step 11: Set Up New Repo CI/CD Secrets

```bash
cd ../new-service

# Copy relevant secrets from monolith repo (if accessible)
# Or prompt user to set them
gh secret set DATABASE_URL --body "[prompt user or derive from convention]"

# Set up deployment secrets based on platform
# Fly.io: gh secret set FLY_API_TOKEN
# Heroku: gh secret set HEROKU_API_KEY
# AWS: gh secret set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY
```

If secrets cannot be determined automatically, output a checklist:
```
## Manual Setup Required
- [ ] Set DATABASE_URL secret in [service-name] repo
- [ ] Set deployment credentials (platform-specific)
- [ ] Configure DNS for [service-name] endpoint
- [ ] Add [service-name] health check to monitoring
```

### Step 12: Update Service Catalog

Update the monolith's CLAUDE.md Service Context:
```markdown
## Service Context
- Role: monolith (extracting services)
- Downstream: billing-service (extracted 2026-03-22)
- Contracts: contracts/billing-api.yaml (consumed)
```

## Safety Checks

- **Never delete monolith code before new service is verified** — extract, verify, then delete
- **Never force-push to the new repo** — treat it as production from creation
- **Always create the contract before migrating code** — contract-first development
- **Always run both test suites before opening PRs** — both sides must be green
- **Branch protection on new repo from day one** — no direct pushes to main

## Phase Output

```
Verdict: SERVICE_EXTRACTED / EXTRACTION_BLOCKED
Next: Deploy new service, then merge monolith PR
Artifacts: [new repo URL, monolith PR URL, contract files, migration checklist]
New Repo: https://github.com/{org}/{service-name}
Monolith PR: https://github.com/{org}/{monolith}/pull/N
New Service PR: https://github.com/{org}/{service-name}/pull/N
Contract: contracts/openapi.yaml
```
$ARGUMENTS
