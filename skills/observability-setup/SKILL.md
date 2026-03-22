---
name: "Observability Setup"
description: "Production observability: structured logging, health endpoints, metrics collection, distributed tracing (OpenTelemetry), alerting rules, and dashboard configuration."
context: fork
agent: infrastructure-engineer
argument-hint: "Observability provider (e.g., 'Datadog', 'Sentry + Grafana', 'AWS CloudWatch') or 'auto-detect'"
---

# Observability Setup

## What This Skill Does

Implements the three pillars of observability — logging, metrics, and tracing — plus health endpoints and alerting. Configures the project for production monitoring from day one.

## When to Invoke

- New project needs monitoring setup
- Adding structured logging to an existing project
- Integrating with a monitoring provider (Datadog, Sentry, Grafana, CloudWatch)
- Setting up alerting rules for production
- Adding OpenTelemetry distributed tracing

## Process

### Step 1: Detect Existing Observability

Scan for existing monitoring configuration:

| Signal | Provider | Status |
|--------|----------|--------|
| `@sentry/node` or `sentry-sdk` in deps | Sentry | Error tracking present |
| `dd-trace` or `datadog` in deps | Datadog | APM present |
| `@opentelemetry/*` in deps | OpenTelemetry | Tracing present |
| `prom-client` or `prometheus` in deps | Prometheus | Metrics present |
| `winston`, `pino`, `bunyan` in deps | Structured logging | Logger present |
| `SENTRY_DSN` in env | Sentry | Configured |
| `DD_API_KEY` in env | Datadog | Configured |

If nothing is found, recommend the default stack: **Pino (logging) + OpenTelemetry (tracing) + Sentry (errors)**.

### Step 2: Structured Logging

Replace `console.log` with structured JSON logging:

#### Logger Configuration
```
Log Format: JSON (machine-parseable, searchable)
Log Levels: error > warn > info > debug
Default Level: info (production), debug (development)
```

#### Required Fields (every log line)
```json
{
  "timestamp": "2026-03-22T10:00:00.000Z",
  "level": "info",
  "message": "User registered",
  "service": "api",
  "environment": "production",
  "request_id": "req_abc123",
  "trace_id": "4bf92f3577b34da6",
  "user_id": "usr_456",
  "duration_ms": 42
}
```

#### Stack-Specific Implementation

**Node.js (Pino — recommended):**
```javascript
// Pino: fastest JSON logger for Node.js
const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  formatters: {
    level: (label) => ({ level: label }),
  },
  base: {
    service: process.env.SERVICE_NAME || 'api',
    environment: process.env.NODE_ENV,
  },
});
```

**Ruby (Rails — Lograge):**
```ruby
# config/environments/production.rb
config.lograge.enabled = true
config.lograge.formatter = Lograge::Formatters::Json.new
config.lograge.custom_payload do |controller|
  { request_id: controller.request.request_id, user_id: controller.current_user&.id }
end
```

**Python (structlog):**
```python
import structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)
logger = structlog.get_logger()
```

#### Logging Rules
- **DO log**: Request lifecycle (start/end with duration), authentication events, business events (order created, payment processed), errors with stack traces
- **DO NOT log**: Passwords, tokens, PII (email, phone), credit card numbers, request/response bodies (unless debug level)
- **Correlation**: Thread a `request_id` through the entire request lifecycle via middleware

### Step 3: Health Endpoints

Configure health checks per `/infra-scaffold` Step 5. Wire health endpoints into the observability stack:
- Dashboard: display health check status on the overview row
- Alerting: trigger "Zero traffic" alert if health endpoint stops responding
- Kubernetes: map probes to the three-tier endpoints (`/health`, `/health/ready`, `/health/live`)

### Step 4: Metrics Collection

Expose application metrics for monitoring:

#### Key Metrics (RED method)

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total requests by method, path, status |
| `http_request_duration_seconds` | Histogram | Request latency (p50, p95, p99) |
| `http_requests_in_flight` | Gauge | Currently active requests |
| `db_query_duration_seconds` | Histogram | Database query latency |
| `db_pool_connections` | Gauge | Active/idle/waiting connections |
| `background_jobs_total` | Counter | Jobs processed by queue, status |
| `background_job_duration_seconds` | Histogram | Job processing time |
| `cache_hits_total` | Counter | Cache hit/miss ratio |

