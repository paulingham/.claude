---
name: "patch-critique"
description: "Use when user wants Final-Gate evaluation of a candidate patch by test results + diff (NOT SOLID/DRY). Spawns the patch-critic agent — Sonnet executor + Opus advisor — to score the patch against four dimensions and produce PATCH_APPROVED or PATCH_REJECTED. Inspired by SWE-bench top scaffolds."
context: fork
agent: patch-critic
---

# Patch Critique

## What This Skill Does

Adds a distinct critic step to the Final Gate that evaluates the candidate patch against test outcomes and the diff itself — orthogonal to the code-reviewer's SOLID/DRY/design audit. SWE-bench top scaffolds (Agentless, AutoCodeRover, MarsCode-Agent) consistently include a critic step of this shape; without it, patches that are "clean code but wrong fix" or "tests pass but huge incidental refactor" slip through.

Verdict gates Ship. PATCH_REJECTED returns to fix-engineer per `protocols/pipeline-protocol.md` § In-Cycle Fix Rule — never escalates to the user.

## Advisor Mode (Sonnet executor + Opus advisor)

**Pairing**: patch-critic ships with `executor: claude-sonnet-4-6` and `advisor: claude-opus-4-5-20251101` in its frontmatter, matching the Wave 1 D1 advisor-tool default for review-style roles. Sonnet drives the rubric scan (cheap, fast, large-diff-friendly); Opus is consulted on regression-or-refactor judgement calls.

**Status**: Intended default — currently advisory because the Agent input schema does not yet expose `advisor`. The `pre-agent-advisor.sh` PreToolUse hook logs the would-be pairing to `metrics/{session}/advisor-dispatch.jsonl`. Same Path-B status as `/code-review` and `/security-review`.

## Current Context
- Branch: !`git branch --show-current`
- Changed files: !`git diff main...HEAD --name-only 2>/dev/null || echo 'N/A'`
- Diff stats: !`git diff main...HEAD --stat 2>/dev/null || echo 'N/A'`

## Inputs

The orchestrator MUST provide all three in the spawn prompt:

| Input | Source |
|-------|--------|
| Candidate diff | `git diff main...HEAD` (full unified diff) |
| Test output | Most recent fresh test-suite run (PASS/FAIL counts, failed test names) |
| Intake spec | Task description from `/intake` — what the patch is supposed to do |
| Verification evidence | `pipeline-state/{task-id}/verification-evidence.json` written by `/verify` Step 6. Freshness validated by `hooks/verification-freshness-guard.sh` (Path-B advisory at v2.1.141); orchestrator MUST re-run `/verify` BEFORE re-dispatch if the hook logs `would_block` with `reason: git_head_mismatch`. Absent → `PATCH_REJECTED` with `reason: missing input: verification-evidence.json`. |
| A11y index (optional) | `pipeline-state/{task-id}/design-qc/index.json` produced by `/design-qc` § 6.25. Drives rubric § 5. Absent → § 5 omitted from output (silent SKIP). |

If any of the three required inputs is missing, the critic returns PATCH_REJECTED with reason `missing input: {name}`. Do NOT guess at missing inputs. The a11y index is optional; absence triggers § 5 SKIP semantics, not PATCH_REJECTED.

## Rubric

Five dimensions, each PASS / SKIP / FAIL with a one-line justification. Any FAIL → PATCH_REJECTED. SKIP counts as PASS for `PATCH_APPROVED` aggregation.

| Dimension | What it checks | Cite |
|-----------|---------------|------|
| Tests cover the change | Every behaviour-changing hunk maps to a test assertion | hunk → test path |
| Diff minimal vs spec | Diff touches only what the intake spec implies | unrelated `file:line` |
| No obvious regressions | No removed guards, weakened validation, swallowed errors | regression `file:line` |
| No incidental refactor | No rename/move/extract not requested by spec | refactor `file:line` |
| § 5 A11y (assertions A1–A6) | Six accessibility assertions over `index.json` snapshots | route + viewport + assertion id |

The rubric is deliberately mechanical — judgement at the boundaries goes to the Opus advisor.

§ 5 SKIP semantics: index-absent → section omitted entirely; `a11y_global.captured == false` with reason `mcp-unavailable` → row rendered with operator-facing remediation pointer to `skills/design-qc/SKILL.md` § 6.25; other reasons → row rendered as `SKIP: <reason>`. See `agents/patch-critic.md` § 5 for the full rubric and the six assertions.

## What This Skill Is NOT

This skill does NOT duplicate code-reviewer scope:

