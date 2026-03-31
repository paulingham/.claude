---
name: "bff-scaffold"
description: "Use when user wants to Generate a Backend for Frontend API layer for a specific channel (web, mobile, voice, device). Handles data aggregation, channel-specific response shaping, and upstream service wiring."
context: fork
agent: software-engineer
argument-hint: "Channel type and upstream services (e.g., 'mobile-bff for user-service + task-service')"
---

# BFF Scaffold

## What This Skill Does

Generates a Backend for Frontend (BFF) API layer tailored to a specific channel. The BFF aggregates data from upstream core services, shapes responses for the channel's constraints, and handles channel-specific concerns (auth flow, caching, offline hints).

## When to Invoke

- Adding a new channel to an existing omnichannel architecture
- Creating channel-specific API aggregation layer
- Separating a growing monolith API into channel-optimized layers

## Prerequisites

- Core services exist with documented APIs (OpenAPI specs or equivalent)
- API gateway is configured (or will be via `/infra-scaffold`)
- Read `knowledge/omnichannel-patterns.md` for BFF architecture context

## Process

### Step 1: Determine Channel Type

| Channel | Response Shape | Auth Pattern | Caching | Special Concerns |
|---------|---------------|-------------|---------|-----------------|
| Web | Full JSON, HTML fragments | Cookie-based session | CDN + server cache | SSR support, CORS |
| Mobile | Compact JSON, pagination | Bearer token (JWT) | Aggressive client cache | Offline hints, delta sync |
| Voice | SSML, minimal JSON | OAuth account linking | Session-scoped | 8s response limit, no visual |
| Device/IoT | Binary (CBOR/Protobuf) | Device certificate + mTLS | Minimal (bandwidth) | Tiny payloads, command queue |

### Step 2: Generate BFF Structure

```
bff-{channel}/
  src/
    routes/              — Channel-specific route definitions
      health.ts          — Health endpoint
      tasks.ts           — /tasks endpoints (aggregated from task-service)
      users.ts           — /users endpoints (from user-service)
    aggregators/         — Compose data from multiple upstream services
      task-dashboard.ts  — Aggregates tasks + user info + stats
    transformers/        — Shape data for channel format
      task.ts            — Full task → channel-appropriate task shape
    clients/             — Upstream service HTTP clients
      task-service.ts    — Client for task-service API
      user-service.ts    — Client for user-service API
    middleware/          — Channel-specific middleware
      auth.ts            — Channel-appropriate auth
      cache.ts           — Channel-appropriate caching
      error-handler.ts   — Channel-appropriate error responses
  Dockerfile
  docker-compose.yml     — Local dev with upstream stubs
  .env.example
```

### Step 3: Generate Upstream Service Clients

For each upstream service, generate an HTTP client wrapper:

```typescript
class TaskServiceClient {
  constructor(
    private readonly httpClient: HttpClient,  // Injected for testing
    private readonly baseUrl: string,
    private readonly circuitBreaker: CircuitBreaker
  ) {}

  async listTasks(userId: string, options: ListOptions): Promise<Task[]> {
    return this.circuitBreaker.execute(() =>
      this.httpClient.get(`${this.baseUrl}/api/v1/tasks`, {
        headers: { 'X-User-ID': userId },
        params: { page: options.page, per_page: options.perPage },
        timeout: 3000,
      })
    );
  }
}
```

Include circuit breaker, timeout, and retry configuration per upstream (reference `knowledge/integration-patterns.md`).

### Step 4: Generate Response Transformers

Transform upstream data into channel-appropriate shape:

```typescript
// Web: full data
function transformForWeb(task: UpstreamTask): WebTask {
  return {
    id: task.id,
    title: task.title,
    description: task.description,         // Full description
    assignee: { name: task.assignee.name, avatarUrl: task.assignee.avatarUrl },
    dueDate: formatDate(task.due_date),     // Human-readable
    attachments: task.attachments,           // Full attachment list
  };
}

// Mobile: compact
function transformForMobile(task: UpstreamTask): MobileTask {
  return {
    id: task.id,
    title: task.title,
    assigneeName: task.assignee.name,       // Flat, no nested objects
    dueDate: task.due_date,                 // ISO string (client formats)
    attachmentCount: task.attachments.length, // Count only (download on demand)
  };
}

// Voice: minimal
function transformForVoice(task: UpstreamTask): VoiceTask {
  return {
    title: task.title,
    dueDateSpoken: formatDateForSpeech(task.due_date), // "due tomorrow"
  };
}

// Device: binary-ready
function transformForDevice(task: UpstreamTask): DeviceTask {
  return {
    id: task.id,
    t: task.title.substring(0, 20),         // Truncated for display
    d: Math.floor(new Date(task.due_date).getTime() / 1000), // Unix timestamp
    p: priorityToByte(task.priority),       // Single byte: 0=low, 1=med, 2=high
  };
}
```

### Step 5: Generate Channel-Specific Middleware

**Auth middleware** (varies by channel):
- Web: validate session cookie, CSRF token
- Mobile: validate Bearer JWT, refresh if expired
- Voice: validate OAuth access token from account linking
- Device: validate device certificate via mTLS, extract device_id

**Cache middleware** (varies by channel):
- Web: CDN cache headers, ETag support, server-side Redis cache
- Mobile: aggressive Cache-Control headers, offline cache hints
- Voice: no caching (session-scoped, always fresh)
- Device: minimal caching (bandwidth priority)

### Step 6: Wire to API Gateway

Add route configuration for the new BFF:

```yaml
# Add to API gateway config
routes:
  - path: /{channel}/api/v1/*
    service: {channel}-bff
    rate_limit: { requests: [appropriate], window: 60s }
    auth: [channel-appropriate]
```

### Step 7: Generate Local Dev Setup

```yaml
# docker-compose.yml — runs BFF with mocked upstream services
services:
  bff:
    build: .
    ports: ["3001:3000"]
    environment:
      TASK_SERVICE_URL: http://task-stub:3000
      USER_SERVICE_URL: http://user-stub:3000

  task-stub:
    image: stoplight/prism:latest  # Mock from OpenAPI spec
    command: mock /specs/task-service.yaml
    volumes: ["./specs:/specs"]

  user-stub:
    image: stoplight/prism:latest
    command: mock /specs/user-service.yaml
    volumes: ["./specs:/specs"]
```

## Phase Output

```
Verdict: BFF_SCAFFOLDED
Next: Implement aggregation logic via /build-implementation, then wire to gateway
Artifacts: [BFF project structure, upstream clients, transformers, middleware, docker-compose, gateway config]
Channel: [web/mobile/voice/device]
Upstream Services: [list of services this BFF connects to]
```
$ARGUMENTS
