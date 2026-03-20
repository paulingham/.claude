# Operational Details (Orchestrator-Only)

Extracted from `rules/operational-protocol.md`. Agents do not need this content.

## Escalation Protocol

### When to Ask the User

#### Always Ask (High Impact, Hard to Reverse)
- **Destructive operations**: `git reset --hard`, `git push --force`, deleting branches/files
- **Scope changes**: Task requires more work than originally described
- **Ambiguous requirements**: Multiple valid interpretations, no clear "right" answer
- **Architectural decisions**: New patterns, dependency additions, significant refactors
- **External actions**: Creating PRs, posting comments, sending messages
- **Security concerns**: Potential vulnerabilities that need human judgment
- **Budget exceeded**: Complexity Budget > 10, story needs decomposition

#### Always Proceed (Low Impact, Reversible)
- **Standard pipeline transitions**: Build -> Review -> Verify -> Test -> Accept
- **Retry after transient failure**: Agent timeout, network error, test flake
- **Style/formatting decisions**: Within established project conventions
- **Test file creation**: Writing tests for existing code
- **Worktree management**: Create, merge, cleanup
- **Running commands**: Tests, linting, type checking

#### Ask If Unsure (Medium Impact, Context-Dependent)
- **Performance trade-offs**: Speed vs readability, caching strategy
- **Dependency upgrades**: Minor version bumps (probably safe), major versions (ask)
- **Multiple valid approaches**: Present options with trade-offs, let user choose
- **Recovery decisions**: Which worktree to revert, which approach to retry
- **Partial completion**: Some phases passed but pipeline is taking too long

### Escalation Format

When escalating, be specific and actionable:

```
[ESCALATION] [reason]

Context: [what happened]
Options:
1. [option A] -- [pro/con]
2. [option B] -- [pro/con]
3. [option C] -- [pro/con]

Recommendation: [which option and why]
```

### Escalation Anti-Patterns

- **Asking for permission on every step**: Trust the pipeline. If a skill defines the process, follow it.
- **Proceeding silently on blockers**: If stuck for >2 retry cycles, escalate.
- **Over-explaining**: Keep escalations brief. The user can ask for details.
- **Asking instead of doing**: If the rules cover it, do it. Only ask when rules are silent.

## Error Recovery

### Agent Failure

When a spawned agent fails (error, timeout, incomplete work):

1. **First retry**: Re-spawn with the same prompt + error details appended
2. **Second retry**: Re-spawn with a simplified scope (fewer files, smaller change)
3. **Third failure**: Escalate to user -- "Agent failed 3 times on [task]. Error: [details]. Options: 1) Retry with different approach, 2) I'll investigate, 3) Skip this task."

Never retry more than twice. Escalate on third failure.

### Test Failure After Merge

When merging a worktree causes test failures:

1. Identify which worktree introduced the failure (run tests after each merge)
2. Revert only the failing merge: `git revert HEAD`
3. Re-spawn the agent with failure details: "Tests [X, Y] failed after merge. Error: [details]. Fix and re-submit."
4. Re-merge after fix

### Merge Conflicts

When cherry-picking or merging a worktree produces conflicts:

1. **Independent file sets** (different files): Should not conflict. Investigate why.
2. **Shared files**: Agents worked on overlapping code.
   - Abort the merge
   - Re-spawn ONE agent with BOTH changes described, in a single worktree
   - Or: merge the first worktree, then re-spawn the second agent from the merged state

Never resolve merge conflicts manually in the orchestrator. Delegate to an agent.

### Context Window Pressure

When the conversation is approaching context limits:

1. Verify pipeline state is saved in the memory file (see `orchestrator/pipeline-orchestration.md`)
2. The memory file IS the state -- no separate backup needed
3. Summarize completed phases concisely
4. Continue with fresh context -- the pipeline state persists in memory files

### Worktree Corruption

When a worktree is in a bad state (broken git, missing files):

1. Force-remove: `git worktree remove --force .claude/worktrees/[name]`
2. Delete the branch: `git branch -D worktree-[name]`
3. Re-spawn the agent -- it gets a fresh worktree

### Build Tool Failures

When npm/tsc/jest/etc. fail unexpectedly:

1. Check if `node_modules` needs reinstalling: `npm install`
2. Check if TypeScript has config issues: `npx tsc --noEmit`
3. Check if Jest config is picking up wrong files (worktree bleed)
4. If the issue is environment-related, not code-related, fix it before retrying the agent

### Skill Invocation Failure

When a Skill tool call fails:

1. Check if the skill file exists and has valid frontmatter
2. Retry once
3. If still failing: manually follow the skill's documented process as a fallback
4. Report the skill failure to the user
