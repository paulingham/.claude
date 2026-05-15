# Global Playbook

## Engineering Identity

- Lean agile: thin vertical slices delivering observable user value
- MVP mindset: smallest increment that validates the hypothesis
- Ship-learn-iterate: deploy independently, measure, adapt
- Modular monolith by default: in-process boundaries first; new services only when a forcing function (see `protocols/module-boundaries-protocol.md`) is explicitly named.
- Engineering discipline: TDD mandatory, SOLID, DRY, clean architecture
- Zero waste: every output line is a test result or a real error
- Proven correct: tests passing is necessary but not sufficient — verify it actually works

> **Default Opus model**: `claude-opus-4-7` (GA 2026-04-16). Pricing unchanged from 4.6 ($5/$25 per-M tokens) — no budget reforecast.

> **80% claim**: Measured on `eval/baselines/{latest}-opus-4-7.md`, not SWE-bench Verified. See `skills/internal-eval/SKILL.md` for methodology.

## Session Start (Automatic)

On every session start, before responding to the user's first message:

1. **Check for in-progress pipeline**: source `~/.claude/hooks/_lib/pipeline-state-paths.sh` and run `_psp_find_active_pipelines "$HOME/.claude/pipeline-state" 2>/dev/null | head -1` (the helper unions new-layout `pipeline-state/{task-id}/pipeline.md`, legacy `pipeline-state/{task-id}-pipeline.md`, and their workstream variants). If found, automatically invoke `/pipeline-resume`. Inform the user: "Resuming [pipeline name] from [phase]."
2. **Check for merged PRs with pending deploy**: if a pipeline state file shows Ship=completed + Deploy=pending, check `gh pr view --json state`. If merged, auto-invoke `/deploy`.

These checks are silent if nothing is found — don't report "no pipelines found."

## Project Readiness Check

Before starting ANY work in a repo, verify:
1. Check for `.claude/CLAUDE.md` or `CLAUDE.md` at project root
2. If missing: **automatically invoke `/project-setup`** before any other work. Do not ask — just run it. The user should never need to request project setup manually.
3. If present: read it and confirm no conflicts with global rules

| Layer | Controls | Example |
|-------|----------|---------|
| Global rules | How: engineering discipline | 8-line methods, TDD, SOLID |
| Global CLAUDE.md | Why: philosophy + pipeline | Lean agile, collaboration protocol |
| Project CLAUDE.md | What: project context | Rails 7, PostgreSQL, deploy via Heroku |

Global wins for quality standards; project wins for project-specific conventions.

## Quick Reference

### Thinking Defaults (Opus 4.7)

