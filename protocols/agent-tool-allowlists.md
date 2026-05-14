# Per-Agent Tool Allowlists (Path B)

Detail prose for the Per-Agent Tool Allowlists (Path B) mechanism. CLAUDE.md keeps only a pointer; the full per-agent tool-scoping contract (frontmatter shape, loader location, allowed/forbidden tool surface) lives in `protocols/agent-protocol.md` § Per-Agent Tool Scoping.

## Mechanism

Every agent's `tools:` frontmatter declares the tools that agent may invoke (YAML list, one tool per line). The `pre-agent-allowlist.sh` PreToolUse hook reads the spawned `subagent_type`, loads the matching frontmatter via `agent_tools_loader`, and computes a subset check against `tool_input.allowed_tools`. Any superset request is logged to `metrics/{session}/tool-allowlist.jsonl` with `source: "path-b-advisory"`.

## Status (v2.1.140)

Allowlist enforcement remains **advisory at v2.1.140** because the `allowed_tools:` field is **not yet schema-exposed** on the Agent tool input. The hook computes the subset check and logs the resolution; no spawn is blocked.

## Operator Controls

- `CLAUDE_DISABLE_TOOL_ALLOWLIST=1` — disable per-session.
- `CLAUDE_HOOK_PROFILE=minimal` — suppresses the hook entirely (matches the four sibling Path-B hooks).

## Promotion to Enforcement

Will be promoted to enforcement (exit 2 on `would_block`) the moment the `allowed_tools:` field lands on the Agent input schema. The change is a single-file flip in `hooks/pre-agent-allowlist.sh` — frontmatter contract, loader, and forensic JSONL format are stable across the flip.

## See Also

- `protocols/agent-protocol.md` § Per-Agent Tool Scoping — full contract: frontmatter shape, allowed tool catalog, MCP server resolution, audit step.
