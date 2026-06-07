# Claude Code Orchestration Layer

> Rolling this harness out to engineers? See [ROLLOUT.md](ROLLOUT.md).

An autonomous software delivery system built on [Claude Code](https://claude.com/claude-code). Takes a feature request and delivers a reviewed, verified, tested, and deployed production-ready application — across web, mobile, voice, and device channels.

## What This Does

You describe what you want. The system:

1. **Classifies** the work and scores complexity
2. **Plans** the architecture (vertical slices, API contracts, data models)
3. **Scaffolds** infrastructure, APIs, databases, design systems — whatever the task needs
4. **Builds** via incremental TDD with mechanical code quality enforcement
5. **Reviews** with parallel code + security review (OWASP Top 10, SAST)
6. **Verifies** with contract tests, smoke tests, mutation testing, and multi-target E2E (mobile via Maestro, web E2E via Playwright/Cypress) — Tier 4 verification dispatched per `protocols/e2e-protocol.md`
7. **Tests** for coverage gaps and writes missing tests
8. **Accepts** against UX heuristics and acceptance criteria
9. **Ships** a PR with quality gate enforcement
10. **Deploys** with post-deploy verification and automatic rollback

**Modular monolith is the default.** New work lives as a bounded context inside the existing repo with an explicit port (in-process module). When a module needs stronger boundaries short of a separate service, `/harness:module-extraction` is the first-class, default extraction path. Splitting a module into its own repo is **advanced** and gated behind a named forcing function (see `protocols/module-boundaries-protocol.md`) — the Advanced service/multi-repo skills are invoked only when a forcing function applies.

11. **Learns** from every run — agents share discoveries in real-time, engineering context survives context compaction, and the system builds instincts that make future runs smarter

## Architecture

```
~/.claude/
  CLAUDE.md                    # Master playbook — philosophy, pipeline, skill directory
  settings.json                # Hook registration, permissions, env vars
  rules/                       # Auto-loaded tier (1 file only)
    core.md                    #   Iron Laws, code shape, pipeline phase order — always loaded
  protocols/                   # Full protocols + verdict catalog — loaded on demand
    agent-protocol.md          #   Worktree isolation, commit protocol, scratchpad
    pipeline-protocol.md       #   Pipeline phases, review loops, state management
    engineering-invariants.md  #   Code shape, naming, error handling, deps, testing, security
    atdd-procedure.md          #   Full ATDD cycle (skill-loaded by /harness:build-implementation)
    operational-protocol.md    #   Complexity Budget scoring, error recovery
    parallel-dispatch-protocol.md  # Parallel review/build dispatch
    multi-repo-protocol.md     #   Project manifests, multi-repo pipelines
    reflection-protocol.md     #   Post-pipeline reflection, auto-learn trigger
    autonomous-intelligence.md #   Scratchpad, session memory, continuous learning
    e2e-protocol.md            #   Multi-target E2E trigger matrix (mobile + web)
    verdict-catalog.md         #   Harness-audit verdict registry (on-demand audit source)
  orchestrator/                # Orchestrator-only detailed procedures (4 files)
  agents/                      # 19 specialized agent definitions
  skills/                      # 66 skills (procedural workflows)
  knowledge/                   # 41 domain pattern references
  hooks/                       # 78 enforcement scripts
    _lib/                      #   Shared helpers, including:
                               #     plan_dag_resolver.py — schema_version: 2 plan
                               #       parsing, validation, topological waves
                               #     plan_dag_validation.py — rule 1-7 enforcement
                               #     pipeline_state_paths_not_before.py — soak
                               #       placeholder activation by ISO date
  learning/                    # Continuous learning: observations + instincts
    {project-hash}/            #   Per-project observations.jsonl
    instincts/                 #   Learned patterns with confidence scores
  session-memory/              # Engineering context that survives compaction
    config/                    #   Template + update prompt
    {project-hash}/            #   Per-project session notes
  agent-memory/                # Per-role, per-project institutional knowledge
  metrics/                     # Session cost, governance, bug detection logs
  pipeline-state/              # Structured phase results + scratchpad
    {task-id}-scratchpad/      #   Cross-agent knowledge sharing within a pipeline
```

## Agent Team

| Agent | Role | Model | Worktree |
|-------|------|-------|----------|
| architect | System design, API contracts, slice decomposition | opus | No (read-only) |
| software-engineer | Backend implementation, TDD, business logic | opus | Yes |
| frontend-engineer | UI implementation, accessibility, design system | opus | Yes |
| database-engineer | Schema, migrations, query optimization | sonnet | Yes |
| infrastructure-engineer | Docker, CI/CD, IaC, deployment | opus | Yes |
| code-reviewer | SOLID/DRY audit, design review, extraction signals | opus | No (read-only) |
| security-engineer | OWASP Top 10, dependency scanning, auth review | opus | No (read-only) |
| qa-engineer | Test strategy, coverage gaps, integration/E2E tests | sonnet | Yes |
| product-reviewer | Acceptance criteria, UX heuristic evaluation | sonnet | No (read-only) |
| patch-critic | Final-Gate critic: test results + diff (NOT SOLID — code-reviewer owns that). Inspired by SWE-bench top scaffolds | sonnet | No (read-only) |

## Delivery Pipeline

```
Intake → Plan → Plan Validation → Scaffold → Build → Review → Verify → Test → Accept → Ship → Deploy
  │                   │               │          │        │        │        │       │       │
  │                   │               │          │        │        │        │       │       └─ /harness:deploy
  │                   │               │          │        │        │        │       └─ /harness:product-acceptance
  │                   │               │          │        │        │        └─ /harness:qa-test-strategy
  │                   │               │          │        │        └─ /harness:verify (contract + smoke + mutation)
  │                   │               │          │        └─ /harness:code-review + /harness:security-review (parallel)
  │                   │               │          └─ /harness:build-implementation (incremental TDD)
  │                   │               └─ /harness:api-scaffold, /harness:db-migration, /harness:infra-scaffold, ...
  │                   └─ Interactive: user approves. Autonomous: agent challengers.
  └─ /harness:intake (classify, score Complexity Budget, route)
```

## Autonomous Intelligence

Three systems make the pipeline self-improving:

### Pipeline Scratchpad
Agents share discoveries within a single pipeline run. Build agent finds a codebase quirk → reviewer receives it automatically. Stored in `pipeline-state/{task-id}-scratchpad/`, cleaned up after pipeline completion.

```
Build agent writes:     "warning: tests require DATABASE_URL set, not mocked"
Review agent receives:  ## Pipeline Scratchpad (findings from prior agents)
                        - [build/software-engineer] warning: tests require DATABASE_URL...
```

### Session Memory
Engineering-focused notes that survive context compaction. Not conversation history — **codebase knowledge**: what builds, what's fragile, what patterns work. Updated by a background agent at phase boundaries. Injected into every agent's prompt.

Sections: Active Work · Codebase Map · Build & Test · Critical Paths · Patterns · Discoveries · Agent Effectiveness

### Continuous Learning Loop
Every pipeline run captures structured observations. After 3+ pipelines, the system auto-invokes `/harness:learn` to extract instincts — atomic patterns with confidence scores (0.0–0.95) that modify agent behavior:

```
Pipeline Run → Observation → /harness:learn → Instinct created
  [0.72] "Read types.ts before editing services in this project"
  [0.85] "Always validate input at controller boundary"

Next pipeline → Instinct injected into agent prompt → Better build → Fewer review findings
```

Review findings classified as "preventable by build agent" become build-targeted instincts — a backward feedback loop from review to build.

## Skills (66)

### Pipeline & Orchestration
| Skill | Purpose |
|-------|---------|
| `/harness:intake` | Entry point — classify work, score complexity, route |
| `/harness:pipeline` | Autonomous conductor — drives all phases in sequence |
| `/harness:pipeline-resume` | Resume interrupted pipeline from state files |
| `/harness:batch-pipeline` | Lightweight pipeline for pre-planned batch work (readiness waves, bulk fixes) |
| `/harness:epic-breakdown` | Decompose epics into estimated stories |
| `/harness:estimation` | Complexity Budget scoring (5 dimensions) |
| `/harness:story-writing` | Write stories with Given/When/Then ACs |
| `/harness:spec-grounding` | Ground raw ACs against codebase evidence (EARS-tagged, Plan Stage 0) |
| `/harness:plan-self-validation` | Architect re-reads its own plan against a holes rubric (non-critical, low-budget) |
| `/harness:plan-cache-lookup` | Plan Stage 0 gate — check plan-template cache for a matching key |
| `/harness:plan-cache-rollout-gate` | Rollout gate deciding plan-cache shadow→on flip readiness |

### Build Phase
| Skill | Purpose |
|-------|---------|
| `/harness:build-implementation` | Incremental TDD with shape enforcement |
| `/harness:refactor` | Safe refactoring with characterization tests |
| `/harness:bug-fix` | Root cause analysis + regression test + fix |
| `/harness:module-extraction` | Default extraction path — bounded context → in-process module with an explicit port (same repo, no forcing function needed) |
| `/harness:tool-synthesis` | Author a one-shot scratch tool inside the worktree mid-task (custom search/AST/lint). Tool lives in `.claude-scratch-tools/`, cleaned up before merge |
| `/harness:tech-spike` | Time-boxed technical research |
| `/harness:best-of-n` | N-candidate parallel build with critic-selected winner (high-stakes variant) |
| `/harness:pdr-rtv` | Parallel-Diverse-Refine + Recursive-Tournament-Verification build variant |
| `/harness:property-based-test` | Tier 1.5 property-based tests for changed-line public functions (auto-invoked) |
| `/harness:sandbox-verify` | Run the test suite in a remote sandbox (E2B) and diff pass sets vs the worktree |
| `/harness:continuous-planning` | Advisory planning-agent that refines the plan during multi-slice Build |

**Continuous Planning**: On multi-slice Build runs (≥2 engineer slices), a `planning-agent` teammate (Sonnet 4.6) monitors the pipeline scratchpad and refines the active plan when findings contradict it. The planning-agent appends `## Plan Update` sections to the plan file and broadcasts updates to active build teammates. It is advisory only — Build engineers never block on it. Controlled by `should_spawn_planning_agent(slice_count, dispatch_mode, phase)` in `hooks/_lib/should_spawn_planning_agent.py`.

**Build Dispatch Variants**: precedence is `pdr_rtv > bestofn > dag > standard`. The standard path is single-engineer or per-slice parallel engineers. `bestofn` and `pdr_rtv` are tournament-style variants for high-stakes work (`critical OR budget>=7`). **Multi-Slice DAG Mode** (`schema_version: 2`) is the bounded-wave dispatcher: when the architect's plan declares `schema_version: 2` with explicit `depends-on` edges per slice, the orchestrator parses the plan via `hooks/_lib/plan_dag_resolver.py`, computes topological waves, and packs each wave with knapsack first-fit so wave width never exceeds `CLAUDE_BUILD_WAVE_MAX_PARALLEL` (mixed `bestofn`/standard slices share the cap). v1 plans (no `schema_version`) bypass the helper entirely — the legacy linear-slice dispatch path is unchanged during the DUAL_PATH soak. Full spec: `orchestrator/parallel-dispatch-details.md` § Multi-Slice DAG Mode (schema_version: 2).

### Scaffolding (Auto-Detected)
| Skill | Trigger |
|-------|---------|
| `/harness:project-setup` | New repo, no CLAUDE.md |
| `/harness:design-system-init` | Frontend project with no design tokens |
| `/harness:api-scaffold` | New API endpoints needed |
| `/harness:db-migration` | Schema changes needed |
| `/harness:infra-scaffold` | No Dockerfile/CI/CD |
| `/harness:observability-setup` | No logging/monitoring |
| `/voice-scaffold` | Voice skill needed (Alexa/Google/Twilio) |

### Advanced — Service / Multi-Repo (forcing function required)
Invoked only when a forcing function from `protocols/module-boundaries-protocol.md` applies. Routing is automatic — `/microservices-scaffold` gates on this at its Step 0 (returns `WRONG_SKILL` if no forcing function is named). For same-repo boundary work, use `/harness:module-extraction` instead.

| Skill | Trigger |
|-------|---------|
| `/service-extraction` | Extract module to own repo (FF required) — autonomous repo creation + migration |
| `/microservices-scaffold` | New microservice (FF required; Step 0 gate) |
| `/cross-service-pipeline` | Cross-repo contract + deploy coordination |
| `/bff-scaffold` | Channel-specific Backend for Frontend layer |

### Quality Gates
| Skill | Verdict |
|-------|---------|
| `/harness:code-review` | APPROVE / CHANGES_REQUESTED |
| `/harness:security-review` | APPROVE / CHANGES_REQUESTED |
| `/harness:verify` | VERIFIED / UNVERIFIED |
| `/harness:load-test` | PERFORMANCE_VERIFIED / FAILED |
| `/harness:qa-test-strategy` | COVERED / GAPS_FOUND |
| `/harness:spec-blind-validate` | Black-box behavioural tests from ACs + public API only (Final Gate) |
| `/harness:accessibility-check` | axe-core WCAG 2.1 AA gate on changed routes |
| `/harness:vlm-critic` | Per-route visual-diff verdict — VISUAL_DIFF_PASS / VISUAL_DIFF_FAIL |
| `/harness:product-acceptance` | APPROVED / REJECTED |
| `/harness:patch-critique` | PATCH_APPROVED / PATCH_REJECTED |
| `/harness:pr-creation` | PR_CREATED / PR_BLOCKED |
| `/harness:deploy` | DEPLOYED / ROLLED_BACK |
| `/harness:deployment-verification` | DEPLOYMENT_VERIFIED / AUTO_ROLLBACK |

### Operations & Tooling
| Skill | Purpose |
|-------|---------|
| `/harness:harness-config` | Modify hooks, settings.json (delegates to infra-engineer) |
| `/harness:harness-audit` | Health check of ~/.claude/ config (+ agnix integration) |
| `/harness:debug` | Persistent debug state for complex, multi-session bugs |
| `/harness:debug-trace` | Toggle prompt tracing on/off for the current session |
| `/harness:forensics` | Post-incident pipeline investigation |
| `/harness:cost-report` | Aggregate per-session tool-timings into a project-wide spend report |
| `/harness:cache-audit` | Project-wide prompt-cache read-ratio report |
| `/harness:cache-flip-gate` | Staged-flip gate for the cache read-ratio target (advisory) |
| `/harness:eval-model-effectiveness` | Recommend per-role model downgrades/upgrades from observations (advisory) |
| `/harness:workstream` | Manage isolated workstreams for parallel development |
| `/harness:polish` | Mechanical cleanup between Build and Review (Haiku, Budget >= 7) |
| `/harness:design-qc` | Visual QA screenshots for product acceptance (frontend changes) |
| `/harness:learn` | Extract instincts from observed behavior (auto-invoked after 3+ pipelines) |
| `/harness:greenfield-scaffold` | Full project bootstrap from scratch: discovery → running app |
| `/harness:creative-direction` | Pre-build design thinking: brand brief → fonts, palette, layout |
| `/harness:health-scan` | Proactive codebase health: security, deps, coverage, tech debt |
| `/harness:skill-builder` | Create new Claude Code skills with YAML frontmatter and structure |

### Reference Patterns
| Skill | Domain |
|-------|--------|
| `/harness:web-frontend-patterns` | React/Next.js, state, a11y, caching, security |
| `/harness:react-native-patterns` | Expo, NativeWind, Maestro E2E |

## Knowledge Library (41 files)

### Core Engineering
`database-patterns` `api-patterns` `testing-patterns` `integration-patterns` `auth-patterns` `env-management-patterns` `devx-patterns` `tech-stack-decision-matrix`

### Domain Patterns
`background-job-patterns` `notification-patterns` `file-upload-patterns` `multi-tenancy-patterns` `payment-patterns` `search-patterns` `realtime-patterns` `feature-flag-patterns` `i18n-patterns` `data-privacy-patterns` `state-machine-patterns` `caching-patterns`

### Architecture
`multi-repo-patterns` `service-mesh-patterns` `horizontal-scaling-patterns` `backup-dr-patterns` `omnichannel-patterns` `voice-patterns` `device-iot-patterns` `composition-patterns` `performance-design-patterns`

### UX/UI
`design-system-patterns` `ui-pattern-library` `ux-heuristics` `motion-design-patterns` `data-visualization-patterns` `content-design-patterns` `creative-direction-database` `next-gen-interaction-patterns`

## Mechanical Enforcement (Hooks)

| Hook | What It Enforces | Level |
|------|-----------------|-------|
| `code-shape-check.sh` | File length limit (configurable, default 50 lines) | Hard block |
| `orchestrator-discipline.sh` | Orchestrator cannot write source files | Hard block |
| `agent-skill-reminder.sh` | Worktree isolation, no Explore agents, reviewer diff required | Hard block |
| `tdd-guard.sh` | Test file must exist before editing source (warns on empty tests) | Block |
| `quality-gate.sh` | Tests, lint, audit, shape check before PR creation | Hard block |
| `sast-check.sh` | Semgrep/Bearer static analysis before PR | Hard block |
| `cc-check.sh` | Cyclomatic complexity (eslint/rubocop/radon/gocyclo) | Advisory |
| `function-body-check.sh` | Function length limit (configurable, default 8 lines) | Advisory |
| `hook-profile.sh` | Runtime profile gating (minimal/standard/strict) | Library |
| `loop-guard.sh` | Re-entrancy prevention (>10 calls in 60s = skip); also provides `check_stuck()` semantic advisory detector | Library |
| `stuck-guard.sh` | Stop-hook entrypoint: runs OpenHands five-pattern semantic stuck-detector (advisory, log-only) | Advisory |
| `config-protection.sh` | Blocks linter/formatter config modifications | Hard block |
| `governance-capture.sh` | Secret detection, policy violation, sensitive path logging | Advisory |
| `auto-bug-detect.sh` | Detects 12 bug-fix categories from edit diffs | Passive |
| `cost-tracker.sh` | Per-session metrics to `metrics/costs.jsonl` | Passive |
| `observation-capture.sh` | Tool-use observations for continuous learning | Passive |
| `context-warning.sh` | Context window usage warnings at 65%/75% thresholds | Advisory |
| `injection-scan.sh` | Prompt injection pattern detection on file writes | Advisory |
| `auto-pr.sh` | Suggests PR creation when branch is ahead | Advisory |
| `subagent-context.sh` | Writes agent role to temp file for observation tagging | Passive |
| `subagent-stop-trajectory.sh` | Records agent completion to pipeline trajectory | Passive |
| `session-start-bootstrap.sh` | Skill awareness, supervisor auto-start, pipeline/session detection | Bootstrap |
| `commit-checkpoint.sh` | Shape + type check on staged files before commit | Advisory |
| `intake-reminder.sh` | Nudges `/harness:intake` when implementation keywords detected | Advisory |
| `pipeline-analytics.sh` | Aggregates phase verdicts into `metrics/pipelines.jsonl` | Passive |
| `subagent-validation.sh` | Reminds orchestrator to validate worktree changes on agent stop | Advisory |
| `depth-guard.sh` | Resource Bounds: refuses subagent spawn beyond max recursion depth (3) | Hard block |
| `runtime-guard.sh` | Resource Bounds: shutdown directive when subagent (1800s) / teammate (3600s) wall-clock exceeded | Hard block |
| `rtk` | CLI token-optimization proxy (github.com/rtk-ai/rtk) on Bash PreToolUse (settings.json:812); compresses dev-tool output before it reaches the LLM. If absent, Claude Code proceeds without rtk interception — no hard failure. Installed by `setup.sh` via universal curl installer (curl \| sh), cargo fallback, or brew last-resort — defaults on for mac+linux; set `CLAUDE_REQUIRE_RTK=0` to skip, `CLAUDE_REQUIRE_RTK=1` to force. | External |
| `reflect-gate-acknowledgment.sh` | Orchestrator-invoked Reflect gate (protocols/reflection-protocol.md:137); enforces Iron Law 6 acknowledgment before pipeline close | Orchestrator-invoked |
| `reflect-token-emit.sh` | Orchestrator-invoked deviation token writer (protocols/reflection-protocol.md:139); emits structured deviation record at Reflect phase | Orchestrator-invoked |

See `protocols/agent-protocol.md > Resource Bounds` for caps, env overrides,
violation log schemas, and the Path-B disclosure on shutdown semantics.

## Omnichannel Support

| Channel | Knowledge | Scaffold | Patterns |
|---------|-----------|----------|----------|
| Web | `web-frontend-patterns` | `/harness:infra-scaffold` + `/harness:design-system-init` | React/Next.js, a11y, design system |
| Mobile | `react-native-patterns` | `/harness:infra-scaffold` | Expo, NativeWind, Maestro |
| Voice | `voice-patterns` | `/voice-scaffold` | Alexa, Google, Twilio, SSML |
| Device/IoT | `device-iot-patterns` | `/microservices-scaffold` | MQTT, OTA, device shadow |
| Cross-channel | `omnichannel-patterns` | `/bff-scaffold` | BFF, unified identity, session continuity |

## Multi-Language Support

Hooks, shape checks, and TDD guard support: **TypeScript**, **JavaScript**, **Ruby**, **Python**, **Go**, **Java**, **Swift**, **Kotlin**, **C#**

## Ticket Automation

Autonomous ticket processing — polls a tracker for ready tickets, runs the full pipeline, creates PRs, and updates the ticket. Supports Jira and GitHub Issues via a pluggable backend.

### Architecture

```
daemon.sh          → polling loop (one per repo)
  backend.sh       → dispatcher (loads jira.sh or github.sh based on config)
    jira.sh        → Jira REST API (transitions, comments, ADF)
    github.sh      → GitHub Issues via gh CLI (labels, comments)
  pool.sh          → worktree pool (3 slots, atomic claiming, stale lock recovery)
  process-ticket.sh → per-ticket: claim slot → run Claude pipeline → update tracker
  prompt-template.md → Claude prompt template (backend-neutral)
```

### Quick Start

```bash
# 1. Create per-repo config
cat > /path/to/your-repo/.claude/automation.env << 'EOF'
TICKET_BACKEND=github          # or "jira"

# --- GitHub Issues ---
GH_OWNER=your-org
GH_REPO=your-repo
GH_READY_LABEL=ready-for-dev   # issues with this label get picked up
GH_IN_PROGRESS_LABEL=in-progress
GH_DONE_LABEL=done
GH_BLOCKED_LABEL=blocked
GH_BOT_ACCOUNT=                # optional: assign issues to this account

# --- OR Jira ---
# JIRA_BASE_URL=https://your-org.atlassian.net
# JIRA_USER_EMAIL=bot@your-org.com
# JIRA_PROJECT_KEY=PROJ
# JIRA_READY_STATUS=Ready for Dev
# JIRA_IN_PROGRESS_STATUS=In Progress
# JIRA_DONE_STATUS=Done
# JIRA_FAILED_STATUS=Blocked
# JIRA_AC_CUSTOM_FIELD=         # custom field ID for acceptance criteria
# JIRA_BOT_ACCOUNT_ID=          # optional: for @mention
EOF

# 2. Set secrets (Jira only — GitHub uses gh auth)
export JIRA_API_TOKEN=your-token   # only if TICKET_BACKEND=jira

# 3. Start the daemon
REPO_PATH=/path/to/your-repo ~/.claude/automation/daemon.sh start

# 4. Check status
REPO_PATH=/path/to/your-repo ~/.claude/automation/daemon.sh status

# 5. Stop
REPO_PATH=/path/to/your-repo ~/.claude/automation/daemon.sh stop
```

### GitHub Issues Setup

1. **Auth**: Run `gh auth login` (the daemon uses your gh auth)
2. **Labels**: Create these labels in your repo (names are configurable):
   - `ready-for-dev` — issues ready for automation to pick up
   - `in-progress` — automation is working on it
   - `done` — automation completed, PR created
   - `blocked` — automation failed
3. **Workflow**: Add `ready-for-dev` label to an issue → daemon picks it up → creates PR → closes issue with link to PR
4. **AC format**: Put acceptance criteria under a `## Acceptance Criteria` heading in the issue body (optional, enhances quality)

### Jira Setup

1. **API Token**: Generate at [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. **Statuses**: Configure `JIRA_READY_STATUS` etc. to match your Jira workflow
3. **AC Field**: If you use a custom field for acceptance criteria, set `JIRA_AC_CUSTOM_FIELD` to the field ID (e.g., `customfield_10042`)
4. **Workflow**: Move ticket to "Ready for Dev" → daemon picks it up → creates PR → moves ticket to "Done"

### Config Hierarchy

```
~/.claude/automation/default.env     ← global defaults (all repos)
/path/to/repo/.claude/automation.env ← per-repo overrides
Environment variables                ← highest priority
```

### Daemon Options

| Variable | Default | Purpose |
|----------|---------|---------|
| `TICKET_BACKEND` | `jira` | `jira` or `github` |
| `POOL_SIZE` | `3` | Parallel worktree slots |
| `BUDGET_CAP` | `10.00` | Max USD per ticket |
| `POLL_INTERVAL` | `60` | Seconds between polls |
| `SHUTDOWN_TIMEOUT` | `300` | Graceful shutdown wait (seconds) |
| `MAX_TICKET_DURATION` | `3600` | Max seconds per ticket |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `CLAUDE_MODEL` | (default) | Override Claude model |
| `CLAUDE_EXTRA_FLAGS` | (none) | Extra flags passed to `claude` CLI |

### Multi-Repo (Autonomous)

A single supervisor manages all repo daemons automatically:

```bash
# Register repos (one-time, or auto-registered by /harness:project-setup)
~/.claude/automation/supervisor.sh add /path/to/api-service
~/.claude/automation/supervisor.sh add /path/to/web-frontend

# Start all registered daemons with one command
~/.claude/automation/supervisor.sh start

# Check everything
~/.claude/automation/supervisor.sh status

# View logs for a specific repo
~/.claude/automation/supervisor.sh logs api-service

# Stop everything
~/.claude/automation/supervisor.sh stop
```

The supervisor:
- **Auto-starts on session start** when repos are registered (via `session-start-bootstrap.sh`)
- Reads `repos.conf` (the single source of truth for registered repos)
- Starts a daemon per repo that has `.claude/automation.env`
- Health-checks every 30s, auto-restarts crashed daemons (max 3/hour)
- Hot-reloads `repos.conf` — add/remove repos without restarting
- Graceful shutdown cascades to all managed daemons

Repos are auto-registered in two ways:
- When `/harness:project-setup` creates an `automation.env`
- **On session start** — if the current repo has `.claude/automation.env`, it's added to `repos.conf` automatically and the supervisor is signalled to reload

## Configuration

### Hook Profiles
Set `CLAUDE_HOOK_PROFILE` in settings.json:
- `minimal` — blocking hooks only (quality-gate, orchestrator-discipline)
- `standard` — all hooks (default)
- `strict` — all hooks (reserved for future stricter checks)

### Shape Limits
Override per project in settings.json env or project `.claude/shape-overrides.json`:
- `CLAUDE_FILE_LINE_LIMIT` — file length (default: 50)
- `CLAUDE_FUNCTION_LINE_LIMIT` — function body length (default: 8)

### Auto-Extraction
Set `CLAUDE_AUTO_EXTRACT=true` in settings.json env to automatically extract modules when 3+ extraction signals are detected during code review.

## Getting Started

### Prerequisites

Install [Claude Code](https://claude.com/claude-code) and the following external tools:

```bash
# Required: AST-based bash command safety (runs in dontAsk mode)
brew tap ldayton/dippy && brew install dippy

# Recommended: Session observability (token attribution, compaction visualization)
brew install --cask claude-devtools

# Required: ML-based prompt injection detection (pure Rust, no native deps)
# Requires: Rust toolchain (curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh)
# Requires: HuggingFace token (free — huggingface.co/settings/tokens, READ scope)
# Requires: Accept model terms at huggingface.co/ProtectAI/deberta-v3-small-prompt-injection-v2
cargo install --git https://github.com/vaporif/parry --features candle --no-default-features
mkdir -p ~/.parry-guard ~/.config/parry-guard
echo "YOUR_HF_TOKEN" > ~/.parry-guard/.hf-token && chmod 600 ~/.parry-guard/.hf-token

# Recommended: Inter-agent communication for team phases
npm install -g hcom

# Optional: Configuration linting (385 validation rules)
npx agnix ~/.claude/

# Required: Professional security skills (Trail of Bits)
claude plugin marketplace add trailofbits/skills
for p in supply-chain-risk-auditor variant-analysis differential-review sharp-edges static-analysis; do
    claude plugin install "$p@trailofbits"
done
```

### Setup

1. Clone this repo to `~/.claude/`
2. Run the bootstrap script: `bash ~/.claude/setup.sh`
3. Start Claude Code in any project repo
4. Say what you want to build — the system handles the rest

The setup script is idempotent — safe to run multiple times. It checks what's already installed and only installs what's missing.

For new projects without a CLAUDE.md, the system automatically runs `/harness:project-setup` to detect your stack, configure commands, classify service architecture, and generate a design system.

### Linux / Claude Code Cloud

The Prerequisites block above is macOS-first (Homebrew). On Ubuntu/Debian/Fedora boxes — including a fresh Claude Code Cloud VM — use `scripts/install-tools.sh` instead: it detects the distro via `/etc/os-release`, installs `gh`, `jq`, `ripgrep`, `sqlite3`, `python3`, and the C/OpenSSL build toolchain via the native package manager, and bootstraps the shared virtualenv at `$HOME/.claude/.venv`.

```bash
bash "$HOME/.claude/scripts/install-tools.sh" --yes   # unattended install
bash "$HOME/.claude/setup.sh"                         # then run the bootstrap
```

`dippy` and `claude-devtools` are Homebrew-only and are skipped on Linux by default. Set `CLAUDE_REQUIRE_DIPPY=1` to opt in if you have a working install path on your Linux host. See the [`## Cloud portability`](#cloud-portability) section below for the full gating matrix.

### External Tool Reference

| Tool | Purpose | Install | Required? |
|------|---------|---------|-----------|
| [Dippy](https://github.com/ldayton/Dippy) | AST-based bash command safety | `brew install dippy` (macOS only; see `CLAUDE_REQUIRE_DIPPY` under Cloud portability) | Yes on macOS (dontAsk mode) |
| [claude-devtools](https://github.com/matt1398/claude-devtools) | Session observability | `brew install --cask claude-devtools` (macOS only; gated by `CLAUDE_REQUIRE_DIPPY`) | Recommended on macOS |
| [parry-guard](https://github.com/vaporif/parry) | ML injection detection (DeBERTa v3) | `cargo install --git ... --features candle` | Required (needs Rust + HF token) |
| [hcom](https://github.com/aannoo/hcom) | Inter-agent communication | `npm install -g hcom` | Recommended |
| [agnix](https://github.com/agent-sh/agnix) | Config linting | `npx agnix` (no install) | Optional |
| [Trail of Bits](https://github.com/trailofbits/skills) | Security analysis (5 plugins) | `claude plugin marketplace add` + install | Required |

## Cloud portability

The harness runs on macOS and Ubuntu 24.04 from the same tree. `scripts/install-tools.sh` detects the OS via `/etc/os-release`, installs `gh`, `jq`, `ripgrep`, `sqlite3`, `python3>=3.11`, and the C/OpenSSL build toolchain (`build-essential`, `libssl-dev`, `pkg-config`, `curl` on Debian/Ubuntu; `gcc`, `gcc-c++`, `openssl-devel` on Fedora) via the platform's package manager, and bootstraps a shared virtualenv at `$HOME/.claude/.venv`. The script is idempotent — re-runs only install what's missing — and accepts `--yes` for unattended provisioning on fresh VMs.

### `CLAUDE_REQUIRE_DIPPY` — Homebrew-only tool gating

`dippy` and `claude-devtools` are Homebrew-only. `setup.sh` gates them behind `CLAUDE_REQUIRE_DIPPY`:

| Value  | macOS   | Linux   | Use |
|--------|---------|---------|-----|
| unset  | install | skip    | Default — best-effort per-platform |
| `1`    | install | install | Opt-in on Linux (you have a working install path) |
| `0`    | skip    | skip    | Opt-out on macOS (e.g. minimal dev shell) |

Skipped installs emit a single `INFO:` line explaining why (platform + env var status).

## Session isolation

Two concurrent Claude Code sessions against the same repo would otherwise fight over HEAD. `scripts/new-session.sh` creates a git worktree per session so each gets an isolated HEAD without branch collisions; `scripts/list-sessions.sh` and `scripts/remove-session.sh` round out the lifecycle. When the harness itself (`$HOME/.claude`) is sessioned, stateful directories (`session-memory/`, `learning/`, `manifests/`, `db/memory.sqlite`) are symlinked from the canonical harness so memory, instincts, and the SQLite store stay single-writer across sessions. See `knowledge/session-isolation-patterns.md` for the full worktree-and-symlink model.

## Ubuntu clone-and-run

On a fresh Ubuntu 24.04 box:

```bash
git clone git@github.com:<org>/claude-harness.git "$HOME/.claude"
bash "$HOME/.claude/scripts/install-tools.sh" --yes
bash "$HOME/.claude/tests/shell/run.sh" --require-bats  # verifies install
```

## Web sandbox bootstrap

Claude Code on the web mounts the harness at `/home/user/.claude` but runs the session as `HOME=/root`, so `~/.claude` resolves to a near-empty runtime config dir and the harness silently degrades (1 hook, 1 skill registered instead of the full chain). `scripts/web-session-bootstrap.sh` makes a sandbox session use the source tree:

```bash
bash /home/user/.claude/scripts/web-session-bootstrap.sh
```

Place this in whatever pre-session env mechanism the sandbox provides (a SessionStart hook, container entrypoint, or shell init file). The session must restart afterwards — `CLAUDE_CONFIG_DIR` is read at session start, mid-session changes don't take effect.

What it does:

1. Exports `CLAUDE_CONFIG_DIR=/home/user/.claude` (the official Claude Code env var for relocating config).
2. Exports `CLAUDE_INSTINCTS_DIR`, `CLAUDE_AGENTS_DIR`, `CLAUDE_PIPELINE_STATE_DIR` so seed instincts, agent frontmatter, and in-progress pipeline state read from the source tree.
3. Symlinks shipped directories (`hooks/`, `skills/`, `rules/`, `agents/`, etc.) from the source tree into `$HOME/.claude/` as a belt-and-braces fallback for any code path that still hardcodes `$HOME/.claude/...`. Pure-runtime dirs (`metrics/`, `db/`, `sessions/`, `state/`, etc.) stay in `$HOME/.claude` where Claude Code's runtime puts them.
4. Verifies the layout (skills/hooks/agents counts) and fails fast if anything is missing.

Idempotent — safe to re-run. Refuses to clobber non-symlink files in `$HOME/.claude` (warns and skips).

Source-tree path is configurable via `CLAUDE_SRC=...`:

```bash
CLAUDE_SRC=/srv/claude-harness bash scripts/web-session-bootstrap.sh
```

After the bootstrap runs and the session restarts, verify in Claude Code: `/harness:intake "test"` should resolve (was "Unknown skill" before), and any Edit on a 51-line `.py` file should fire `code-shape-check.sh`.

The portable-config-dir convention this bootstrap depends on is documented in `protocols/agent-protocol.md` § Portable Config Dir.

## Internal Evaluation

The internal-eval harness runs a fixed suite of real Claude Code cases against the current harness, captures pass/fail + tier per case, compares to a stored baseline, and surfaces regressions before they ship. It is how the 80% adoption claim is produced and re-validated.

- Skill: `skills/internal-eval/` with sub-skills `capture/`, `run/`, `score/`, `validate/`
- Invoke: `bash skills/internal-eval/run/run-suite.sh --run-id <id> --model opus`
- Baselines: `eval/baselines/` (per-model, append-only — promotion gated by `/harness:internal-eval`)
- Privacy gate: requires `eval/.privacy-acked` marker OR `CLAUDE_EVAL_CAPTURE_ACKED=1` in the environment before any session capture runs
- **80% claim**: Measured on `eval/baselines/{latest}-opus-4-7.md`, not SWE-bench Verified. Methodology: strict binary pass (all ACs satisfied AND all pipeline gates green). Case count, contamination filter, and flakiness tiers documented in `skills/internal-eval/SKILL.md`.

## License

Private configuration. Not licensed for redistribution.