Every Agent spawn carries a `thinking` field — `effort` (`low|medium|high|xhigh`) and `display` (`omitted|text`). Defaults are applied automatically by the `pre-agent-thinking.sh` PreToolUse hook. The four primary build/design roles — `architect`, `software-engineer`, `frontend-engineer`, `infrastructure-engineer` — default to `effort=high` and promote to `xhigh` on a per-role gate (PR #124, narrow-xhigh-promotion 2026-05-14): `architect` on `critical=true OR budget>=6`, the other three on `critical=true OR budget>=7`. Same shape as `security-engineer`'s gate but with a disjunctive (OR) operator instead of conjunctive (AND). Review/critic/database roles (`code-reviewer`, `qa-engineer`, `product-reviewer`, `patch-critic`, `database-engineer`) default to `effort=high`. `planning-agent` stays `low`. `security-engineer` keeps its dual treatment — `high` by default, xhigh only when `critical=true AND budget>=7`. `fix-engineer` (Opus 4.7) is NOT on the gated-promotion list and inherits `high`. Best-of-N candidates promote when `budget>=7`. When the active pipeline is in a debug state (`{task_id}-debug.md` exists OR phase is `debugging`), `display=text` is forced. Override via `CLAUDE_THINKING_EFFORT` / `CLAUDE_THINKING_DISPLAY` env vars (reversibility preserved per-session). See `protocols/_proposals/2026-05-14-narrow-xhigh-promotion.md` for the cost rationale and `protocols/thinking-defaults.md` for the full precedence table.

**Postmortem note (May 2026):** the four gated promotions reflect the **Apr 23 2026** cost/quality data — promotion-on-trigger lift was concentrated in stakes-bearing build/design work — combined with the **Opus 4.7** adaptive-thinking floor change (manual `budget_tokens` rejected at the API layer; adaptive thinking allocates budget dynamically). The May 2026 unconditional-promotion policy over-corrected: empirical cost forensics (PR #124) showed routine mid-budget pipelines spent ~18% of weekly Max 20x output on xhigh spawns whose stakes did not warrant the floor. PR #124 restores the cost gate for sub-threshold spawns (`critical=false AND budget<N` → `high`) while preserving xhigh for stakes-bearing work (`critical=true OR budget>=N`).

**Note:** the hook is **advisory/log-only at v2.1.140** — the per-spawn `tool_input.thinking.effort` field is **not yet exposed** on the Agent tool input schema, so resolved effort/display values are written to `metrics/{session}/hook-injections.jsonl` but no spawn is blocked. `$CLAUDE_EFFORT` env var IS consumed (resolver rule 2a, source token `"claude-effort-env"`); `settings.autoMode.effortLevel` session key sets a global default. Will be promoted to enforcement via a single-file flip in `hooks/pre-agent-thinking.sh` once the per-spawn field is exposed in a future Claude Code release.

### Advisor-Mode Reviews (Opus 4.7)

Sonnet-executor + Opus-advisor pairing for `code-reviewer` and `security-engineer`; advisory at v2.1.140. Full mechanism, status, cost estimate, and operator controls: `protocols/advisor-mode.md`.

### Cost Discipline

May 8 2026 subagent-summary cache fix delivers ~3× `cache_creation` reduction when preambles are cache-stable. Full mechanism, drift surface, and measurement controls: `protocols/cost-discipline.md`.

### Per-Agent Tool Allowlists (Path B)

`tools:` frontmatter declares per-agent tool allowlist; `pre-agent-allowlist.sh` checks subset against `tool_input.allowed_tools` (advisory at v2.1.140). Full contract: `protocols/agent-tool-allowlists.md` and `protocols/agent-protocol.md` § Per-Agent Tool Scoping.

### Instinct Injection (Path B)

`instinct_categories:` frontmatter selects instincts per spawn; `instinct-injector.sh` resolves and logs (advisory at v2.1.140), orchestrator splices the `## Learned Patterns` block. Full contract: `protocols/autonomous-intelligence.md` § Instinct Injection and `orchestrator/agent-orchestration.md` § Instinct Injection.

### Agent Team

| Agent | Phase | Worktree | Default Model | Tunable |
|-------|-------|----------|---------------|---------|
| architect | Plan | No | opus | No |
| software-engineer | Build | Yes | sonnet | Yes |
| frontend-engineer | Build | Yes | sonnet | Yes |
| database-engineer | Build | Yes | sonnet | Yes |
| infrastructure-engineer | Build | Yes | opus | Yes |
| planning-agent | Build (advisory) | No | haiku | No |
| code-reviewer | Review | No | opus [1] | Yes |
| security-engineer | Review | No | opus | No |
| qa-engineer | Test | Yes | sonnet | Yes |
| product-reviewer | Accept | No | sonnet | Yes |
| patch-critic | Final Gate | No | sonnet | No |

> `[1]` Sonnet-solo via `model_conditional` when `complexity_budget.total < 6`; Opus default arm with Sonnet-executor + Opus-advisor pairing otherwise. See `agents/code-reviewer.md` frontmatter and `hooks/_lib/advisor_resolver.py::resolve_model_conditional`.

**Model self-tuning**: For tunable agents, the orchestrator checks `learning/instincts/` for model-efficiency instincts. If data shows Sonnet achieves identical outcomes for a phase/task-type, the model is downgraded. Architect and security-engineer are never downgraded (design and security decisions require highest capability). See `orchestrator/agent-orchestration.md` § Instinct Injection.

**Model-efficiency recommendations (advisory)**: `/eval-model-effectiveness` produces a recommendation report at `~/.claude/learning/{project-hash}/model-recommendations.md` by analysing observations + cost records per `(agent_role, task-classification)`. It is **advisory only** — it never modifies agent configs and never routes models at runtime. A human operator reviews the report and decides whether to edit an agent's `model:` frontmatter. `architect` and `security-engineer` are hard-locked out of recommendations.

### Dispatch (parallel subagents by default; teams opt-in)

Parallelizable phases dispatch as **parallel subagent calls in a single message** — equivalent fan-out, no idle teammates burning context. Teams (`TeamCreate`) are opt-in via `CLAUDE_VISIBLE_TEAMS=1` or `/pipeline --visible` for human-observable runs.

| Phase | Default Dispatch | Visible-mode (opt-in) |
|-------|------------------|------------------------|
| Plan | Subagent | Subagent |
| Build (single) | Subagent + worktree | Subagent + worktree |
| Build (multi) | Parallel subagents (1 message, N calls) | Team in tmux panes |
| Review | Parallel subagents (1 message, 2 calls) | Team in tmux panes |
| Final Gate | Parallel subagents (1 message, 4 calls) | Team in tmux panes |
| Ship / Deploy | Subagent | Subagent |

**Role selection**: Pick agents from the Agent Team table above. Every spawn prompt MUST include: "Read `~/.claude/agents/[role].md` for your full role definition, checklist, and output format."

**Re-review context**: re-dispatching the same `subagent_type` with the original finding + fix diff in the prompt preserves context. No long-lived teammate process is required for context continuity.

### How the System Works

Orchestrator coordinates; never writes code/tests. Flow, dispatch mechanisms (Skill/Subagent/Team), and orchestrator boundaries: `protocols/pipeline-overview.md` § How the System Works.

### Work-Class Routing (T0-T6)

`/intake` Step 1.5 (Fingerprint) classifies every user request into one of seven tiers based on what files change and how they change — not what the user said. Tier determines dispatch shape; Complexity Budget shapes intra-tier dispatch (multi-slice Build at T5, Best-of-N vs PDR-RTV at T6). T0-T3 are fast paths that bypass `/pipeline` entirely. T4-T6 enter `/pipeline` at progressively heavier dispatch. Full protocol: `protocols/work-class-routing.md`.

| Tier | Class | Dispatch target |
|---|---|---|
| **T0** | Question / Spike | Direct answer or `/tech-spike` |
| **T1** | Doc-only | Orchestrator direct edit (Iron Law 3 exception) |
| **T2** | Config-only | `/harness-config` |
| **T3** | Mechanical sweep | `/batch-pipeline` |
| **T4** | Bug fix | `/pipeline` (lightweight) |
| **T5** | Standard feature | `/pipeline` (standard) |
| **T6** | Critical / cross-cutting | `/pipeline` (heavy: Best-of-N or PDR-RTV) |

### Delivery Pipeline

1. **Plan** → Architect designs slices (subagent). Gate: chosen approach documented (full alternatives table only when critical/Budget ≥7/interactive).
2. **Plan Validation** → Interactive: user approves. Autonomous: heavy challengers (product-reviewer + software-engineer in parallel) when `critical OR Budget >= 7`; otherwise lightweight `/plan-self-validation` (architect re-reads its own plan against a structured rubric). Gate: PLAN_APPROVED.
3. **Build** → `/build-implementation` (subagent for single-slice, parallel subagents for multi-slice). Gate: tests green, cohesion met, AND `/code-review` APPROVE (code-review runs as the final step of Build, no longer a separate phase).
4. **Security Review** → `/security-review` (parallel subagent). Gate: APPROVE. Security is a separate phase from code-review — orthogonal concern.
5. **Final Gate** → parallel subagents running verify + test + accept + patch-critique:
   - `/verify` (contract + smoke + mutation). Gate: VERIFIED.
   - `/qa-test-strategy`. Gate: all ACs covered, no gaps.
   - `/product-acceptance`. Gate: APPROVED.
   - `/patch-critique` (test results + diff, NOT SOLID). Gate: PATCH_APPROVED.
6. **Ship** → `/pr-creation` (subagent). Gate: quality gate hook passes.
7. **Deploy** → `/deploy` + `/deployment-verification` (subagent). Gate: DEPLOYMENT_VERIFIED.
8. **Reflect** → Review pipeline execution, capture observation, auto-learn if gate met, update session memory, clean up scratchpad. Always runs.

No phase skipped. No gate bypassed. CHANGES_REQUESTED = go back.

### Autonomous Intelligence

Three systems make the pipeline self-improving (see `protocols/autonomous-intelligence.md`):

| System | Scope | Purpose |
|--------|-------|---------|
| **Pipeline Scratchpad** | Within one pipeline | Agents share discoveries in real-time. Build agent finds a quirk → reviewer knows immediately |
| **Session Memory** | Across compaction | Engineering context (build commands, fragile files, patterns) survives context compression |
| **Continuous Learning** | Across pipelines | Observations → instincts → better agents. Auto-invokes `/learn` when gate conditions met |

Every agent spawn includes: instincts + agent memory + session memory + scratchpad findings.

Tracing is off by default (`CLAUDE_ENABLE_TRACE=0` in `settings.json`). Enable per-session with `/debug-trace on` to capture rendered spawn prompts to `metrics/{session}/trace/`; turn it off again with `/debug-trace off`. See `protocols/autonomous-intelligence.md` § Prompt Tracing.

### Skill Directory

Full catalog of every user-invocable skill (active + forcing-function-deferred) with entry conditions and verdicts: `protocols/skill-directory.md`. Verdict semantics: `rules/verdict-catalog.md`.

### Definition of Done

A story is DONE when ALL are true:
- All ACs have passing tests (unit + integration + E2E where applicable)
- Code reviewer: APPROVED
- Security engineer: no CRITICAL/HIGH findings
- Verification report: VERIFIED
- QA engineer: no test gaps
- Product reviewer: APPROVED
- Quality gate hook passes
- PR merged to main
- Post-task reflection completed (rules/patterns updated if learnings identified)

### Multi-Repo Support

Projects spanning multiple repos are managed via **project manifests** (`~/.claude/manifests/{project}.md`). Everything is automatic — no manual commands needed.

- **Detection**: Intake auto-detects multi-repo signals (service extraction, cross-repo features, Service Context in CLAUDE.md)
- **Manifest**: Auto-created when multi-repo work detected. Tracks repos, dependencies, GitHub config, deploy order
- **GitHub**: Repo creation, branch protection, environments — all config-driven from manifest
- **PRs**: Linked across repos with dependency ordering. Merge order enforced (providers first)
- **Deploy**: Dependency-aware ordering. Health checks cascade. Rollback in reverse order
- **Agents**: One agent per repo, worktree isolation per-repo. Parallel when independent

See `protocols/multi-repo-protocol.md` for full details.

## Detailed Protocols

Two-tier layout: auto-load is `rules/core.md` only (Iron Laws, code shape limits, worktree + commit protocol, pipeline phase order). Full protocol index (skill-loaded + orchestrator-only): `protocols/pipeline-overview.md` § Detailed Protocols.
