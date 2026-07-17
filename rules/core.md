# Core Invariants

Always-loaded by every agent on every spawn. The smallest set of facts every spawn needs to operate correctly. Detailed protocols live in `protocols/<topic>.md` and are pulled in by skills/agents only when the phase needs them.

This file is a thin index over the two law-tier files below. Iron Laws are globally numbered 1-8 across both files — `rules/safety.md` carries the non-contiguous universal subset (2, 3, 4, 6, 8) enforced in every gear, and `rules/pipeline-rigour.md` carries the non-contiguous Build/Pipeline-only subset (1, 5, 7).

@rules/safety.md
@rules/pipeline-rigour.md

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
