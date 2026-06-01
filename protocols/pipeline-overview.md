# Pipeline Overview

How the system fits together: orchestrator role and boundaries, dispatch mechanisms, and the on-demand protocol index that skills/agents pull from. CLAUDE.md keeps only a pointer here.

## How the System Works

The orchestrator (Claude) coordinates work. It never writes code, reads source files, or runs tests.

**Flow (parallel-subagents default):**
```
User → /harness:intake (classify + score) → /harness:pipeline (drive phases)
  → Sequential subagent phases (Plan, single-slice Build, Ship, Deploy):
    → Skill tool or Agent tool → agent works → returns verdict
  → Parallelizable phases (multi-slice Build, Review, Final Gate):
    → Single message with N parallel Agent calls
    → Each agent reads its skill file, works, returns verdict
    → Orchestrator collects all verdicts before advancing

  Visible mode (opt-in: CLAUDE_VISIBLE_TEAMS=1 or /harness:pipeline --visible):
    → TeamCreate("pipeline-{task-id}") + spawn teammates into team
    → Tmux panes show parallel work in real time
    → Teammates shut down after phase
```

**Dispatch mechanisms:**

| Mechanism | When | Visible? |
|-----------|------|----------|
| **Skill tool** | Sequential read-only phases | No |
| **Subagent** (Agent + worktree) | Default for every phase, including parallel fan-outs | No |
| **Team** (TeamCreate + teammates) | Opt-in for human-observable runs only | Yes (tmux) |

**Orchestrator boundaries:**

| ONLY does | NEVER does |
|-----------|------------|
| Invoke skills, spawn agents/teammates | Read source files (`.ts`, `.tsx`, `.js`, etc.) |
| Run `git` commands (status, log, diff, merge) | Run tests, linters, or build commands |
| Manage teams (create, assign, shutdown) | Use Explore or general-purpose agents |
| Track pipeline state + report progress | Compute analysis or make code decisions |

## Detailed Protocols

**Two-tier rules layout.** Auto-load is `rules/core.md` only — load-bearing invariants every spawn needs (Iron Laws, code shape limits, worktree + commit protocol, pipeline phase order, where-to-look-next index). Full protocols live in `protocols/<topic>.md` and are pulled in by skills/agents only when the phase needs them. The original `rules/<topic>.md` files are stubs that preserve backwards-compatible references.

### Skill-Loaded Protocols (read on demand by specific skills/agents)
- `protocols/agent-protocol.md` — Worktree isolation, commit protocol, scratchpad, agent memory, fix-receiving rules, dynamic agents, resource bounds, per-agent tool scoping
- `protocols/pipeline-protocol.md` — Pipeline phases, review loop with in-cycle fix detail, environment-dependent debugging loop, enforcement
- `protocols/engineering-invariants.md` — Engineering baseline: shape decomposition rules, naming, SOLID, error handling, dependency resolution, testing standards, security baseline
- `protocols/atdd-procedure.md` — Full ATDD cycle, mutation gate, per-behaviour TDD exceptions (loaded by `/harness:build-implementation` and `/harness:bug-fix`)
- `protocols/operational-protocol.md` — Complexity Budget, error recovery principles, escalation decision tree
- `protocols/parallel-dispatch-protocol.md` — Hybrid dispatch: teams for Build/Review/Final Gate, subagents for Plan/Ship/Deploy, Best-of-N team variant
- `protocols/module-boundaries-protocol.md` — Modular monolith default, canonical forcing-function list (FF1–FF5)
- `protocols/multi-repo-protocol.md` — Project manifests, multi-repo pipelines, GitHub service config, linked PRs, deploy ordering
- `protocols/e2e-protocol.md` — Multi-target E2E trigger matrix (mobile via Maestro, web via Playwright/Cypress) and prerequisites
- `protocols/reflection-protocol.md` — Post-pipeline reflection, observation capture, auto-learn gate, session-memory + scratchpad cleanup
- `protocols/autonomous-intelligence.md` — Pipeline scratchpad, session memory, continuous learning loop, instinct injection, prompt tracing
- `protocols/thinking-defaults.md` — Default `effort`/`display` resolution, role layer rules, xhigh allocation policy
- `protocols/advisor-mode.md` — Sonnet-executor + Opus-advisor pairing for review roles (Path-B advisory)
- `protocols/cost-discipline.md` — Subagent-summary cache fix, preamble cache stability, per-spawn measurement surface
- `protocols/agent-tool-allowlists.md` — Per-agent `tools:` frontmatter, allowlist hook, Path-B advisory status
- `protocols/skill-directory.md` — Canonical skill catalog (active + deferred) with verdicts and entry conditions

### Orchestrator-Only Protocols (not auto-loaded, read when needed)
- `orchestrator/pipeline-orchestration.md` — State tracking, continuity, progress reporting, anti-patterns
- `orchestrator/agent-orchestration.md` — Agent selection, team management, orchestrator discipline
- `orchestrator/operational-details.md` — Escalation procedures, error recovery details
- `orchestrator/parallel-dispatch-details.md` — Team dispatch procedure, review loop with persistent reviewers, audit trail
