---
name: Integration Patterns
description: Service boundary design, event-driven patterns, saga, circuit breaker, retry with backoff, idempotency, and outbox pattern
type: reference
---

# Integration Patterns

## Service Boundary Design

### When to Introduce a Service Boundary
- Independent scaling requirement (the feature has 10x the traffic)
- Independent deployment requirement (different release cadence)
- Team ownership boundary (separate team owns the feature)
- Technology isolation requirement (different runtime, language)
- Data isolation requirement (compliance, different retention policy)

### When NOT to Introduce a Service Boundary
- Just because it's a different "domain" (monolith-first)
- Because microservices are fashionable
- When the teams are the same
- When transactions would span the boundary frequently

### Boundary Design Rules
- Services own their data — no shared databases across service boundaries
- Communicate via explicit contracts (events, APIs) — not shared libraries containing domain logic
- Design for failure at every boundary call
- Services must be independently deployable

## Event-Driven Patterns

### Event Structure
```json
{
  "id": "evt-uuid-123",
  "type": "order.placed",
  "version": "1.0",
  "source": "order-service",
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "req-abc-xyz",
  "data": {
    "order_id": "ord-456",
    "customer_id": "cust-789",
    "total_cents": 5000
  }
}
```

- Events are facts — past tense, immutable
- Always include `id`, `type`, `timestamp`, `correlation_id`
- Version events to support consumers at different versions
- Store events before publishing (outbox pattern)

### At-Least-Once Delivery
- Message queues typically guarantee at-least-once delivery
- Consumers MUST be idempotent (process same event twice = same result)
- Use event `id` to detect duplicates: store processed IDs in a seen-events table

### Event Ordering
- Do not assume events arrive in order
- Use sequence numbers or timestamps for ordering if order matters
- Consider: does the consumer care about order? Design accordingly.

## Saga Pattern (Distributed Transactions)

For transactions spanning multiple services — never use distributed 2PC.

### Choreography Saga (event-driven)
```
OrderService → [order.placed] → InventoryService → [inventory.reserved]
             → PaymentService → [payment.captured] → OrderService → [order.confirmed]

Compensating:
PaymentService → [payment.failed] → InventoryService → [inventory.released]
               → OrderService → [order.cancelled]
```
- Simple, no central coordinator
- Hard to track overall saga state
- Suitable for < 4 steps

### Orchestration Saga (coordinator-driven)
```
SagaOrchestrator:
  1. Reserve inventory → if fail: done (saga failed)
  2. Capture payment → if fail: release inventory, done
  3. Confirm order → if fail: refund payment, release inventory, done
  4. Send confirmation email → if fail: log, don't compensate (non-critical)
```
- Central saga tracks state and drives steps
- Easier to monitor and debug
- Suitable for > 4 steps or complex compensation logic

### Compensation Rules
- Every step must have a compensating action
- Compensating actions must also be idempotent
- Some steps are "pivot" — after pivot, only forward (compensation not possible)
- Log saga state at every step for observability

## Circuit Breaker

Prevent cascade failures when a dependency is unhealthy:

```
States: CLOSED → OPEN → HALF_OPEN → CLOSED

CLOSED: requests pass through
  - Track failure rate
  - If failure rate > threshold: → OPEN

OPEN: requests fail fast (no calls to dependency)
  - After timeout: → HALF_OPEN

HALF_OPEN: allow one probe request
  - If success: → CLOSED
  - If failure: → OPEN
```

```typescript
class CircuitBreaker {
  private state: 'closed' | 'open' | 'half-open' = 'closed';
  private failures = 0;
  private threshold = 5;
  private timeout = 60000; // 1 minute
  private lastFailureTime?: number;

  async call<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'open') {
      if (Date.now() - this.lastFailureTime! > this.timeout) {
        this.state = 'half-open';
      } else {
        throw new Error('Circuit open — dependency unavailable');
      }
    }
    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (err) {
      this.onFailure();
      throw err;
    }
  }

  private onSuccess() { this.failures = 0; this.state = 'closed'; }
  private onFailure() {
    this.failures++;
    this.lastFailureTime = Date.now();
    if (this.failures >= this.threshold) this.state = 'open';
  }
}
```

## Retry with Exponential Backoff

