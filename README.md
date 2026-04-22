# Claude Code Orchestration Layer

An autonomous software delivery system built on [Claude Code](https://claude.com/claude-code). Takes a feature request and delivers a reviewed, verified, tested, and deployed production-ready application — across web, mobile, voice, and device channels.

## What This Does

You describe what you want. The system:

1. **Classifies** the work and scores complexity
2. **Plans** the architecture (vertical slices, API contracts, data models)
3. **Scaffolds** infrastructure, APIs, databases, design systems — whatever the task needs
4. **Builds** via incremental TDD with mechanical code quality enforcement
5. **Reviews** with parallel code + security review (OWASP Top 10, SAST)
6. **Verifies** with contract tests, smoke tests, and mutation testing
7. **Tests** for coverage gaps and writes missing tests
8. **Accepts** against UX heuristics and acceptance criteria
9. **Ships** a PR with quality gate enforcement
10. **Deploys** with post-deploy verification and automatic rollback

**Modular monolith is the default.** New work lives as a bounded context inside the existing repo with an explicit port (in-process module). When a module needs stronger boundaries short of a separate service, `/module-extraction` is the first-class, default extraction path. Splitting a module into its own repo is **advanced** and gated behind a named forcing function (see `rules/module-boundaries-protocol.md`) — the Advanced service/multi-repo skills are invoked only when a forcing function applies.

11. **Learns** from every run — agents share discoveries in real-time, engineering context survives context compaction, and the system builds instincts that make future runs smarter

## Architecture

```
~/.claude/
  CLAUDE.md                    # Master playbook — philosophy, pipeline, skill directory
  settings.json                # Hook registration, permissions, env vars
  rules/                       # Auto-loaded protocols (9 files)
    agent-protocol.md          #   Worktree isolation, commit protocol, scratchpad
    pipeline-protocol.md       #   Pipeline phases, review loops, state management
    engineering-protocol.md    #   Code shape, TDD, testing standards, security baseline
    operational-protocol.md    #   Complexity Budget scoring, error recovery
    parallel-dispatch-protocol.md  # Parallel review/build dispatch
    multi-repo-protocol.md     #   Project manifests, multi-repo pipelines
    reflection-protocol.md     #   Post-pipeline reflection, auto-learn trigger
    autonomous-intelligence.md #   Scratchpad, session memory, continuous learning
    e2e-protocol.md            #   Maestro E2E trigger matrix
  orchestrator/                # Orchestrator-only detailed procedures (4 files)
  agents/                      # 9 specialized agent definitions
  skills/                      # 44 skills (procedural workflows)
  knowledge/                   # 37 domain pattern references
  hooks/                       # 25 enforcement scripts
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

## Delivery Pipeline

```
Intake → Plan → Plan Validation → Scaffold → Build → Review → Verify → Test → Accept → Ship → Deploy
  │                   │               │          │        │        │        │       │       │
  │                   │               │          │        │        │        │       │       └─ /deploy
  │                   │               │          │        │        │        │       └─ /product-acceptance
  │                   │               │          │        │        │        └─ /qa-test-strategy
  │                   │               │          │        │        └─ /verify (contract + smoke + mutation)
  │                   │               │          │        └─ /code-review + /security-review (parallel)
  │                   │               │          └─ /build-implementation (incremental TDD)
  │                   │               └─ /api-scaffold, /db-migration, /infra-scaffold, ...
  │                   └─ Interactive: user approves. Autonomous: agent challengers.
  └─ /intake (classify, score Complexity Budget, route)
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
Every pipeline run captures structured observations. After 3+ pipelines, the system auto-invokes `/learn` to extract instincts — atomic patterns with confidence scores (0.0–0.95) that modify agent behavior:

```
Pipeline Run → Observation → /learn → Instinct created
  [0.72] "Read types.ts before editing services in this project"
  [0.85] "Always validate input at controller boundary"

Next pipeline → Instinct injected into agent prompt → Better build → Fewer review findings
```

Review findings classified as "preventable by build agent" become build-targeted instincts — a backward feedback loop from review to build.

## Skills (44)

### Pipeline & Orchestration
| Skill | Purpose |
|-------|---------|
| `/intake` | Entry point — classify work, score complexity, route |
| `/pipeline` | Autonomous conductor — drives all phases in sequence |
| `/pipeline-resume` | Resume interrupted pipeline from state files |
| `/epic-breakdown` | Decompose epics into estimated stories |
| `/estimation` | Complexity Budget scoring (5 dimensions) |
| `/story-writing` | Write stories with Given/When/Then ACs |

### Build Phase
| Skill | Purpose |
|-------|---------|
| `/build-implementation` | Incremental TDD with shape enforcement |
| `/refactor` | Safe refactoring with characterization tests |
| `/bug-fix` | Root cause analysis + regression test + fix |
| `/module-extraction` | Default extraction path — bounded context → in-process module with an explicit port (same repo, no forcing function needed) |
| `/tech-spike` | Time-boxed technical research |

### Scaffolding (Auto-Detected)
| Skill | Trigger |
|-------|---------|
| `/project-setup` | New repo, no CLAUDE.md |
| `/design-system-init` | Frontend project with no design tokens |
| `/api-scaffold` | New API endpoints needed |
| `/db-migration` | Schema changes needed |
| `/infra-scaffold` | No Dockerfile/CI/CD |
| `/observability-setup` | No logging/monitoring |
| `/voice-scaffold` | Voice skill needed (Alexa/Google/Twilio) |

### Advanced — Service / Multi-Repo (forcing function required)
Invoked only when a forcing function from `rules/module-boundaries-protocol.md` applies. Routing is automatic — `/microservices-scaffold` gates on this at its Step 0 (returns `WRONG_SKILL` if no forcing function is named). For same-repo boundary work, use `/module-extraction` instead.

| Skill | Trigger |
|-------|---------|
| `/service-extraction` | Extract module to own repo (FF required) — autonomous repo creation + migration |
| `/microservices-scaffold` | New microservice (FF required; Step 0 gate) |
| `/cross-service-pipeline` | Cross-repo contract + deploy coordination |
| `/bff-scaffold` | Channel-specific Backend for Frontend layer |

### Quality Gates
| Skill | Verdict |
|-------|---------|
| `/code-review` | APPROVE / CHANGES_REQUESTED |
| `/security-review` | APPROVE / CHANGES_REQUESTED |
| `/verify` | VERIFIED / UNVERIFIED |
| `/load-test` | PERFORMANCE_VERIFIED / FAILED |
| `/qa-test-strategy` | COVERED / GAPS_FOUND |
| `/product-acceptance` | APPROVED / REJECTED |
| `/pr-creation` | PR_CREATED / PR_BLOCKED |
| `/deploy` | DEPLOYED / ROLLED_BACK |
| `/deployment-verification` | DEPLOYMENT_VERIFIED / AUTO_ROLLBACK |

### Operations & Tooling
| Skill | Purpose |
|-------|---------|
| `/harness-config` | Modify hooks, settings.json (delegates to infra-engineer) |
| `/harness-audit` | Health check of ~/.claude/ config (+ agnix integration) |
| `/debug` | Persistent debug state for complex, multi-session bugs |
| `/forensics` | Post-incident pipeline investigation |
| `/workstream` | Manage isolated workstreams for parallel development |
| `/polish` | Mechanical cleanup between Build and Review (Haiku, Budget >= 7) |
| `/design-qc` | Visual QA screenshots for product acceptance (frontend changes) |
| `/learn` | Extract instincts from observed behavior (auto-invoked after 3+ pipelines) |
| `/greenfield-scaffold` | Full project bootstrap from scratch: discovery → running app |
| `/creative-direction` | Pre-build design thinking: brand brief → fonts, palette, layout |
| `/health-scan` | Proactive codebase health: security, deps, coverage, tech debt |
| `/skill-builder` | Create new Claude Code skills with YAML frontmatter and structure |

### Reference Patterns
| Skill | Domain |
|-------|--------|
| `/web-frontend-patterns` | React/Next.js, state, a11y, caching, security |
| `/react-native-patterns` | Expo, NativeWind, Maestro E2E |

## Knowledge Library (37 files)

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
| `function-body-check.sh` | Function length limit (configurable, default 5 lines) | Advisory |
| `hook-profile.sh` | Runtime profile gating (minimal/standard/strict) | Library |
| `loop-guard.sh` | Re-entrancy prevention (>10 calls in 60s = skip) | Library |
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
| `intake-reminder.sh` | Nudges `/intake` when implementation keywords detected | Advisory |
| `pipeline-analytics.sh` | Aggregates phase verdicts into `metrics/pipelines.jsonl` | Passive |
| `subagent-validation.sh` | Reminds orchestrator to validate worktree changes on agent stop | Advisory |

## Omnichannel Support

| Channel | Knowledge | Scaffold | Patterns |
|---------|-----------|----------|----------|
| Web | `web-frontend-patterns` | `/infra-scaffold` + `/design-system-init` | React/Next.js, a11y, design system |
| Mobile | `react-native-patterns` | `/infra-scaffold` | Expo, NativeWind, Maestro |
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
# Register repos (one-time, or auto-registered by /project-setup)
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
- When `/project-setup` creates an `automation.env`
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
- `CLAUDE_FUNCTION_LINE_LIMIT` — function body length (default: 5)

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

For new projects without a CLAUDE.md, the system automatically runs `/project-setup` to detect your stack, configure commands, classify service architecture, and generate a design system.

### External Tool Reference

| Tool | Purpose | Install | Required? |
|------|---------|---------|-----------|
| [Dippy](https://github.com/ldayton/Dippy) | AST-based bash command safety | `brew install dippy` | Yes (dontAsk mode) |
| [claude-devtools](https://github.com/matt1398/claude-devtools) | Session observability | `brew install --cask claude-devtools` | Recommended |
| [parry-guard](https://github.com/vaporif/parry) | ML injection detection (DeBERTa v3) | `cargo install --git ... --features candle` | Required (needs Rust + HF token) |
| [hcom](https://github.com/aannoo/hcom) | Inter-agent communication | `npm install -g hcom` | Recommended |
| [agnix](https://github.com/agent-sh/agnix) | Config linting | `npx agnix` (no install) | Optional |
| [Trail of Bits](https://github.com/trailofbits/skills) | Security analysis (5 plugins) | `claude plugin marketplace add` + install | Required |

## Cloud portability

The harness runs on macOS and Ubuntu 24.04 from the same tree. `scripts/install-tools.sh` detects the OS via `/etc/os-release`, installs `gh`, `jq`, `ripgrep`, `sqlite3`, and `python3>=3.11` via the platform's package manager, and bootstraps a shared virtualenv at `$HOME/.claude/.venv`. The script is idempotent — re-runs only install what's missing — and accepts `--yes` for unattended provisioning on fresh VMs.

## Session isolation

Two concurrent Claude Code sessions against the same repo would otherwise fight over HEAD. `scripts/new-session.sh` creates a git worktree per session so each gets an isolated HEAD without branch collisions; `scripts/list-sessions.sh` and `scripts/remove-session.sh` round out the lifecycle. When the harness itself (`$HOME/.claude`) is sessioned, stateful directories (`session-memory/`, `learning/`, `manifests/`, `db/memory.sqlite`) are symlinked from the canonical harness so memory, instincts, and the SQLite store stay single-writer across sessions. See `knowledge/session-isolation-patterns.md` for the full worktree-and-symlink model.

## Ubuntu clone-and-run

On a fresh Ubuntu 24.04 box:

```bash
git clone git@github.com:<org>/claude-harness.git "$HOME/.claude"
bash "$HOME/.claude/scripts/install-tools.sh" --yes
bash "$HOME/.claude/tests/shell/run.sh" --require-bats  # verifies install
```

## License

Private configuration. Not licensed for redistribution.
