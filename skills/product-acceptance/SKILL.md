---
name: "product-acceptance"
description: "Use when user wants to Accept phase skill: spawn product-reviewer to validate acceptance criteria are met, assess UX quality, and verify business value delivery. Produces APPROVED or APPROVED WITH CONDITIONS verdict."
context: fork
agent: product-reviewer
---

# Product Acceptance

## What This Skill Does

Automates the Accept phase. Spawns a read-only product-reviewer to validate the feature meets business requirements.

## Current Context
- Branch: !`git branch --show-current`
- Changed files: !`git diff main...HEAD --name-only 2>/dev/null || echo 'N/A'`
- Diff stats: !`git diff main...HEAD --stat 2>/dev/null || echo 'N/A'`

## When to Invoke

- After Test phase passes (QA confirms coverage, no gaps)
- Before Ship phase (`/pr-creation`)

## Process

### 1. Gather Context

Collect acceptance criteria, test results, verification report, and any design specs.

### 2. Spawn Product Reviewer (per-AC verdicts)

```
Agent({
  subagent_type: "product-reviewer",
  prompt: "Product acceptance review for this feature.
    Acceptance Criteria: [list ACs, numbered AC1, AC2, ...]
    Test Results: [summary]
    Verification Report: [VERIFIED/UNVERIFIED]

    Validate EACH AC INDEPENDENTLY. For every AC produce one of:
      - APPROVED        (AC fully met, evidence cited)
      - REJECTED        (AC not met or behavior is wrong)
    For each rejected AC, state which condition failed and what evidence is missing.

    Then assess cross-AC concerns:
    - UX quality: is the user experience acceptable? Any rough edges?
    - Business value: does this deliver what was promised?
    - Edge cases: are error states handled gracefully?
    - Accessibility: WCAG 2.1 AA compliance where applicable
    - E2E status: review Tier 4 from the verification report
       - If VERIFIED_WITH_SKIP: acknowledge the skip reason and assess risk
       - If E2E flows ran (PASS): confirm they cover the changed behavior
       - If E2E flows failed: this should have been caught in Verify -- flag if it wasn't
    - visual_regression machine pre-check (frontend-touching changes):
       - Read pipeline-state/{task-id}/design-qc/index.json
       - REJECT the story-level verdict if any route has pixel_diff_ratio > threshold OR vlm_verdict == FAIL
       - If the visual_regression block is missing on a frontend-touching change, treat as vlm_verdict == BLOCKED and REJECT with reason `visual_regression block missing — producer (vlm-critic) did not run` (AC3+AC4 atomicity guard; see agents/product-reviewer.md § Outcome)
       - Per-route threshold (routes[*].visual_regression.threshold) overrides default 0.02 when present
    If Design QC screenshots are available (from /design-qc):
    - Visual review: check screenshots against design system compliance
       - No hardcoded colors, spacing follows scale, type scale respected
       - Empty/error states have proper treatment
       - Mobile layout is usable, animations respect prefers-reduced-motion

    Output format:
    ## Per-AC Verdicts
    | AC | Verdict | Evidence / Failure |
    |----|---------|---------------------|
    | AC1 | APPROVED | tests/test_X.py::test_Y passes |
    | AC2 | REJECTED | Error path returns 500 instead of structured 400 |

    ## Story-Level Verdict (derived)
    - APPROVED            — all per-AC verdicts are APPROVED
    - APPROVED_WITH_CONDITIONS — UX/cross-cutting concerns exist but every AC is APPROVED; conditions listed
    - REJECTED            — at least one per-AC verdict is REJECTED"
})
```

No `isolation: "worktree"` — product-reviewer is read-only.

### 3. Process Verdict

- **APPROVED**: Advance to Ship phase. Record product summary for PR narrative.
- **APPROVED WITH CONDITIONS**: Spawn engineer (with worktree) to address conditions. Re-run acceptance.
- **REJECTED**: Return to Build phase with specific feedback.

**In-cycle enforcement:** Conditions and rejections MUST be resolved in the current pipeline. The orchestrator is not permitted to ship APPROVED_WITH_CONDITIONS as a "follow-up ticket" compromise, and must not ask the user whether to defer. If product-reviewer surfaces a defect that makes the fix-being-shipped incomplete, broken, or misleading (e.g. docs point users at a command that still fails), that is CHANGES_REQUESTED territory — dispatch a fix-engineer, roll the fix in, re-run acceptance. See `protocols/pipeline-protocol.md` § In-Cycle Fix Rule.

Then proceed to Step 4 to write the approval token.

### 4. Write Approval Token (MANDATORY)

After determining the verdict, write the approval token so the Ship phase can verify authorization:

```bash
bash "$HOME/.claude/hooks/_lib/write-approval-token.sh" \
  --task-id "$TASK_ID" \
  --verdict "$VERDICT"
```

- `$TASK_ID`: the current pipeline task ID (from `CLAUDE_PIPELINE_TASK_ID` env or branch name last segment)
- `$VERDICT`: one of `APPROVED`, `APPROVED_WITH_CONDITIONS`, `REJECTED`
- Token is written for ALL verdicts — readers distinguish "phase ran and approved" from "phase ran and rejected" from "phase never ran (missing)"
- Token is deleted at Reflect step 6d alongside the other `pipeline-state/{task-id}/` artifacts (canonical write path: `pipeline-state/{task-id}/approval.token`; legacy `pipeline-state/{task-id}-approval.token` is read-tolerated during the 90-day DUAL_PATH soak)

## Acceptance Checklist

- [ ] Every AC has evidence of completion (passing test, screenshot, or demo)
- [ ] User-facing behavior matches requirements
- [ ] Error states are handled gracefully (no raw errors shown to users)
- [ ] Accessibility requirements met (if applicable)
- [ ] Performance is acceptable for the use case
- [ ] No regressions in existing functionality
- [ ] Business stakeholder would understand what was built from the PR description
- [ ] If VERIFIED_WITH_SKIP: E2E skip reason acknowledged and risk assessed (see `protocols/e2e-protocol.md`)
- [ ] If E2E flows exist for changed behavior: confirm they passed in verification report

## Prerequisite

- Test phase complete: `/qa-test-strategy` returned COVERED

## Phase Output

```
Verdict: APPROVED / APPROVED_WITH_CONDITIONS / REJECTED
Next: If APPROVED → /pr-creation
      If APPROVED_WITH_CONDITIONS → spawn engineer to address conditions, then re-run this skill
      If REJECTED → return to Build phase with specific feedback
Conditions: [list of conditions if applicable]
Agent summaries: [product-reviewer's 2-3 sentence summary]
```