```typescript
async function withRetry<T>(
  fn: () => Promise<T>,
  maxAttempts = 3,
  baseDelayMs = 100
): Promise<T> {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      if (attempt === maxAttempts) throw err;
      if (!isTransient(err)) throw err; // Don't retry 4xx errors
      const delay = baseDelayMs * Math.pow(2, attempt - 1) + Math.random() * 100;
      await sleep(delay);
    }
  }
  throw new Error('unreachable');
}

function isTransient(err: Error): boolean {
  // Retry: network timeouts, 429, 503
  // Don't retry: 400, 401, 403, 404, 409, 422
  return err.message.includes('ECONNRESET') ||
         (err as any).statusCode === 429 ||
         (err as any).statusCode === 503;
}
```

Rules:
- Jitter prevents thundering herd (add random delay)
- Cap maximum delay (e.g., 30 seconds)
- Don't retry non-transient errors (validation, auth failures)
- Log each retry attempt with attempt number

## Idempotency at Boundaries

Every mutating operation that crosses a service boundary must be idempotent:

```typescript
// Producer: include idempotency key
await paymentService.charge({
  idempotencyKey: `order-${orderId}-payment`,
  amount: 5000,
  currency: 'USD',
});

// Consumer: check before processing
async function processPayment(request: PaymentRequest) {
  const existing = await db.payments.findByIdempotencyKey(request.idempotencyKey);
  if (existing) return existing; // Return previous result

  const result = await chargeCard(request);
  await db.payments.save({ ...result, idempotencyKey: request.idempotencyKey });
  return result;
}
```

Idempotency key design:
- Scoped to operation: `{entity}-{id}-{operation}` e.g. `order-123-payment`
- Client-generated (not server) so client can retry safely
- Store result, not just "was processed" (return same result on duplicate)
- Expire after reasonable window (24h for payments, 7d for emails)

## Outbox Pattern

Guarantee message publication even on publish failure:

```
1. Begin transaction
2. Write domain record to DB
3. Write event to outbox table (same transaction)
4. Commit
5. (Async) Outbox relay reads unpublished events, publishes to queue, marks published
```

```sql
CREATE TABLE outbox (
  id BIGSERIAL PRIMARY KEY,
  event_type VARCHAR NOT NULL,
  payload JSONB NOT NULL,
  published_at TIMESTAMP,  -- NULL = unpublished
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_outbox_unpublished ON outbox (created_at) WHERE published_at IS NULL;
```

```typescript
// Outbox relay (runs on schedule or as CDC consumer)
async function relayOutboxEvents() {
  const events = await db.outbox.findAll({ where: { publishedAt: null }, limit: 100 });
  for (const event of events) {
    await queue.publish(event.eventType, event.payload);
    await db.outbox.update({ publishedAt: new Date() }, { where: { id: event.id } });
  }
}
```

Why outbox:
- Eliminates the dual-write problem (DB write succeeds but publish fails)
- At-least-once guarantee without distributed transactions
- The transaction makes DB write + outbox write atomic

## Third-Party API Integration

### Client Wrapper Design
```
Wrap every third-party API in a dedicated client class/module:
- Single responsibility: one client per provider
- Inject the HTTP client (for testing with recorded responses)
- Map provider errors to domain errors (don't leak provider details)
- Handle rate limits: respect Retry-After header, implement backoff
- Log requests/responses (redact secrets, truncate large bodies)
```

### Credential Management
```
- Store API keys in env vars, never in code
- Use separate credentials per environment (dev/staging/prod)
- Rotate credentials on compromise (track in env-management-patterns.md)
- Use scoped API keys where providers support them (least privilege)
```

### Webhook Consumption
```
1. Verify signature (provider-specific: Stripe uses HMAC, GitHub uses SHA-256)
2. Check for replay attacks (verify timestamp is recent, < 5 minutes)
3. Process idempotently (track webhook ID, skip duplicates)
4. Return 200 OK quickly (process in background job, not inline)
5. Handle out-of-order delivery (events may arrive non-chronologically)
```

### Testing
```
Use recorded HTTP responses (VCR/Nock pattern):
- Record real API responses during development
- Replay recorded responses in tests (deterministic, fast, no API calls)
- Periodically re-record to catch API changes
- Test error scenarios: timeout, rate limit (429), server error (500), malformed response
```
