---
name: "microservices-scaffold"
description: "Use when user wants to Scaffold a new microservice: service template, API gateway config, service discovery, inter-service communication, distributed tracing wiring. For when monolith extraction is needed."
context: fork
agent: infrastructure-engineer
argument-hint: "Service name and responsibility (e.g., 'billing-service: handles subscriptions and payments')"
---

# Microservices Scaffold

## What This Skill Does

Scaffolds a new microservice when extracting from a monolith or building a service-oriented architecture. Generates the service structure, inter-service communication patterns, API gateway configuration, and distributed tracing wiring.

## When to Invoke

- Extracting a bounded context from a monolith
- Adding a new independent service to an existing microservices architecture
- Setting up API gateway routing for multiple services

**Important:** Default to monolith-first. Only invoke this skill when there is a clear reason for service separation (team boundaries, independent scaling needs, different technology requirements, or compliance isolation).

## Process

### Step 1: Validate the Split

Before scaffolding, verify the extraction makes sense:

```markdown
## Service Extraction Checklist
- [ ] Clear bounded context: the service owns its data and business logic
- [ ] Independent deployment: can be deployed without coordinating with other services
- [ ] Team ownership: a single team will own this service
- [ ] Data isolation: the service has its own database (no shared tables)
- [ ] Justified complexity: the operational overhead of a separate service is worth the benefit
```

If any checklist item is NO, consider keeping it in the monolith and using module boundaries instead.

### Step 2: Generate Service Structure

Use `/infra-scaffold` for the base (Dockerfile, docker-compose, CI/CD), then add:

```
service-name/
  src/
    api/              # HTTP/gRPC handlers
    domain/           # Business logic (no framework deps)
    infrastructure/   # Database, message queue, external clients
    events/           # Published and consumed events
  Dockerfile
  docker-compose.yml  # Local dev (includes dependencies)
  .env.example
  README.md
```

### Step 3: Inter-Service Communication

| Pattern | When | Implementation |
|---------|------|---------------|
| Synchronous HTTP/REST | Request-response, low latency needed | HTTP client with circuit breaker |
| Async events | Eventual consistency OK, decoupling needed | Message queue (RabbitMQ, SQS, Redis Streams) |
| gRPC | High throughput, strong typing, internal services | Protobuf schemas, code generation |

**Default: async events for service-to-service. HTTP for external-facing APIs.**

### Event-Driven Communication

```
Publishing service:
  1. Write to database
  2. Publish event to message queue (use outbox pattern for reliability)
  3. Event format: { type, source, id, timestamp, data }

Consuming service:
  1. Subscribe to relevant event topics
  2. Process idempotently (track processed event IDs)
  3. Handle out-of-order delivery
```

### Step 4: API Gateway Configuration

```yaml
# Route configuration (Kong, AWS API Gateway, Traefik, nginx)
routes:
  - path: /api/v1/billing/*
    service: billing-service
    strip_prefix: false
    rate_limit: 100/minute

  - path: /api/v1/users/*
    service: user-service
    strip_prefix: false
    rate_limit: 200/minute

# Auth: gateway handles JWT validation, passes user context to services
# CORS: configured at gateway level, not per service
# Rate limiting: per-route at gateway
```

### Step 5: Service Discovery

| Environment | Method |
|-------------|--------|
| Docker Compose (local) | Container name as hostname (`http://billing-service:3000`) |
| Kubernetes | DNS-based (`billing-service.namespace.svc.cluster.local`) |
| AWS | ALB/NLB + service discovery or App Mesh |
| Consul/Eureka | Service registry with health checks |

### Step 6: Distributed Tracing

```
Every service MUST propagate trace context:
  - HTTP: traceparent header (W3C Trace Context)
  - Message queue: trace context in message attributes
  - Logs: include trace_id and span_id in every log line

Setup per service:
  1. Install OpenTelemetry SDK
  2. Auto-instrument HTTP client and server
  3. Auto-instrument message queue producer/consumer
  4. Export to collector (Jaeger, Zipkin, Datadog, or OTLP)
```

### Step 7: Data Isolation

```
Each service owns its database:
  - No shared database tables between services
  - No cross-service JOINs
  - Data needed from other services: replicate via events or query via API
  - Eventual consistency is the norm — design for it

Migration: when extracting from monolith:
  1. Identify tables owned by the new service
  2. Create new database with those tables
  3. Dual-write during migration period
  4. Switch reads to new service's database
  5. Remove old tables from monolith after verification
```

### Step 8: Local Development

```yaml
# docker-compose.yml for the service
services:
  billing-service:
    build: .
    ports: ["3001:3000"]
    environment:
      DATABASE_URL: postgres://postgres:postgres@billing-db:5432/billing_dev
      RABBITMQ_URL: amqp://rabbitmq:5672
      USER_SERVICE_URL: http://user-service:3000
    depends_on:
      billing-db: { condition: service_healthy }
      rabbitmq: { condition: service_healthy }

  billing-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: billing_dev
      POSTGRES_PASSWORD: postgres

  rabbitmq:
    image: rabbitmq:3-management-alpine
    ports: ["5672:5672", "15672:15672"]
```

## Phase Output

```
Verdict: SERVICE_SCAFFOLDED
Next: Implement business logic via /build-implementation, then wire into API gateway
Artifacts: [service directory, Dockerfile, docker-compose, event schemas, gateway config]
```
$ARGUMENTS
