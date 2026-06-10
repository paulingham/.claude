# Core Invariants

Always-loaded by every agent on every spawn. The smallest set of facts every spawn needs to operate correctly. Detailed protocols live in `protocols/<topic>.md` and are pulled in by skills/agents only when the phase needs them.

## Iron Laws

These are absolutes. No exceptions. No "just this once."

1. [ASPIRATIONAL] **NO ACCEPTANCE CRITERION SHIPS WITHOUT (a) a failing-then-passing test for that AC in the diff and (b) mutation score ≥ 70% on changed lines.** (Full ATDD cycle: `protocols/atdd-procedure.md`.)
2. [ASPIRATIONAL] **NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.** Stale test output from earlier in the session is not evidence — re-run before claiming done. (Enforcement: `hooks/verification-freshness-guard.sh`, log-only at v2.1.141, blocks once `permissionDecision` ships on Agent matcher.) (ADVISORY — NOT ENFORCED — schema-gap)
3. [ENFORCED] **THE ORCHESTRATOR NEVER WRITES SOURCE CODE.** The orchestrator coordinates agents; it does not Edit, Write, or shell-pipe into source files. Config exception: `.md` files in `.claude/`, `memory/`, `rules/` for documentation/state tracking only. (Detail: `protocols/agent-protocol.md`.)
4. [ENFORCED] **REPO_ROOT HEAD STAYS ON `main` FOR THE ENTIRE DURATION OF EVERY PIPELINE RUN.** All HEAD-mutating git commands run via worktree delegation (`git -C "$WORKTREE" …` or `(cd "$WORKTREE" && …)`). Bare `git checkout`, `git switch`, `git reset --hard`, `git merge`, `git rebase`, `gh pr create` are blocked by `hooks/main-branch-guard.sh`. (Allowed/forbidden surface: `protocols/agent-protocol.md` § Main-Branch Invariant.)
5. [ASPIRATIONAL] **NO PHASE SKIPPED. NO GATE BYPASSED. NO SKILL OMITTED.** Every pipeline phase runs the corresponding skill; verdicts gate advancement. (Detail: `protocols/pipeline-protocol.md`.)
6. [ASPIRATIONAL] **FINDINGS SURFACED DURING REVIEW ARE FIXED IN THIS PIPELINE.** Never filed as follow-ups. Never surfaced as questions to the user. The pipeline does not ship known-incomplete fixes. Escalate ONLY when the required fix is architecturally large (>~100 LOC, cross-service) or outside the current task's layer. (Detail: `protocols/pipeline-protocol.md` § In-Cycle Fix Rule.)
7. [ASPIRATIONAL] **EVERY PIPELINE PRODUCES AN OBSERVATION.** No exceptions — successes and failures both. The continuous learning loop depends on data volume. (Format and pipeline: `protocols/reflection-protocol.md` § Capture Pipeline Observation, `protocols/autonomous-intelligence.md` § Observation Capture.)

## Code Shape Rules

Every code-touching agent enforces continuously.

- **Naming is the primary cohesion gate:** can't name a unit without "and" → split; can't give an extract an honest name → do NOT extract.
- **Per-language hard block on new/changed code:** Ruby methods > 5 lines blocked (exit 2); TypeScript/JS functions > 12 lines blocked; Python/Go fallback cap retained. Legacy is advisory.
- **One thing per function.** If you cannot name it without a conjunction ("X and Y"), split.
- **Cyclomatic complexity ≤ 5.** Nesting ≤ 2 — guard clauses or extraction, not deeper if/else.
- **DRY on 2nd occurrence.** Extract immediately when logic recurs.
- **≤ 4 params** per function. More signals a missing abstraction.
- **Single public entry point** per class (`.call`/`.run`/`.execute`).
- **Entanglement escape valve:** if understanding unit A requires reading unit B, bring them together — this is HOW to fix a flagged function, not a bypass.
- **Comments carry WHY only.** New/changed WHAT-comments in source are blocked (exit 2) by hook; doc-comments, license headers, and `# WHY:`/`# SAFETY:` prefixes are always allowed.
- **Don't complect** (Hickey): one concern per unit; complected code defeats reasoning and breaks reliability.
- **Classes/files:** one responsibility, no hard size number — size is a smell that triggers the naming check. Safety-net cap: `CLAUDE_FILE_LINE_LIMIT` (default 300). Per-glob overrides via `.claude/shape-overrides.json` still apply.

Full standards (naming, SOLID, error handling, dependency resolution, security baseline, test mix): `protocols/engineering-invariants.md`.

## Worktree + Commit Protocol

- **Write-capable subagents** (software-engineer, frontend-engineer, qa-engineer, database-engineer, infrastructure-engineer): `isolation: "worktree"` — MANDATORY.
- **Read-only subagents** (code-reviewer, security-engineer, product-reviewer, architect): no worktree.
- **Team teammates** manage their own feature branches (e.g. `build/{task-id}-{slice}`) and commit before completing.
- **Every agent commits** before completing — uncommitted work cannot be merged. WIP commits use `WIP:` prefix.
- **No `git add -A` / `git add .`** — stage specific files to avoid sensitive-file leakage.

Full protocol: `protocols/agent-protocol.md`.

## Pipeline Phase Order

`Plan → Plan Validation → Build (incl. code-review as final step) → Security Review → Final Gate (Verify + Test + Accept + Patch Critique) → Ship → Deploy → Reflect`. No phase skipped. Every phase has a corresponding skill. Code-review is no longer its own phase — it runs as the final step of Build (the value-add is "second model with different priors", not a separate phase boundary). Security review remains a separate phase (orthogonal concern). Reflect always runs (§ Iron Law 7). Build has three dispatch variants — standard, Best-of-N, and PDR-RTV — selected by `/harness:intake` flags with precedence `pdr_rtv > bestofn > standard`. Detail: `protocols/pipeline-protocol.md`.

## Where to Look Next

| Need | File |
|------|------|
| ATDD cycle (build/fix phases) | `protocols/atdd-procedure.md` |
| Engineering standards (full) | `protocols/engineering-invariants.md` |
| Worktree, commit, scratchpad, main-branch surface | `protocols/agent-protocol.md` |
| Pipeline phases, review loop, in-cycle fix detail | `protocols/pipeline-protocol.md` |
| Complexity Budget, error recovery | `protocols/operational-protocol.md` |
| Team dispatch, Best-of-N, Plan Validation team | `protocols/parallel-dispatch-protocol.md` |
| Modular monolith, FF1–FF5 forcing functions | `protocols/module-boundaries-protocol.md` |
| Multi-repo, manifests, linked PRs | `protocols/multi-repo-protocol.md` |
| E2E (Maestro) trigger matrix | `protocols/e2e-protocol.md` |
| Reflect step, observation capture, README/MEMORY updates | `protocols/reflection-protocol.md` |
| Scratchpad, session memory, instinct injection | `protocols/autonomous-intelligence.md` |
| Thinking effort/display defaults | `protocols/thinking-defaults.md` |
