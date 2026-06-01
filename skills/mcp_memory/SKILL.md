---
name: mcp_memory
description: MCP stdio server exposing recall memory as JSON-RPC 2.0 tools. Four read-only tools over ~/.claude/db/memory.sqlite.
---

# /harness:mcp_memory — MCP Memory Server

Long-lived stdio process that any MCP-compatible client can spawn to read
observations + scratchpad findings from `memory.sqlite`. Built directly on
the S3 `recall` API — no subprocess overhead, no duplicated logic.

## Tools

| Tool | Purpose | Arguments |
|------|---------|-----------|
| `search_memory` | FTS5 full-text search | `query` (req), `source`, `limit`, `db_path`, `filters` |
| `get_timeline`  | Chronological rows    | `source`, `limit`, `db_path`, `filters` |
| `get_observations` | Hydrate observation rows | `ids` or `content_hashes`, `db_path` |
| `get_findings`     | Hydrate scratchpad rows  | `ids` or `content_hashes`, `db_path` |

Each tool returns MCP content:

```json
{
  "content": [{"type":"text","text":"<envelope JSON>"}],
  "isError": false,
  "structuredContent": {"tier":"...","hits":[...],"total":N,"truncated":bool}
}
```

Envelope tier values: `search`, `timeline`, `hydrate`.

## Transport

JSON-RPC 2.0 (MCP protocol version `2024-11-05`), newline-delimited JSON
over stdio. One message per line; responses one per line.

## Settings.json

Register via `mcpServers`:

```json
"mcpServers": {
  "memory": {
    "command": "python3",
    "args": ["$HOME/.claude/skills/mcp_memory/server.py"]
  }
}
```

Explicit file path avoids needing `skills/__init__.py`.

## Smoke Test

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | python3 skills/mcp_memory/server.py
```

## Privacy

`include_private` is NOT exposed as a tool argument. Even if a caller
sends it, the per-tool whitelist drops it. Private rows (`is_private=1`)
are never returned.

## Error Codes

| Code    | Meaning                                  |
|---------|------------------------------------------|
| -32700  | Parse error (unparseable JSON line)       |
| -32601  | Method / tool not found                   |
| -32602  | Invalid params (ValueError from recall)   |
| -32603  | Internal error (class name only leaks)    |

## Stdout Discipline

Only JSON-RPC messages on stdout, one per line. All logging (including
recall's `db_missing` warning) goes to stderr.
