# Session Memory Index

_This directory holds engineering context for ONE project. Each project hash gets a sub-directory with five sub-files; the orchestrator selects sub-files by filename and concatenates them under `## Session Context` when spawning agents._

## Layout

```
session-memory/
├── config/
│   ├── template.md                # this index
│   └── templates/                 # seed templates copied per project
│       ├── codebase-map.md
│       ├── build-test.md
│       ├── patterns.md
│       ├── fragility.md
│       └── active-work.md
└── {project-hash}/
    ├── codebase-map.md            # Key dirs, files, entry points
    ├── build-test.md              # Build / test commands, env quirks
    ├── patterns.md                # Patterns, conventions, discoveries, agent effectiveness
    ├── fragility.md               # Critical paths, timing sensitivities, fragile areas
    └── active-work.md             # Orchestrator-only — NEVER injected into agent prompts
```

## Sub-file Roles

- **codebase-map.md** — orientation map for new spawns: which file does what, how the modules connect.
- **build-test.md** — commands, env vars, test-runner quirks, package-manager specifics.
- **patterns.md** — code patterns in use, framework idioms, session discoveries, agent effectiveness notes.
- **fragility.md** — fragile files, complex dependencies, timing sensitivities, areas needing care.
- **active-work.md** — current pipeline phase, task id, branch, immediate next steps. Orchestrator state, not engineering knowledge.

## Injection Rule

`active-work.md` is NEVER injected into agent prompts (encoded in `hooks/_lib/session_memory_role_resolver.py` — every role's sub-file list excludes it). The orchestrator reads it directly via `session_store_get $hash active-work` for its own state tracking.

The other four sub-files are injected per the role × sub-file mapping in `rules/_detail/autonomous-intelligence.md` § Injection Priority. Empty bodies (< 50 chars after stripping headers + italic descriptions) are omitted from the rendered block — no role sees a header with no content.
