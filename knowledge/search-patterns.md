# Search Patterns

## Strategy Selection

| Strategy | When | Complexity | Performance |
|----------|------|-----------|-------------|
| SQL LIKE/ILIKE | < 10K records, simple matching | Trivial | Slow at scale |
| PostgreSQL Full-Text | < 1M records, good enough search | Low | Good |
| Elasticsearch/OpenSearch | > 1M records, complex queries, facets | High | Excellent |
| Algolia / Meilisearch / Typesense | Fast setup, hosted search, typo tolerance | Low | Excellent |

**Default: PostgreSQL Full-Text Search.** Only add Elasticsearch or a search service when PostgreSQL FTS becomes insufficient.

## PostgreSQL Full-Text Search

### Setup
```sql
-- Add tsvector column (materialized for performance)
ALTER TABLE posts ADD COLUMN search_vector tsvector;

-- Populate
UPDATE posts SET search_vector =
  setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
  setweight(to_tsvector('english', coalesce(body, '')), 'B');

-- Index
CREATE INDEX idx_posts_search ON posts USING GIN(search_vector);

-- Trigger to keep in sync
CREATE TRIGGER posts_search_update
  BEFORE INSERT OR UPDATE ON posts
  FOR EACH ROW EXECUTE FUNCTION
  tsvector_update_trigger(search_vector, 'pg_catalog.english', title, body);
```

### Query
```sql
SELECT *, ts_rank(search_vector, query) AS rank
FROM posts, to_tsquery('english', 'api & design') AS query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 20;
```

### ORM Integration

**Rails:**
```ruby
scope :search, ->(query) {
  where("search_vector @@ plainto_tsquery('english', ?)", query)
    .order(Arel.sql("ts_rank(search_vector, plainto_tsquery('english', #{connection.quote(query)})) DESC"))
}
```

**Django:**
```python
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
Post.objects.annotate(
    rank=SearchRank(SearchVector('title', 'body'), SearchQuery(query))
).filter(rank__gte=0.1).order_by('-rank')
```

## Search-as-a-Service (Algolia, Meilisearch, Typesense)

### When to Use
- Typo tolerance, fuzzy matching needed
- Instant search (< 50ms response time)
- Faceted search (filter by category, price range, etc.)
- Team doesn't want to manage search infrastructure

### Architecture
```
Database (source of truth) → Background Job → Search Index (read replica)

On create/update/delete:
1. Save to database
2. Enqueue index update job
3. Job syncs record to search service

Search queries go to the search service, not the database.
```

### Index Design
```
Only index searchable and filterable fields (not entire records)
Include: title, body, tags, category, created_at, tenant_id
Exclude: internal IDs, audit fields, large text blobs
```

## Search UI Patterns

### Debounced Input
```
Wait 300ms after user stops typing before sending search request.
Show loading indicator during search.
Cancel previous in-flight request when new input arrives.
```

### Faceted Search
```
Filters appear alongside results:
  Category: [Electronics (42)] [Books (28)] [Clothing (15)]
  Price:    [Under $25] [$25-$50] [$50-$100] [$100+]
  Rating:   [★★★★+ (35)] [★★★+ (58)]

Counts update dynamically as filters are applied.
```

### Autocomplete / Typeahead
```
Suggest completions as user types (distinct from full search results).
Source: recent searches, popular queries, or prefix-matched titles.
Show 5-8 suggestions max.
```

## Multi-Tenant Search

```
ALWAYS filter by tenant_id in search queries.

PostgreSQL: WHERE tenant_id = ? AND search_vector @@ query
Algolia:    filters: 'tenant_id:acme'
Meilisearch: filter: 'tenant_id = acme'

Never return search results from other tenants.
Index tenant_id as a filterable (not searchable) attribute.
```

## Testing Search

```
Unit:        Test query building, filter parsing
Integration: Index test records, verify search returns expected results
Key tests:
  - Relevance: "api design" finds "API Design Patterns" before "Designing APIs"
  - Tenant isolation: tenant A's records not in tenant B's results
  - Empty query: returns recent/popular, not everything
  - Special characters: query with quotes, dashes, unicode handled safely
```
