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

| Budget | Action | Fibonacci |
|--------|--------|-----------|
| 5-6 | Single task, execute directly | 1-2 pts |
| 7-8 | Compound task, plan first | 3-5 pts |
| 9-10 | Compound task, plan first | 8 pts |
| 11-12 | Multi-session, break into sub-tasks | 13 pts |
| 13-15 | Must decompose before starting | 21+ pts (must split) |

## Error Recovery Principles

- **Retry twice, then escalate.** Never retry more than twice. Third failure goes to the user.
- **Never fail silently.** Surface errors with context (what failed, why, options).
- **Never resolve merge conflicts manually in the orchestrator.** Delegate to an agent.
- **Worktree corruption**: Force-remove, delete branch, re-spawn agent with fresh worktree.
- **Build tool failures**: Check `node_modules`, TypeScript config, Jest config before retrying agent.
