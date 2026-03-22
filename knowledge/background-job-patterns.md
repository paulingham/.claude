# Background Job Patterns

## Framework Selection

| Stack | Framework | Queue Backend |
|-------|-----------|--------------|
| Ruby/Rails | Sidekiq, Solid Queue (Rails 8+) | Redis, Database |
| Node.js | BullMQ, Agenda | Redis, MongoDB |
| Python | Celery, RQ, Dramatiq | Redis, RabbitMQ |
| Go | Asynq, Machinery | Redis |

## Job Design Principles

### Idempotency (mandatory)
Every job must be safe to run multiple times with the same arguments. Use unique job IDs and check completion status before executing.

```
BAD:  charge_customer(user_id, amount) — double charge on retry
GOOD: charge_customer(user_id, amount, idempotency_key) — check if key already processed
```

### Small, Focused Jobs
- One job = one responsibility
- Break large operations into chains or batches
- Jobs should complete in under 5 minutes (configure per-job timeouts)

### Serializable Arguments
- Pass IDs, not objects (objects may change between enqueue and execution)
- Keep payloads small (< 10KB)
- Never pass database connections or file handles

## Retry Strategy

```
Retry with exponential backoff + jitter:
  Attempt 1: immediate
  Attempt 2: 15s + random(0-5s)
  Attempt 3: 60s + random(0-15s)
  Attempt 4: 300s + random(0-60s)
  Attempt 5: 3600s + random(0-300s)
  Max retries: 5 (configurable per job type)

After max retries: move to dead letter queue for manual inspection
```

### Non-Retryable Errors
Some errors should NOT be retried:
- Validation errors (bad input)
- Authorization errors (user lacks permission)
- Resource not found (deleted between enqueue and execution)

Distinguish retryable (network timeout, rate limit) from permanent (validation, auth).

## Queue Priority

```
Critical:   payment processing, security alerts (process within seconds)
Default:    user-triggered actions (email, export, report generation)
Low:        analytics, cleanup, batch processing (process within hours)
Scheduled:  cron jobs (daily reports, weekly digests)
```

## Common Job Types

### Email Sending
```
SendEmailJob.perform_async(user_id, template, params)
- Fetch user, render template, send via provider
- Retry on provider timeout, fail permanently on invalid email
```

### Webhook Processing
```
ProcessWebhookJob.perform_async(webhook_id)
- Load webhook payload from database (not from job args — too large)
- Verify signature, process event, mark as processed
- Idempotency: check if webhook_id already processed
```

### Report Generation
```
GenerateReportJob.perform_async(report_id, user_id)
- Generate report, store as file (S3/GCS)
- Notify user when complete (email or in-app notification)
- Timeout: 10 minutes max
```

### Data Cleanup
```
CleanupExpiredTokensJob.perform_async
- Delete tokens where expires_at < now
- Run as scheduled job (daily)
- Batch delete (1000 at a time) to avoid long locks
```

## Scheduling (Cron Jobs)

```
Use the framework's scheduler, not system crontab:
- Sidekiq: sidekiq-cron or sidekiq-scheduler
- BullMQ: QueueScheduler with repeat options
- Celery: celery beat

Common schedules:
- Every minute:  health checks, queue monitoring
- Every hour:    cleanup expired sessions/tokens
- Daily:         reports, analytics aggregation, backup verification
- Weekly:        digest emails, usage reports
```

## Monitoring

```
Key metrics:
- Queue depth (by queue name)
- Job processing time (p50, p95, p99)
- Job failure rate
- Dead letter queue size
- Worker utilization

Alerts:
- Queue depth > 1000 for > 15 minutes → Warning
- Dead letter queue > 0 → Warning (investigate failures)
- Job failure rate > 5% → Critical
- Workers at 0 → Critical (workers crashed)
```

## Testing Async Jobs

```
Unit test:     Test job logic synchronously (call perform directly, not async)
Integration:   Verify job is enqueued with correct args (assert_enqueued_with)
               Process inline in test environment (Sidekiq::Testing.inline!)
Never:         Rely on actual async processing in tests (flaky, slow)
```
