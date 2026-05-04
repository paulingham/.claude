# Core Invariants

Always-loaded by every agent on every spawn. The smallest set of facts every spawn needs to operate correctly. Detailed protocols live in `rules/_detail/<topic>.md` and are pulled in by skills/agents only when the phase needs them.

## Iron Laws

These are absolutes. No exceptions. No "just this once."

1. **NO ACCEPTANCE CRITERION SHIPS WITHOUT (a) a failing-then-passing test for that AC in the diff and (b) mutation score ≥ 70% on changed lines.** (Full ATDD cycle: `rules/_detail/atdd-procedure.md`.)
2. **NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.** Stale test output from earlier in the session is not evidence — re-run before claiming done.
3. **THE ORCHESTRATOR NEVER WRITES SOURCE CODE.** The orchestrator coordinates agents; it does not Edit, Write, or shell-pipe into source files. Config exception: `.md` files in `.claude/`, `memory/`, `rules/` for documentation/state tracking only. (Detail: `rules/_detail/agent-protocol.md`.)
4. **REPO_ROOT HEAD STAYS ON `main` FOR THE ENTIRE DURATION OF EVERY PIPELINE RUN.** All HEAD-mutating git commands run via worktree delegation (`git -C "$WORKTREE" …` or `(cd "$WORKTREE" && …)`). Bare `git checkout`, `git switch`, `git reset --hard`, `git merge`, `git rebase`, `gh pr create` are blocked by `hooks/main-branch-guard.sh`. (Allowed/forbidden surface: `rules/_detail/agent-protocol.md` § Main-Branch Invariant.)
5. **NO PHASE SKIPPED. NO GATE BYPASSED. NO SKILL OMITTED.** Every pipeline phase runs the corresponding skill; verdicts gate advancement. (Detail: `rules/_detail/pipeline-protocol.md`.)
6. **FINDINGS SURFACED DURING REVIEW ARE FIXED IN THIS PIPELINE.** Never filed as follow-ups. Never surfaced as questions to the user. The pipeline does not ship known-incomplete fixes. Escalate ONLY when the required fix is architecturally large (>~100 LOC, cross-service) or outside the current task's layer. (Detail: `rules/_detail/pipeline-protocol.md` § In-Cycle Fix Rule.)
7. **EVERY PIPELINE PRODUCES AN OBSERVATION.** No exceptions — successes and failures both. The continuous learning loop depends on data volume. (Format and pipeline: `rules/_detail/reflection-protocol.md` § Capture Pipeline Observation, `rules/_detail/autonomous-intelligence.md` § Observation Capture.)

## Code Shape Rules (cohesion, not line count)

Every code-touching agent enforces continuously. Cohesion is the design rule; line counts are advisory smell signals only.

- **One thing per function.** If you cannot name it without a conjunction ("X and Y"), split.
- **Cyclomatic complexity ≤ 5.** Nesting ≤ 2 — guard clauses or extraction, not deeper if/else.
- **DRY on 2nd occurrence.** Extract immediately when logic recurs.
- **Single public entry point** per class (`.call`/`.run`/`.execute`).

Soft warnings (advisory, surface in review but don't block): function bodies > 30 lines, files > 150 lines. The shape hook enforces a generous safety-net cap (`CLAUDE_FILE_LINE_LIMIT`, default 300) for clearly runaway output. Per-glob overrides via `.claude/shape-overrides.json` still apply.

Full standards (naming, SOLID, error handling, dependency resolution, security baseline, test mix): `rules/_detail/engineering-invariants.md`.

## Worktree + Commit Protocol

- **Write-capable subagents** (software-engineer, frontend-engineer, qa-engineer, database-engineer, infrastructure-engineer): `isolation: "worktree"` — MANDATORY.
- **Read-only subagents** (code-reviewer, security-engineer, product-reviewer, architect): no worktree.
- **Team teammates** manage their own feature branches (e.g. `build/{task-id}-{slice}`) and commit before completing.
- **Every agent commits** before completing — uncommitted work cannot be merged. WIP commits use `WIP:` prefix.
- **No `git add -A` / `git add .`** — stage specific files to avoid sensitive-file leakage.

Full protocol: `rules/_detail/agent-protocol.md`.

## Pipeline Phase Order

`Plan → Plan Validation → Build (incl. code-review as final step) → Security Review → Final Gate (Verify + Test + Accept + Patch Critique) → Ship → Deploy → Reflect`. No phase skipped. Every phase has a corresponding skill. Code-review is no longer its own phase — it runs as the final step of Build (the value-add is "second model with different priors", not a separate phase boundary). Security review remains a separate phase (orthogonal concern). Reflect always runs (§ Iron Law 7). Detail: `rules/_detail/pipeline-protocol.md`.

## Where to Look Next

| Need | File |
|------|------|
| ATDD cycle (build/fix phases) | `rules/_detail/atdd-procedure.md` |
| Engineering standards (full) | `rules/_detail/engineering-invariants.md` |
| Worktree, commit, scratchpad, main-branch surface | `rules/_detail/agent-protocol.md` |
| Pipeline phases, review loop, in-cycle fix detail | `rules/_detail/pipeline-protocol.md` |
| Complexity Budget, error recovery | `rules/_detail/operational-protocol.md` |
| Team dispatch, Best-of-N, Plan Validation team | `rules/_detail/parallel-dispatch-protocol.md` |
| Modular monolith, FF1–FF5 forcing functions | `rules/_detail/module-boundaries-protocol.md` |
| Multi-repo, manifests, linked PRs | `rules/_detail/multi-repo-protocol.md` |
| E2E (Maestro) trigger matrix | `rules/_detail/e2e-protocol.md` |
| Reflect step, observation capture, README/MEMORY updates | `rules/_detail/reflection-protocol.md` |
| Scratchpad, session memory, instinct injection | `rules/_detail/autonomous-intelligence.md` |
| Thinking effort/display defaults | `rules/_detail/thinking-defaults.md` |
