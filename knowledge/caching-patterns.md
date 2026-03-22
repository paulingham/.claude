# Caching Patterns

## Strategy Selection

| Strategy | When | Consistency | Complexity |
|----------|------|-------------|-----------|
| Cache-aside (lazy) | Most common, read-heavy | Eventual | Low |
| Read-through | Transparent caching layer | Eventual | Medium |
| Write-through | Write consistency critical | Strong | Medium |
| Write-behind (async) | Write-heavy, tolerance for lag | Eventual | High |

**Default: cache-aside.** It's the simplest, most widely applicable pattern.

## Cache-Aside (Lazy Loading)

```
Read:
  1. Check cache for key
  2. If HIT: return cached value
  3. If MISS: query database, store in cache with TTL, return value

Write:
  1. Write to database
  2. Invalidate cache key (delete, don't update)
  3. Next read will populate cache from fresh DB data

Why delete, not update:
  - Avoids race conditions between concurrent writes
  - Simpler to reason about (cache is always a read-through copy)
  - Update can leave stale data if write fails after cache update
```

### Implementation

**Node.js (Redis):**
```typescript
async function getUser(id: string): Promise<User> {
  const cached = await redis.get(`user:${id}`);
  if (cached) return JSON.parse(cached);
  const user = await db.users.findById(id);
  await redis.set(`user:${id}`, JSON.stringify(user), 'EX', 300);
  return user;
}

async function updateUser(id: string, data: Partial<User>): Promise<User> {
  const user = await db.users.update(id, data);
  await redis.del(`user:${id}`);  // Invalidate, don't update
  return user;
}
```

**Rails (built-in):**
```ruby
def show
  @user = Rails.cache.fetch("user:#{params[:id]}", expires_in: 5.minutes) do
    User.find(params[:id])
  end
end
```

## Cache Invalidation

### Key Strategies
```
TTL-based:       Set expiry on every cache entry (simplest, always safe)
Event-based:     Invalidate on write events (most consistent)
Version-based:   Include version in cache key (user:42:v3) — bump version to invalidate
Tag-based:       Tag entries with categories, invalidate by tag (Rails cache tags)
```

### Multi-Tenant Cache Keys
```
ALWAYS include tenant_id in cache keys:
  BAD:  cache.get("users:list")
  GOOD: cache.get("tenant:acme:users:list")

ALWAYS include locale if content is localized:
  GOOD: cache.get("tenant:acme:products:list:en-US")
```

## Cache Stampede Prevention

```
Problem: cache expires, 1000 concurrent requests all miss and hit the database

Solutions:
1. Mutex/lock: first request acquires lock, others wait for cache repopulation
2. Probabilistic early expiry: randomly refresh before TTL expires
3. Background refresh: separate process keeps hot keys warm
4. Stale-while-revalidate: serve stale value, refresh async in background
```

**Mutex pattern (Redis):**
```typescript
async function getWithLock(key: string, fetchFn: () => Promise<any>, ttl: number) {
  const cached = await redis.get(key);
  if (cached) return JSON.parse(cached);
  const lockKey = `lock:${key}`;
  const acquired = await redis.set(lockKey, '1', 'NX', 'EX', 10);
  if (!acquired) {
    await sleep(100);
    return getWithLock(key, fetchFn, ttl); // Retry after brief wait
  }
  const value = await fetchFn();
  await redis.set(key, JSON.stringify(value), 'EX', ttl);
  await redis.del(lockKey);
  return value;
}
```

## HTTP Caching

```
Static assets:     Cache-Control: public, max-age=31536000, immutable
                   (fingerprinted filenames: app.abc123.js)

API responses:     Cache-Control: private, no-cache
                   ETag: "hash-of-response-body"
                   (client sends If-None-Match, server returns 304 if unchanged)

HTML pages:        Cache-Control: no-cache
                   (always revalidate, serve from cache if unchanged)

Authenticated:     Cache-Control: private, no-store
                   (never cache responses with user-specific data in shared caches)
```

## What to Cache

| Good candidates | Bad candidates |
|----------------|---------------|
| Database query results (read-heavy) | Rapidly changing data (stock prices) |
| API responses from external services | User-specific session data (use session store) |
| Computed aggregations (dashboards) | Writes (cache reads, invalidate on writes) |
| Configuration / feature flags | Large blobs (use CDN instead) |
| Rendered HTML fragments | Security-sensitive data (tokens, passwords) |

## TTL Guidelines

| Data type | TTL | Rationale |
|-----------|-----|-----------|
| Static config | 1 hour | Changes rarely |
| User profile | 5 minutes | Changes occasionally |
| List/search results | 1-2 minutes | Changes frequently |
| Dashboard aggregations | 30 seconds - 5 minutes | Depends on freshness needs |
| External API responses | Match their Cache-Control | Respect provider's guidance |
| Feature flags | 30 seconds | Need relatively fast propagation |

## Monitoring

```
Key metrics:
  - Hit rate (target: > 90%)
  - Miss rate
  - Eviction rate (cache too small if high)
  - Memory usage
  - Latency (cache should be < 1ms)

Alerts:
  - Hit rate drops below 80% → Warning
  - Cache server unreachable → Critical (degrade gracefully to DB)
  - Memory > 90% → Warning (increase size or reduce TTL)
```

## Anti-Patterns

```
- Caching everything: only cache what's read-heavy and expensive to compute
- No TTL: every cache entry MUST have an expiry (prevents stale data forever)
- Cache as primary store: cache is ephemeral — always be able to rebuild from DB
- Caching nulls without TTL: cache "not found" with short TTL to prevent repeated DB misses
- Large objects: keep cached values small (< 1MB). Serialize only needed fields.
```
