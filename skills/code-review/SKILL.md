---
name: "code-review"
description: "Use when user wants to Review phase skill: spawn code-reviewer agent to audit code for SOLID/DRY violations, security issues, test quality, performance, and complexity. Produces APPROVE or CHANGES_REQUESTED verdict."
context: fork
agent: code-reviewer
---

# Code Review

## Advisor Mode (Sonnet executor + Opus advisor)

**Pairing**: code-reviewer ships with `executor: claude-sonnet-4-6` and `advisor: claude-opus-4-7` in its frontmatter. Sonnet drives the review (cheap, fast, large-context-friendly), Opus is consulted for design-judgement calls.

**Status**: This is the **intended default** — currently advisory because the Agent input schema does not yet expose `advisor`. Will become the enforced default the moment the schema lands. Until then, the `pre-agent-advisor.sh` PreToolUse hook logs the would-be pairing to `metrics/{session}/advisor-dispatch.jsonl` for observability; no spawn is blocked, no model is downgraded.

**Fallback semantics** (all log-only today, all enforced later):
- Frontmatter pairing present + `ANTHROPIC_API_KEY` set + `CLAUDE_REVIEW_ADVISOR_DISABLED` unset → executor=sonnet, advisor=opus (`source: frontmatter-pairing`)
- `CLAUDE_REVIEW_ADVISOR_DISABLED=1` → executor/advisor both null, `source: env-disabled` (operator override; pure `model:` opus solo)
- `ANTHROPIC_API_KEY` missing → executor/advisor both null, `source: no-api-key`
- Frontmatter omits executor/advisor (e.g. software-engineer) → not a reviewer; `source: no-pairing-frontmatter`

**Cost** (PROVISIONAL pending advisor-baseline):
- Naive Opus-solo cost vs. Sonnet+Opus-advisor pairing: roughly ~40% cheaper per review (PROVISIONAL — see `eval/baselines/{latest}-advisor-baseline.md`).
- Quality-equivalence claim (≥95% verdict-agreement on the regression suite) is also PROVISIONAL until advisor-baseline runs.

## What This Skill Does

Automates the Review phase code audit. Spawns a read-only code-reviewer agent to assess code quality against engineering standards.

## Current Context
- Branch: !`git branch --show-current`
- Changed files: !`git diff main...HEAD --name-only 2>/dev/null || echo 'N/A'`
- Diff stats: !`git diff main...HEAD --stat 2>/dev/null || echo 'N/A'`

## Review Focus

The build agent has already passed: shape hooks (blocking), TypeScript strict, full test suite, and self-review. Do not re-verify these.

Focus on what requires judgment:
- Design decisions and abstractions
- Naming clarity and intent
- DRY/SOLID at the design level (not line counting)
- Edge cases and untested scenarios
- Integration with the broader codebase

If shape violations reach you, flag it as a process issue ("build hooks should have caught this") rather than a code finding.

## When to Invoke

- After Build phase completes (tests green, shape constraints met)
- Run IN PARALLEL with `/security-review` — both are read-only, independent
- Both must APPROVE before advancing to Verify phase

## Process

### 1. Gather Context

```bash
git diff main...HEAD --stat
git log main...HEAD --oneline
```

### 2. Spawn Code Reviewer

```
Agent({
  subagent_type: "code-reviewer",
  prompt: "Review the changes on this branch against main. Check for:
    - SOLID/DRY violations
    - Test quality (coverage, meaningful assertions, edge cases)
    - Performance red flags (N+1 queries, unnecessary re-renders, memory leaks)
    - Complexity (CC > 5, nesting > 2, methods > 8 lines, files > 50 lines)
    - Naming clarity and code readability
    Produce a verdict: APPROVE or CHANGES_REQUESTED with specific findings."
})
```

No `isolation: "worktree"` — code-reviewer is read-only.

### 3. Process Verdict

- **APPROVE**: Advance to next phase. Record reviewer summary for PR narrative.
- **CHANGES_REQUESTED**: Spawn the original engineer (with worktree) to address findings. Then re-run this skill.

## Review Checklist

Shape measurements are enforced by build hooks. Include measurements in your report for the audit trail, but do not flag passing measurements as findings. Only flag if a measurement EXCEEDS limits despite hooks — this indicates a hook bypass, and the finding severity is "process" (fix the hooks, not the code).

