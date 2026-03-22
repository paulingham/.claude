# Service Mesh & API Gateway Patterns

## API Gateway

### Gateway Responsibilities
```
Cross-cutting concerns handled once, at the edge:
  - Authentication (JWT validation, API key check)
  - Rate limiting (per client, per endpoint)
  - TLS termination (SSL offload from services)
  - Request routing (path → service mapping)
  - CORS handling
  - Request/response logging
  - Load balancing across service instances
  - Circuit breaking (prevent cascading failures)
```

### Gateway Selection
| Gateway | Strength | When |
|---------|----------|------|
| Kong | Plugin ecosystem, declarative config | Multi-protocol, enterprise features |
| AWS API Gateway | Serverless, managed, Lambda integration | AWS-native, serverless backends |
| Traefik | Kubernetes-native, auto-discovery | K8s environments, Docker Compose |
| NGINX | Raw performance, battle-tested | High throughput, simple routing |
| Envoy | Programmable, observability, xDS API | Service mesh sidecar, gRPC |
| Cloudflare Workers | Edge computing, global distribution | Low-latency API, edge logic |

### Route Configuration Pattern
```yaml
routes:
  # Channel BFFs
  - path: /web/api/v1/*
    service: web-bff
    rate_limit: { requests: 200, window: 60s }

  - path: /mobile/api/v1/*
    service: mobile-bff
    rate_limit: { requests: 100, window: 60s }

  - path: /voice/api/v1/*
    service: voice-bff
    rate_limit: { requests: 50, window: 60s }

  # Core services (internal, not exposed externally)
  - path: /internal/users/*
    service: user-service
    auth: mTLS  # service-to-service only
```

### Gateway vs BFF
```
Gateway: cross-cutting, infrastructure concern
  → Auth, rate limiting, TLS, routing, logging
  → Owned by platform/infra team
  → One gateway for all channels

BFF: channel-specific, application concern
  → Data aggregation, response shaping, channel auth flows
  → Owned by channel team
  → One BFF per channel
```

## When to Use a Service Mesh

### Decision Framework
```
USE a mesh when:
  ✓ 10+ services in production
  ✓ Multiple languages/frameworks (mesh provides uniform observability)
  ✓ Zero-trust security required (mTLS everywhere)
  ✓ Complex traffic routing (canary, A/B, fault injection)
  ✓ Team can handle operational complexity

DO NOT use a mesh when:
  ✗ Fewer than 5 services (overkill, use gateway + in-app patterns)
  ✗ Single language (framework provides retries, circuit breaking)
  ✗ Team lacks Kubernetes expertise (mesh adds K8s complexity)
  ✗ Latency-critical paths (sidecar adds 1-3ms per hop)
```

### Mesh Implementations
| Mesh | Proxy | Complexity | Strengths |
|------|-------|-----------|-----------|
| Istio | Envoy | High | Full-featured, traffic management, security |
| Linkerd | Rust proxy | Low | Lightweight, fast, simpler operations |
| Consul Connect | Envoy | Medium | Multi-platform (K8s + VMs), HashiCorp ecosystem |
| AWS App Mesh | Envoy | Medium | Managed, AWS integration |

**Default: Linkerd for most teams (simpler). Istio when you need advanced traffic management.**

## Traffic Management

### Canary at Gateway/Mesh Level
```
Deploy new version alongside old:
  1. Route 5% of traffic to v2, 95% to v1
  2. Monitor error rate and latency for v2
  3. If healthy: shift to 25%, then 50%, then 100%
  4. If unhealthy: route 100% back to v1

Implementation:
  Istio:   VirtualService with weight-based routing
  Linkerd: TrafficSplit resource
  Gateway: header-based or percentage-based routing rules
```

### Circuit Breaking
```
At mesh level (complements application-level in integration-patterns.md):

Mesh circuit breaker:
  - Connection pool limits (max connections per service)
  - Pending request limits (max queued requests)
  - Outlier detection (eject unhealthy instances after N consecutive 5xx)
  - Retry budget (max % of requests that can be retries)

Application circuit breaker:
  - Business logic awareness (knows which errors are retryable)
  - Fallback responses (cache, default value)
  - Custom timeout per operation

Both layers work together. Mesh handles connection-level protection.
Application handles business-level protection.
```

### Retry and Timeout Policies
```
IMPORTANT: avoid double-retry

If mesh retries AND app retries:
  Mesh retry (3) × App retry (3) = 9 actual requests (amplification)

Strategy: retry at ONE layer only
  - Mesh retries: for infrastructure failures (connection refused, 503)
  - App retries: for business failures (rate limit, transient error)
  - Configure mesh: retry on 503, connect-failure only
  - Configure app: retry on 429, 500 with backoff
```

## Security at the Mesh Level

### mTLS (Mutual TLS)
```
Mesh automates certificate provisioning and rotation:
  1. Each service gets a short-lived certificate (24h)
  2. Mesh proxy handles TLS handshake (app code doesn't change)
  3. Both sides verify identity (mutual authentication)
  4. Certificates rotate automatically before expiry

Benefits:
  - Encryption in transit between all services
  - Service identity verification (prevent spoofing)
  - No manual cert management
```

### Authorization Policies
```
Define which services can call which:

Allow: web-bff → user-service (GET, POST)
Allow: web-bff → task-service (GET, POST, PATCH)
Deny:  web-bff → billing-service (only billing-bff can call billing)
Allow: voice-bff → task-service (GET only — voice is read-heavy)

Default: deny all. Explicitly allow required paths.
```

## Observability via Mesh

```
Mesh provides "free" observability (no code changes):

Distributed tracing:
  - Mesh injects trace headers automatically
  - Every service-to-service call appears in trace
  - Visualize request flow across all services

Metrics per service pair:
  - Request rate (RPS)
  - Latency (p50, p95, p99)
  - Error rate (4xx, 5xx)
  - Retries and circuit breaker trips

Service topology:
  - Auto-generated service dependency graph
  - Traffic flow visualization
  - Identify unused service dependencies
```

## Anti-Patterns

```
- Mesh as a silver bullet: mesh adds complexity. Only adopt when benefits outweigh costs.
- Business logic in mesh config: mesh handles infrastructure. Business rules stay in code.
- Double retry: mesh AND app both retrying = request amplification = cascading failure
- Ignoring sidecar resources: each sidecar consumes CPU/memory. Budget for it.
- Same timeout everywhere: different operations need different timeouts (read: 5s, write: 30s)
```
