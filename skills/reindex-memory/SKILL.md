---
name: "reindex-memory"
description: "Rebuild ~/.claude/db/memory.sqlite from learning/*/observations.jsonl and scratchpad findings. Idempotent; Python stdlib only."
---

# Reindex Memory

## What It Does

Rebuilds `~/.claude/db/memory.sqlite` — a derived SQLite index with FTS5 —
from the canonical `learning/{project_hash}/observations.jsonl` files and
scratchpad findings. The JSONL files remain the source of truth; this DB
is a fast, queryable read index used by Stories 3-5 (`/recall`, MCP memory
server, and embedding similarity search).

## When To Use

- **First install**: schema does not exist yet.
- **After observation drift**: hooks appended new rows the index hasn't seen.
- **Schema bump**: `schema_version.version` less than code's `CURRENT_VERSION`
  triggers a rebuild of data tables; embeddings whose `content_hash` still
  maps to a live observation/scratchpad row are preserved.

## How To Invoke

```bash
python3 ~/.claude/skills/reindex-memory/reindex.py
python3 ~/.claude/skills/reindex-memory/reindex.py \
  --db /tmp/test.sqlite --learning /tmp/learning
```

## Contract

- **Inputs**: `--db` (default `~/.claude/db/memory.sqlite`), `--learning`
  (default `~/.claude/learning`).
- **Archive exclusion**: ingest globs `learning/*/observations.jsonl` — the `archive/` subdirectory is never scanned.
- **Dedup key**: `sha256(session_id|timestamp|tool|file)`.
- **Output line**: `REINDEXED db=... inserted=N skipped=N bad=N`.
- **Exit code**: `0` even when malformed rows are present (they are logged
  to stderr and skipped).
- **Safety**: Python stdlib only. No network access. No third-party
  packages. Runs offline on a fresh install.

## Verdict

- `REINDEXED` — schema ensured, inserts/skips reported, exit 0.
- `NOOP` — nothing to do (no JSONL files under `learning/`).
- `FAILED` — fatal error (I/O, corrupt DB). Error printed to stderr, exit 1.

## Shape Notes

Each helper module in `_lib/` is intentionally small (<=50 lines). Function
bodies are <=8 lines per project shape rules. Tests live at the repo root
in `tests/`.
