---
name: Database Patterns
description: Schema design, migration safety, query optimization, N+1 prevention, and connection pooling patterns
type: reference
---

# Database Patterns

## Schema Design Principles

- Every table has a primary key and timestamps (`created_at`, `updated_at`)
- Foreign keys with explicit `ON DELETE` behavior (CASCADE, RESTRICT, SET NULL — be intentional)
- Check constraints enforce domain rules at the DB level, not just the app layer
- Prefer enums or lookup tables over magic strings
- Normalize to 3NF; denormalize only with measured justification (profiling evidence required)
- Soft deletes via `deleted_at` timestamp, not boolean flags (enables timeline queries)
- Audit columns: `created_by`, `updated_by` for compliance-sensitive data

## Migration Safety (Zero-Downtime)

### Column Operations
- **Adding a column**: add as nullable first, backfill, then add NOT NULL constraint in a separate migration
- **Removing a column**: stop reading it in app first (deploy), then drop in next migration
- **Renaming a column**: add new column → copy data → update app to use new → drop old (3 deploys)
- **Never**: add NOT NULL without a default in a single migration on a live table

### Index Operations
- Create indexes with `CONCURRENTLY` (PostgreSQL) to avoid table locks
- Drop indexes with `CONCURRENTLY` too
- Verify index usage before dropping (`pg_stat_user_indexes`)

### Data Migrations
- Keep schema migrations separate from data migrations
- Data migrations must be idempotent (safe to re-run)
- Batch large data migrations (1000 rows at a time) to avoid long locks

### Reversibility
- Every migration must have a reversible `down` method
- If truly irreversible (data destruction), document why and add explicit guard

## ORM Usage (Preferred — Raw SQL Requires Justification)

**Default to the project's ORM.** ORMs parameterise values automatically, reducing SQL injection risk. Use the ORM's query DSL for all standard CRUD, filtering, and association loading.

### Why ORMs First
- ORMs parameterise all values automatically — minimal injection surface
- Query objects stay composable and testable
- Schema changes reflect automatically via migrations
- Raw SQL sidesteps the ORM's identity map, caching, and type coercion

### When Raw SQL Is Justified
- **Window functions, recursive CTEs, lateral joins** that the ORM cannot express
- **EXPLAIN ANALYZE** for query profiling
- **DB-admin scripts** run outside the application process
- **Performance-critical queries** where the ORM generates suboptimal SQL (profile first)

**If using raw SQL**: always use parameterised placeholders (`?`, `:name`, `$1`) — never string interpolation. Document why the ORM was insufficient. Wrap in a Query Object for testability.

### Rails (ActiveRecord)
```ruby
# Good — ORM handles parameterisation
User.where(email: params[:email])
User.where("created_at > ?", 7.days.ago)     # ? placeholder if DSL won't reach
Order.joins(:user).where(users: { role: :admin }).select(:id, :total)

# Bad — string interpolation = injection
User.where("email = '#{params[:email]}'")    # NEVER
User.find_by_sql("SELECT * FROM users WHERE email = '#{email}'")  # NEVER

# N+1: eager load associations
Post.includes(:author, :tags).limit(20)      # 3 queries, not N+1
Post.eager_load(:author).where(authors: { verified: true })  # JOIN when filtering

# Query Objects
class RecentActiveUsersQuery
  def call
    User.where(active: true)
        .where("last_seen_at > ?", 30.days.ago)
        .order(last_seen_at: :desc)
  end
end
```

### TypeORM (Node/TypeScript)
```typescript
// Good — query builder with parameterisation
const users = await dataSource
  .getRepository(User)
  .createQueryBuilder('user')
  .where('user.email = :email', { email })        // named param, safe
  .andWhere('user.active = :active', { active: true })
  .getMany();

// Also good — find options
const user = await userRepo.findOne({ where: { email, active: true } });

// Bad — template literal in raw query
await dataSource.query(`SELECT * FROM users WHERE email = '${email}'`);  // NEVER
```

### Prisma (Node/TypeScript)
```typescript
// Good — all values parameterised by Prisma internals
const users = await prisma.user.findMany({
  where: { email, active: true, createdAt: { gte: subDays(new Date(), 30) } },
  include: { orders: true },
  orderBy: { createdAt: 'desc' },
  take: 20,
});

// Raw query — only for EXPLAIN ANALYZE, never feature queries
// await prisma.$queryRaw`EXPLAIN ANALYZE SELECT ...`  // profiling only
```

### SQLAlchemy (Python)
```python
# Good — ORM expressions
users = session.execute(
    select(User)
    .where(User.email == email)         # parameterised automatically
    .where(User.active == True)
    .options(selectinload(User.orders)) # eager load to prevent N+1
).scalars().all()

# Bad — string formatting
session.execute(f"SELECT * FROM users WHERE email = '{email}'")  # NEVER
```

### Django ORM (Python)
```python
# Good
users = User.objects.filter(email=email, active=True).select_related('profile')

# Bad
users = User.objects.raw(f"SELECT * FROM users WHERE email = '{email}'")  # NEVER
```

## Query Optimization

- Run `EXPLAIN ANALYZE` in a migration or script — never in application code paths
- Index columns used in `WHERE`, `ORDER BY`, `JOIN`, and foreign keys
- Composite indexes: most selective column first
- Partial indexes for common filtered queries (via migration, not raw SQL)
- Avoid loading all records to count — use ORM `.count()` methods
- Use `LIMIT`/`take` on any query without a guaranteed bound