#### Business Metrics (application-specific)
```
user_registrations_total
orders_created_total
payments_processed_total{status="success|failed"}
api_rate_limit_exceeded_total
```

#### Export Format
- **Prometheus** (pull): Expose `/metrics` endpoint
- **OpenTelemetry** (push): Export to collector via OTLP
- **Datadog** (push): Export via DogStatsD or dd-trace
- **CloudWatch** (push): Export via AWS SDK

### Step 5: Distributed Tracing

Implement OpenTelemetry for request tracing across services:

#### Setup
```
1. Install OpenTelemetry SDK for the project's language
2. Configure exporter (OTLP to collector, or direct to Jaeger/Zipkin/Datadog)
3. Auto-instrument HTTP, database, and cache libraries
4. Add custom spans for business-critical operations
```

#### Trace Context Propagation
- HTTP: `traceparent` header (W3C Trace Context standard)
- Message queues: Trace context in message attributes
- Background jobs: Trace context in job metadata

#### Key Spans to Instrument
```
[HTTP Request] → [Auth Middleware] → [Controller] → [Service] → [Database Query]
                                                              → [Cache Lookup]
                                                              → [External API Call]
```

#### Sampling Strategy
- **Development**: 100% sampling (all traces)
- **Staging**: 100% sampling
- **Production**: 10-25% sampling (head-based), or 100% for errors (tail-based)

### Step 6: Error Tracking

Configure error tracking with context:

```
1. Capture all unhandled exceptions
2. Attach context: user_id, request_id, environment, release version
3. Group by root cause (not by message string)
4. Set up source maps (JavaScript) or debug symbols for readable stack traces
5. Configure alert thresholds: >5 new errors/hour triggers notification
6. Source maps: upload to error tracker privately (Sentry source map upload). **Never** serve .map files publicly — they expose business logic and injection points
```

**Sentry configuration (recommended):**
- `environment`: staging / production
- `release`: git SHA or semver
- `tracesSampleRate`: 0.1 (production), 1.0 (staging)
- `beforeSend`: strip PII from error context
- `ignoreErrors`: expected client errors (404, rate limit)

### Step 7: Alerting Rules

Define alerting rules for production:

| Alert | Condition | Severity | Channel |
|-------|-----------|----------|---------|
| High error rate | >1% of requests return 5xx (5min window) | Critical | PagerDuty / Slack |
| Latency spike | p95 latency >2s (5min window) | Warning | Slack |
| Database connection pool exhausted | available connections = 0 | Critical | PagerDuty |
| Disk usage high | >85% disk usage | Warning | Slack |
| Memory usage high | >90% memory usage | Warning | Slack |
| Background job queue growing | queue depth >1000 (15min) | Warning | Slack |
| Certificate expiring | SSL cert expires in <14 days | Warning | Email |
| Deployment failed | deploy health check fails | Critical | Slack |
| Zero traffic | 0 requests for >5 minutes | Critical | PagerDuty |

#### Alert Fatigue Prevention
- Group related alerts (don't fire DB + app + queue alerts for one DB outage)
- Require minimum duration before firing (no single-blip alerts)
- Separate critical (pages someone) from warning (Slack notification)
- Review and tune thresholds monthly

### Step 8: Dashboard

Recommend dashboard layout:

```
## Production Dashboard

Row 1: Traffic Overview
  - Request rate (requests/second)
  - Error rate (% 5xx)
  - p95 latency

Row 2: Infrastructure
  - CPU usage per instance
  - Memory usage per instance
  - Database connection pool

Row 3: Business Metrics
  - Key business events/hour
  - Active users
  - Revenue metrics (if applicable)

Row 4: Dependencies
  - External API latency
  - Cache hit ratio
  - Queue depth
```

## Phase Output

```
Verdict: OBSERVABILITY_CONFIGURED
Next: Deploy to staging, generate initial traffic, verify dashboards populate
Artifacts: [logger config, health endpoints, metrics middleware, tracing setup, alert rules, dashboard spec]
Provider: [Sentry/Datadog/Grafana/CloudWatch/self-hosted]
```
