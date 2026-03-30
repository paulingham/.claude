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

If a module outgrows the monolith, it detects extraction signals during review and can autonomously create a new repo, migrate the code, generate contracts, refactor the monolith, and open PRs in both repos.

## Architecture

```
~/.claude/
  CLAUDE.md                    # Master playbook — philosophy, pipeline, skill directory
  settings.json                # Hook registration, permissions, env vars
  rules/                       # Auto-loaded protocols (6 files)
    agent-protocol.md          #   Worktree isolation, commit protocol
    pipeline-protocol.md       #   Pipeline phases, review loops, state management
    engineering-protocol.md    #   Code shape, TDD, testing standards, security baseline
    operational-protocol.md    #   Complexity Budget scoring, error recovery
    parallel-dispatch-protocol.md  # Parallel review/build dispatch
    e2e-protocol.md            #   Maestro E2E trigger matrix
  orchestrator/                # Orchestrator-only detailed procedures (4 files)
  agents/                      # 9 specialized agent definitions
  skills/                      # 42 skills (procedural workflows)
  knowledge/                   # 31 domain pattern references
  hooks/                       # 22 enforcement scripts
  learning/                    # Continuous learning: observations + instincts
  metrics/                     # Session cost, governance, bug detection logs
  pipeline-state/              # Structured phase results (survives context compaction)
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
Intake → Plan → Scaffold → Build → Review → Verify → Load Test → Test → Accept → Ship → Deploy
  │                │           │        │         │         │          │        │        │
  │                │           │        │         │         │          │        │        └─ /deploy + /deployment-verification
  │                │           │        │         │         │          │        └─ /product-acceptance (UX heuristics 14/20)
  │                │           │        │         │         │          └─ /qa-test-strategy
  │                │           │        │         │         └─ /load-test (k6/Artillery)
  │                │           │        │         └─ /verify (contract + smoke + mutation)
  │                │           │        └─ /code-review + /security-review (parallel, SAST)
  │                │           └─ /build-implementation (incremental TDD)
  │                └─ /api-scaffold, /db-migration, /infra-scaffold, /design-system-init, ...
  └─ /intake (classify, score Complexity Budget, route)
```

## Skills (38)

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
| `/bff-scaffold` | New channel needs Backend for Frontend |
| `/microservices-scaffold` | New service extraction |
| `/service-extraction` | Full autonomous repo creation + code migration |

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

### Cross-Service
| Skill | Purpose |
|-------|---------|
| `/cross-service-pipeline` | Contract verification, deploy coordination |
| `/harness-config` | Modify hooks, settings.json (delegates to infra-engineer) |
| `/harness-audit` | Health check of ~/.claude/ config (+ agnix integration) |
| `/debug` | Persistent debug state for complex, multi-session bugs |
| `/forensics` | Post-incident pipeline investigation |
| `/workstream` | Manage isolated workstreams for parallel development |
| `/polish` | Mechanical cleanup between Build and Review (Haiku, Budget >= 7) |
| `/design-qc` | Visual QA screenshots for product acceptance (frontend changes) |
| `/learn` | Extract instincts from observed behavior (continuous learning) |

### Reference Patterns
| Skill | Domain |
|-------|--------|
| `/web-frontend-patterns` | React/Next.js, state, a11y, caching, security |
| `/react-native-patterns` | Expo, NativeWind, Maestro E2E |

## Knowledge Library (31 files)

### Core Engineering
`database-patterns` `api-patterns` `testing-patterns` `integration-patterns` `auth-patterns` `env-management-patterns`

### Domain Patterns
`background-job-patterns` `notification-patterns` `file-upload-patterns` `multi-tenancy-patterns` `payment-patterns` `search-patterns` `realtime-patterns` `feature-flag-patterns` `i18n-patterns` `data-privacy-patterns` `state-machine-patterns` `caching-patterns`

### Architecture
`multi-repo-patterns` `service-mesh-patterns` `horizontal-scaling-patterns` `backup-dr-patterns` `omnichannel-patterns` `voice-patterns` `device-iot-patterns`

### UX/UI
`design-system-patterns` `ui-pattern-library` `ux-heuristics` `motion-design-patterns` `data-visualization-patterns` `content-design-patterns`

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
| `subagent-stop-trajectory.sh` | Records agent completion to pipeline trajectory | Passive |

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

# Recommended: ML-based prompt injection detection
cargo install parry

# Recommended: Inter-agent communication for team phases
npm install -g hcom

# Optional: Configuration linting (385 validation rules)
npx agnix ~/.claude/

# Optional: Professional security skills
claude plugins install trailofbits/skills
```

### Setup

1. Clone this repo to `~/.claude/`
2. Verify external tools: `dippy --version && which parry && which hcom`
3. Start Claude Code in any project repo
4. Say what you want to build — the system handles the rest

For new projects without a CLAUDE.md, the system automatically runs `/project-setup` to detect your stack, configure commands, classify service architecture, and generate a design system.

### External Tool Reference

| Tool | Purpose | Install | Required? |
|------|---------|---------|-----------|
| [Dippy](https://github.com/ldayton/Dippy) | AST-based bash command safety | `brew install dippy` | Yes (dontAsk mode) |
| [claude-devtools](https://github.com/matt1398/claude-devtools) | Session observability | `brew install --cask claude-devtools` | Recommended |
| [parry-guard](https://github.com/vaporif/parry) | ML injection detection | `cargo install parry` | Recommended |
| [hcom](https://github.com/aannoo/hcom) | Inter-agent communication | `npm install -g hcom` | Recommended |
| [agnix](https://github.com/agent-sh/agnix) | Config linting | `npx agnix` (no install) | Optional |
| [Trail of Bits](https://github.com/trailofbits/skills) | Security analysis skills | `claude plugins install` | Optional |

## License

Private configuration. Not licensed for redistribution.
