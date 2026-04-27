# Session-Store Adapters

> ⚠ **Semantic divergence from the SDK SessionStore.** This contract is harness-shaped, not a literal port of the SDK. Specifically: `append`, `load`, `subpath`, and `session_id` carry different semantics. **Writes are whole-blob replacements; do not implement byte-append.** The contract names the mutator `put` (not `append`) and the reader `get` (not `load`) to make this explicit. `subpath` is repurposed as Markdown `# section headers` extracted from the blob (see `list_subkeys`). `session_id` is currently always the literal string `notes` — per-pipeline or per-agent notes would change call sites only; the contract already supports them.

This directory holds the per-backend adapters for session memory. The dispatcher lives at `hooks/_lib/session-store.sh`; the resolution and sync helpers live alongside it. The default backend is `local` (on-disk markdown file under `~/.claude/session-memory/{project_hash}/{session_id}.md`); s3 and redis adapters are opt-in via env var.

## Contract — five callable functions

```bash
session_store_put           <project_hash> <session_id> <blob_path_or_dash>
# Reads blob (file or stdin if "-"); writes to backend.
# Exit 0 on success, 1 on backend error.

session_store_get           <project_hash> <session_id>
# Echoes blob to stdout.
# Exit 0 on hit, 1 on miss-or-error (missing file, missing project dir,
# network error, permission denied, 5xx — all collapse to exit 1 because
# remote CLIs (aws, redis-cli) cannot reliably distinguish miss from
# error without a probe-then-fetch sequence on every call). The contract
# guarantees only the exit code; CLI stderr from real errors may surface
# at the call site if not redirected.

session_store_delete        <project_hash> <session_id>
# Removes blob. Exit 0 on success or absent, 1 on backend error.

session_store_list
# Echoes one project_hash per line, sorted ascending. Exit 0 always.

session_store_list_subkeys  <project_hash> <session_id>
# Echoes one section header per line (the literal text after "# ", no leading "#").
# Exit 0 on hit, 1 on miss.
```

Plus two sync helpers used by the orchestrator-side wrap around the
`session-memory-updater` agent (Model b — see `orchestrator/agent-orchestration.md`
§ Session Memory Update):

```bash
session_memory_sync_in      <project_hash> <notes_path>
# Materialises backend → file at notes_path.
# Local: byte-no-op, exit 0.
# Remote GET hit: write blob to notes_path (umask 077), exit 0.
# Remote GET miss-or-error + local exists: leave untouched, exit 0.
# Remote GET miss-or-error + local missing: write template stamp, exit 0.
# (Per the walked-back GET contract — adapters cannot distinguish miss
# from backend error without a probe-then-fetch sequence on every call.)

session_memory_sync_out     <project_hash> <notes_path>
# Mirrors file → backend.
# Local: byte-no-op, exit 0.
# Remote PUT success: exit 0.
# Remote PUT failure: JSONL forensic line via hooks/_lib/log-injection.sh
# at metrics/$CLAUDE_SESSION_ID/session-store-mirror.jsonl + stderr warning
# + exit 0 (workflow never blocks on durability).
```

## Return-code summary

| Function | exit 0 | exit 1 |
|---|---|---|
| `session_store_put` | wrote blob | backend error |
| `session_store_get` | hit (blob on stdout) | miss-or-error (collapsed) |
| `session_store_delete` | removed or absent | backend error |
| `session_store_list` | always | — |
| `session_store_list_subkeys` | hit (headers on stdout) | miss-or-error |
| `session_memory_sync_in` | always | — |
| `session_memory_sync_out` | always (PUT failure logged + warned, never blocks) | — |

> **Note on exit 1 collapse**: The `get` contract previously reserved exit 2 for backend errors, but `aws s3 cp` and `redis-cli GET` both return exit 1 for "key not found", auth failure, 5xx, and network errors alike. Distinguishing miss from error would require an EXISTS / HEAD probe before every GET, doubling round-trip cost. The walked-back contract collapses miss-or-error to exit 1. The contract guarantees only the exit code; the underlying CLI's stderr from real errors may surface at the call site if it is not explicitly redirected.

