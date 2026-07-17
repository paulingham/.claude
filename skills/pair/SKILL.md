---
name: "pair"
description: "The Pair-gear entry point: fastest path from request to working change, for work that gear-select classifies as low-risk and single-file/small-scope. Use when gear-select emits PAIR, or the user says 'just pair' / 'pair on this'."
verdict: "PAIR_COMPLETE"
phase: "build"
dispatch: "subagent"
---

# Pair

The lightest gear. One request in, one worker out, no ceremony.

## When to Invoke

- **Trigger**: `hooks/_lib/gear-select.sh` classified the request as `PAIR` (the default), or the user said "just pair" / "pair on this".
- **Do NOT use when**: the request touches multiple files/a public contract/new AC scope (that's `BUILD`), or is security-sensitive/critical (that's `PIPELINE`) — `gear-select` escalates automatically; do not second-guess it here.

## Safety Invariant (non-negotiable)

**The orchestrator never writes code — not even in Pair mode.** Pair's speed comes *entirely* from skipping the worktree-branch dance, the PR, and the multi-agent gates. It does NOT come from letting the top-level agent Edit or Write. The actual change is always made by a spawned engineer worker, never by the agent running this skill.

## Procedure

### Step 1: Spawn a single worker

Dispatch exactly one lightweight engineer subagent (`software-engineer`, or `frontend-engineer`/`database-engineer` when the request is clearly domain-specific) to make the change. No `TeamCreate`, no worktree-branch ceremony beyond whatever the worker's own tool use requires, no PR.

```
Spawn: software-engineer
Prompt: "<the user's request, verbatim>. Read ~/.claude/agents/software-engineer.md
for your full role definition. This is Pair-gear work: make the change directly,
run relevant tests, report what changed. No PR required."
```

### Step 2: Relay the result

Report the worker's diff/output back to the user as-is. No code-review pass, no security-review pass, no Final Gate — those are what `BUILD`/`PIPELINE` are for.

## Output

- **Verdict**: `PAIR_COMPLETE` (informational — no gate).
- **Artifacts**: whatever the spawned worker produced (diff, test output).

## Verdict

| Verdict | Meaning | Downstream |
|---------|---------|------------|
| `PAIR_COMPLETE` | Worker made the change and reported back. | None — conversation continues; user may say "build it" or "ship it properly" to escalate the same request to `BUILD`/`PIPELINE`. |

## Anti-Patterns

- **Orchestrator edits directly**: the single most important thing this skill must never do. Even a "trivial" one-line fix goes through a spawned worker.
- **Adding ceremony back in**: no PR, no worktree-branch dance, no multi-agent gates. If a request needs those, it isn't Pair-gear work — let `gear-select` escalate it instead of bolting ceremony onto this skill.
