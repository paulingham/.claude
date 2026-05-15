# Per-Agent Tool Allowlists (ENFORCING since 2026-05-14)

Detail prose for the Per-Agent Tool Allowlists mechanism. CLAUDE.md keeps only a pointer; the full per-agent tool-scoping contract (frontmatter shape, loader location, allowed/forbidden tool surface) lives in `protocols/agent-protocol.md` § Per-Agent Tool Scoping.

## Mechanism

Every agent's `tools:` frontmatter declares the tools that agent may invoke (YAML list, one tool per line). The `pre-agent-allowlist.sh` PreToolUse hook reads the spawned `subagent_type`, loads the matching frontmatter via `agent_tools_loader`, and computes a subset check against `tool_input.allowed_tools`. When the resolver returns `action == "would_block"` (the requested allowlist exceeds frontmatter), the hook:

1. Appends an audit line to `metrics/{session}/tool-allowlist.jsonl` with `action: "blocked"` and the offending tool list (`source: "path-b-advisory"` is retained for backward compatibility with existing log consumers).
2. Prints `BLOCKED: tool-allowlist subset violation — subagent=<role> offending=[...]` to stderr.
3. Exits with code 2, denying the spawn.

For `action ∈ {ok, advisory}`, the hook logs and exits 0 (audit trail preserved on the happy path).

## Status (ENFORCING since 2026-05-14)

The allowlist gate uses the **pure-deny** flip path: refusing a spawn is delivered via the existing `exit 2 + stderr` harness idiom (`hooks/main-branch-guard.sh`, `hooks/agent-skill-reminder.sh`, `hooks/depth-guard.sh`), which does **not** require the `modified_tool_input` schema. The hook flipped from advisory to enforcement on 2026-05-14; see `learning/instincts/hook-enforcement-semantics.md` for the pure-deny vs mutation-semantic class boundary that makes this hook eligible while `pre-agent-thinking.sh` / `pre-agent-advisor.sh` / `instinct-injector.sh` remain advisory.

## Operator Controls

- `CLAUDE_DISABLE_TOOL_ALLOWLIST=1` — disable the gate per-session (the hook short-circuits to `exit 0` before invoking the resolver; no JSONL line). Use when the gate mis-classifies a legitimate spawn; investigate, file a frontmatter PR, then unset.
- `CLAUDE_HOOK_PROFILE=minimal` — suppresses the hook entirely (matches the four sibling Path-B hooks).

## Promotion Criterion (satisfied 2026-05-14)

Mirrors `protocols/_proposals/2026-05-14-iron-law-2-freshness-hook.md`:

1. ≥14 days post-merge AND ≥50 pipelines with zero unexpected `blocked` JSONL records on gated roles — measured post-flip; rollback below.
2. Schema dependency satisfied — the pure-deny path requires no new schema; `exit 2 + stderr` is the working idiom today.
3. Operator manual review of `metrics/{session}/tool-allowlist.jsonl` over the 14-day window.
4. Rollback path: swap `exit 2` → `exit 0` on the block branch in `hooks/pre-agent-allowlist.sh`, OR set `CLAUDE_DISABLE_TOOL_ALLOWLIST=1` at runtime.

## See Also

- `protocols/agent-protocol.md` § Per-Agent Tool Scoping — full contract: frontmatter shape, allowed tool catalog, MCP server resolution, audit step.
