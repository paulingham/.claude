---
type: proposal
date: 2026-05-15
status: accepted
task_id: mcp-tool-search-and-mcp-prune
---

# MCP Tool Configuration: ENABLE_TOOL_SEARCH pin + mcpServers prune

## Summary

T2 config-only change covering three slices in a single atomic PR:

1. Pin `ENABLE_TOOL_SEARCH=true` in `settings.json` env block.
2. Document `chrome-devtools-mcp` consumers and the MCP server allowlist policy (this file).
3. Remove the unused `mcpServers["memory"]` stdio entry (server file `skills/mcp_memory/server.py` had zero in-tree callers among skills/agents/hooks/orchestrator/protocols).

No source code changes. No Iron Law surface touched. Budget 4, critical false.

## Policy: MCP server allowlist

Every entry in `mcpServers` of `settings.json` MUST have a named in-tree consumer — at least one of: a skill, an agent's `tools:` frontmatter, or a hook. Orphan entries (servers that load on start but no skill/agent/hook resolves their tools) burn cold-start cost and surface area for nothing and are pruned on sight.

After this PR, surviving `mcpServers` entries (line numbers reflect post-edit `settings.json`):

| Server slug | Line | Consumer(s) |
|---|---|---|
| `gh-cache` | ~1226 | `hooks/_lib/github-cache-server.py` — GitHub API response caching for review/CI lookups; consumed indirectly via `gh` shell commands and hook pre-fetch paths. |
| `lsp-typescript` | ~1233 | `hooks/_lib/lsp-bridge-server.py --language ts` — TypeScript LSP bridge; consumed by code-review, software-engineer, frontend-engineer on `.ts/.tsx` edits. |
| `lsp-pyright` | ~1240 | `hooks/_lib/lsp-bridge-server.py --language py` — Pyright LSP bridge; consumed by code-review, software-engineer on `.py` edits. |
| `chrome-devtools` | ~1247 | See § chrome-devtools-mcp consumers below. |

## chrome-devtools-mcp consumers

Two confirmed in-tree consumers; both are load-bearing for active pipeline phases.

### `skills/build-implementation/SKILL.md` — Step 2d DOM smoke

Consumes:
- `mcp_chrome_devtools_navigate_page` — load each changed route in a headless Chromium.
- `mcp_chrome_devtools_list_console_messages` — collect console errors after route load.
- `mcp_chrome_devtools_list_network_requests` — collect 4xx/5xx XHR responses.

Emits verdicts (declared in `protocols/verdict-catalog.md`):
- `DOM_SMOKE_PASSED` — all routes loaded with no console errors and no 4xx/5xx XHR; Build proceeds.
- `DOM_SMOKE_SKIPPED` — reason ∈ {`env-hatch`, `no-changed-routes`, `no-route-resolver`, `mcp-unavailable-first-run`}; Build proceeds.
- `DOM_SMOKE_FAILED` — console error or 4xx/5xx XHR detected after ignore-filter, OR `mcp-unavailable-after-warm`, OR `ignore-list-overbroad`, OR `dev-server-non-loopback`; HALT Build, spawn fix-engineer in-cycle.

### `agents/frontend-engineer.md` — per-agent tool allowlist

Declares `mcp_chrome_devtools_*` tools in its `tools:` frontmatter for the per-agent allowlist hook (`pre-agent-allowlist.sh`, ENFORCING since 2026-05-14). Without these tools declared, the hook blocks frontend-engineer from invoking DOM-smoke utilities mid-build.

## Pinning provenance (settings.json:~1253 — the chrome-devtools block `_comment` field)

The existing `_comment` rationale on the `chrome-devtools` entry is retained verbatim post-edit:

> Pinned to 0.26.0. Future hardening: replace npx with npm ci against committed lockfile under ~/.claude/mcp-servers/chrome-devtools/ — tracked separately. Provenance: github.com/ChromeDevTools/chrome-devtools-mcp (Google org).

