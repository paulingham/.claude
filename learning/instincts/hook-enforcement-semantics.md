---
id: hook-enforcement-semantics
confidence: 0.6
roles:
  - architect
  - infrastructure-engineer
  - software-engineer
domain: hooks
---

## Pattern

Advisory PreToolUse Agent hooks fall into two semantic classes — **pure-deny** and **mutation-semantic** — and the class determines whether a single-line flip from `exit 0` to `exit 2` is a viable promotion path.

### pure-deny

The hook's value-add is *refusing* a spawn that violates a frontmatter/contract constraint. The decision is binary: allow or deny. No `tool_input` mutation is required to convey the verdict; the harness already encodes `exit 2 + stderr` as the canonical denial idiom (`hooks/main-branch-guard.sh`, `hooks/agent-skill-reminder.sh`, `hooks/depth-guard.sh`, `hooks/bash-write-guard.sh`).

Examples:
- `hooks/pre-agent-allowlist.sh` — denies spawns whose `tool_input.allowed_tools` exceeds frontmatter `tools:` (flipped 2026-05-14).
- `hooks/verification-freshness-guard.sh` — denies stale-evidence spawns (eligible for flip; awaiting promotion criterion).

Flip mechanics: one branch in the wrapper, `printf 'BLOCKED: …\n' >&2; exit 2` before the existing log path. Reversibility: `CLAUDE_DISABLE_<NAME>=1` short-circuit plus a 1-line `exit 2 → exit 0` rollback.

### mutation-semantic

The hook's value-add is *injecting* fields into the rendered spawn — defaults, advisor pairings, instinct blocks. There is no useful "denial" verdict: the spawn is legitimate, the hook only enriches it. Without `modified_tool_input` round-trip on the PreToolUse Agent matcher, the wrapper has no way to deliver the mutation; the harness must rely on orchestrator-side splice or environment variables.

Examples:
- `hooks/pre-agent-thinking.sh` — wants to inject `tool_input.thinking.{effort,display}` defaults.
- `hooks/pre-agent-advisor.sh` — wants to inject the `advisor:` field for reviewer pairings.
- `hooks/instinct-injector.sh` — wants to splice a `## Learned Patterns` block into the prompt.
- `hooks/cache-breakpoint-injector.sh` — wants to inject cache breakpoints into long preambles.

Flip mechanics: requires both a resolver-emitted `MUTATE` decision token AND a wrapper branch that prints `{"decision":"approve","modified_tool_input":{…}}` to stdout. Both are inert today because the Agent input schema does not expose `modified_tool_input`. Promoting these hooks requires an empirical probe (`hooks/probe-modified-tool-input.sh`) plus operator-run manual verification of `metrics/{session}/hook-injections.jsonl` mutation counters over a 14-day soak.

## Why

The two classes have asymmetric risk profiles, so they warrant different promotion criteria:

- A **pure-deny flip** that mis-classifies has a bounded blast radius — the operator sees `BLOCKED: …` on the spawn that was denied, sets `CLAUDE_DISABLE_<NAME>=1`, and proceeds. The audit JSONL preserves the record. Rollback is one line.
- A **mutation-semantic flip** that silently fails (e.g. `modified_tool_input` round-trips in the probe but is dropped by the production Agent matcher) has an unbounded blast radius — every spawn renders with the un-mutated input, the JSONL mutation counter increments but no actual behaviour changes, and the failure is invisible until someone reads a rendered prompt and notices the missing field. The trace-read seam at `metrics/{session}/trace/{role}-{task-id}-{timestamp}.txt` is plain-text with no parser, so we cannot mechanically detect the silent failure.

Conflating the two classes leads to one of two failures:
1. **Premature mutation flip** — wide flip that includes thinking/advisor/instinct deny-paths refuses legitimate spawns the orchestrator should be enriching.
2. **Stalled pure-deny flip** — refusing to flip allowlist/freshness because "we're waiting on `modified_tool_input`" leaves a working enforcement path unused.

## How to Apply

- **Before drafting a flip plan**, identify the class of each target hook. The Path-B template (resolver → `LOG` decision → log-injection.sh → exit 0) hides this — the value-add semantic must come from reading the resolver, not the wrapper.
- **For pure-deny hooks**: flip path is one-line wrapper branch; promotion criterion is operational (≥14 days, ≥50 pipelines, zero unexpected blocks). No schema dependency.
- **For mutation-semantic hooks**: flip path requires resolver-emitted `MUTATE` token + wrapper stdout JSON envelope. Promotion criterion adds (a) empirical probe round-trip confirmation, (b) operator-run manual JSONL review over the soak window because the trace-read seam is plain-text.
- **For `instinct-injector.sh` specifically**: do NOT flip. The resolver invokes the splice unconditionally — there is no DECISION branch in the shell layer. The delivery path is the orchestrator-side prompt splice (`orchestrator/agent-orchestration.md` § Instinct Injection), not the Agent matcher. Flipping to `exit 2` would refuse every legitimate spawn.

## When NOT to Apply

- Hooks that gate a non-Agent matcher (Bash, Write, Edit, etc.). Those have always-supported deny paths via `permissionDecision` JSON OR `exit 2 + stderr`; class-of-semantic analysis is unnecessary.
- Pre-emptive refactor sweeps. The class is a property of the hook's value-add, not its file shape — code-restructuring without changing semantics does not move a hook between classes.

## Provenance

Pattern crystallised during `promote-advisory-hooks-enforcement` pipeline (2026-05-14). Architect-recon mapping at `pipeline-state/promote-advisory-hooks-enforcement/architect-context.md` § Code Archaeology surfaced the Finding A3 outlier (`instinct-injector.sh` has no shell DECISION branch) and the trace-read seam M1 (plain-text trace, no parser). The pipeline flipped one pure-deny hook (`pre-agent-allowlist.sh`) and held two mutation-semantic hooks (`pre-agent-thinking.sh`, `pre-agent-advisor.sh`) behind probe RED.