- NOT SOLID. NOT DRY. NOT naming quality. NOT abstraction design.
- NOT shape constraints (hooks enforce; code-reviewer flags bypass).
- NOT security (security-engineer owns).
- NOT acceptance criteria (product-reviewer owns).
- NOT coverage gap analysis (qa-engineer owns).

The critic explicitly excludes SOLID-style design audits. If a finding sounds like "this could be cleaner" or "this abstraction leaks" — that is code-reviewer territory and was already gated upstream.

## When to Invoke

- Final Gate phase, in parallel with `/verify`, `/qa-test-strategy`, and `/product-acceptance`
- After `/code-review` and `/security-review` both APPROVED
- All four Final Gate teammates work read-only on the same final state — no lock contention

## Process

### 1. Gather Inputs

The orchestrator hands the three inputs in the spawn prompt. If any is missing, return PATCH_REJECTED immediately.

### 2. Spawn Persona-1 (default — always runs)

Dispatch is **persona-1-first, escalate-on-uncertainty**. Persona-1 (Persona: `correctness`) runs on every Final Gate dispatch, alongside `/verify`, `/qa-test-strategy`, and `/product-acceptance`. No criticality or budget gate.

```
Agent({
  subagent_type: "patch-critic",
  team_name: "pipeline-{task-id}",
  name: "patch-critic-correctness",
  prompt: "Read ~/.claude/skills/patch-critique/SKILL.md and execute fully.
           Read ~/.claude/agents/patch-critic.md for your role definition.

           Persona: correctness

           Inputs:
           - Candidate diff: [git diff main...HEAD output]
           - Test output: [latest fresh test run summary]
           - Intake spec: [intake task description]
           - Verification evidence: pipeline-state/{task-id}/verification-evidence.json
           - A11y index (optional): pipeline-state/{task-id}/design-qc/index.json

           Score the five-dimension rubric. Emit:
             Verdict: PATCH_APPROVED or PATCH_REJECTED with file:line citations
             Uncertainty: true | false
             Uncertainty Reason: (when Uncertainty=true) per the canonical enum
                                 in agents/patch-critic.md § Uncertainty signal."
})
```

No `isolation: "worktree"` — patch-critic is read-only.

### 3. Read Persona-1 Output

Parse the structured output for `Verdict` AND `Uncertainty`:

- `Uncertainty: false` + `Verdict: PATCH_APPROVED` → gate verdict `PATCH_APPROVED`. **Skip step 4.** A confident persona-1 approval gates Ship.
- `Uncertainty: false` + `Verdict: PATCH_REJECTED` → gate verdict `PATCH_REJECTED`. **Skip step 4.** Forward persona-1 findings to fix-engineer (in-cycle, per `protocols/pipeline-protocol.md` § In-Cycle Fix Rule).
- `Uncertainty: true` (regardless of `Verdict`) → proceed to step 4 (escalation). Persona-1's verdict still counts as one vote in the eventual aggregation.

If the output omits the `Uncertainty` field entirely, treat as `Uncertainty: true` (conservative default — over-escalation is the correct local choice; see `agents/patch-critic.md` § Close-call bias guidance).

### 4. Escalate (only when Uncertainty: true)

Spawn two additional personas in PARALLEL (single message, two `Agent({…})` calls). Independent context — neither sees persona-1's output nor the other escalation persona's output.

```
Agent({
  subagent_type: "patch-critic",
  team_name: "pipeline-{task-id}",
  name: "patch-critic-regression-risk",
  prompt: "Persona: regression-risk
           [same inputs as persona-1, identical diff/tests/spec/a11y context]"
})

Agent({
  subagent_type: "patch-critic",
  team_name: "pipeline-{task-id}",
  name: "patch-critic-scope-creep",
  prompt: "Persona: scope-creep
           [same inputs as persona-1]"
})
```

Full spawn templates with `Persona:` token semantics and search-emphasis prompts live in `orchestrator/parallel-dispatch-details.md` § Multi-Persona Patch Critic Dispatch.

### 5. Aggregate (escalation path only — majority-of-3)

On the escalation path, apply majority-of-3 across persona-1 + 2 escalation personas:

- ≥2 `PATCH_APPROVED` → gate `PATCH_APPROVED`.
- ≥2 `PATCH_REJECTED` → gate `PATCH_REJECTED`. Forward findings from ALL rejecting personas to fix-engineer.

Operator override: `CLAUDE_PATCH_CRITIC_AGGREGATION=or` reverts to OR-aggregation (any REJECT → gate REJECT) on the escalation path. Default is `majority`.

### 6. Process Verdict

