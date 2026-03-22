# Horizontal Scaling Patterns

## Scaling Strategy

| Component | Scaling Method | Key Concern |
|-----------|---------------|-------------|
| Web/API servers | Add instances behind load balancer | Stateless design |
| Database reads | Read replicas | Replication lag |
| Database writes | Connection pooling, query optimization | Single writer bottleneck |
| Background jobs | Add worker processes | Queue partitioning |
| File storage | Object storage (S3/GCS) | Already horizontally scaled |
| Cache | Redis Cluster or managed service | Memory per node |
| Search | Elasticsearch sharding | Index design |

## Stateless Application Design

```
For horizontal scaling, every request must be handleable by ANY instance.

Stateless requirements:
  - No in-memory session storage (use Redis or database)
  - No local filesystem for user data (use object storage)
  - No in-memory caches that need consistency (use shared Redis)
  - No sticky sessions (unless WebSocket — see realtime-patterns.md)
  - Configuration via environment variables (not local files)
```

## Database Scaling

### Connection Pooling
```
Problem: 10 app instances × 20 connections = 200 DB connections
PostgreSQL default max_connections: 100

Solutions:
1. Application-level pooling: configure pool size per instance
   - Total pool = max_connections / num_instances
   - Leave headroom for migrations, admin, monitoring

2. Connection proxy (PgBouncer, ProxySQL):
   - Sits between app and database
   - Multiplexes hundreds of app connections to fewer DB connections
   - Transaction-level pooling for best efficiency
```

### Read Replicas
```
Architecture:
  Primary (writes) ──replication──→ Replica 1 (reads)
                                 ──→ Replica 2 (reads)

Implementation:
  - Route writes to primary, reads to replica
  - Rails: ActiveRecord multi-database (reading/writing roles)
  - Django: database routers
  - Node.js: separate connection configs for read/write
  - Prisma: read replicas via datasource URL array

Replication lag:
  - Typically < 100ms for async replication
  - After a write, read from primary for 2-5 seconds (read-your-writes consistency)
  - Use primary for reads in the same request that performed a write
```

### Query Optimization at Scale
```
Before adding replicas, optimize:
  1. EXPLAIN ANALYZE on slow queries (> 100ms)
  2. Add missing indexes (check pg_stat_user_indexes for unused indexes too)
  3. Fix N+1 queries (includes/preload/DataLoader)
  4. Paginate all list endpoints (never SELECT * without LIMIT)
  5. Denormalize hot read paths (materialized views, counter caches)
```

## Background Job Scaling

```
Scaling workers:
  - Add worker processes/containers independently from web
  - Partition queues by priority: critical (1 worker), default (3 workers), low (1 worker)
  - Monitor queue depth — auto-scale workers when depth exceeds threshold

Concurrency:
  - Sidekiq: concurrency setting per process (default 10 threads)
  - BullMQ: concurrency option per worker
  - Celery: --concurrency flag

Rate limiting:
  - Use job-level rate limiting for external API calls
  - Prevent worker stampede on API rate limits
```

## CDN and Static Asset Scaling

```
Strategy:
  1. Serve static assets (JS, CSS, images) from CDN
  2. Use content-addressed filenames (app.abc123.js) for cache-busting
  3. Set long cache headers (max-age=31536000, immutable)
  4. Origin server only handles dynamic requests

Popular CDNs: CloudFront, Cloudflare, Fastly, Vercel Edge

Image optimization:
  - Resize on upload (thumbnails) or on-the-fly (Imgix, Cloudinary, Next.js Image)
  - Serve WebP/AVIF with fallback
  - Lazy load below-fold images
```

## Auto-Scaling

```
Metrics to scale on:
  - CPU utilization > 70% for 2 minutes → scale up
  - CPU utilization < 30% for 10 minutes → scale down
  - Request queue depth > 100 → scale up
  - Memory > 80% → scale up

Minimum instances: 2 (redundancy)
Maximum instances: set a cap to prevent cost runaway
Cooldown period: 5 minutes between scale events (prevent flapping)
```

## Load Balancer Configuration

```
Algorithm: round-robin (default) or least-connections
Health check: GET /health every 10s, unhealthy after 3 failures
Draining: on scale-down, stop sending new requests, wait for in-flight to complete
Sticky sessions: avoid unless WebSocket (breaks horizontal scaling benefit)
SSL termination: at the load balancer (offload from app servers)
```

## Monitoring at Scale

```
Per-instance metrics: CPU, memory, request count, error rate
Aggregate metrics: total throughput, p95 latency, error rate across all instances
Database: connections in use, replication lag, query duration
Cache: hit rate, memory usage, eviction rate
Queue: depth, processing rate, failure rate

Dashboard: overlay instance count on traffic graphs to validate scaling correlation
```

## Common Bottlenecks

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| High latency, low CPU | Database queries | Index, read replica, caching |
| High CPU, normal latency | CPU-bound processing | Add instances, optimize code |
| Errors under load | Connection exhaustion | PgBouncer, increase pool |
| Intermittent timeouts | Single slow query blocking pool | Query timeout, async processing |
| Memory growth over time | Memory leak | Profile, fix leak, restart periodically |
