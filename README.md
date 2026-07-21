# Claude Code Orchestration Layer

An autonomous software-delivery system built on [Claude Code](https://claude.com/claude-code).
You describe a feature; it plans, builds, reviews, tests, ships, and deploys it — then
learns from the run so the next one goes better.

> **Rolling this out to a team?** See [ROLLOUT.md](ROLLOUT.md) for plugin install and enterprise config.

---

## The one-paragraph mental model

A single **orchestrator** drives the work but never writes code itself. It hands each
phase to a **specialised agent** (architect, software-engineer, reviewer, …), each running
in an isolated git worktree. Every phase ends in a **verdict** — `APPROVED`,
`CHANGES_REQUESTED`, etc. — and a failing verdict sends the work back, not forward. A set of
**hooks** mechanically enforce the rules (no code without a failing test, orchestrator can't
edit source, HEAD stays on `main`). Everything the system learns — what's fragile, what
patterns work — is captured and fed back into future runs.

That's the whole thing. The rest of this README expands those five ideas.

---

## First, the request is sized: three gears

Not every request deserves the full pipeline. Before anything else, each request is
classified into one of **three gears** — this is the routing decision that determines how
much machinery runs.

| Gear | For | What runs |
|------|-----|-----------|
| **Pair** | Questions, doc tweaks, config changes, trivial one-file edits | A direct answer or a single lightweight change — no heavy pipeline, no gates you don't need. Interactive: the assistant can ask you a question. |
| **Build** | A bug fix or a standard feature | The full pipeline at normal weight — plan, build, review, gate, ship. |
| **Pipeline** | Critical or cross-cutting work | The full pipeline at maximum rigour — plan validation, tournament-style build variants, the works. |

The gear is chosen automatically from the shape of your request; you can override it with a
single word ("just pair on this", "run the full pipeline"). **Pair is the default** — most
requests don't need the heavy machinery, and the system only reaches for it when the work
warrants it. Full routing rules: [`protocols/work-class-routing.md`](protocols/work-class-routing.md).

Everything below describes what **Build** and **Pipeline** gears run. Pair skips most of it.

---

## The pipeline

In Build and Pipeline gears, one request flows through these phases. No phase is skipped; no
gate is bypassed.

```
Intake ─▶ Plan ─▶ Build ─▶ Review ─▶ Final Gate ─▶ Ship ─▶ Deploy ─▶ Reflect
   │        │       │         │           │           │        │         │
classify  design  TDD     code +      verify +     open    deploy +   capture
 + route  slices  loop   security      test +       PR     rollback  learnings
                         (parallel)   accept
```

| Phase | What happens | Who | Verdict |
|-------|--------------|-----|---------|
| **Intake** | Classify the request, score its complexity, choose the route | orchestrator | — |
| **Plan** | Design vertical slices, API contracts, data models; validate the plan | architect | `PLAN_APPROVED` |
| **Build** | Incremental TDD, then a self-review pass | software / frontend / db engineers | — |
| **Review** | SOLID/DRY audit **and** OWASP security audit, run in parallel | code-reviewer + security-engineer | `APPROVE` / `CHANGES_REQUESTED` |
| **Final Gate** | Contract/smoke/mutation verify, coverage check, acceptance, patch critique | qa / product-reviewer / patch-critic | `APPROVED` / `REJECTED` |
| **Ship** | Open a PR behind a quality gate | orchestrator | `PR_CREATED` / `PR_BLOCKED` |
| **Deploy** | Deploy, verify, auto-rollback on failure | orchestrator | `DEPLOYED` / `ROLLED_BACK` |
| **Reflect** | Record an observation for the learning loop | orchestrator | — |

Which of these phases run — and how heavily — is set by the gear (above). Full phase
contract: [`rules/core.md`](rules/core.md) and
[`protocols/pipeline-protocol.md`](protocols/pipeline-protocol.md).

---

## The four iron laws

These are absolute — enforced by hooks, not by good intentions.

1. **No production code without a failing test first.** (TDD is mandatory.)
2. **No "done" without fresh verification.** Stale test output from earlier doesn't count — re-run.
3. **The orchestrator never writes source code.** It coordinates agents; only agents edit code.
4. **`main` stays on `main`.** Every code change happens in an isolated worktree, never on the repo's HEAD.

Full set and rationale: [`rules/core.md`](rules/core.md).

---

## The agents

The orchestrator delegates each phase to a specialist. Write-capable agents work in an
isolated worktree and commit before finishing; read-only agents review a diff.

| Agent | Job | Worktree |
|-------|-----|----------|
| `architect` | System design, API contracts, slice decomposition | read-only |
| `software-engineer` | Backend implementation, business logic | yes |
| `frontend-engineer` | UI, accessibility, design system | yes |
| `database-engineer` | Schema, migrations, query optimisation | yes |
| `infrastructure-engineer` | Docker, CI/CD, IaC, deploy config | yes |
| `qa-engineer` | Test strategy, coverage gaps, integration/E2E tests | yes |
| `code-reviewer` | SOLID/DRY and design review | read-only |
| `security-engineer` | OWASP Top 10, dependency + secrets scanning | read-only |
| `product-reviewer` | Acceptance criteria, UX evaluation | read-only |
| `patch-critic` | Final-Gate check of the diff against test results | read-only |

There are 19 agents in total (the rest are recon/validation helpers). Each is defined in
[`agents/`](agents/) with its full checklist and the model it runs on. The authoritative
model/worktree table lives in [`CLAUDE.md`](CLAUDE.md) § Agent Team.

---

## What the system learns

Three feedback loops, at three different timescales, make the pipeline self-improving.

| Loop | Scope | What it does |
|------|-------|--------------|
| **Scratchpad** | One pipeline run | Agents share discoveries live — a build agent's "tests need `DATABASE_URL`" reaches the reviewer automatically. |
| **Session memory** | Across context compaction | Codebase knowledge (what builds, what's fragile, which patterns work) survives the context window shrinking. |
| **Continuous learning** | Across pipelines | Every run produces an observation. Recurring patterns become **instincts** — confidence-scored rules injected into future agent prompts. |

A review finding tagged "the build agent should have caught this" becomes a build-targeted
instinct — a backward feedback loop from review into build. Details:
[`protocols/autonomous-intelligence.md`](protocols/autonomous-intelligence.md).

---

## What's in the repo

```
~/.claude/
  CLAUDE.md          The master playbook — philosophy, pipeline, agent + skill directory
  rules/core.md      Always-loaded invariants: iron laws, code-shape rules, phase order
  settings.json      Hook registration, permissions, env vars

  agents/            # 19 specialized agent definitions (role, checklist, model)
  skills/            # 74 skills — the procedural workflows the orchestrator invokes
  hooks/             # 89 enforcement scripts (the mechanical guardrails)
  protocols/         # 19 deep-dive protocol docs, loaded on demand
  orchestrator/      # orchestrator-only dispatch procedures
  knowledge/         # 42 domain pattern references (auth, caching, payments, …)

  learning/          Observations + learned instincts (per project)
  session-memory/    Engineering context that survives compaction
  metrics/           Cost, governance, and bug-detection logs
  pipeline-state/    Live phase results + the per-run scratchpad
```

The split that matters: **`rules/core.md` is loaded into every agent on every spawn**
(it's the minimum every agent must know); **`protocols/` is loaded only when a phase needs
it.** That keeps the always-on context small.

---

## Getting Started

```bash
# 1. Clone into your Claude config dir
git clone <repo> ~/.claude

# 2. Run the idempotent bootstrap (installs missing tools, sets up the venv)
bash ~/.claude/setup.sh        # macOS
# On Linux / Claude Code Cloud, provision tools first:
bash ~/.claude/scripts/install-tools.sh --yes && bash ~/.claude/setup.sh

# 3. Start Claude Code in any repo and describe what you want to build.
```

`setup.sh` is safe to re-run — it only installs what's missing. In a new repo with no
`CLAUDE.md`, the system auto-runs `/harness:project-setup` to detect your stack and
conventions before doing anything else.

External tools (a few required, most optional) and the full platform gating matrix are
listed in [`docs/SETUP.md`](docs/SETUP.md).

### Linux / Claude Code Cloud

The macOS bootstrap is Homebrew-first. On Ubuntu/Debian/Fedora — including a fresh Claude
Code Cloud VM — run `scripts/install-tools.sh` first: it detects the distro, installs the
toolchain via the native package manager, and bootstraps the shared venv. Homebrew-only
tools (`dippy`, `claude-devtools`) are skipped on Linux unless you opt in with
`CLAUDE_REQUIRE_DIPPY=1`.

```bash
bash ~/.claude/scripts/install-tools.sh --yes && bash ~/.claude/setup.sh
```

---

## Day-to-day usage

You rarely call skills by hand — the orchestrator routes for you. But the entry points are:

- **`/harness:intake "<what you want>"`** — the front door. Classifies and routes everything.
- **`/harness:pipeline`** — drive a request through every phase autonomously.
- **`/harness:pipeline-resume`** — pick an interrupted run back up from its state files.

The full skill catalogue (74 skills, grouped by phase) lives in
[`protocols/skill-directory.md`](protocols/skill-directory.md). Quality limits and behaviour
are tunable via env vars in `settings.json` — file/function size limits, hook profiles,
auto-extraction — documented in [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).

### Build dispatch variants

For high-stakes work, Build can fan out instead of running a single engineer. Precedence is
`pdr_rtv > dag > bestofn > standard`:

- **standard** — one engineer, or one per slice.
- **bestofn** / **pdr_rtv** — tournament-style: generate N candidate patches, pick the best.
- **Multi-Slice DAG Mode** (`schema_version: 2`) — when the architect's plan declares
  `depends-on` edges, the orchestrator parses it with `hooks/_lib/plan_dag_resolver.py`,
  computes topological waves, and runs each wave in parallel within a width cap.

Canonical spec: [`orchestrator/parallel-dispatch-details.md`](orchestrator/parallel-dispatch-details.md).

### Verification & E2E

Beyond unit tests, the Final Gate runs contract, smoke, and mutation verification.
End-to-end coverage — web E2E (Playwright/Cypress) and mobile E2E (Maestro) — is dispatched
per the trigger matrix in [`protocols/e2e-protocol.md`](protocols/e2e-protocol.md), and
Deploy runs post-deploy verification with automatic rollback.

---

## Configuration

Behaviour is tunable via `settings.json` at the user level. Settings files are resolved in precedence order: managed (org policy) → user → project. Feature toggles belong at the **user layer** so each developer can adjust them without touching org policy.

### Settings file locations

| Platform | Path |
|----------|------|
| macOS / Linux | `~/.claude/settings.json` |
| Windows | `%USERPROFILE%\.claude\settings.json` |

Set `CLAUDE_CONFIG_DIR` to override the default location on any platform.

### Developer-facing toggles

All values are **case-sensitive**. Enum values such as `shadow` must be lowercase exactly (e.g. `shadow` not `Shadow`); binary toggles require `0` or `1` exactly.

| Setting | What it does | Values | Default | Layer |
|---------|-------------|--------|---------|-------|
| `CLAUDE_PIPELINE_MODE` | Pipeline execution mode | `autonomous` \| `interactive` | `autonomous` | user |
| `CLAUDE_ENABLE_TRACE` | Enable prompt-tracing for agent spawns | `0` \| `1` | `0` | user |
| `CLAUDE_DISABLE_SANDBOX_VERIFY` | Disable Final-Gate sandbox-verify engineer | `0` \| `1` | `0` | user |
| `CLAUDE_DISABLE_VLM_CRITIC` | Disable Final-Gate visual-diff critic | `0` \| `1` | `0` | user |
| `CLAUDE_DISABLE_SWE_PRUNER` | Disable SWE-bench candidate pruner | `0` \| `1` | `0` | user |
| `CLAUDE_DISABLE_INSTINCT_INJECTION` | Disable instinct injection into agent prompts | `0` \| `1` | `0` | user |
| `CLAUDE_DISABLE_WORKTREE_REAPER` | Disable the worktree reaper (stale-worktree cleanup) | `0` \| `1` | `0` | user |
| `CLAUDE_VISIBLE_TEAMS` | Use visible team dispatch (tmux panes) instead of parallel subagents | `0` \| `1` | `0` | user |
| `CLAUDE_PLAN_CACHE_MODE` | Plan-cache mode | `off` \| `shadow` \| `on` | `shadow` | user |

### Enforcement flow

The intake → pipeline enforcement flow is **always-on and not configurable** — there is no workflow off-switch. An emergency recovery escape exists for situations where the harness itself has become inoperable, but it is intentionally undocumented as a routine setting and should not be used in normal operation.

---

## Skills (74)

Skills are the procedural workflows the orchestrator invokes per phase — `/harness:intake`,
`/harness:build-implementation`, `/harness:code-review`, `/harness:patch-critique`, and the
rest. The full catalogue, grouped by phase with entry conditions and verdicts, lives in
[`protocols/skill-directory.md`](protocols/skill-directory.md).

## Mechanical Enforcement (Hooks)

The hooks are the harness's guardrails — they enforce the iron laws so the rules don't rely
on the model remembering them. They run at three levels:

- **Hard block** — refuses the action (orchestrator editing source, a PR that fails the
  quality gate, a file over the line-length safety net).
- **Advisory** — surfaces a warning but lets the action through (cyclomatic complexity,
  function length, context-window usage).
- **Passive** — records data for cost, learning, and governance without affecting the action.

A separate set enforces **Resource Bounds** — recursion-depth and wall-clock caps on
subagent spawns. The full hook registry lives in [`settings.json`](settings.json); per-hook
behaviour, levels, env overrides, and the Resource Bounds caps are documented in
[`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) and
[`protocols/agent-protocol.md`](protocols/agent-protocol.md) § Resource Bounds.

One hook is external tooling: **rtk** (a token-optimisation proxy) is installed best-effort by `setup.sh`.
It compresses dev-tool output before it reaches the model and defaults on for
mac+linux; set `CLAUDE_REQUIRE_RTK=0` to skip it or `CLAUDE_REQUIRE_RTK=1` to force it. If
absent, the harness proceeds without it — no hard failure.

Two hooks support the Reflect phase deviation-acknowledgment loop. **reflect-token-emit**
writes named-deviation tokens during Build and Review phases whenever an agent records a
deviation from protocol; the tokens persist in pipeline state. **reflect-gate-acknowledgment**
is the Reflect-phase gate that reads those tokens and exits nonzero if any deviation token
remains unacknowledged, blocking the pipeline from completing until each deviation is
explicitly addressed. Both hooks are skill-invoked (not event-registered) per
[`protocols/reflection-protocol.md`](protocols/reflection-protocol.md).

One SubagentStop hook gathers mutation-testing soak data: **mutation-score-gate** fires when
a `software-engineer` or `fix-engineer` subagent completes, recording changed-files context and
mutation-tool availability to `metrics/$SESSION_ID/mutation-score.jsonl`. It is advisory-log
only (exit 0 always). The soak converges once >=10 sessions reach a median changed-line score
>=70%; use `skills/mutation-score-report/SKILL.md` to view convergence progress.

## Omnichannel Support

The same pipeline delivers across channels: **web** (React/Next.js), **mobile** (Expo,
NativeWind, Maestro), **voice** (Alexa, Google, Twilio), and **device/IoT** (MQTT, OTA).
Cross-channel concerns (BFF, unified identity) are covered in
[`knowledge/omnichannel-patterns.md`](knowledge/omnichannel-patterns.md).

## Ticket automation

A daemon polls Jira or GitHub Issues for ready tickets, runs the full pipeline per ticket,
opens a PR, and updates the tracker — managed across repos by a supervisor. Full setup,
config, and daemon options: [`docs/TICKET-AUTOMATION.md`](docs/TICKET-AUTOMATION.md).

## Cloud portability

The harness runs on macOS and Ubuntu 24.04 from the same tree.
[`scripts/install-tools.sh`](scripts/install-tools.sh) detects the OS via `/etc/os-release`,
installs the toolchain via the platform package manager, and bootstraps a shared venv. It's
idempotent and accepts `--yes` for unattended provisioning. The `CLAUDE_REQUIRE_DIPPY`
gating matrix for Homebrew-only tools is in [`docs/SETUP.md`](docs/SETUP.md).

## Session isolation

Two concurrent Claude Code sessions against one repo would fight over HEAD.
[`scripts/new-session.sh`](scripts/new-session.sh) creates a git worktree per session so each
gets an isolated HEAD; `list-sessions.sh` and `remove-session.sh` round out the lifecycle.
When the harness itself is sessioned, stateful dirs are symlinked from the canonical harness
so memory and instincts stay single-writer. Full model:
[`knowledge/session-isolation-patterns.md`](knowledge/session-isolation-patterns.md).

## Ubuntu clone-and-run

On a fresh Ubuntu 24.04 box:

```bash
git clone git@github.com:<org>/claude-harness.git "$HOME/.claude"
bash "$HOME/.claude/scripts/install-tools.sh" --yes
bash "$HOME/.claude/tests/shell/run.sh" --require-bats
```

---

## License

Private configuration. Not licensed for redistribution.