## N+1 Detection and Prevention

### Detection
- Enable query logging in development (`log_level: :debug` in Rails, `logging=True` in Django/SQLAlchemy)
- Use Bullet gem (Ruby), Django Debug Toolbar (Python), or TypeORM query logging
- Monitor query count per request in staging

### Prevention
- Eager load associations: `includes`/`eager_load` (Rails), `select_related`/`prefetch_related` (Django), `selectinload` (SQLAlchemy), `include` (Prisma)
- Batch loading for GraphQL resolvers (use DataLoader pattern — see `api-patterns.md`)
- Use `joins` for filtering, `includes` for rendering (Rails distinction)
- Never load all records to count them — use the ORM's count method

## Connection Pooling

- Pool size = (web server threads) × (number of processes) + headroom
- Set statement timeout to prevent runaway queries (e.g., 5000ms)
- Configure idle connection cleanup (idle_timeout)
- Use PgBouncer in transaction mode for high-concurrency scenarios
- Monitor pool exhaustion — it surfaces as timeout errors under load

## Transactions

- Wrap read-modify-write sequences in transactions to prevent race conditions
- Keep transactions short — no external API calls, no email sends inside a transaction
- Use optimistic locking (`lock_version` column) for concurrent updates to the same record
- Use advisory locks for cross-process coordination (e.g., cron job deduplication)
- Rollback on any exception — never swallow errors inside a transaction block

## Soft Deletes

Define the column in a migration (not raw SQL) and use ORM scopes:

```ruby
# Rails migration
add_column :records, :deleted_at, :datetime
add_index :records, :deleted_at, where: 'deleted_at IS NULL'  # partial index via migration DSL

# Model — use paranoia or acts_as_paranoid gem, or a manual default_scope
class Record < ApplicationRecord
  scope :active, -> { where(deleted_at: nil) }
  def soft_delete! = update!(deleted_at: Time.current)
  def restore!     = update!(deleted_at: nil)
end

Record.active.where(user: current_user)  # always scoped, never raw WHERE
```

```python
# Django — soft delete via manager
class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

class Record(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    objects = ActiveManager()

    def soft_delete(self): self.deleted_at = timezone.now(); self.save()
    def restore(self):     self.deleted_at = None;          self.save()
```

```typescript
// Prisma — global soft-delete middleware
prisma.$use(async (params, next) => {
  if (params.action === 'findMany') {
    params.args.where = { ...params.args.where, deletedAt: null };
  }
  return next(params);
});
```

## Audit Trail Pattern

Define the audit table via migration and write audit records through the ORM:

```ruby
# Rails migration (not raw SQL)
create_table :audit_logs do |t|
  t.string   :table_name, null: false
  t.bigint   :record_id,  null: false
  t.string   :action,     null: false  # 'create', 'update', 'destroy'
  t.jsonb    :old_values
  t.jsonb    :new_values
  t.bigint   :actor_id
  t.datetime :created_at, null: false, default: -> { 'NOW()' }
end
add_index :audit_logs, [:table_name, :record_id]
add_index :audit_logs, :actor_id

# Writing audit records via ORM — no raw INSERT
AuditLog.create!(
  table_name: 'orders',
  record_id:  order.id,
  action:     'update',
  old_values: old_attrs,
  new_values: order.attributes,
  actor_id:   Current.user&.id
)
```

```typescript
// TypeORM audit subscriber — hooks into ORM lifecycle, no raw SQL
@EventSubscriber()
class AuditSubscriber implements EntitySubscriberInterface {
  afterUpdate(event: UpdateEvent<any>) {
    event.manager.save(AuditLog, {
      tableName: event.metadata.tableName,
      recordId:  event.entity.id,
      action:    'update',
      oldValues: event.databaseEntity,
      newValues: event.entity,
    });
  }
}
```

## Database Seeding

### Seed File Organization
```
db/seeds/
  development.rb     — realistic dev data (10-50 records per table)
  staging.rb          — anonymized production subset
  essential.rb        — lookup tables, enum values (runs in all envs)
```

### Principles
- **Idempotent**: safe to run multiple times (use `find_or_create_by` / upsert)
- **Dependency-ordered**: respect foreign key constraints (create parents before children)
- **Factory-based**: use test factories for consistency (FactoryBot, Faker)
- **Environment-aware**: never seed production with test data

### Examples

**Rails:**
```ruby
# db/seeds/development.rb
10.times do
  user = User.find_or_create_by!(email: Faker::Internet.unique.email) do |u|
    u.name = Faker::Name.name
    u.password = 'password123'
  end
  3.times { user.posts.create!(title: Faker::Lorem.sentence, body: Faker::Lorem.paragraphs(number: 3).join("\n")) }
end
```

**Prisma:**
```typescript
// prisma/seed.ts
async function main() {
  for (let i = 0; i < 10; i++) {
    await prisma.user.upsert({
      where: { email: `user${i}@example.com` },
      update: {},
      create: { email: `user${i}@example.com`, name: `User ${i}` },
    });
  }
}
```

**Django:**
```python
# management/commands/seed.py
class Command(BaseCommand):
    def handle(self, *args, **options):
        for i in range(10):
            User.objects.get_or_create(email=f"user{i}@example.com", defaults={"name": f"User {i}"})
```
