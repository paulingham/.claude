# Multi-Tenancy Patterns

## Strategy Selection

| Strategy | Isolation | Complexity | Cost | When |
|----------|-----------|-----------|------|------|
| Shared DB, tenant_id column | Low | Low | Low | Most SaaS apps, startups |
| Schema-per-tenant | Medium | Medium | Medium | Compliance requirements, moderate scale |
| Database-per-tenant | High | High | High | Enterprise, strict data isolation |

**Default: shared database with tenant_id column.** Only escalate to schema/DB-per-tenant when compliance or enterprise contracts require it.

## Shared Database (Row-Level Tenancy)

### Tenant Identification

| Method | When | Example |
|--------|------|---------|
| Subdomain | B2B SaaS with custom domains | `acme.app.com` → tenant: acme |
| JWT claim | API-first, mobile | `{ tenant_id: "acme" }` in token |
| Path prefix | Simple multi-tenant | `/api/v1/tenants/acme/...` |
| Header | Internal services | `X-Tenant-ID: acme` |

### Middleware Pattern
```
Every request:
1. Extract tenant identifier (subdomain, JWT, header)
2. Look up tenant record (cache in Redis, TTL 5 minutes)
3. Set tenant context for the request (thread-local / async context)
4. All subsequent database queries automatically scoped to tenant
```

### Default Query Scoping (Critical)

**Every model with a tenant_id MUST have a default scope.**

```ruby
# Rails: default scope
class Post < ApplicationRecord
  belongs_to :tenant
  default_scope { where(tenant_id: Current.tenant_id) }
end
```

```python
# Django: custom manager
class TenantManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=get_current_tenant_id())

class Post(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    objects = TenantManager()
    unscoped = models.Manager()  # escape hatch for admin/migrations
```

```typescript
// TypeORM/Prisma: middleware or extension
prisma.$use(async (params, next) => {
  if (params.model && tenantScopedModels.includes(params.model)) {
    params.args.where = { ...params.args.where, tenantId: getCurrentTenantId() };
  }
  return next(params);
});
```

### Data Isolation Verification

```
Test: Create records as tenant A, query as tenant B → must return empty
Test: Update record belonging to tenant A as tenant B → must fail with 404 (not 403)
Test: Admin queries (unscoped) → must work for internal tools only
```

## Tenant-Aware Features

### Caching
```
Cache keys MUST include tenant_id:
  BAD:  cache.get("users:list")
  GOOD: cache.get("tenant:acme:users:list")
```

### Background Jobs
```
Jobs MUST carry tenant context:
  SendEmailJob.perform_async(tenant_id, user_id, template)
  Worker sets tenant context before processing
```

### File Storage
```
Storage paths MUST include tenant:
  {bucket}/{tenant_id}/uploads/{uuid}/{filename}
```

### Search Indexes
```
Index per tenant OR filter by tenant_id in queries:
  Elasticsearch: include tenant_id as a filter field
  PostgreSQL FTS: include tenant_id in WHERE clause
```

## Migration Patterns

### Adding Tenancy to Existing App
```
1. Create tenants table
2. Add tenant_id to all user-facing tables (nullable initially)
3. Create a default tenant, assign all existing records
4. Add NOT NULL constraint after backfill
5. Add composite indexes: (tenant_id, id), (tenant_id, created_at)
6. Add default scope / query middleware
7. Add tenant resolution middleware
8. Test data isolation thoroughly
```

### Cross-Tenant Operations (Admin Only)
```
- Explicitly bypass tenant scope (use unscoped/admin manager)
- Require admin authentication
- Audit log all cross-tenant access
- Never expose cross-tenant data to regular users
```

## Security Checklist

- [ ] Every table with user data has tenant_id column
- [ ] Default query scope filters by tenant_id automatically
- [ ] Middleware sets tenant context on every request
- [ ] Cache keys include tenant_id
- [ ] Background jobs carry tenant context
- [ ] File storage paths include tenant_id
- [ ] Admin cross-tenant access is audited
- [ ] Tests verify data isolation between tenants
- [ ] Composite indexes on (tenant_id, primary_key) for performance
- [ ] Tenant not found → 404 (not 403, to prevent tenant enumeration)
