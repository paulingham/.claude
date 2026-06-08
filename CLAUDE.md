# Global Playbook

## Engineering Identity

- Lean agile: thin vertical slices delivering observable user value
- MVP mindset: smallest increment that validates the hypothesis
- Ship-learn-iterate: deploy independently, measure, adapt
- Modular monolith by default: in-process boundaries first; new services only when a forcing function (see `protocols/module-boundaries-protocol.md`) is explicitly named
- Engineering discipline: TDD mandatory, SOLID, DRY, clean architecture
- Zero waste: every output line is a test result or a real error
- Proven correct: tests passing is necessary but not sufficient — verify it actually works

> **Default Opus model**: `claude-opus-4-7` (GA 2026-04-16). Pricing unchanged from 4.6 ($5/$25 per-M tokens).
> **80% claim**: measured on `eval/baselines/{latest}-opus-4-7.md`, not SWE-bench Verified. See `skills/internal-eval/SKILL.md`.

## Runtime State Location

All runtime state (pipeline-state, session-memory, agent-memory session dirs, metrics, db, learning project dirs) lives in `$CLAUDE_PLUGIN_DATA` (end-user local, never committed back to the harness repo). The maintainer's repo ships only curated seed: `learning/instincts/`, `agent-memory/<role>/MEMORY.md`, `session-memory/config/`, `session-memory/adapters/`. At Reflect, confirm no runtime state dirs are staged for commit — only seed files belong in the repo.

Paths shown as `~/.claude/…` in agent and protocol files resolve at runtime via `HARNESS_ROOT` (shipped content) or `HARNESS_DATA` (runtime state) — see `hooks/_lib/harness-paths.sh`.

## Session Start (automatic)

1. **In-progress pipeline check**: source `hooks/_lib/pipeline-state-paths.sh` and run `_psp_find_active_pipelines 2>/dev/null | head -1`. If found, auto-invoke `/harness:pipeline-resume` and inform: "Resuming [pipeline name] from [phase]."
2. **Merged-PR pending-deploy check**: if a pipeline state file shows Ship=completed + Deploy=pending, check `gh pr view --json state`. If merged, auto-invoke `/harness:deploy`.

Silent if nothing is found — don't report "no pipelines found."

## Project Readiness Check

Before starting ANY work in a repo:
1. Check for `.claude/CLAUDE.md` or `CLAUDE.md` at project root
2. If missing: **automatically invoke `/harness:project-setup`** before any other work — do not ask
3. If present: read it and confirm no conflicts with global rules

| Layer | Controls | Example |
|-------|----------|---------|
| Global rules | How: engineering discipline | 8-line methods, TDD, SOLID |
| Global CLAUDE.md | Why: philosophy + pipeline | Lean agile, collaboration protocol |
| Project CLAUDE.md | What: project context | Rails 7, PostgreSQL, deploy via Heroku |

Global wins for quality standards; project wins for project-specific conventions.

## Quick Reference

### Thinking Defaults (Opus 4.7)

Every Agent spawn carries a `thinking` field (`effort`, `display`). Applied by `pre-agent-thinking.sh`. Full precedence table, role defaults, gated xhigh promotion, postmortem note, and v2.1.140 advisory status: `protocols/thinking-defaults.md`.

### Advisor-Mode Reviews (Opus 4.7)

Sonnet-executor + Opus-advisor pairing for `code-reviewer` and `security-engineer`; advisory at v2.1.140. Full mechanism: `protocols/advisor-mode.md`.

### Cost Discipline

May 8 2026 subagent-summary cache fix delivers ~3× `cache_creation` reduction when preambles are cache-stable. Full mechanism: `protocols/cost-discipline.md`.

### Per-Agent Tool Allowlists (ENFORCING since 2026-05-14)

`tools:` frontmatter declares per-agent tool allowlist; `pre-agent-allowlist.sh` enforces via `exit 2 + stderr`. Full contract: `protocols/agent-tool-allowlists.md` and `protocols/agent-protocol.md` § Per-Agent Tool Scoping.

### Reversibility Escapes (PreToolUse Agent hooks)

Per-session env vars short-circuit each gate to `exit 0`. Full table: `protocols/agent-protocol.md` § Reversibility Escapes (PreToolUse Agent hooks).

### Instinct Injection (Path B)

`instinct_categories:` frontmatter selects instincts per spawn; `instinct-injector.sh` resolves and logs (advisory at v2.1.140). Full contract: `protocols/autonomous-intelligence.md` § Instinct Injection and `orchestrator/agent-orchestration.md` § Instinct Injection.

### Agent Team

