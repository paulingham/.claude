# Multi-Repo / Multi-Service Patterns

## Monorepo vs Polyrepo Decision

| Factor | Monorepo | Polyrepo |
|--------|----------|----------|
| Team structure | Single team or tightly coupled teams | Independent teams, different cadences |
| Language | Same language/toolchain | Different languages per service |
| Deployment | Coordinated releases OK | Independent deployment critical |
| Code sharing | Lots of shared code | Minimal sharing (contracts only) |
| CI/CD | Unified pipeline | Per-repo pipelines |
| Tooling | Nx, Turborepo, Bazel, Rush | Standard git + package registry |

**Hybrid (recommended for most):** Shared libraries in a monorepo, services in separate repos. Best of both — shared types are atomic, services deploy independently.

## Repository Structure (Polyrepo)

```
Typical omnichannel service map:

github.com/org/
  api-gateway/           — API gateway config (Kong/Traefik/NGINX)
  user-service/          — Auth, identity, profiles
  task-service/          — Core business logic
  billing-service/       — Payments, subscriptions
  notification-service/  — Email, push, SMS, voice notifications
  web-app/               — Next.js web frontend
  mobile-app/            — React Native mobile app
  voice-skill/           — Alexa/Google voice skill
  device-firmware/       — IoT device firmware
  shared-contracts/      — OpenAPI specs, Protobuf, event schemas
  shared-types/          — TypeScript/language type packages
```

## Shared Contract Management

### Contract-First Development
```
1. Define the contract (OpenAPI, Protobuf, JSON Schema, GraphQL SDL)
2. Review the contract (all consumers participate)
3. Publish the contract (to shared-contracts repo or schema registry)
4. Generate clients from contract (openapi-generator, protoc, graphql-codegen)
5. Implement the provider (must pass contract tests)
6. Implement consumers (using generated clients)
```

### Schema Registry
```
Central store for versioned schemas:
  - Confluent Schema Registry (for Kafka/event schemas)
  - Buf Schema Registry (for Protobuf)
  - SwaggerHub / Stoplight (for OpenAPI)
  - Git repo (shared-contracts/) with CI validation

Compatibility rules:
  - BACKWARD: new schema can read old data (safe for consumers)
  - FORWARD: old schema can read new data (safe for providers)
  - FULL: both backward and forward compatible
  - Default: BACKWARD (consumers update first)
```

### Contract Evolution Rules
```
SAFE changes (backward compatible):
  ✓ Add optional field
  ✓ Add new endpoint
  ✓ Add new event type
  ✓ Widen a type (int32 → int64)

BREAKING changes (require versioning):
  ✗ Remove field
  ✗ Rename field
  ✗ Change field type
  ✗ Remove endpoint
  ✗ Change required/optional

Breaking change protocol:
  1. Add v2 endpoint (keep v1 running)
  2. Migrate consumers to v2 (with timeline)
  3. Deprecate v1 (Sunset header, log warnings)
  4. Remove v1 after all consumers migrated
  5. Typical migration window: 2-4 weeks
```

## Cross-Repo Dependency Management

### Shared Library Publishing
```
Package registries:
  - npm: GitHub Packages, npmjs.com (private), Verdaccio
  - Ruby: private gem server, GitHub Packages
  - Python: private PyPI (devpi), GitHub Packages
  - Go: Go modules (tag-based versioning in Git)

Publishing workflow:
  1. PR to shared-types/ repo
  2. CI runs tests + compatibility check
  3. Merge triggers version bump + publish
  4. Dependabot/Renovate opens PRs in consuming repos
```

### Semantic Versioning
```
MAJOR.MINOR.PATCH
  1.0.0 → 1.1.0 (new feature, backward compatible)
  1.1.0 → 1.2.0 (another feature)
  1.2.0 → 2.0.0 (breaking change)

Rules for shared packages:
  - PATCH: bug fixes only (no API changes)
  - MINOR: additive changes (new functions, new fields)
  - MAJOR: breaking changes (removed functions, changed signatures)
  - Pin exact versions in services: "shared-types": "1.2.3"
  - Use ranges in development: "shared-types": "^1.2.0"
```

## Cross-Repo Testing

