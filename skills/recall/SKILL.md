---
name: recall
description: Progressive-disclosure read-only query API over memory.sqlite (observations + scratchpad findings). Python API + thin CLI.
argument-hint: "[search <query> | timeline] [--source observations|scratchpad|both] [--limit N] [--db PATH]"
---

# /recall — Progressive Disclosure Over memory.sqlite

Three query tiers tune token cost to caller need. Read-only, stdlib only.

## Tiers

1. **search** — FTS5 bm25-ranked hits (≤200 bytes each). Returns
   `{id, content_hash, timestamp, tool, file, snippet[, source]}`.
2. **timeline** — rows ordered by timestamp ASC, backed by
   `idx_observations_timestamp`. Never touches FTS.
3. **get_observations / get_findings** — hydrate full rows by ids or
   content_hashes. Unknown ids silently omitted.

## Python API

```python
from recall import recall

hits = recall.search("widget", source="both", db_path=db)
rows = recall.get_observations(ids=[h["id"] for h in hits[:3]], db_path=db)
```

Default `source` is `"both"` for search. All tiers accept `include_private=True`
(opt-in; CLI has no `--include-private` flag — privacy-first).

### Source Defaults and Valid Values

| Tier     | Valid sources                        | Default         |
|----------|--------------------------------------|-----------------|
| search   | `both`, `observations`, `scratchpad` | `both`          |
| timeline | `both`, `observations`, `scratchpad` | `observations`  |

Unknown `source` raises `ValueError` on both search and timeline.

### Limits and Caps

`limit` clamps to `[1, 500]`; `limit <= 0` raises `ValueError`.
`ids` / `content_hashes` cap at 100 per call; above that raises.

### Defaults

`db_path=None` resolves to `reindex-memory.paths.default_db()`
(`~/.claude/db/memory.sqlite`).

## CLI

```bash
python3 -m recall._lib.cli search "widget" --source both --limit 20
python3 -m recall._lib.cli timeline --source observations --limit 50
```

Returns JSON envelope `{"tier", "hits", "total", "truncated"}`.

## Filter Whitelist

- `observations`: session_id, project_hash, tool, agent_role, phase,
  time_from, time_to
- `scratchpad`:   task_id, category, agent_role, phase, time_from, time_to

All binds parameterised — no free-form SQL.

## Missing DB

If `db_path` does not exist, all tiers return `[]`, write one stderr warning
`recall: db missing at <path> — run reindex-memory`, exit 0.

## S4 MCP Contract (forward-looking)

Planned MCP tools: `search_memory`, `get_observation`, `get_timeline`.
S4 imports `recall.recall.{search,timeline,get_observations,get_findings}`
directly — no subprocess.

## Read-only Invariant

Two layers of defence:

1. Connection opens via `sqlite3.connect("file:...?mode=ro", uri=True)`.
2. `PRAGMA query_only = 1` is issued on every connection.

`db_path` strings containing `?`, `#`, `&`, or newline are rejected
(`ValueError`) to close the URI-fragment bypass.
Any attempted write raises `sqlite3.OperationalError`.
