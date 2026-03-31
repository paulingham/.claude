---
name: "database-migration"
description: "Use when user wants to Structured database migration workflow: schema design, migration generation, zero-downtime validation, reversibility testing, data migration strategies. ORM-first, multi-framework."
context: fork
agent: database-engineer
argument-hint: "Migration description (e.g., 'add email_verified column to users')"
---

# Database Migration

## What This Skill Does

Manages the full lifecycle of a database migration: schema design, migration file generation, zero-downtime validation, reversibility testing, and data migration when needed. ORM-first — uses the project's ORM migration tooling, not raw SQL.

## When to Invoke

- Adding, modifying, or removing database columns or tables
- Creating or modifying indexes
- Data migrations (backfilling, transforming existing data)
- Schema changes that require zero-downtime deployment

## Process

### Step 1: Detect ORM and Migration Tooling

| Signal | ORM | Migration Tool | Generate Command |
|--------|-----|---------------|-----------------|
| `prisma/schema.prisma` | Prisma | Prisma Migrate | `npx prisma migrate dev --name [name]` |
| `db/migrate/` + `Gemfile` (rails) | ActiveRecord | Rails Migrations | `rails generate migration [Name]` |
| `alembic/` | SQLAlchemy | Alembic | `alembic revision --autogenerate -m "[name]"` |
| `migrations/` + `manage.py` | Django ORM | Django Migrations | `python manage.py makemigrations` |
| TypeORM config | TypeORM | TypeORM Migrations | `npx typeorm migration:generate -n [Name]` |
| `drizzle.config.*` | Drizzle | Drizzle Kit | `npx drizzle-kit generate` |
| `knexfile.*` | Knex | Knex Migrations | `npx knex migrate:make [name]` |

### Step 2: Design the Schema Change

Before writing any migration:

1. **Define the change** in ORM terms (not SQL):
   - What models/entities are affected?
   - What columns are being added/modified/removed?
   - What indexes are needed?
   - What foreign key relationships change?

2. **Check for breaking changes**:
   - Does this remove a column that existing code reads? → Requires two-phase migration
   - Does this rename a column? → Requires two-phase migration
   - Does this add a NOT NULL column without a default? → Will fail on existing rows
   - Does this drop an index that queries depend on? → Check query performance first

3. **Design for zero-downtime** (see Step 4)

### Step 3: Generate and Write the Migration

Use the ORM's migration generator. Never write raw SQL migration files manually.

#### ORM-Specific Patterns

**Prisma:**
```prisma
// Update schema.prisma first, then generate migration
model User {
  id            String   @id @default(cuid())
  email         String   @unique
  emailVerified Boolean  @default(false)  // ← new column
  createdAt     DateTime @default(now())
}
```
Then: `npx prisma migrate dev --name add-email-verified`

**ActiveRecord:**
```ruby
class AddEmailVerifiedToUsers < ActiveRecord::Migration[7.1]
  def change
    add_column :users, :email_verified, :boolean, default: false, null: false
    add_index :users, :email_verified
  end
end
```

**Django:**
```python
# Update model first, then auto-generate
class User(models.Model):
    email_verified = models.BooleanField(default=False, db_index=True)
```
Then: `python manage.py makemigrations`

**Alembic/SQLAlchemy:**
```python
# Update model, then auto-generate
def upgrade():
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index('ix_users_email_verified', 'users', ['email_verified'])

def downgrade():
    op.drop_index('ix_users_email_verified', 'users')
    op.drop_column('users', 'email_verified')
```

### Step 4: Zero-Downtime Migration Patterns

#### Safe Operations (no downtime risk)
- Adding a new table
- Adding a nullable column
- Adding a column with a default value
- Adding an index concurrently
- Adding a new foreign key (nullable)

#### Dangerous Operations (require two-phase migration)

**Removing a column:**
```
Phase 1: Deploy code that stops reading/writing the column
Phase 2: Migration that drops the column
```

**Renaming a column:**
```
Phase 1: Add new column, dual-write to both, read from new
Phase 2: Migration to drop old column
```

**Adding NOT NULL to existing column:**
```
Phase 1: Add column as nullable with default, backfill existing rows
Phase 2: Add NOT NULL constraint after all rows have values
```

**Changing column type:**
```
Phase 1: Add new column with new type, dual-write, backfill
Phase 2: Switch reads to new column
Phase 3: Drop old column
```

#### Concurrent Index Creation
For large tables, always create indexes concurrently:
- **PostgreSQL**: `CREATE INDEX CONCURRENTLY` (ActiveRecord: `algorithm: :concurrently, disable_ddl_transaction: true`)
- **MySQL**: `ALTER TABLE ... ADD INDEX` (online DDL, usually safe)
- **Prisma**: Use `@@index` in schema, Prisma handles it
- **Django**: `AddIndex` with `concurrently=True` in `SeparateDatabaseAndState`

### Step 5: Reversibility Testing

Every migration must be reversible:

1. **Run migration forward**: `migrate up`
2. **Run migration backward**: `migrate down` / `rollback`
3. **Run migration forward again**: `migrate up`
4. **Verify schema matches expected state**

If a migration is not reversible (e.g., data loss on rollback), document this explicitly and require manual approval.

### Step 6: Data Migration

When existing data needs transformation:

```markdown
## Data Migration Checklist
- [ ] Estimated row count for affected tables
- [ ] Batch processing for large tables (1000 rows at a time)
- [ ] Idempotent (safe to re-run if interrupted)
- [ ] Progress logging (every N batches)
- [ ] Tested with production-like data volume
- [ ] Rollback plan documented
- [ ] Separate from schema migration (run independently)
```

**Never mix schema changes and data migrations in the same migration file.**

Data migration pattern:
```ruby
# Rails example — separate data migration
class BackfillEmailVerified < ActiveRecord::Migration[7.1]
  disable_ddl_transaction!

  def up
    User.where(email_verified: nil).in_batches(of: 1000) do |batch|
      batch.update_all(email_verified: false)
    end
  end

  def down
    # Idempotent: no-op on rollback
  end
end
```

### Step 7: Index Strategy

Verify indexes support the application's query patterns:

| Query Pattern | Index Type |
|--------------|------------|
| Exact match (`WHERE email = ?`) | B-tree (default) |
| Range query (`WHERE created_at > ?`) | B-tree |
| Full-text search | GIN (PostgreSQL) / FULLTEXT (MySQL) |
| JSON field query | GIN (PostgreSQL) |
| Geospatial | GiST (PostgreSQL) / SPATIAL (MySQL) |
| Composite lookup (`WHERE tenant_id = ? AND status = ?`) | Composite index (most selective column first) |

**Index anti-patterns:**
- Index on every column (write overhead, storage waste)
- Missing index on foreign keys (slow JOINs)
- Redundant indexes (composite index on `(a, b)` already covers queries on `a` alone)
- Index on low-cardinality columns (boolean, status with 3 values — usually not worth it unless combined)

### Step 8: Verify Migration

After running the migration:

```
1. Run migration:     [ORM migrate command]
2. Check schema:      Verify schema matches expectations
3. Run tests:         Full test suite to catch regressions
4. Check queries:     EXPLAIN ANALYZE on queries touching changed tables
5. Rollback test:     Migrate down, then up again
```

## Phase Output

```
Verdict: MIGRATION_COMPLETE / MIGRATION_BLOCKED
Next: Deploy migration (staging first), then verify with /deploy
Artifacts: [migration files, schema diff, reversibility test results, index analysis]
Downtime Risk: [none / requires two-phase deployment]
```
$ARGUMENTS