### Consumer-Driven Contract Tests
```
Consumer (web-app) writes:
  "I expect GET /api/v1/tasks to return { id: string, title: string, status: string }"

Provider (task-service) verifies:
  Run consumer's expectations against real API → all pass? Contract upheld.

Tools: Pact (HTTP), Specmatic (OpenAPI-based), custom schema validation

CI integration:
  - Consumer publishes contract to Pact Broker on PR merge
  - Provider CI runs contract verification on every build
  - Provider cannot deploy if consumer contracts fail
```

### Integration Test Environments
```
Shared staging:
  - Each service deploys to staging independently
  - Service versions are tracked (service A: v1.2, service B: v3.1)
  - Cross-service smoke tests run after each deploy
  - Staging mirrors production topology

Ephemeral environments (preferred for PR review):
  - Spin up full environment per PR (using Docker Compose or K8s namespaces)
  - Run cross-service tests in isolation
  - Tear down after PR merge
  - More expensive but avoids staging contention
```

## Cross-Repo CI/CD Coordination

### Independent Deployments (Default)
```
Each service deploys independently via its own CI/CD pipeline.
Services must be backward compatible — no coordinated deployment required.

Independent deployment rules:
  1. New endpoint → deploy provider first, then consumers
  2. Remove endpoint → deploy consumers first, then provider
  3. Change payload → version the endpoint, deploy in parallel
  4. Shared library update → each consumer updates on its own timeline
```

### Coordinated Deployments (When Needed)
```
When a change requires multiple services to deploy together:

1. Create an "umbrella issue" that tracks PRs across all affected repos
2. Each repo has its PR with the relevant changes
3. PRs reference the umbrella issue
4. Deploy order is documented in the umbrella issue
5. Each deploy is followed by cross-service smoke tests
6. If any deploy fails: halt remaining deploys, investigate

CI triggers:
  - GitHub Actions: repository_dispatch event
  - Contract change in shared-contracts/ → triggers CI in all consuming repos
  - Webhook on schema registry update → triggers provider verification
```

### Backwards Compatibility Window
```
When changing an API:
  Old: GET /api/v1/tasks → { tasks: [...] }
  New: GET /api/v2/tasks → { data: [...], meta: { total, page } }

Window:
  Week 1: Deploy v2 alongside v1 (both active)
  Week 2: Consumers migrate to v2
  Week 3: Monitor v1 usage (should be zero)
  Week 4: Remove v1

Sunset header (RFC 8594):
  Sunset: Sat, 01 Apr 2026 00:00:00 GMT
  Deprecation: true
  Link: <https://docs.api.com/migration>; rel="sunset"
```

## Service Catalog

```
Central registry of all services (even in polyrepo):

| Service | Owner | Repo | Health | API Docs | On-Call |
|---------|-------|------|--------|----------|---------|
| user-service | Auth team | github.com/org/user-service | /health | /docs | @auth-oncall |
| task-service | Product team | github.com/org/task-service | /health | /docs | @product-oncall |

Tools: Backstage (Spotify), Port, OpsLevel, custom wiki

Minimum per service:
  - README with setup instructions
  - OpenAPI spec (auto-generated or hand-written)
  - Health endpoint
  - Runbook for common incidents
  - Owner and on-call rotation
```

## Local Development

```
Working on one service locally while depending on others:

Option 1: Docker Compose with all services (heavyweight but accurate)
  docker-compose -f docker-compose.deps.yml up

Option 2: Service stubs / mocks (lightweight, fast)
  Mock external services with recorded responses (WireMock, Prism)
  Only run the service you're working on + database

Option 3: Shared dev environment (remote)
  Run dependent services in a shared dev cluster
  Your local service connects to remote dependencies
  Tools: Telepresence, Tilt, Skaffold

Recommendation: Option 2 for day-to-day development, Option 1 for integration testing
```

## Anti-Patterns

```
- Distributed monolith: services that must deploy together defeat the purpose
- Shared database: services sharing tables creates tight coupling — each service owns its data
- Chatty services: if service A calls service B 10 times per request → merge them
- No contract tests: deploying without contract verification = production surprises
- No service catalog: "which team owns this?" should never be a question
- Versioning everything: only version external/public APIs. Internal APIs can evolve freely
  with contract tests as the safety net
```