- [ ] Shape constraints met (see `rules/engineering-invariants.md`)
- [ ] No DRY violations (duplicated logic)
- [ ] SRP: each class/module has one reason to change
- [ ] Tests are meaningful (not just coverage padding)
- [ ] No TODO/FIXME without linked ticket
- [ ] Error handling follows guard clause pattern
- [ ] No hardcoded values (extract to constants)

## Adversarial Review Mode (Budget >= 10 OR Sensitive Code)

When activated by the pipeline, two code-reviewers are spawned with different focus areas:

- **Reviewer A** (this default prompt): Focus on abstractions, naming, DRY/SOLID, design quality
- **Reviewer B** (edge-case prompt): Focus on edge cases, error paths, integration concerns, race conditions

Each reviews independently without seeing the other's output. The orchestrator merges findings:
- Both flag the same area → HIGH confidence finding
- Only one flags it → MEDIUM confidence, both perspectives included
- Both APPROVE → advance. Either requests changes → normal review loop.

This mode is transparent to the reviewer — the orchestrator controls dispatch. The reviewer follows this skill normally.

## Parallel Execution

This skill belongs to the `review` parallel group. It is dispatched via Parallel Dispatch Protocol (see `rules/parallel-dispatch-protocol.md`), not via sequential Skill tool invocation. The code-reviewer agent reads this file directly and executes it.

When dispatched in parallel:
1. The orchestrator spawns code-reviewer + security-engineer in a single message
2. Each agent reads its own skill file independently
3. The orchestrator collects both verdicts before proceeding

## Prerequisite

- Build phase complete: BUILD_COMPLETE verdict from `/build-implementation`, `/refactor`, or `/bug-fix`
- Must be dispatched IN PARALLEL with `/security-review` via Parallel Dispatch Protocol

## Severity Grading

Every finding MUST be assigned a severity. Use the calibration table below:

| Severity | Definition | Examples | Blocks? |
|----------|-----------|----------|---------|
| CRITICAL | Security vulnerability or data loss risk | SQL injection, exposed secrets, auth bypass | Yes |
| HIGH | Correctness bug or significant design flaw | Missing error handling, broken invariant, SOLID violation | Yes |
| MEDIUM | Code quality issue causing maintenance pain | DRY violation across files, unclear naming, missing edge case test, unnecessary coupling | Yes |
| LOW | Minor improvement or style preference | Variable rename suggestion, comment improvement | No |
| INFO | Observation, context, or positive feedback | "Nice pattern," "FYI this also handles X" | No |

**Verdict rule:** APPROVE if no CRITICAL, HIGH, or MEDIUM findings. CHANGES_REQUESTED if any CRITICAL, HIGH, or MEDIUM findings exist. LOW and INFO are noted but do not block.

**In-cycle enforcement:** CHANGES_REQUESTED findings MUST be fixed in the current pipeline. The orchestrator is not permitted to downgrade findings to follow-up tickets, ship with known-broken behavior, or ask the user whether to defer. See `rules/pipeline-protocol.md` § In-Cycle Fix Rule. If a finding is genuinely orthogonal (different module, different contract, different user journey), mark it INFO, not MEDIUM.

## Preventability Classification (Backward Feedback)

For each finding, classify whether the build agent could have prevented it:

| Classification | Criteria | Example |
|---|---|---|
| **Preventable** | Standard pattern violation a build agent should catch | Missing input validation, SOLID violation, naming issue |
| **Review-level** | Requires cross-cutting perspective only a reviewer has | Architectural concern, subtle race condition, design inconsistency |

Tag each finding with `preventable: true/false`. The `/learn` skill uses this during Reflect to create build-targeted instincts that prevent the same findings in future pipelines.

## Phase Output

```
Verdict: APPROVE / CHANGES_REQUESTED
Next: If BOTH code-review and security-review APPROVE → /verify
      If CHANGES_REQUESTED → spawn engineer to fix → re-invoke BOTH review skills
Findings: [list of specific findings with severity and preventability]
Agent summaries: [code-reviewer's 2-3 sentence summary]
```

### Context for Next Phase

Include a `## Context for Fix/Verify` section in the pipeline state file:

```markdown
## Context for Fix/Verify
- **Finding context**: [for each finding: not just "fix X" but "fix X because Y, consider approach Z"]
- **Areas of strength**: [what the build agent did well — reinforces good patterns]
- **Decision record responses**: [agree/disagree/note on build agent's decision record entries]
```