## Environment variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `CLAUDE_SESSION_STORE_BACKEND` | no | `local` | One of `local`, `s3`, `redis` |
| `CLAUDE_SESSION_STORE_BUCKET` | when `BACKEND=s3` | — | Target S3 bucket name |
| `CLAUDE_SESSION_STORE_REDIS_URL` | when `BACKEND=redis` | — | e.g. `redis://host:6379/0` |
| `CLAUDE_SESSION_STORE_PREFIX` | no | `sessions/` | **IGNORED by local adapter**; applies only to s3/redis |

## Backend storage layouts

```
local: ~/.claude/session-memory/${PROJECT_HASH}/${SESSION_ID}.md
s3:    s3://${BUCKET}/${PREFIX}${PROJECT_HASH}/${SESSION_ID}
redis: ${PREFIX}${PROJECT_HASH}:${SESSION_ID}
```

## Resolution and fallback

Resolution order (locked):

1. Env-var check FIRST: `CLAUDE_SESSION_STORE_BACKEND` ∈ `{local, s3, redis}`.
2. Required-env validation: `BUCKET` for s3, `REDIS_URL` for redis.
3. Tool availability: `command -v aws` for s3, `command -v redis-cli` for redis.
4. On 2 or 3 failure: emit one-line stderr warning AND a JSONL line via `log-injection.sh`, fall back to `local`. Resolution is cached per-process in the exported shell var `_SESSION_STORE_RESOLVED_BACKEND` so the warning fires at most once per process, and parallel pipelines with different `BACKEND` values do not stomp each other (no shared file sentinel).

Warning format (byte-identical across operators for log parsing):

```
[session-store] {backend} backend selected but {reason} — falling back to local
```

Where `{reason}` is one of:
`'aws' CLI not found`, `'redis-cli' not found`,
`CLAUDE_SESSION_STORE_BUCKET not set`, `CLAUDE_SESSION_STORE_REDIS_URL not set`.

## Security

- **Key validation**: `_session_store_validate_key` rejects `project_hash` or `session_id` containing `/`, `..`, leading dot, or empty string. Enforced at the dispatcher boundary before backend dispatch — applies to all backends. Path traversal POCs are covered by 5 cases in the conformance suite per backend.
- **Redis URL credentials**: when `CLAUDE_SESSION_STORE_REDIS_URL` embeds credentials (`redis://user:password@host:6379/0`), the adapter parses them once into `REDISCLI_AUTH` (env var, supported on redis 5.x+) and passes a credential-stripped URL to `redis-cli -u`. The password is no longer visible in the local process table (`ps auxe`, `/proc/$pid/cmdline`) for any put/get/list/delete invocation. Operators on shared hosts should still use OS-level access control, network ACLs, and IAM as the access boundary — REDISCLI_AUTH closes the argv-leakage surface but the env var itself is still readable to a process running as the same user.
- **File permissions**: local adapter creates blobs with mode 0600 and parent directories with mode 0700 (`umask 077` subshell wraps both `cat`/`cp` writes and `mkdir -p` calls).
- **Failure-open fallback**: when an opt-in backend (s3/redis) is misconfigured (env var missing, CLI absent), the dispatcher falls back to `local` and emits both a stderr warning and a JSONL forensic record via `log-injection.sh`. Data is not silently lost.

## Atomicity and race semantics

- **Local**: existing Edit semantics. Whole-file replace via `cat > "$dest"`.
- **S3**: `PutObject` is atomic at the object level. Whole-blob replacement.
- **Redis**: `SET key blob` is atomic.

The read-modify-write (RMW) window for `sync_in` (GET) → agent edits → `sync_out` (PUT) is the agent lifetime. Same race exists locally today; documented, not fixed. Future fix: S3 conditional PUT (`If-Match: ETag`) / Redis `WATCH` — single-file swap.

**Operational invariant**: `session-memory-updater` is the sole writer per project. No two agents may `sync_out` to the same backend key concurrently. Documented in `agents/session-memory-updater.md`.

## Adding a new adapter

1. Create `session-memory/adapters/<name>.sh` exposing `_<name>_put|get|delete|list|list_subkeys` (function bodies ≤ 5 lines, file ≤ 50 lines).
2. Add a `case` arm to `_session_store_dispatch` in `hooks/_lib/session-store.sh`.
3. Add detection + warning in `hooks/_lib/session-store-resolve.sh` (`_resolve_check_<name>` + `_resolve_pick`).
4. Add a driver `tests/shell/session_store_conformance_<name>.bats` sourcing `_conformance_cases.bash`.
5. Update env-var table in this README.

The conformance suite ensures contract parity across all adapters.