- **PATCH_APPROVED**: Ship gate satisfied for this dimension. Combined with VERIFIED + COVERED + APPROVED, advance to `/pr-creation`.
- **PATCH_REJECTED**: Spawn fix-engineer with rubric findings. Re-run `/patch-critique` (and any other failed Final Gate skills) on the combined diff. Re-critique dispatch shape depends on the rejection mode:
  - Rejected at `mode=persona-1` (no escalation fired) → re-dispatch persona-1 only.
  - Rejected at `mode=escalated` → re-dispatch ALL three personas (fix may have introduced a new issue in another persona's territory).
  Max 2 rounds, same as Review.

## Output Format

Each persona spawn emits the structured output below. The orchestrator-aggregated artifact at `pipeline-state/{task-id}/patch-critic.md` concatenates one such block per persona that ran (1 when `mode=persona-1`, 3 when `mode=escalated`).

```markdown
## Patch Critique: [task-id] [Persona: correctness | regression-risk | scope-creep]

### Verdict: PATCH_APPROVED / PATCH_REJECTED
### Uncertainty: true | false
### Uncertainty Reason: ambiguous diff | incomplete test coverage assessment | <free-form> | —

### Rubric
| Dimension | Verdict | Justification |
|-----------|---------|---------------|
| Tests cover the change | PASS / FAIL | one line |
| Diff minimal vs spec | PASS / FAIL | one line |
| No obvious regressions | PASS / FAIL | one line |
| No incidental refactor | PASS / FAIL | one line |
| § 5 Accessibility | PASS / SKIP / FAIL | one line; SKIP allowed per § 5 SKIP semantics |

### Findings
- `file:line` — [description]

### Test Result Summary
- Passed: N
- Failed: N (names if any)

### Diff Summary
- Files changed: N
- Lines added/removed: +X / -Y
- Spec scope alignment: [one sentence]
```

Frontmatter of the aggregated artifact: `task_id, phase=final-gate, verdict, timestamp, mode=persona-1 | escalated, uncertainty_fired: bool, aggregation: majority | or`.

## Parallel Execution

This skill belongs to the `final-gate` parallel group. Dispatched via Parallel Dispatch Protocol (`protocols/parallel-dispatch-protocol.md` § Final Gate Team), not via sequential Skill tool invocation.

When dispatched in parallel:
1. The orchestrator spawns patch-critic + qa-engineer (verify) + qa-engineer (test) + product-reviewer in a single message
2. Each teammate reads its own skill file independently
3. All four work read-only on the same final state — no lock contention possible
4. The orchestrator collects all four verdicts before advancing to Ship

## Prerequisite

- Review phase complete: BOTH `/code-review` and `/security-review` returned APPROVE
- Build phase tests are GREEN (the test-output input must reflect a fresh run)

## Phase Output

```
Verdict: PATCH_APPROVED / PATCH_REJECTED
Next: If PATCH_APPROVED + verify VERIFIED + test COVERED + accept APPROVED → /pr-creation
      If PATCH_REJECTED → spawn fix-engineer (no user escalation), then re-invoke /patch-critique
Findings: [rubric dimension verdicts with file:line citations]
Agent summary: [patch-critic 2-3 sentence summary]
```

## Severity Grading

Patch-critique is rubric-binary (PASS/FAIL per dimension). Severity grading from `/code-review` does NOT apply here — every FAIL is gating. There is no "minor critic finding"; either the rubric passes or the patch goes back to fix-engineer.

## Anti-Patterns

- **Reinstating the always-3 dispatch**: don't. The prior shape spent 3x patch-critic cost on every critical/Budget>=7 Final Gate; the trimmed shape spends 1x by default and recovers the full safety net via the `uncertainty` signal. A single confident persona-1 CAN ship — that is intentional. The uncertainty bool is the safety valve.
- **Over-confident persona-1**: persona-1 must bias toward `uncertainty: true` on close calls (see `agents/patch-critic.md` § Close-call bias guidance). Under-escalation is the failure mode, not over-escalation; the escalation cost is the prior multi-persona baseline cost.
- **Treating `uncertainty: true` as an abstention**: persona-1 STILL emits one of PATCH_APPROVED / PATCH_REJECTED when uncertain; that verdict counts as one vote in the majority-of-3 aggregation on the escalation path. The bool is a request for second opinions, NOT a withholding of the first opinion.
- **Skipping the structured output**: missing `Uncertainty:` field is parsed as `Uncertainty: true` (conservative default). Persona spawns MUST emit the field on every run, including legacy single-critic dispatch.

## In-Cycle Fix Rule

PATCH_REJECTED is gated by `protocols/pipeline-protocol.md` § In-Cycle Fix Rule:

- Findings are fixed in this pipeline. No follow-up tickets.
- The orchestrator dispatches fix-engineer autonomously. No user question.
- Re-run on the combined diff is mandatory before Ship.