Hardening pathway (deferred, separate task):
- Replace the `npx -y --ignore-scripts chrome-devtools-mcp@0.26.0` invocation with a `npm ci` against a committed `package-lock.json` under `~/.claude/mcp-servers/chrome-devtools/`.
- Pinning to a lockfile (vs npm registry semver) closes the supply-chain window between release and consumption.
- Provenance: source repo is `github.com/ChromeDevTools/chrome-devtools-mcp` under the Google ChromeDevTools org — same trust root as Chromium itself.

## Slice 1: `ENABLE_TOOL_SEARCH=true`

### What it does (per https://code.claude.com/docs/en/mcp#scale-with-mcp-tool-search)

Claude Code's MCP Tool Search is on by default in current builds. With Tool Search enabled, every MCP server's tools are loaded **deferred** — only the tool *names* surface in the initial tool list; the full JSONSchema for each tool is fetched on demand via `ToolSearch`. This is the lowest-upfront-token configuration.

Three possible values:

| Value | Behaviour | Upfront tokens |
|---|---|---|
| (unset, default) | Defer ALL MCP tools behind ToolSearch | Lowest |
| `"true"` | Same as default (defer all) — explicit pin | Lowest |
| `"auto"` | Load servers ≤10% of context window upfront; defer the rest | Higher than default |
| `"false"` | Load all MCP tools upfront (legacy behaviour) | Highest |

### Why pin to `"true"` and not `"auto"`

`auto` was REJECTED at intake. Its 10%-context-window threshold mode loads small MCP servers upfront — INCREASES tool-definition token cost vs the default. Our ACs explicitly target lower upfront tokens, so `auto` works against the stated cost-cap criterion.

### Why pin and not leave unset

The default is currently "defer all" but Claude Code's default-flip cadence is fast. Pinning `"true"` locks our policy regardless of future Claude Code default changes. The pin is harmless on builds that don't recognize the env var (no behaviour change).

### Compatibility caveat

Tool Search requires Sonnet 4+ or Opus 4+. Haiku does not support it. Our default Opus model is `claude-opus-4-7` (per global CLAUDE.md); Sonnet variants we use (Sonnet 4+) all support it. No agent dispatched at Haiku tier (`planning-agent`) calls MCP tools, so the unsupported-model case never fires in practice.

## Slice 3: Remove `mcpServers["memory"]`

The stdio entry at `settings.json:1224-1231` (key `"memory"`, server at `skills/mcp_memory/server.py`) had zero in-tree callers among skills/agents/hooks/orchestrator/protocols. A grep for `mcp__memory__*` tool invocations returned only documentation references in `skills/harness-audit/SKILL.md` (listing `memory` as an example slug in an explanatory paragraph — not a call site).

### What is preserved (deliberately not deleted)

The `skills/mcp_memory/` directory itself is retained:
- `tests/test_*.py` at `~/.claude/tests/` import from `mcp_memory._lib` modules (in-process Python imports, not the JSON-RPC interface). Removing the directory would break the test suite.
- `session-memory/8efffd88329f34786e1828737702e911/notes.md` references the directory as a live JSON-RPC interface in its notes — kept for forensic continuity.

### Reversibility

Restoring the MCP server is a one-line addition to `mcpServers` if a future skill or agent needs the JSON-RPC surface. No file system migration needed.

## Acceptance evidence (post-merge)

Gather via `cache-audit` skill over next ≥5 pipelines vs the prior 5 same-tier pipelines:
- Per-session input-token median.
- Per-session cache-creation token median.

Target: ≥10% drop in per-session input tokens.

Realistic expectation: given Slice 3 prunes only one unused stdio entry (the `memory` server was deferred anyway under Tool Search), the cost delta will be **smaller than 10%**. Record the actual delta in observation; do not fail-loud if <10%. The Slice 1 pin is defensive (guards against future default flip), not an immediate cost-reduction lever.

## Deviation note

Spec dictated removal of `mcpServers["mcp_memory"]` at line 1229. The actual key at that location was `"memory"` (the server file lives at `skills/mcp_memory/server.py`, which appears to be the source of the naming confusion in the spec). Block removed matches spec intent (zero-caller stdio entry whose server lives at `skills/mcp_memory/server.py`); the literal key name `"memory"` is used in the actual delete.