| Agent | Phase | Worktree | Default Model | Tunable |
|-------|-------|----------|---------------|---------|
| architect | Plan | No | opus | No |
| architect-context-recon | Plan (recon) | No | haiku | No |
| code-reviewer | Review | No | opus [1] | Yes |
| database-engineer | Build | Yes | sonnet | Yes |
| fix-engineer | Build (in-cycle) | Yes | sonnet | Yes |
| frontend-engineer | Build | Yes | sonnet | Yes |
| infrastructure-engineer | Build | Yes | opus | Yes |
| patch-critic | Final Gate | No | sonnet | No |
| pbt-engineer | Build | Yes | sonnet | No |
| plan-cache-adapter | Plan | No | haiku | No |
| planning-agent | Build (advisory) | No | haiku | No |
| product-reviewer | Accept | No | sonnet | Yes |
| qa-engineer | Test | Yes | sonnet | Yes |
| sandbox-verify-engineer | Build | No | sonnet | No |
| security-engineer | Review | No | opus | No |
| session-memory-updater | Post-phase | No | haiku | No |
| software-engineer | Build | Yes | sonnet | Yes |
| spec-blind-validator | Final Gate | No | sonnet | No |
| vlm-critic | Final Gate | No | sonnet | No |

> `[1]` Sonnet-solo via `model_conditional` when `complexity_budget.total < 6`; Opus + advisor pairing otherwise. See `agents/code-reviewer.md` and `hooks/_lib/advisor_resolver.py::resolve_model_conditional`.

Model self-tuning, downgrade rules, and `architect`/`security-engineer` hard locks: `orchestrator/agent-orchestration.md` § Instinct Injection. Advisory recommendation report (`/harness:eval-model-effectiveness`): see skill SKILL.md.

### Dispatch (parallel subagents by default; teams opt-in)

Parallelizable phases dispatch as **parallel subagent calls in a single message**. Teams (`TeamCreate`) are opt-in via `CLAUDE_VISIBLE_TEAMS=1` or `/harness:pipeline --visible`.

| Phase | Default Dispatch | Visible-mode (opt-in) |
|-------|------------------|------------------------|
| Plan | Subagent | Subagent |
| Build (single) | Subagent + worktree | Subagent + worktree |
| Build (multi) | Parallel subagents (1 message, N calls) | Team in tmux panes |
| Review | Parallel subagents (1 message, 2 calls) | Team in tmux panes |
| Final Gate | Parallel subagents (1 message, 4 calls) | Team in tmux panes |
| Ship / Deploy | Subagent | Subagent |

Every spawn prompt MUST include: "Read `~/.claude/agents/[role].md` for your full role definition, checklist, and output format." Full dispatch protocol: `protocols/parallel-dispatch-protocol.md`.

### How the System Works

Orchestrator coordinates; never writes code/tests. Flow, dispatch mechanisms, orchestrator boundaries: `protocols/pipeline-overview.md` § How the System Works.

### Work-Class Routing (T0-T6)

`/harness:intake` Step 1.5 (Fingerprint) classifies every request into seven tiers. T0-T3 bypass `/harness:pipeline`; T4-T6 enter at progressively heavier dispatch. Full protocol: `protocols/work-class-routing.md`.

| Tier | Class | Dispatch target |
|---|---|---|
| **T0** | Question / Spike | Direct answer or `/harness:tech-spike` |
| **T1** | Doc-only | Orchestrator direct edit (Iron Law 3 exception) |
| **T2** | Config-only | `/harness:harness-config` |
| **T3** | Mechanical sweep | `/harness:batch-pipeline` |
| **T4** | Bug fix | `/harness:pipeline` (lightweight) |
| **T5** | Standard feature | `/harness:pipeline` (standard) |
| **T6** | Critical / cross-cutting | `/harness:pipeline` (heavy: Best-of-N or PDR-RTV) |

### Delivery Pipeline

Phase order, gates, and skill mapping: `rules/core.md` § Pipeline Phase Order and `protocols/pipeline-protocol.md` § Phase Checklist. No phase skipped. No gate bypassed. CHANGES_REQUESTED = go back.

### Autonomous Intelligence

Three systems make the pipeline self-improving (see `protocols/autonomous-intelligence.md`):

| System | Scope | Purpose |
|--------|-------|---------|
| **Pipeline Scratchpad** | Within one pipeline | Agents share discoveries in real-time |
| **Session Memory** | Across compaction | Engineering context survives context compression |
| **Continuous Learning** | Across pipelines | Observations → instincts → better agents (auto-invokes `/harness:learn`) |

Every agent spawn includes: instincts + agent memory + session memory + scratchpad findings. Tracing off by default; toggle per-session with `/harness:debug-trace on|off`. See `protocols/autonomous-intelligence.md` § Prompt Tracing.

### Skill Directory

Full catalog of user-invocable skills with entry conditions and verdicts: `protocols/skill-directory.md`. Verdict semantics: `protocols/verdict-catalog.md`.

### Definition of Done

Full checklist (all ACs covered, all reviewers APPROVED, PR merged, reflection completed): `protocols/pipeline-protocol.md` § Definition of Done.

### Multi-Repo Support

Project manifests at `~/.claude/manifests/{project}.md` drive auto-detection, GitHub config, linked PRs, dependency-aware deploy, and rollback ordering. Full protocol: `protocols/multi-repo-protocol.md`.

## Detailed Protocols

Two-tier layout: auto-load is `rules/core.md` only (Iron Laws, code shape limits, worktree + commit protocol, pipeline phase order). Full protocol index (skill-loaded + orchestrator-only): `protocols/pipeline-overview.md` § Detailed Protocols.
