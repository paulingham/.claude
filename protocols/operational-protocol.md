# Operational Protocol

Detailed orchestrator procedures: see `~/.claude/orchestrator/operational-details.md`

## Complexity Budget

Score each dimension 1-3:

| Dimension | 1 (Low) | 2 (Medium) | 3 (High) |
|-----------|---------|-----------|----------|
| **Scope** (files to touch) | 1-3 files | 4-10 files | 11+ files |
| **Ambiguity** (requirement clarity) | Fully specified ACs | Interpretation needed | Discovery required |
| **Context Pressure** (codebase knowledge) | Single module | Cross-module | System-wide |
| **Novelty** (precedent exists?) | Pattern to follow | Partial precedent | Greenfield |
| **Coordination** (cross-cutting?) | Isolated | 2-3 concerns | Auth + data + UI + infra |

### Thresholds

| Budget | Action |
|--------|--------|
| 5-6 | Single task, execute directly |
| 7-8 | Compound task, plan first |
| 9-10 | Compound task, plan first |
| 11-12 | Multi-session, break into sub-tasks |
| 13-15 | Must decompose before starting |

The Fibonacci/story-points mapping was removed in May 2026. The budget number IS the routing signal — no second translation is needed for AI work, and the harness consumes the raw budget directly (`bestofn`, `critical`, decompose-or-execute thresholds).

## Work-Class Routing (Overview)

Task class is orthogonal to the Complexity Budget. Tier (T0..T6) determines which dispatch shape a task receives; Complexity Budget controls intra-tier shape (e.g. multi-slice Build at T5, Best-of-N vs PDR-RTV at T6). The auto-detection happens at `/harness:intake` Step 1.5 (Fingerprint), runs BEFORE Step 2 (Complexity Budget).

| Tier | Class | Examples | Dispatch target |
|---|---|---|---|
| **T0** | Question / Spike | "How does X work?", "Investigate Y" | Direct answer or `/harness:tech-spike` |
| **T1** | Doc-only | README/CLAUDE.md edits, protocol updates, comments | Orchestrator direct edit (Iron Law 3 exception) |
| **T2** | Config-only | settings.json keys, agent frontmatter, hook entry syntax (NOT hook script bodies) | `/harness:harness-config` |
| **T3** | Mechanical sweep | rename, find/replace, lint-fix, import-sort, dependency bump | `/harness:batch-pipeline` |
| **T4** | Bug fix | Failing test + targeted fix | `/harness:pipeline` (lightweight) |
| **T5** | Standard feature | New AC, single-slice, isolated module | `/harness:pipeline` (standard) |
| **T6** | Critical / cross-cutting | Auth, payment, security, multi-repo, system-wide | `/harness:pipeline` (heavy: Best-of-N or PDR-RTV) |

Source of truth: protocols/work-class-routing.md

## Error Recovery Principles

- **Retry twice, then escalate.** Never retry more than twice. Third failure goes to the user.
- **Never fail silently.** Surface errors with context (what failed, why, options).
- **Never resolve merge conflicts manually in the orchestrator.** Delegate to an agent.
- **Worktree corruption**: Force-remove, delete branch, re-spawn agent with fresh worktree.
- **Build tool failures**: Check `node_modules`, TypeScript config, Jest config before retrying agent.

## Escalation Decision Tree

| Situation | Action |
|-----------|--------|
| Command fails with "not found" | Source shell profile, retry once |
| Test fails after merge | Identify which worktree introduced failure, revert merge, re-spawn |
| Agent fails twice on same task | Escalate to user with context |
| Merge conflict | Delegate to agent — orchestrator NEVER resolves manually |
| Worktree corrupted | Force-remove worktree, delete branch, re-spawn fresh |
| Review not resolved after 2 rounds | Escalate to user with options |
| Context window approaching limit | Compress, use pipeline memory for continuity |

## Complexity Budget Example

Scoring a "biometric settings screen" feature:
- **Scope**: 4-10 files (toggle component, hook, settings route, nav bar update) → 2
- **Ambiguity**: ACs are clear (toggle on/off, disabled state) → 1
- **Context Pressure**: Cross-module (components + hooks + routing) → 2
- **Novelty**: No settings screen exists yet, but patterns available → 2
- **Coordination**: UI + storage + navigation → 2
- **Total**: 9 → Compound task, plan first
